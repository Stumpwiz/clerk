"""Offline regressions through both real restore paths after successful resume."""
import unittest
from unittest.mock import patch

from botocore.exceptions import ClientError
import test_backend_cutover as backend
import test_frontend_cutover as frontend


class ResumeStatusTests(unittest.TestCase):
    def setUp(self):
        for target in ('botocore.session.Session.create_client', 'socket.socket.connect'):
            guard = patch(target, side_effect=AssertionError('No external calls'))
            guard.start()
            self.addCleanup(guard.stop)

    def cases(self):
        yield backend.m, backend.Tests().client(), backend.fixture()
        yield frontend.core, frontend.clients()[2], frontend.fixture()

    def assert_mutations(self, client, *, update=0, pause=1):
        self.assertEqual(client.resume_service.call_count, 1)
        self.assertEqual(client.update_service.call_count, update)
        self.assertEqual(client.pause_service.call_count, pause)
        client.start_deployment.assert_not_called()

    def run_failure(self, core, client, service, clock, *, unconfirmed=False):
        diagnostics = core.Diagnostics()
        with self.assertRaises(core.CutoverError) as error:
            core.restore(client, service, lambda: True, clock=clock,
                         sleep=clock.sleep, timeout=10, diagnostics=diagnostics)
        self.assertEqual('UNCONFIRMED' in str(error.exception), unconfirmed)
        self.assertNotIn('sensitive-canary', '\n'.join(diagnostics.lines))
        return diagnostics.lines

    def test_transitional_summary_then_running_updates_once(self):
        for core, client, service in self.cases():
            with self.subTest(core=core.__name__):
                clock = frontend.Clock(); original = client.list_services.side_effect
                def summary(**kwargs):
                    if client.resume_service.called and clock.now < 10:
                        state = 'PAUSED' if clock.now == 0 else 'OPERATION_IN_PROGRESS'
                        return {'ServiceSummaryList': [{'ServiceArn': core.ARN, 'Status': state}]}
                    return original(**kwargs)
                client.list_services.side_effect = summary
                original_update = client.update_service.side_effect
                def update(**kwargs):
                    self.assertEqual(clock.now, 10)
                    return original_update(**kwargs)
                client.update_service.side_effect = update
                result = core.restore(client, service, lambda: True, clock=clock,
                                      sleep=clock.sleep, timeout=20)
                self.assertEqual(result['result'], 'verified')
                self.assert_mutations(client, update=1, pause=0)

    def test_original_resume_deadline_is_not_restarted(self):
        for core, client, service in self.cases():
            with self.subTest(core=core.__name__):
                clock = frontend.Clock(); original_ops = client.list_operations.side_effect
                original_status = client.list_services.side_effect
                consumed = False
                def operations(**kwargs):
                    nonlocal consumed
                    if client.resume_service.called and not consumed:
                        consumed = True
                        clock.sleep(7)
                    return original_ops(**kwargs)
                def summary(**kwargs):
                    if client.resume_service.called and clock.now < 10:
                        return {'ServiceSummaryList': [{'ServiceArn': core.ARN, 'Status': 'OPERATION_IN_PROGRESS'}]}
                    return original_status(**kwargs)
                client.list_operations.side_effect = operations
                client.list_services.side_effect = summary
                lines = self.run_failure(core, client, service, clock)
                self.assertEqual(clock.now, 10)
                self.assertIn('failure: stage=resume requested code=resume_running_timeout', lines)
                self.assertIn('stage: containment completed', lines)
                self.assert_mutations(client)

    def test_never_running_times_out_and_containment_stays_conservative(self):
        for core, client, service in self.cases():
            with self.subTest(core=core.__name__):
                clock = frontend.Clock(); original = client.list_services.side_effect
                def summary(**kwargs):
                    if client.resume_service.called:
                        return {'ServiceSummaryList': [{'ServiceArn': core.ARN, 'Status': 'OPERATION_IN_PROGRESS'}]}
                    return original(**kwargs)
                client.list_services.side_effect = summary
                lines = self.run_failure(core, client, service, clock, unconfirmed=True)
                self.assertEqual(clock.now, 20)
                self.assertIn('failure: stage=resume requested code=resume_running_timeout', lines)
                self.assert_mutations(client, pause=0)

    def test_missing_summary_fails_closed_and_contains(self):
        for core, client, service in self.cases():
            with self.subTest(core=core.__name__):
                clock = frontend.Clock(); original = client.list_services.side_effect
                missing = False
                def summary(**kwargs):
                    nonlocal missing
                    if client.resume_service.called and not missing:
                        missing = True
                        return {'ServiceSummaryList': []}
                    return original(**kwargs)
                client.list_services.side_effect = summary
                lines = self.run_failure(core, client, service, clock)
                self.assertIn('failure: stage=resume requested code=local_failure', lines)
                self.assert_mutations(client)

    def test_status_api_failure_is_sanitized_and_contains(self):
        for core, client, service in self.cases():
            with self.subTest(core=core.__name__):
                clock = frontend.Clock(); original = client.list_services.side_effect
                failed = False
                def summary(**kwargs):
                    nonlocal failed
                    if client.resume_service.called and not failed:
                        failed = True
                        raise ClientError({'Error': {'Code': 'AccessDeniedException',
                                          'Message': 'sensitive-canary'}}, 'sensitive-canary')
                    return original(**kwargs)
                client.list_services.side_effect = summary
                lines = self.run_failure(core, client, service, clock)
                self.assertIn('failure: stage=resume requested code=AccessDeniedException', lines)
                self.assert_mutations(client)

    def test_late_running_response_is_rejected(self):
        for core, client, service in self.cases():
            with self.subTest(core=core.__name__):
                clock = frontend.Clock(); original = client.list_services.side_effect
                delayed = False
                def summary(**kwargs):
                    nonlocal delayed
                    if client.resume_service.called and not delayed:
                        delayed = True
                        clock.sleep(11)
                    return original(**kwargs)
                client.list_services.side_effect = summary
                lines = self.run_failure(core, client, service, clock)
                self.assertIn('failure: stage=resume requested code=resume_running_timeout', lines)
                self.assert_mutations(client)

    def test_status_pagination_shares_deadline(self):
        for core, client, service in self.cases():
            with self.subTest(core=core.__name__):
                clock = frontend.Clock(); original = client.list_services.side_effect
                count = 0
                def summary(**kwargs):
                    nonlocal count
                    if client.resume_service.called and count < 2:
                        count += 1
                        clock.sleep(6)
                        if count == 1: return {'ServiceSummaryList': [], 'NextToken': 'second'}
                    return original(**kwargs)
                client.list_services.side_effect = summary
                lines = self.run_failure(core, client, service, clock)
                self.assertEqual(count, 2)
                self.assertIn('failure: stage=resume requested code=resume_running_timeout', lines)
                self.assert_mutations(client)

    def test_status_token_cycle_fails_closed(self):
        for core, client, service in self.cases():
            with self.subTest(core=core.__name__):
                clock = frontend.Clock(); original = client.list_services.side_effect
                count = 0
                def summary(**kwargs):
                    nonlocal count
                    if client.resume_service.called and count < 2:
                        count += 1
                        return {'ServiceSummaryList': [], 'NextToken': 'repeated'}
                    return original(**kwargs)
                client.list_services.side_effect = summary
                lines = self.run_failure(core, client, service, clock)
                self.assertEqual(count, 2)
                self.assertIn('failure: stage=resume requested code=local_failure', lines)
                self.assert_mutations(client)


if __name__ == '__main__': unittest.main()
