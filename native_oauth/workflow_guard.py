"""Current-release launch checks. Historical evidence remains readable offline.

The lease is process-local; copying its JSON receipt does not authorize a call.
This guards repository entry points, not arbitrary external CLI installations.
"""
import hashlib
import json
import os
import re
import subprocess
import threading
import time
import uuid
from contextlib import contextmanager
from pathlib import Path

from native_oauth.workflow_io import atomic_json

ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = 'https://github.com/hiraga1305/CaoTruyen'
POLICY = 'current-workflow-1'
LOCK = 'workflow_release.json'
_leases = {}
_mutex = threading.RLock()


class WorkflowGateError(RuntimeError):
    kind = 'WORKFLOW'
    action = 'SYNC_CURRENT_WORKFLOW_AND_RELAUNCH_WITH_NEW_JOB_REVISION'


def file_hash(path):
    # Git checkouts may use CRLF on Windows and LF on Linux. Code only;
    # original novels/native evidence keep their byte-level hashing unchanged.
    return hashlib.sha256(Path(path).read_bytes().replace(b'\r\n', b'\n')).hexdigest()


_import_lock_hash = file_hash(ROOT / LOCK) if (ROOT / LOCK).exists() else None


def local_release(root=None):
    root = Path(root or ROOT).resolve()
    try:
        workflow = json.loads((root / 'workflow.json').read_text(encoding='utf-8'))
        lock = json.loads((root / LOCK).read_text(encoding='utf-8'))
        from native_oauth.resilient_policy import POLICY as CONTENT, REVIEW_POLICY
        from native_oauth.resilient_continuity import VERSION as CONTINUITY
        if (lock.get('schema') != 'caotruyen-release-1' or lock.get('workflow_id') != workflow['id']
                or lock.get('version') != workflow['version'] or workflow.get('repository') != REPOSITORY
                or not isinstance(workflow['version'],str) or re.fullmatch(r'\d+\.\d+\.\d+(?:[-+][A-Za-z0-9.-]+)?',workflow['version']) is None
                or workflow.get('launch_policy') != POLICY or workflow.get('validation_policy') != CONTENT
                or workflow.get('review_policy') != REVIEW_POLICY or workflow.get('continuity_policy') != CONTINUITY):
            raise WorkflowGateError('Workflow metadata, implementation policies and release lock do not match')
        files = lock.get('files')
        required = {'workflow.json', 'translate.py', 'native_oauth/workflow_guard.py',
                    'native_oauth/resilient_translation.py', 'native_oauth/run_agy.py'}
        if not isinstance(files, dict) or not required.issubset(files):
            raise WorkflowGateError('Missing required workflow release files')
        for name, expected in files.items():
            path = (root / name).resolve()
            if (not path.is_relative_to(root) or not isinstance(expected, str)
                    or re.fullmatch('[0-9a-f]{64}', expected) is None or file_hash(path) != expected):
                raise WorkflowGateError('Workflow file differs from the release lock: ' + name)
        return {'workflow': workflow, 'lock_hash': file_hash(root / LOCK), 'root': str(root)}
    except WorkflowGateError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise WorkflowGateError('Cannot verify the local workflow release: ' + str(error)) from error


def git_output(root, *args):
    try:
        result = subprocess.run(['git', *args], cwd=root, capture_output=True,
                                timeout=25, check=True)
        return result.stdout.decode('utf-8').strip()
    except (OSError, subprocess.SubprocessError, UnicodeError) as error:
        raise WorkflowGateError('Git/upstream verification unavailable; preserve the job and verify again before live calls') from error


def verify_checkout(release):
    root = Path(release['root'])
    if Path(git_output(root, 'rev-parse', '--show-toplevel')).resolve() != root:
        raise WorkflowGateError('Launch from the repository root, never an audit/workflow_snapshot copy')
    head = git_output(root, 'rev-parse', 'HEAD')
    remote = git_output(root, 'ls-remote', '--exit-code', REPOSITORY + '.git', 'refs/heads/main').split()
    if len(remote) != 2 or re.fullmatch('[0-9a-f]{40,64}', head) is None or remote[0] != head:
        raise WorkflowGateError('Checkout is not the current canonical GitHub main; sync workflow files safely, then launch again')
    tracked_lock = git_output(root, 'show', 'HEAD:' + LOCK)
    tracked_hash = hashlib.sha256((tracked_lock + '\n').encode('utf-8')).hexdigest()
    if tracked_hash != release['lock_hash']:
        raise WorkflowGateError('Working release lock differs from the verified Git commit')
    return head


def doctor(root=None, job=None):
    release = local_release(root)
    head = verify_checkout(release)
    result = {'status': 'CURRENT', 'workflow_version': release['workflow']['version'],
              'git_commit': head, 'repository': REPOSITORY, 'release_hash': release['lock_hash'],
              'launch_policy': POLICY, 'continuity_policy': release['workflow']['continuity_policy']}
    if job is not None:
        config = Path(job) / 'configuration.json'
        try:frozen = json.loads(config.read_text(encoding='utf-8')) if config.exists() else {}
        except (OSError,ValueError) as error:raise WorkflowGateError('Cannot read the frozen job configuration; preserve it and select a new revision') from error
        if not isinstance(frozen,dict):raise WorkflowGateError('Invalid frozen job configuration; preserve it and select a new revision')
        result['job_compatible_release'] = frozen.get('workflow_release') == release_identity(release)
        result['job_action'] = 'RESUME_IF_CONFIGURATION_MATCHES' if result['job_compatible_release'] else 'LAUNCH_NEW_REVISION_KEEP_APPROVED_PREFIX'
    return result


