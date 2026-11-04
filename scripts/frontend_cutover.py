"""One-off frontend cutover core. No CLI, client creation, or import-time AWS calls.

Execution requires separate authorization for secret-bearing DescribeService access,
resume/update, HTTP health verification and failure containment. Never log SDK
requests/responses or exceptions. Use SDK clients with retries disabled and bounded
connect/read timeouts. A future executor must disable SDK debug logging/core dumps.
"""
from copy import deepcopy
import time
from botocore.session import Session
from botocore.validate import validate_parameters
import backend_cutover as shared

ARN = 'arn:aws:apprunner:us-east-1:365591166807:service/clerk-frontend/7d7f42151edb48fb87d706a4cceb2e4a'
REPO = '365591166807.dkr.ecr.us-east-1.amazonaws.com/clerk-frontend'
DIGEST = 'sha256:41e28cb7e92a9f65aa62be9b55d81dfda66f778f7bb958e25cea21cb47e6a5db'
IMAGE = REPO + '@' + DIGEST

CutoverError = shared.CutoverError
Diagnostics = shared.Diagnostics
check_deadline = shared.check_deadline
pages = shared.pages


def prepare(service):
    """Preserve source settings; omit unrelated top-level fields from update."""
    try:
        if (service['ServiceArn'] != ARN or service['ServiceName'] != 'clerk-frontend'
                or service['Status'] != 'PAUSED'):
            raise ValueError()
        source = deepcopy(service['SourceConfiguration'])
        image = source['ImageRepository']
        if (source.get('AutoDeploymentsEnabled') is not False
                or 'CodeRepository' in source
                or image['ImageIdentifier'] != REPO + ':latest'
                or image['ImageRepositoryType'] != 'ECR'):
            raise ValueError()
        if not source.get('AuthenticationConfiguration', {}).get('AccessRoleArn'):
            raise ValueError()
        image['ImageIdentifier'] = IMAGE
        request = {'ServiceArn': ARN, 'SourceConfiguration': source}
        validate_parameters(request, Session().get_service_model('apprunner')
                            .operation_model('UpdateService').input_shape)
        return request
    except Exception:
        raise CutoverError('Configuration preflight refused.') from None


TERMINAL = shared.TERMINAL


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


def contain(client, *, clock, sleep, timeout, known_operations=(), uncertain=False,
            diagnostics=None):
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
            if diagnostics is not None:
                diagnostics.operation('pause', operation)
            if not isinstance(operation, str) or not operation:
                raise CutoverError('Containment unconfirmed.')
            known.add(operation)
            check_deadline(clock, deadline)
            wait_operation(client, operation, clock=clock, sleep=sleep, deadline=deadline)
            continue  # Recheck PAUSED and all operations, within the same deadline.
        check_deadline(clock, deadline)
        sleep(min(5, deadline - clock()))


def restore(client, service, health, *, clock=time.monotonic, sleep=time.sleep,
            timeout=900, diagnostics=None):
    """Frontend-only adaptation of the proven backend operation/containment order.

    Caller verifies identity, digest, PAUSED and idle before retrieving configuration.
    health() performs bounded, inert HTTPS login HTML verification. No key rotation.
    """
    touched = False
    diagnostics = diagnostics if diagnostics is not None else Diagnostics()
    uncertain = False
    known_operations = []
    try:
        request = prepare(service)  # Only the image changes; prepare before resume.
        diagnostics.stage('configuration prepared')
        if status(client, clock=clock, timeout=timeout) != 'PAUSED':
            raise CutoverError('State changed before resume.')
        deadline = clock() + timeout
        if any(op['Status'] not in TERMINAL for op in
               operations(client, clock=clock, deadline=deadline)):
            raise CutoverError('Operation appeared before resume.')
        check_deadline(clock, deadline)
        touched = True  # A timeout can hide a successful resume request.
        uncertain = True
        diagnostics.stage('resume requested')
        operation = client.resume_service(ServiceArn=ARN)['OperationId']
        diagnostics.operation('resume', operation)
        if not isinstance(operation, str) or not operation:
            raise CutoverError('Missing operation identity.')
        known_operations.append(operation)
        uncertain = False
        check_deadline(clock, deadline)
        wait_operation(client, operation, clock=clock, sleep=sleep, deadline=deadline)
        shared.wait_running(client, clock=clock, sleep=sleep, deadline=deadline,
                            status_reader=status)
        diagnostics.stage('resume completed')
        deadline = clock() + timeout
        uncertain = True
        diagnostics.stage('update requested')
        operation = client.update_service(**request)['OperationId']
        diagnostics.operation('update', operation)
        if not isinstance(operation, str) or not operation:
            raise CutoverError('Missing operation identity.')
        known_operations.append(operation)
        uncertain = False
        diagnostics.stage('update accepted')
        check_deadline(clock, deadline)
        wait_operation(client, operation, clock=clock, sleep=sleep, deadline=deadline)
        diagnostics.stage('update completed')
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
        diagnostics.stage('health verified')
        return {'result': 'verified', 'update_operation_id': operation, 'image': IMAGE}
    except BaseException as error:
        diagnostics.failure(error)
        if touched:
            diagnostics.stage('containment requested')
            try:
                contain(client, clock=clock, sleep=sleep, timeout=timeout,
                        known_operations=known_operations, uncertain=uncertain,
                        diagnostics=diagnostics)
            except BaseException as containment_error:
                diagnostics.failure(containment_error)
                diagnostics.stage('containment unconfirmed')
                raise CutoverError('Cutover failed; containment UNCONFIRMED. Operator action required.') from None
            diagnostics.stage('containment completed')
            raise CutoverError('Cutover failed; frontend PAUSED.') from None
        raise CutoverError('Preflight failed; no mutation attempted.') from None
