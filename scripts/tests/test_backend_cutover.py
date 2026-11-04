"""Offline synthetic tests; no AWS clients or network requests are created."""
import importlib.util
from pathlib import Path
from copy import deepcopy
import unittest
import contextlib
import io
from unittest.mock import Mock, patch
from botocore.session import Session
from botocore.validate import validate_parameters

spec = importlib.util.spec_from_file_location('cutover', Path(__file__).parents[1] / 'backend_cutover.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


def fixture():
    return {'ServiceArn': m.ARN, 'Status': 'PAUSED',
            'InstanceConfiguration': {'Cpu': '1024', 'Memory': '2048'},
            'NetworkConfiguration': {'EgressConfiguration': {'EgressType': 'DEFAULT'}},
            'HealthCheckConfiguration': {'Protocol': 'HTTP', 'Path': '/health'},
            'SourceConfiguration': {'AutoDeploymentsEnabled': False,
                'AuthenticationConfiguration': {'AccessRoleArn': 'arn:aws:iam::365591166807:role/synthetic'},
                'ImageRepository': {'ImageIdentifier': m.REPO + ':latest', 'ImageRepositoryType': 'ECR',
                    'ImageConfiguration': {'Port': '8000', 'StartCommand': 'synthetic-command',
                        'RuntimeEnvironmentVariables': {'DATABASE_URL': 'synthetic-db-canary', 'KEEP': 'keep',
                                                        'AUTH_SECRET_KEY': 'old-canary'},
                        'RuntimeEnvironmentSecrets': {'KEEP_REF': 'synthetic-reference',
                                                     'AUTH_SECRET_KEY': 'old-reference'}}}}}


class Tests(unittest.TestCase):
    def test_preservation_and_sdk_shape(self):
        original = fixture(); saved = deepcopy(original)
        request = m.prepare(original)
        validate_parameters(request, Session().get_service_model('apprunner').operation_model('UpdateService').input_shape)
        self.assertEqual(original, saved)
        expected = deepcopy(original['SourceConfiguration'])
        config = expected['ImageRepository']['ImageConfiguration']
        key = request['SourceConfiguration']['ImageRepository']['ImageConfiguration']['RuntimeEnvironmentVariables']['AUTH_SECRET_KEY']
        self.assertGreaterEqual(len(key), 64)
        config['RuntimeEnvironmentVariables'].update(m.SETTINGS, AUTH_SECRET_KEY=key)
        del config['RuntimeEnvironmentSecrets']['AUTH_SECRET_KEY']
        expected['ImageRepository']['ImageIdentifier'] = m.IMAGE
        self.assertEqual(request, {'ServiceArn': m.ARN, 'SourceConfiguration': expected})
        self.assertNotEqual(m.prepare(original), request)

    def test_refusals(self):
        for field, value in [('Status', 'RUNNING'), ('ServiceArn', 'wrong')]:
            s = fixture(); s[field] = value
            with self.assertRaises(m.CutoverError): m.prepare(s)
        s = fixture(); s['SourceConfiguration']['AutoDeploymentsEnabled'] = True
        with self.assertRaises(m.CutoverError): m.prepare(s)

    def client(self):
        c = Mock(); c.state = 'PAUSED'; c.current = fixture()
        c.list_services.side_effect = lambda **kw: {'ServiceSummaryList': [{'ServiceArn': m.ARN, 'Status': c.state}]}
        def resume(**kw): c.state = 'RUNNING'; return {'OperationId': 'resume'}
        def update(**kw):
            c.current['SourceConfiguration'] = deepcopy(kw['SourceConfiguration'])
            c.current['Status'] = 'RUNNING'
            return {'OperationId': 'update'}
        def pause(**kw): c.state = 'PAUSED'; return {'OperationId': 'pause'}
        c.resume_service.side_effect = resume; c.update_service.side_effect = update; c.pause_service.side_effect = pause
        c.list_operations.side_effect = lambda **kw: {'OperationSummaryList': [{'Id': x, 'Status': 'SUCCEEDED'} for x in ('resume','update','pause')]}
        c.describe_service.side_effect = lambda **kw: {'Service': c.current}
        return c

    def test_order_and_no_extra_deployment(self):
        c = self.client()
        result = m.restore(c, fixture(), lambda: True)
        self.assertEqual(result['result'], 'verified')
        names = [x[0] for x in c.method_calls]
        self.assertLess(names.index('resume_service'), names.index('list_operations'))
        self.assertLess(names.index('list_operations'), names.index('update_service'))
        c.start_deployment.assert_not_called(); c.pause_service.assert_not_called()
        self.assertNotIn('canary', str(result))

    def test_failures_pause_and_sanitize(self):
        for failure in ('update', 'health', 'configuration', 'resume'):
            c = self.client(); clock = Clock()
            if failure == 'update': c.update_service.side_effect = RuntimeError('secret-canary')
            if failure == 'resume':
                def uncertain(**kw): c.state = 'RUNNING'; raise RuntimeError('secret-canary')
                c.resume_service.side_effect = uncertain
            if failure == 'configuration': c.describe_service.side_effect = RuntimeError('secret-canary')
            with self.assertRaises(m.CutoverError) as error:
                m.restore(c, fixture(), lambda: failure != 'health', clock=clock, sleep=clock.sleep, timeout=10)
            self.assertEqual('UNCONFIRMED' in str(error.exception), failure in ('update', 'resume'))
            c.pause_service.assert_called_once()

    def test_operation_failure_and_timeout(self):
        c = Mock()
        c.list_operations.return_value = {'OperationSummaryList': [{'Id':'x','Status':'FAILED'}]}
        with self.assertRaises(m.CutoverError):
            m.wait_operation(c, 'x', clock=lambda:0, sleep=lambda _:None, timeout=1)
        c.list_operations.return_value = {'OperationSummaryList': []}
        clock = Clock()
        with self.assertRaises(m.CutoverError):
            m.wait_operation(c, 'x', clock=clock, sleep=clock.sleep, timeout=1)

    def test_containment_unavailable(self):
        c = self.client(); c.update_service.side_effect = RuntimeError('secret-canary')
        c.pause_service.side_effect = RuntimeError('secret-canary')
        with self.assertRaises(m.CutoverError) as error: m.restore(c, fixture(), lambda:True)
        self.assertIn('UNCONFIRMED', str(error.exception)); self.assertNotIn('canary', str(error.exception))

    def test_preflight_no_mutations(self):
        c = self.client(); s = fixture(); s['Status'] = 'RUNNING'
        with self.assertRaises(m.CutoverError): m.restore(c,s,lambda:True)
        c.resume_service.assert_not_called(); c.update_service.assert_not_called(); c.pause_service.assert_not_called()

    def test_secret_reference_database_preserved(self):
        s = fixture()
        config = s['SourceConfiguration']['ImageRepository']['ImageConfiguration']
        del config['RuntimeEnvironmentVariables']['DATABASE_URL']
        config['RuntimeEnvironmentSecrets']['DATABASE_URL'] = 'synthetic-db-reference'
        result = m.prepare(s)['SourceConfiguration']['ImageRepository']['ImageConfiguration']
        self.assertNotIn('DATABASE_URL', result['RuntimeEnvironmentVariables'])
        self.assertEqual(result['RuntimeEnvironmentSecrets']['DATABASE_URL'], 'synthetic-db-reference')

    def test_silent_execution_and_delayed_containment(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            m.restore(self.client(), fixture(), lambda: True)
        self.assertEqual(output.getvalue(), '')
        c = self.client()
        with patch.object(m, 'status', side_effect=['OPERATION_IN_PROGRESS', 'RUNNING', 'PAUSED']):
            sleep = Mock()
            m.contain(c, clock=lambda: 0, sleep=sleep, timeout=10)
        sleep.assert_called_once_with(5)
        c.pause_service.assert_called_once()

if __name__ == '__main__': unittest.main()


class Clock:
    def __init__(self): self.now = 0
    def __call__(self): return self.now
    def sleep(self, seconds): self.now += seconds


class DeadlineContainmentTests(unittest.TestCase):
    def test_ambiguous_resume_paused_without_visibility_is_unconfirmed(self):
        client = Tests().client(); clock = Clock()
        client.resume_service.side_effect = TimeoutError('secret-canary')
        client.list_operations.side_effect = lambda **kw: {'OperationSummaryList': []}
        with self.assertRaises(m.CutoverError) as error:
            m.restore(client, fixture(), lambda: True, clock=clock, sleep=clock.sleep, timeout=10)
        self.assertIn('UNCONFIRMED', str(error.exception))
        client.pause_service.assert_not_called()
        client.update_service.assert_not_called()

    def test_late_success_response_is_not_accepted(self):
        client = Mock(); clock = Clock()
        def slow(**kw):
            clock.now = 11
            return {'OperationSummaryList': [{'Id': 'x', 'Status': 'SUCCEEDED'}]}
        client.list_operations.side_effect = slow
        with self.assertRaises(m.CutoverError):
            m.wait_operation(client, 'x', clock=clock, sleep=clock.sleep, timeout=10)

    def test_pagination_does_not_restart_deadline(self):
        client = Mock(); clock = Clock()
        def page(**kw):
            clock.now += 6
            return ({'OperationSummaryList': [], 'NextToken': 'second'} if 'NextToken' not in kw
                    else {'OperationSummaryList': [{'Id':'x','Status':'SUCCEEDED'}]})
        client.list_operations.side_effect = page
        with self.assertRaises(m.CutoverError):
            m.wait_operation(client, 'x', clock=clock, sleep=clock.sleep, timeout=10)
        self.assertEqual(client.list_operations.call_count, 2)

    def test_known_resume_delayed_visibility_then_pending_blocks_pause(self):
        c = Tests().client(); clock = Clock()
        def listed(**kw):
            if clock.now == 0: return {'OperationSummaryList': []}
            if clock.now == 5:
                c.state = 'RUNNING'  # A stale RUNNING summary cannot override pending work.
                return {'OperationSummaryList': [{'Id':'resume','Status':'PENDING'}]}
            return {'OperationSummaryList': [{'Id':'resume','Status':'SUCCEEDED'}] +
                    ([{'Id':'pause','Status':'SUCCEEDED'}] if c.pause_service.called else [])}
        c.list_operations.side_effect = listed
        original = c.pause_service.side_effect
        def pause(**kw):
            self.assertEqual(clock.now, 10)
            return original(**kw)
        c.pause_service.side_effect = pause
        m.contain(c, clock=clock, sleep=clock.sleep, timeout=20, known_operations=['resume'])
        c.pause_service.assert_called_once()
        self.assertEqual(c.state, 'PAUSED')

    def test_paused_with_pending_update_is_not_contained(self):
        c = Tests().client(); clock = Clock()
        c.list_operations.side_effect = lambda **kw: {'OperationSummaryList':[
            {'Id':'update', 'Status':'IN_PROGRESS'}]}
        with self.assertRaises(m.CutoverError):
            m.contain(c, clock=clock, sleep=clock.sleep, timeout=10, known_operations=['update'])
        c.pause_service.assert_not_called()
        self.assertEqual(clock.now, 10)

    def test_unknown_resume_delayed_visibility_never_claims_containment(self):
        c = Tests().client(); clock = Clock()
        c.resume_service.side_effect = TimeoutError('secret-canary')
        def listed(**kw):
            if clock.now < 5: return {'OperationSummaryList': []}
            if clock.now < 10:
                return {'OperationSummaryList': [{'Id':'delayed', 'Status':'PENDING'}]}
            if not c.pause_service.called: c.state = 'RUNNING'
            return {'OperationSummaryList': [{'Id':'delayed','Status':'SUCCEEDED'},
                                            {'Id':'pause','Status':'SUCCEEDED'}]}
        c.list_operations.side_effect = listed
        with self.assertRaises(m.CutoverError) as error:
            m.restore(c,fixture(),lambda:True,clock=clock,sleep=clock.sleep,timeout=25)
        self.assertIn('UNCONFIRMED',str(error.exception))
        c.pause_service.assert_called_once()
        c.update_service.assert_not_called()

    def test_missing_known_operation_times_out_without_pause(self):
        c = Tests().client(); clock = Clock(); c.state = 'RUNNING'
        c.list_operations.side_effect = lambda **kw: {'OperationSummaryList': []}
        with self.assertRaises(m.CutoverError):
            m.contain(c,clock=clock,sleep=clock.sleep,timeout=10,known_operations=['missing'])
        c.pause_service.assert_not_called()

    def test_ambiguous_pause_is_not_repeated(self):
        c = Tests().client(); clock = Clock(); c.state = 'RUNNING'
        c.pause_service.side_effect = TimeoutError('secret-canary')
        with self.assertRaises(TimeoutError):
            m.contain(c,clock=clock,sleep=clock.sleep,timeout=10,known_operations=['resume'])
        c.pause_service.assert_called_once()

    def test_repeated_tokens_fail_closed_in_operations_and_status(self):
        for key, method in [('OperationSummaryList','list_operations'),('ServiceSummaryList','list_services')]:
            c = Mock(); clock = Clock()
            getattr(c,method).return_value = {key: [], 'NextToken':'same'}
            with self.assertRaises(m.CutoverError):
                if method == 'list_operations':
                    m.wait_operation(c,'x',clock=clock,sleep=clock.sleep,timeout=10)
                else: m.status(c,clock=clock,timeout=10)
            self.assertEqual(getattr(c,method).call_count,2)

    def test_status_slow_pagination_and_exhausted_deadline(self):
        c = Mock(); clock = Clock()
        def page(**kw):
            clock.now += 6
            return ({'ServiceSummaryList': [], 'NextToken':'second'} if 'NextToken' not in kw else
                    {'ServiceSummaryList':[{'ServiceArn':m.ARN,'Status':'PAUSED'}]})
        c.list_services.side_effect = page
        with self.assertRaises(m.CutoverError): m.status(c,clock=clock,deadline=10)
        self.assertEqual(c.list_services.call_count,2)
        c.list_services.reset_mock()
        with self.assertRaises(m.CutoverError): m.status(c,clock=clock,deadline=10)
        c.list_services.assert_not_called()

    def test_containment_does_not_reset_deadline_after_pause(self):
        c = Tests().client(); c.state='RUNNING'; clock=Clock()
        def pause(**kw):
            clock.now=9; c.state='PAUSED'; return {'OperationId':'pause'}
        c.pause_service.side_effect=pause
        original=c.list_operations.side_effect
        def listed(**kw):
            if c.pause_service.called: clock.now+=2
            return original(**kw)
        c.list_operations.side_effect=listed
        with self.assertRaises(m.CutoverError):
            m.contain(c,clock=clock,sleep=clock.sleep,timeout=10,known_operations=['resume'])
        c.pause_service.assert_called_once()
