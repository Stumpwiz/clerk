"""One-off backend cutover core. No CLI, client creation, or import-time AWS calls.

Execution requires separate authorization for secret-bearing DescribeService access,
resume/update, HTTP health verification and failure containment. Never log SDK
requests/responses or exceptions. Use SDK clients with retries disabled and bounded
connect/read timeouts. A future executor must disable SDK debug logging/core dumps.
"""
from copy import deepcopy
import secrets
import time
from botocore.session import Session
from botocore.validate import validate_parameters

ARN = 'arn:aws:apprunner:us-east-1:365591166807:service/clerk-backend/181518238ff148e88363a488640dd90d'
REPO = '365591166807.dkr.ecr.us-east-1.amazonaws.com/clerk-backend'
SHA = 'b6e2d5e6e0c9bc62bc666229229c1515bbc9b45a'
DIGEST = 'sha256:85b15c42d701b7b17cabf88412fbc3e6aa437c18cd7467eb8e661dda44a7d8a5'
IMAGE = REPO + '@' + DIGEST
SETTINGS = {
    'CLERK_ENV': 'production', 'DEBUG': 'false',
    'SESSION_COOKIE_SECURE': 'true', 'SESSION_COOKIE_SAMESITE': 'lax',
    'CORS_ORIGINS': 'https://clerk.mrrc.online',
    'DISABLE_AUTO_MIGRATE': 'true', 'ENABLE_IONOS_ROSTER_PUBLISH': 'false',
}


class CutoverError(Exception):
    """Only static, secret-free messages may cross this boundary."""


def prepare(service):
    """Preserve source settings; omit unrelated top-level fields from update."""
    try:
        if service['ServiceArn'] != ARN or service['Status'] != 'PAUSED':
            raise ValueError()
        source = deepcopy(service['SourceConfiguration'])
        image = source['ImageRepository']
        if (source.get('AutoDeploymentsEnabled') is not False
                or 'CodeRepository' in source
                or image['ImageIdentifier'] != REPO + ':latest'
                or image['ImageRepositoryType'] != 'ECR'):
            raise ValueError()
        config = image.setdefault('ImageConfiguration', {})
        env = config.setdefault('RuntimeEnvironmentVariables', {})
        refs = config.get('RuntimeEnvironmentSecrets', {})
        if not (bool(env.get('DATABASE_URL')) ^ bool(refs.get('DATABASE_URL'))):
            raise ValueError()
        key = secrets.token_urlsafe(48)
        env.update(SETTINGS)
        env['AUTH_SECRET_KEY'] = key
        # Avoid duplicate variable names overriding the approved values.
        for name in (*SETTINGS, 'AUTH_SECRET_KEY'):
            refs.pop(name, None)
        image['ImageIdentifier'] = IMAGE
        request = {'ServiceArn': ARN, 'SourceConfiguration': source}
        validate_parameters(request, Session().get_service_model('apprunner')
                            .operation_model('UpdateService').input_shape)
        return request
    except Exception:
        raise CutoverError('Configuration preflight refused.') from None


TERMINAL = {'SUCCEEDED', 'FAILED', 'ROLLBACK_SUCCEEDED', 'ROLLBACK_FAILED'}


def check_deadline(clock, deadline):
    if clock() >= deadline:
        raise CutoverError('Operation timed out.')


def pages(method, key, *, clock, deadline, **kwargs):
    """One shared deadline, including response processing; reject token cycles."""
    token = None
    seen = set()
    while True:
        check_deadline(clock, deadline)
        response = method(**kwargs, **({'NextToken': token} if token else {}))
        check_deadline(clock, deadline)
        yield response[key]
        token = response.get('NextToken')
        if not token:
            return
        if token in seen:
            raise CutoverError('Repeated pagination token.')
        seen.add(token)


def operations(client, *, clock, deadline):
    return [operation for page in pages(client.list_operations, 'OperationSummaryList',
            ServiceArn=ARN, clock=clock, deadline=deadline) for operation in page]


def wait_operation(client, operation_id, *, clock, sleep, timeout=900, deadline=None):
    deadline = clock() + timeout if deadline is None else deadline
    while True:
        for operation in operations(client, clock=clock, deadline=deadline):
            if operation['Id'] == operation_id:
                state = operation['Status']
                if state == 'SUCCEEDED':
                    return
                if state not in ('PENDING', 'IN_PROGRESS', 'ROLLBACK_IN_PROGRESS'):
                    raise CutoverError('Operation failed.')
        check_deadline(clock, deadline)
        sleep(min(5, deadline - clock()))


