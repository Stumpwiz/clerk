"""Explicitly gated executor for the single reviewed Clerk frontend cutover."""
import argparse
import contextlib
import faulthandler
import re
from html import unescape
from html.parser import HTMLParser
import logging
import resource
import signal
import time
import urllib.request

import frontend_cutover as core

ACCOUNT = '365591166807'
REGION = 'us-east-1'
IDENTITY = 'arn:aws:iam::365591166807:user/twin'
HEALTH_URL = 'https://clerk.mrrc.online/local-login'
MAX_HTML = 1024 * 1024
SAFE_ERRORS = {
    'Preflight failed; no mutation attempted.',
    'Cutover failed; frontend PAUSED.',
    'Cutover failed; containment UNCONFIRMED. Operator action required.',
}


def execute(sts, ecr, apprunner, health, *, clock=time.monotonic, sleep=time.sleep,
            diagnostics=None):
    """All dependencies injected: synthetic tests never construct live clients."""
    diagnostics = diagnostics if diagnostics is not None else core.Diagnostics()
    diagnostics.stage('preflight')
    try:
        identity = sts.get_caller_identity()
        if identity['Account'] != ACCOUNT or identity['Arn'] != IDENTITY:
            raise ValueError()
        deadline = clock() + 60
        if core.status(apprunner, clock=clock, deadline=deadline) != 'PAUSED':
            raise ValueError()
        if any(op['Status'] not in core.TERMINAL for op in
               core.operations(apprunner, clock=clock, deadline=deadline)):
            raise ValueError()
        images = ecr.describe_images(registryId=ACCOUNT, repositoryName='clerk-frontend',
                                     imageIds=[{'imageDigest': core.DIGEST}])['imageDetails']
        if len(images) != 1 or images[0]['imageDigest'] != core.DIGEST:
            raise ValueError()
        core.check_deadline(clock, deadline)
        # Secret-bearing response: memory only, within the silenced CLI boundary.
        service = apprunner.describe_service(ServiceArn=core.ARN)['Service']
        core.check_deadline(clock, deadline)
        if service['ServiceArn'] != core.ARN or service['ServiceName'] != 'clerk-frontend':
            raise ValueError()
    except BaseException as error:
        diagnostics.failure(error)
        raise core.CutoverError('Preflight failed; no mutation attempted.') from None
    return core.restore(apprunner, service, health, clock=clock, sleep=sleep,
                        diagnostics=diagnostics)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


INDICATORS = tuple(re.compile(pattern, re.IGNORECASE) for pattern in (
    r'data:\s*(?:text|application)/(?:java|ecma)script',
    r'eval\s*\(\s*atob\s*\(', r'eth_call',
    r'bsc-testnet[^\s\"\x27]*\.binance', r'data-seed-prebsc',
))


class LoginHTML(HTMLParser):
    """Parse inert markup only. Never fetch or interpret a script."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.in_form = 0
        self.inputs = set()
        self.scripts = 0
        self.safe = True

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'form':
            self.in_form += 1
        if tag == 'input' and self.in_form:
            self.inputs.add((attributes.get('type') or '').lower())
        if tag == 'script' and 'src' in attributes:
            source = attributes['src'] or ''
            self.scripts += 1
            if not re.fullmatch(r'/_next/static/[a-zA-Z0-9_./%-]+\.js(?:\?[^\"\x27<>]*)?', source):
                self.safe = False

    def handle_endtag(self, tag):
        if tag == 'form':
            self.in_form = max(0, self.in_form - 1)


def verify_html(body):
    """Selected incident indicators and expected login markup; not a malware proof."""
    try:
        if not body or len(body) > MAX_HTML:
            return False
        text = body.decode('utf-8', errors='strict')
        normalized = unescape(text).replace('\\/', '/')
        if any(pattern.search(normalized) for pattern in INDICATORS):
            return False
        parser = LoginHTML()
        parser.feed(text)
        parser.close()
        return (parser.safe and parser.scripts > 0
                and {'email', 'password'} <= parser.inputs and 'Local Login' in text)
    except Exception:
        return False


def health_check(*, opener=None, clock=time.monotonic, sleep=time.sleep):
    """Main-thread only: 60s total alarm, 5s I/O timeout, <=1 MiB inert HTML.

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
                request = urllib.request.Request(HEALTH_URL, headers={
                    'Cache-Control': 'no-cache', 'Accept': 'text/html',
                    'Accept-Encoding': 'identity'})
                with opener.open(request, timeout=min(5, max(.01, deadline-clock()))) as response:
                    if response.status == 200:
                        body = response.read(MAX_HTML + 1)
                        # A suspect or unexpected 200 response fails immediately.
                        return (clock() < deadline and response.geturl() == HEALTH_URL
                                and response.headers.get_content_type() == 'text/html'
                                and verify_html(body) and clock() < deadline)
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
        description='One-off Clerk frontend restoration. No AWS calls without --execute-approved-cutover.',
        epilog='Later authorized execution: .venv/bin/python scripts/execute_frontend_cutover.py --execute-approved-cutover')
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
        error = 'Executor failed; inspect frontend status before any further action.'
    finally:
        signal.signal(signal.SIGTERM, old_sigterm)
    for line in diagnostics.lines:
        print(line)
    if error:
        print(error)
        return 1
    # Never serialize a raw result/SDK dictionary; print only known-safe output.
    print('Frontend cutover verified: RUNNING; configured digest and /local-login HTML verified.')
    print('Image: ' + core.IMAGE)
    operation = result.get('update_operation_id', '')
    if isinstance(operation, str) and len(operation) == 32 and all(c in '0123456789abcdef' for c in operation):
        print('Update operation: ' + operation)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