def release_identity(release):
    return {'version': release['workflow']['version'], 'release_hash': release['lock_hash'], 'launch_policy': POLICY}


def _verify_lease(lease, remote=False):
    release = local_release()
    if release_identity(release) != lease['identity'] or _import_lock_hash != release['lock_hash']:
        raise WorkflowGateError('Workflow changed after process import; finish no new native call, restart the current entry point')
    config = lease['job'] / 'configuration.json'
    try:config_hash=file_hash(config)
    except OSError as error:raise WorkflowGateError('Frozen job configuration is missing or unreadable') from error
    if config_hash != lease['configuration_hash']:
        raise WorkflowGateError('Frozen job configuration changed during the invocation')
    if remote and verify_checkout(release) != lease['commit']:
        raise WorkflowGateError('Canonical release changed; start a new process/job revision before another wave')


@contextmanager
def authorized_invocation(job, configuration):
    job = Path(job).resolve()
    release = local_release()
    if _import_lock_hash != release['lock_hash']:
        raise WorkflowGateError('The Python process loaded an older release; restart via translate.py launch')
    if (configuration.get('workflow_release') != release_identity(release)
            or configuration.get('continuity_policy') != release['workflow']['continuity_policy']
            or configuration.get('review_policy') != release['workflow']['review_policy']
            or configuration.get('validation_policy') != release['workflow']['validation_policy']):
        raise WorkflowGateError('Frozen job uses another release/policy; launch a new revision without changing old evidence')
    if not (os.environ.get('ANTIGRAVITY_ARTIFACT_DIR') or os.environ.get('ANTIGRAVITY_CONVERSATION_ID')):
        raise WorkflowGateError('Bind the current real Antigravity session before live execution')
    commit = verify_checkout(release)
    config_file = job / 'configuration.json'
    frozen_config=json.loads(config_file.read_text(encoding='utf-8'))
    if frozen_config != configuration:
        raise WorkflowGateError('Live configuration differs from its frozen file')
    lease = {'job': job, 'identity': release_identity(release), 'commit': commit,
             'configuration_hash': file_hash(config_file), 'configuration': frozen_config}
    receipt = {'status': 'WORKFLOW_CURRENT', 'workflow_version': configuration['workflow_release']['version'],
               'git_commit': commit, 'release_hash': release['lock_hash'], 'launch_policy': POLICY,
               'continuity_policy': configuration['continuity_policy'], 'job': str(job),
               'book': configuration['book'], 'through_chapter': configuration['through'],
               'pid': os.getpid(), 'started_epoch': time.time(), 'configuration_hash': lease['configuration_hash']}
    with _mutex:
        if str(job) in _leases:
            raise WorkflowGateError('The job already has an active workflow invocation')
        _leases[str(job)] = lease
    try:
        atomic_json(job / 'workflow_startup.json', receipt)
        atomic_json(job / 'workflow_starts' / (uuid.uuid4().hex + '.json'), receipt)
        print(json.dumps(receipt, ensure_ascii=False), flush=True)
        yield receipt
    finally:
        with _mutex:
            _leases.pop(str(job), None)


def check_boundary(job):
    with _mutex:
        lease = _leases.get(str(Path(job).resolve()))
    if lease is None:
        raise WorkflowGateError('No current-workflow invocation; use translate.py launch')
    _verify_lease(lease, remote=True)


def before_native(prompt_file, run_dir, model, workspace, approve_tools, stdin_prompt):
    work = Path(workspace).resolve() if workspace is not None else None
    with _mutex:
        leases = list(_leases.values())
    lease = next((item for item in leases if work is not None and work.is_relative_to(item['job'] / 'native_attempts')), None)
    if lease is None:
        raise WorkflowGateError('Native call has no process-local current-workflow lease; archived/legacy runners cannot launch it')
    _verify_lease(lease)
    if (approve_tools or not stdin_prompt or not Path(prompt_file).resolve().is_relative_to(work)
            or not Path(run_dir).resolve().is_relative_to(work)):
        raise WorkflowGateError('Only owned, tool-free finite JSON native requests are authorized')
    scope = work.relative_to(lease['job'] / 'native_attempts').parts
    config = lease['configuration']
    field = {'translator': 'translator', 'meaning-reviewer': 'reviewer', 'literary-reviewer': 'reviewer2'}.get(scope[0]) if scope else None
    if len(scope) != 2 or field is None or model not in (config[field], config['fallback']):
        raise WorkflowGateError('Native role/workspace/model differs from the current frozen job')
    packet = json.loads((work / 'native_oauth/runs/chapter1/source.json').read_text(encoding='utf-8'))
    policy = (packet.get('continuity_contract') or {}).get('version') if scope[0] == 'translator' else packet.get('continuity_policy')
    if policy != config['continuity_policy']:
        raise WorkflowGateError('Native packet is missing the current mandatory continuity policy')
    if (scope[0]=='translator' and packet.get('validation_policy')!=config['validation_policy']
            or scope[0]!='translator' and packet.get('review_policy')!=config['review_policy']):
        raise WorkflowGateError('Native packet downgraded its mandatory content/review policy')
