"""Executor integration using synthetic SDK responses and fake HTTP transport."""
import contextlib
import io
import sys
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).parents[1]))
import execute_backend_cutover as adapter
import test_backend_cutover as core_tests


class ExecutorTests(TestCase):
    def clients(self):
        sts, ecr = Mock(), Mock()
        sts.get_caller_identity.return_value = {'Account': adapter.ACCOUNT,
            'Arn': 'arn:aws:iam::365591166807:user/synthetic'}
        ecr.describe_images.return_value = {'imageDetails': [{'imageDigest': adapter.core.DIGEST}]}
        runner = core_tests.Tests().client()
        runner.current['ServiceName'] = 'clerk-backend'
        return sts, ecr, runner

    def test_success_order_identity_digest_and_backend_only(self):
        clients = self.clients(); timeline = Mock()
        for name, client in zip(('sts', 'ecr', 'runner'), clients): timeline.attach_mock(client, name)
        health = Mock(return_value=True); timeline.attach_mock(health, 'health')
        result = adapter.execute(*clients, health)
        self.assertEqual(result['result'], 'verified')
        calls = [c[0] for c in timeline.mock_calls]
        self.assertLess(calls.index('sts.get_caller_identity'), calls.index('ecr.describe_images'))
        self.assertLess(calls.index('ecr.describe_images'), calls.index('runner.resume_service'))
        self.assertLess(calls.index('runner.resume_service'), calls.index('runner.update_service'))
        self.assertLess(calls.index('runner.update_service'), calls.index('health'))
        clients[1].describe_images.assert_called_once_with(registryId=adapter.ACCOUNT,
            repositoryName='clerk-backend', imageIds=[{'imageDigest':adapter.core.DIGEST}])
        for call in clients[2].method_calls:
            if 'ServiceArn' in call.kwargs: self.assertEqual(call.kwargs['ServiceArn'], adapter.core.ARN)
        clients[2].start_deployment.assert_not_called()

    def test_preflight_refusals_never_resume(self):
        for case in ('account', 'identity', 'digest', 'active', 'name', 'state', 'api'):
            with self.subTest(case=case):
                sts,ecr,c = self.clients()
                if case == 'account': sts.get_caller_identity.return_value['Account']='wrong'
                if case == 'identity': sts.get_caller_identity.return_value['Arn']='arn:aws:iam::000000000000:user/wrong'
                if case == 'digest': ecr.describe_images.return_value={'imageDetails':[{'imageDigest':'wrong'}]}
                if case == 'active': c.list_operations.side_effect=lambda **kw: {'OperationSummaryList':[{'Status':'IN_PROGRESS'}]}
                if case == 'name': c.current['ServiceName']='clerk-frontend'
                if case == 'state': c.state='RUNNING'
                if case == 'api': ecr.describe_images.side_effect=RuntimeError('sensitive-canary')
                with self.assertRaises(adapter.core.CutoverError) as error:
                    adapter.execute(sts,ecr,c,lambda:True)
                self.assertEqual(str(error.exception),'Preflight failed; no mutation attempted.')
                c.resume_service.assert_not_called(); c.update_service.assert_not_called(); c.pause_service.assert_not_called()

    def test_health_failure_and_update_error_pause(self):
        for api_error in (False, True):
            clients=self.clients()
            if api_error: clients[2].update_service.side_effect=RuntimeError('sensitive-canary')
            clock = core_tests.Clock()
            with self.assertRaises(adapter.core.CutoverError) as error:
                adapter.execute(*clients, lambda:False, clock=clock, sleep=clock.sleep)
            self.assertEqual('UNCONFIRMED' in str(error.exception), api_error)
            clients[2].pause_service.assert_called_once_with(ServiceArn=adapter.core.ARN)

    def test_update_timeout_triggers_containment(self):
        clients=self.clients(); c=clients[2]; tick=[0]
        def clock(): return tick[0]
        def sleep(seconds): tick[0]+=seconds
        c.list_operations.side_effect=lambda **kw: {'OperationSummaryList':[
            {'Id':'resume','Status':'SUCCEEDED'}, {'Id':'update','Status':'IN_PROGRESS' if tick[0] < 905 else 'FAILED'},
            {'Id':'pause','Status':'SUCCEEDED'}]}
        # Preflight must see no active operation before resume.
        original=c.list_operations.side_effect
        c.list_operations.side_effect=lambda **kw: ({'OperationSummaryList':[]} if c.state=='PAUSED' and not c.pause_service.called else original())
        # After resume, the fake update stays in progress until the core deadline.
        with self.assertRaises(adapter.core.CutoverError) as error:
            adapter.execute(*clients, lambda:True,clock=clock,sleep=sleep)
        self.assertEqual(str(error.exception),'Cutover failed; backend PAUSED.')
        c.pause_service.assert_called_once()

    def test_default_and_help_no_clients(self):
        factory=Mock()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(adapter.main([],client_factory=factory),0)
            with self.assertRaises(SystemExit) as result: adapter.main(['--help'],client_factory=factory)
        self.assertEqual(result.exception.code,0); factory.assert_not_called()

    def test_cli_suppresses_sensitive_output(self):
        clients=self.clients()
        def factory():
            print('sensitive-canary'); print('sensitive-canary',file=sys.stderr)
            return clients
        health = Mock(side_effect=RuntimeError('sensitive-canary'))
        output=io.StringIO()
        with patch.object(adapter.resource,'setrlimit'), patch.object(adapter.faulthandler,'disable'), patch.object(adapter.logging,'disable'):
            with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
                code=adapter.main(['--execute-approved-cutover'],client_factory=factory,health=health)
        self.assertEqual(code,1)
        self.assertEqual(output.getvalue(),'Cutover failed; backend PAUSED.\n')

    def test_http_success_and_bad_responses(self):
        for body,status,expected in [(b'{"status":"healthy"}',200,True),(b'bad',200,False),
                                      (b'{"status":"healthy"}',302,False),(b'x'*4097,200,False)]:
            opener=Mock(); response=Mock(); response.status=status; response.read.return_value=body
            opener.open.return_value.__enter__=Mock(return_value=response)
            opener.open.return_value.__exit__=Mock(return_value=False)
            ticks=[0]
            def clock(): return ticks[0]
            def sleep(_): ticks[0]=61
            self.assertEqual(adapter.health_check(opener=opener,clock=clock,sleep=sleep),expected)
            response.read.assert_called_with(4097)
            self.assertEqual(opener.open.call_args.args,(adapter.HEALTH_URL,))
        self.assertIsNone(adapter.NoRedirect().redirect_request(None,None,302,'',{},'https://elsewhere.invalid'))

    def test_http_timeout_no_details(self):
        opener=Mock(); opener.open.side_effect=TimeoutError('sensitive-canary')
        ticks=[0]
        def sleep(_): ticks[0]=61
        output=io.StringIO()
        with contextlib.redirect_stdout(output),contextlib.redirect_stderr(output):
            self.assertFalse(adapter.health_check(opener=opener,clock=lambda:ticks[0],sleep=sleep))
        self.assertEqual(output.getvalue(),'')

    def test_live_factory_config_without_live_clients(self):
        with patch('boto3.Session') as factory:
            adapter.live_clients()
        factory.assert_called_once_with(region_name='us-east-1')
        self.assertEqual([call.args[0] for call in factory.return_value.client.call_args_list],
                         ['sts', 'ecr', 'apprunner'])
        for call in factory.return_value.client.call_args_list:
            config = call.kwargs['config']
            self.assertEqual(config.retries, {'total_max_attempts': 1})
            self.assertEqual(config.connect_timeout, 5)
            self.assertEqual(config.read_timeout, 15)

    def test_active_operation_on_second_page_refuses(self):
        clients = self.clients()
        clients[2].list_operations.side_effect = [
            {'OperationSummaryList': [], 'NextToken': 'second'},
            {'OperationSummaryList': [{'Status': 'ROLLBACK_IN_PROGRESS'}]}]
        with self.assertRaises(adapter.core.CutoverError):
            adapter.execute(*clients, lambda: True)
        clients[2].resume_service.assert_not_called()

    def test_preflight_slow_page_refuses_before_secret_read(self):
        clients=self.clients(); clock=core_tests.Clock()
        def slow(**kw):
            clock.now=61
            return {'OperationSummaryList': []}
        clients[2].list_operations.side_effect=slow
        with self.assertRaises(adapter.core.CutoverError):
            adapter.execute(*clients,lambda:True,clock=clock,sleep=clock.sleep)
        clients[2].describe_service.assert_not_called()
        clients[2].resume_service.assert_not_called()

    def test_late_resume_poll_response_enters_containment(self):
        clients=self.clients(); c=clients[2]; clock=core_tests.Clock(); original=c.list_operations.side_effect
        def slow_once(**kw):
            if c.resume_service.called and clock.now == 0: clock.now=901
            return original(**kw)
        c.list_operations.side_effect=slow_once
        with self.assertRaises(adapter.core.CutoverError) as error:
            adapter.execute(*clients,lambda:True,clock=clock,sleep=clock.sleep)
        self.assertEqual(str(error.exception),'Cutover failed; backend PAUSED.')
        c.update_service.assert_not_called()
        c.pause_service.assert_called_once()
