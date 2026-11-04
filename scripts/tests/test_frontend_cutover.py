"""Synthetic frontend cutover tests. AWS clients and HTTP transport are mocked."""
from copy import deepcopy
import contextlib
import io
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

from botocore.exceptions import ClientError
from botocore.session import Session
from botocore.validate import validate_parameters

sys.path.insert(0, str(Path(__file__).parents[1]))
import frontend_cutover as core
import execute_frontend_cutover as adapter

CANARY = 'synthetic-sensitive-canary'
HTML = (b'<!doctype html><html><head><script src="/_next/static/chunks/login.js" defer></script>'
        b'</head><body><h1>Local Login</h1><form><input type="email"/>'
        b'<input type="password"/><button type="submit">Login</button></form></body></html>')
IDS = {'resume': '1' * 32, 'update': '2' * 32, 'pause': '3' * 32}


class Clock:
    def __init__(self): self.now = 0
    def __call__(self): return self.now
    def sleep(self, seconds): self.now += seconds


def fixture():
    return {'ServiceArn': core.ARN, 'ServiceName': 'clerk-frontend', 'Status': 'PAUSED',
            'SourceConfiguration': {'AutoDeploymentsEnabled': False,
                'AuthenticationConfiguration': {'AccessRoleArn': 'arn:aws:iam::365591166807:role/synthetic'},
                'ImageRepository': {'ImageIdentifier': core.REPO + ':latest', 'ImageRepositoryType': 'ECR',
                    'ImageConfiguration': {'Port': '3000', 'StartCommand': 'node server.js',
                        'RuntimeEnvironmentVariables': {'KEEP': CANARY},
                        'RuntimeEnvironmentSecrets': {'KEEP_REF': 'synthetic-reference'}}}},
            'InstanceConfiguration': {'Cpu': '1024', 'Memory': '2048'},
            'NetworkConfiguration': {'EgressConfiguration': {'EgressType': 'DEFAULT'}},
            'HealthCheckConfiguration': {'Protocol': 'HTTP', 'Path': '/local-login'}}


def clients():
    sts, ecr, app = Mock(), Mock(), Mock()
    sts.get_caller_identity.return_value = {'Account': adapter.ACCOUNT, 'Arn': adapter.IDENTITY}
    ecr.describe_images.return_value = {'imageDetails': [{'imageDigest': core.DIGEST}]}
    app.current = fixture()
    app.state = 'PAUSED'
    app.ops = []
    app.list_services.side_effect = lambda **kw: {'ServiceSummaryList': [
        {'ServiceArn': core.ARN, 'Status': app.state}]}
    app.list_operations.side_effect = lambda **kw: {'OperationSummaryList': deepcopy(app.ops)}
    app.describe_service.side_effect = lambda **kw: {'Service': deepcopy(app.current)}

    def mutate(name, kwargs):
        if kwargs['ServiceArn'] != core.ARN: raise AssertionError('Wrong service')
        app.ops.append({'Id': IDS[name], 'Status': 'SUCCEEDED'})
        app.state = 'PAUSED' if name == 'pause' else 'RUNNING'
        app.current['Status'] = app.state
        if name == 'update': app.current['SourceConfiguration'] = deepcopy(kwargs['SourceConfiguration'])
        return {'OperationId': IDS[name]}
    app.resume_service.side_effect = lambda **kw: mutate('resume', kw)
    app.update_service.side_effect = lambda **kw: mutate('update', kw)
    app.pause_service.side_effect = lambda **kw: mutate('pause', kw)
    return sts, ecr, app


