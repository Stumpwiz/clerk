"""Explicitly gated executor for the single reviewed Clerk backend cutover."""
import argparse
import contextlib
import faulthandler
import json
import logging
import resource
import signal
import time
import urllib.request

import backend_cutover as core

ACCOUNT = '365591166807'
REGION = 'us-east-1'
HEALTH_URL = 'https://api.mrrc.online/health'
ACTIVE = {'PENDING', 'IN_PROGRESS', 'ROLLBACK_IN_PROGRESS'}
SAFE_ERRORS = {
    'Preflight failed; no mutation attempted.',
    'Cutover failed; backend PAUSED.',
    'Cutover failed; containment UNCONFIRMED. Operator action required.',
}


def execute(sts, ecr, apprunner, health, *, clock=time.monotonic, sleep=time.sleep,
            diagnostics=None):
    """All dependencies injected: synthetic tests never construct live clients."""
    diagnostics = diagnostics if diagnostics is not None else core.Diagnostics()
    diagnostics.stage('preflight')
    try:
        identity = sts.get_caller_identity()
        if identity['Account'] != ACCOUNT or identity['Arn'].split(':')[4] != ACCOUNT:
            raise ValueError()
        deadline = clock() + 60
        if core.status(apprunner, clock=clock, deadline=deadline) != 'PAUSED':
            raise ValueError()
        if any(op['Status'] in ACTIVE for op in
               core.operations(apprunner, clock=clock, deadline=deadline)):
            raise ValueError()
        images = ecr.describe_images(registryId=ACCOUNT, repositoryName='clerk-backend',
                                     imageIds=[{'imageDigest': core.DIGEST}])['imageDetails']
        if len(images) != 1 or images[0]['imageDigest'] != core.DIGEST:
            raise ValueError()
        # Secret-bearing response: memory only, within the silenced CLI boundary.
        service = apprunner.describe_service(ServiceArn=core.ARN)['Service']
        if service['ServiceArn'] != core.ARN or service['ServiceName'] != 'clerk-backend':
            raise ValueError()
    except BaseException as error:
        diagnostics.failure(error)
        raise core.CutoverError('Preflight failed; no mutation attempted.') from None
    return core.restore(apprunner, service, health, clock=clock, sleep=sleep,
                        diagnostics=diagnostics)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def health_check(*, opener=None, clock=time.monotonic, sleep=time.sleep):
    """Main-thread only: 60s total alarm, 5s I/O timeout, <=4096-byte JSON.

    No redirects, proxy environment, credentials, cookies, or response logging.
    The real CLI uses the default verified HTTPS handler. Tests inject transport.
    """
    opener = opener or urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    previous = signal.getsignal(signal.SIGALRM)
    class HealthDeadline(BaseException):
        pass
    def expired(*_):
        raise HealthDeadline()
    signal.signal(signal.SIGALRM, expired)
    signal.setitimer(signal.ITIMER_REAL, 60)
    deadline = clock() + 60
    try:
        while clock() < deadline:
            try:
                with opener.open(HEALTH_URL, timeout=min(5, max(.01, deadline-clock()))) as response:
                    body = response.read(4097)
                    if (clock() < deadline and response.status == 200 and len(body) <= 4096
                            and json.loads(body) == {'status': 'healthy'}):
                        return True
            except Exception:
                pass
            sleep(min(2, max(0, deadline-clock())))
        return False
    except HealthDeadline:
        return False
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous)


def live_clients():
    # Only called after the explicit execution flag, inside output suppression.
    import boto3
    from botocore.config import Config
    session = boto3.Session(region_name=REGION)
    config = Config(region_name=REGION, connect_timeout=5, read_timeout=15,
                    retries={'total_max_attempts': 1})
    return tuple(session.client(name, config=config) for name in ('sts', 'ecr', 'apprunner'))


def main(argv=None, *, client_factory=live_clients, health=health_check):
    parser = argparse.ArgumentParser(
        description='One-off Clerk backend restoration. No AWS calls without --execute-approved-cutover.',
        epilog='Later authorized execution: .venv/bin/python scripts/execute_backend_cutover.py --execute-approved-cutover')
    parser.add_argument('--execute-approved-cutover', action='store_true',
                        help='Execute separately authorized secret-bearing reads, resume/update and failure pause.')
    args = parser.parse_args(argv)
    if not args.execute_approved_cutover:
        print('Preparation only; no AWS calls. Execution requires separate approval and --execute-approved-cutover.')
        return 0
    result = None
    error = None
    diagnostics = core.Diagnostics()
    old_sigterm = signal.getsignal(signal.SIGTERM)
    def interrupted(*_):
        raise KeyboardInterrupt()
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        faulthandler.disable()
        logging.disable(logging.CRITICAL)
        signal.signal(signal.SIGTERM, interrupted)
        with open('/dev/null', 'w') as sink, contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
            clients = client_factory()
            result = execute(*clients, health, diagnostics=diagnostics)
    except core.CutoverError as exc:
        error = str(exc) if str(exc) in SAFE_ERRORS else 'Cutover failed; containment UNCONFIRMED. Operator action required.'
    except BaseException as unexpected:
        diagnostics.failure(unexpected)
        error = 'Executor failed; inspect backend status before any further action.'
    finally:
        signal.signal(signal.SIGTERM, old_sigterm)
    for line in diagnostics.lines:
        print(line)
    if error:
        print(error)
        return 1
    # Never serialize a raw result/SDK dictionary; print only known-safe output.
    print('Backend cutover verified: RUNNING; configured digest and /health verified.')
    print('Image: ' + core.IMAGE)
    operation = result.get('update_operation_id', '')
    if isinstance(operation, str) and len(operation) == 32 and all(c in '0123456789abcdef' for c in operation):
        print('Update operation: ' + operation)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