def status(client, *, clock=time.monotonic, timeout=60, deadline=None):
    deadline = clock() + timeout if deadline is None else deadline
    for page in pages(client.list_services, 'ServiceSummaryList', clock=clock, deadline=deadline):
        for service in page:
            if service['ServiceArn'] == ARN:
                return service['Status']
    raise CutoverError('Service not found.')


def contain(client, *, clock, sleep, timeout, known_operations=(), uncertain=False):
    """Never infer rejection of a lost mutation response from an empty list.

    A request without an operation ID remains uncertain for this invocation.
    Best-effort pause is still permitted once, but cannot establish containment.
    Known IDs must all be visible and terminal; any nonterminal operation blocks
    pause/confirmation. Requires no concurrent external service mutations.
    """
    deadline = clock() + timeout
    known = set(known_operations)
    pause_attempted = False
    while True:
        state = status(client, clock=clock, deadline=deadline)
        listed = operations(client, clock=clock, deadline=deadline)
        settled = {op['Id'] for op in listed if op['Status'] in TERMINAL}
        idle = all(op['Status'] in TERMINAL for op in listed)
        resolved = known <= settled
        if state == 'PAUSED' and idle and resolved and not uncertain:
            return
        if state == 'RUNNING' and idle and resolved and not pause_attempted:
            check_deadline(clock, deadline)
            pause_attempted = True  # Never retry an ambiguous pause request.
            operation = client.pause_service(ServiceArn=ARN)['OperationId']
            if not isinstance(operation, str) or not operation:
                raise CutoverError('Containment unconfirmed.')
            known.add(operation)
            check_deadline(clock, deadline)
            wait_operation(client, operation, clock=clock, sleep=sleep, deadline=deadline)
            continue  # Recheck PAUSED and all operations, within the same deadline.
        check_deadline(clock, deadline)
        sleep(min(5, deadline - clock()))


def restore(client, service, health, *, clock=time.monotonic, sleep=time.sleep,
            timeout=900):
    """Injected client and bounded health callback only; no automatic live adapter.

    Caller verifies STS account, ECR tag/digest, IAM, no active operation, and
    obtains service in memory immediately before calling. health() must check
    HTTPS /health status 200 and exact {"status": "healthy"}, without logging
    response bodies, using bounded request timeouts and no redirects.
    """
    touched = False
    uncertain = False
    known_operations = []
    try:
        request = prepare(service)  # Generate key and prepare everything before resume.
        if status(client, clock=clock, timeout=timeout) != 'PAUSED':
            raise CutoverError('State changed before resume.')
        deadline = clock() + timeout
        touched = True  # A timeout can hide a successful resume request.
        uncertain = True
        operation = client.resume_service(ServiceArn=ARN)['OperationId']
        if not isinstance(operation, str) or not operation:
            raise CutoverError('Missing operation identity.')
        known_operations.append(operation)
        uncertain = False
        check_deadline(clock, deadline)
        wait_operation(client, operation, clock=clock, sleep=sleep, deadline=deadline)
        if status(client, clock=clock, deadline=deadline) != 'RUNNING':
            raise CutoverError('Resume state mismatch.')
        deadline = clock() + timeout
        uncertain = True
        operation = client.update_service(**request)['OperationId']
        if not isinstance(operation, str) or not operation:
            raise CutoverError('Missing operation identity.')
        known_operations.append(operation)
        uncertain = False
        check_deadline(clock, deadline)
        wait_operation(client, operation, clock=clock, sleep=sleep, deadline=deadline)
        check_deadline(clock, deadline)
        current = client.describe_service(ServiceArn=ARN)['Service']
        check_deadline(clock, deadline)
        if current['Status'] != 'RUNNING' or current['SourceConfiguration'] != request['SourceConfiguration']:
            raise CutoverError('Updated configuration mismatch.')
        for field in ('InstanceConfiguration', 'NetworkConfiguration',
                      'HealthCheckConfiguration', 'AutoScalingConfigurationSummary',
                      'ObservabilityConfiguration', 'EncryptionConfiguration'):
            if current.get(field) != service.get(field):
                raise CutoverError('Unrelated configuration changed.')
        if health() is not True:
            raise CutoverError('Health verification failed.')
        return {'result': 'verified', 'update_operation_id': operation, 'image': IMAGE}
    except BaseException:
        if touched:
            try:
                contain(client, clock=clock, sleep=sleep, timeout=timeout,
                        known_operations=known_operations, uncertain=uncertain)
            except BaseException:
                raise CutoverError('Cutover failed; containment UNCONFIRMED. Operator action required.') from None
            raise CutoverError('Cutover failed; backend PAUSED.') from None
        raise CutoverError('Preflight failed; no mutation attempted.') from None