class CutoverTests(unittest.TestCase):
    def setUp(self):
        # Any accidental attempt to create a real SDK client or HTTP connection fails.
        self.guard = patch('botocore.session.Session.create_client', side_effect=AssertionError('No AWS'))
        self.guard.start(); self.addCleanup(self.guard.stop)
        self.network = patch('socket.socket.connect', side_effect=AssertionError('No network'))
        self.network.start(); self.addCleanup(self.network.stop)

    def test_image_only_request_and_sdk_validation(self):
        original = fixture(); before = deepcopy(original)
        request = core.prepare(original)
        expected = deepcopy(original['SourceConfiguration'])
        expected['ImageRepository']['ImageIdentifier'] = core.IMAGE
        self.assertEqual(request, {'ServiceArn': core.ARN, 'SourceConfiguration': expected})
        self.assertEqual(original, before)
        validate_parameters(request, Session().get_service_model('apprunner')
                            .operation_model('UpdateService').input_shape)

    def test_configuration_refusals(self):
        for case in ('backend', 'running', 'autodeploy', 'wrong-image', 'role', 'type'):
            with self.subTest(case=case):
                s = fixture(); source = s['SourceConfiguration']
                if case == 'backend': s['ServiceArn'] = core.shared.ARN
                if case == 'running': s['Status'] = 'RUNNING'
                if case == 'autodeploy': source['AutoDeploymentsEnabled'] = True
                if case == 'wrong-image': source['ImageRepository']['ImageIdentifier'] = core.IMAGE
                if case == 'role': del source['AuthenticationConfiguration']
                if case == 'type': source['ImageRepository']['ImageRepositoryType'] = 'ECR_PUBLIC'
                with self.assertRaises(core.CutoverError): core.prepare(s)

    def test_success_order_ids_and_frontend_only(self):
        c = clients(); d = core.Diagnostics(); clock = Clock()
        with patch.object(core, 'prepare', wraps=core.prepare) as prepare:
            old_resume = c[2].resume_service.side_effect
            def resume(**kw):
                prepare.assert_called_once()
                return old_resume(**kw)
            c[2].resume_service.side_effect = resume
            result = adapter.execute(*c, lambda: adapter.verify_html(HTML),
                                     clock=clock, sleep=clock.sleep, diagnostics=d)
        self.assertEqual(result['image'], core.IMAGE)
        self.assertEqual(d.lines[-1], 'stage: health verified')
        for action in ('resume', 'update'):
            getattr(c[2], action + '_service').assert_called_once()
            self.assertIn('operation: ' + action + ' id=' + IDS[action], d.lines)
        names = [call[0] for call in c[2].method_calls]
        self.assertLess(names.index('resume_service'), names.index('update_service'))
        for call in c[2].method_calls:
            if 'ServiceArn' in call.kwargs: self.assertEqual(call.kwargs['ServiceArn'], core.ARN)
        c[1].describe_images.assert_called_once_with(registryId=adapter.ACCOUNT,
            repositoryName='clerk-frontend', imageIds=[{'imageDigest': core.DIGEST}])
        c[2].pause_service.assert_not_called(); c[2].start_deployment.assert_not_called()

    def test_preflight_refuses_without_mutation(self):
        for case in ('identity', 'account', 'digest', 'active', 'unknown-status', 'state', 'name', 'api'):
            with self.subTest(case=case):
                sts, ecr, app = clients()
                if case == 'identity': sts.get_caller_identity.return_value['Arn'] = adapter.IDENTITY + '-other'
                if case == 'account': sts.get_caller_identity.return_value['Account'] = '000000000000'
                if case == 'digest': ecr.describe_images.return_value['imageDetails'] = []
                if case in ('active', 'unknown-status'):
                    app.ops = [{'Id': 'x', 'Status': 'PENDING' if case == 'active' else 'UNKNOWN'}]
                if case == 'state': app.state = 'RUNNING'
                if case == 'name': app.current['ServiceName'] = 'clerk-backend'
                if case == 'api': ecr.describe_images.side_effect = RuntimeError(CANARY)
                with self.assertRaisesRegex(core.CutoverError, 'Preflight failed'):
                    adapter.execute(sts, ecr, app, lambda: True)
                for action in ('resume', 'update', 'pause'):
                    getattr(app, action + '_service').assert_not_called()

    def test_operation_appearing_after_prepare_stops_resume(self):
        c = clients(); app = c[2]
        app.list_operations.side_effect = [ {'OperationSummaryList': []},
            {'OperationSummaryList': [{'Id': 'x', 'Status': 'PENDING'}]}]
        with self.assertRaisesRegex(core.CutoverError, 'Preflight failed'):
            adapter.execute(*c, lambda: True)
        app.resume_service.assert_not_called()

    def test_failed_html_or_image_or_preservation_pauses(self):
        for case in ('html', 'image', 'network'):
            with self.subTest(case=case):
                c = clients(); app = c[2]; clock = Clock(); d = core.Diagnostics()
                update = app.update_service.side_effect
                def changed(**kw):
                    result = update(**kw)
                    if case == 'image': app.current['SourceConfiguration']['ImageRepository']['ImageIdentifier'] = 'wrong'
                    if case == 'network': app.current['NetworkConfiguration'] = {}
                    return result
                app.update_service.side_effect = changed
                with self.assertRaisesRegex(core.CutoverError, 'frontend PAUSED'):
                    adapter.execute(*c, lambda: adapter.verify_html(HTML + b'eval(atob(x))'),
                                    clock=clock, sleep=clock.sleep, diagnostics=d)
                app.pause_service.assert_called_once_with(ServiceArn=core.ARN)
                self.assertEqual(app.state, 'PAUSED')
                self.assertEqual(d.lines[-1], 'stage: containment completed')

    def test_ambiguous_mutations_remain_unconfirmed(self):
        for action in ('resume', 'update'):
            c = clients(); app = c[2]; clock = Clock(); d = core.Diagnostics()
            original = getattr(app, action + '_service').side_effect
            def lost(**kw):
                original(**kw)
                raise TimeoutError(CANARY)
            getattr(app, action + '_service').side_effect = lost
            with self.assertRaisesRegex(core.CutoverError, 'UNCONFIRMED'):
                adapter.execute(*c, lambda: True, clock=clock, sleep=clock.sleep, diagnostics=d)
            app.pause_service.assert_called_once()
            self.assertEqual(app.state, 'PAUSED')
            self.assertNotIn(CANARY, '\n'.join(d.lines))
            if action == 'resume': app.update_service.assert_not_called()

    def test_update_timeout_then_settled_failure_contained(self):
        c = clients(); app = c[2]; clock = Clock()
        original = app.list_operations.side_effect
        def operations(**kw):
            result = original(**kw)
            for op in result['OperationSummaryList']:
                if op['Id'] == IDS['update']:
                    op['Status'] = 'IN_PROGRESS' if clock.now < 905 else 'FAILED'
            return result
        app.list_operations.side_effect = operations
        with self.assertRaisesRegex(core.CutoverError, 'frontend PAUSED'):
            adapter.execute(*c, lambda: True, clock=clock, sleep=clock.sleep)
        app.pause_service.assert_called_once()
        self.assertEqual(clock.now, 905)

    def test_paused_pending_or_missing_operation_not_contained(self):
        for ops in ([], [{'Id': IDS['update'], 'Status': 'PENDING'}]):
            app = clients()[2]; app.ops = ops; clock = Clock()
            with self.assertRaises(core.CutoverError):
                core.contain(app, clock=clock, sleep=clock.sleep, timeout=10,
                             known_operations=[IDS['update']])
            app.pause_service.assert_not_called()
            self.assertEqual(clock.now, 10)

    def test_pause_api_failure_not_retried(self):
        c = clients(); c[2].pause_service.side_effect = RuntimeError(CANARY)
        with self.assertRaisesRegex(core.CutoverError, 'UNCONFIRMED'):
            adapter.execute(*c, lambda: False)
        c[2].pause_service.assert_called_once()

    def test_slow_pagination_and_token_cycle(self):
        for slow in (True, False):
            app = Mock(); clock = Clock()
            def page(**kw):
                if slow: clock.sleep(6)
                return {'OperationSummaryList': [], 'NextToken': 'same'}
            app.list_operations.side_effect = page
            with self.assertRaises(core.CutoverError):
                core.wait_operation(app, 'x', clock=clock, sleep=clock.sleep, timeout=10)
            self.assertEqual(app.list_operations.call_count, 2)

    def test_slow_status_response_rejected(self):
        app = clients()[2]; clock = Clock()
        def slow(**kw):
            clock.sleep(11)
            return {'ServiceSummaryList': [{'ServiceArn': core.ARN, 'Status': 'PAUSED'}]}
        app.list_services.side_effect = slow
        with self.assertRaises(core.CutoverError): core.status(app, clock=clock, timeout=10)

    def test_default_and_help_are_inert(self):
        factory = Mock()
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(adapter.main([], client_factory=factory), 0)
            with self.assertRaises(SystemExit): adapter.main(['--help'], client_factory=factory)
        factory.assert_not_called()

    def test_cli_separates_original_and_containment_failure_safely(self):
        c = clients(); clock = Clock(); original_execute = adapter.execute
        c[2].update_service.side_effect = ClientError(
            {'Error': {'Code': 'AccessDeniedException', 'Message': CANARY}, 'payload': CANARY}, CANARY)
        c[2].pause_service.side_effect = RuntimeError(CANARY)
        def factory():
            print(CANARY); print(CANARY, file=sys.stderr)
            return c
        def offline(*args, **kwargs):
            return original_execute(*args, **kwargs, clock=clock, sleep=clock.sleep)
        out = io.StringIO()
        with patch.object(adapter, 'execute', side_effect=offline), \
             patch.object(adapter.resource, 'setrlimit'), patch.object(adapter.faulthandler, 'disable'), \
             patch.object(adapter.logging, 'disable'), contextlib.redirect_stdout(out), contextlib.redirect_stderr(out):
            code = adapter.main(['--execute-approved-cutover'], client_factory=factory)
        self.assertEqual(code, 1)
        self.assertIn('failure: stage=update requested code=AccessDeniedException', out.getvalue())
        self.assertIn('failure: stage=containment requested code=unexpected_error', out.getvalue())
        for forbidden in (CANARY, 'Traceback', 'payload', 'RuntimeEnvironment'):
            self.assertNotIn(forbidden, out.getvalue())
        for action in ('resume', 'update', 'pause'):
            getattr(c[2], action + '_service').assert_called_once()

    def test_inert_html_success(self):
        self.assertTrue(adapter.verify_html(HTML))

    def test_known_loader_patterns_rejected(self):
        for marker in (b'<script src="data:text/javascript;base64,synthetic"></script>',
                       b'eval ( atob ( "synthetic" ))', b'ETH_CALL',
                       b'https://bsc-testnet.example.binance.org', b'data-seed-prebsc',
                       b'data&#58;text/javascript;base64,synthetic'):
            with self.subTest(marker=marker): self.assertFalse(adapter.verify_html(HTML + marker))

    def test_wrong_or_missing_markup_rejected(self):
        for body in (b'', b'not html', HTML.replace(b'password', b'text'),
                     HTML.replace(b'/_next/static/chunks/login.js', b'https://example.invalid/x.js'),
                     HTML + b'\xff', b'x' * (adapter.MAX_HTML + 1)):
            self.assertFalse(adapter.verify_html(body))

    def response(self, body=HTML):
        opener = Mock(); response = Mock()
        response.status = 200; response.read.return_value = body
        response.geturl.return_value = adapter.HEALTH_URL
        response.headers.get_content_type.return_value = 'text/html'
        opener.open.return_value.__enter__ = Mock(return_value=response)
        opener.open.return_value.__exit__ = Mock(return_value=False)
        return opener, response

    def test_https_transport_bounded_and_no_credentials(self):
        opener, response = self.response(); clock = Clock()
        self.assertTrue(adapter.health_check(opener=opener, clock=clock, sleep=clock.sleep))
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, adapter.HEALTH_URL)
        self.assertEqual(request.get_method(), 'GET')
        self.assertIsNone(request.data)
        self.assertFalse(request.has_header('Authorization')); self.assertFalse(request.has_header('Cookie'))
        response.read.assert_called_once_with(adapter.MAX_HTML + 1)
        self.assertLessEqual(opener.open.call_args.kwargs['timeout'], 5)

    def test_http_mismatch_and_slow_response_fail(self):
        for case in ('redirect', 'mime', 'url', 'body', 'slow', 'timeout'):
            opener, response = self.response(); clock = Clock()
            if case == 'redirect': response.status = 302
            if case == 'mime': response.headers.get_content_type.return_value = 'application/json'
            if case == 'url': response.geturl.return_value = 'https://example.invalid/'
            if case == 'body': response.read.return_value = HTML + b'eth_call'
            if case == 'slow':
                def slow(*args): clock.sleep(61); return HTML
                response.read.side_effect = slow
            if case == 'timeout': opener.open.side_effect = TimeoutError(CANARY)
            self.assertFalse(adapter.health_check(opener=opener, clock=clock, sleep=clock.sleep))
            if case == 'body': opener.open.assert_called_once()
            self.assertLessEqual(clock.now, 61)
        self.assertIsNone(adapter.NoRedirect().redirect_request(None, None, 302, None, None, 'https://example.invalid'))


if __name__ == '__main__': unittest.main()
