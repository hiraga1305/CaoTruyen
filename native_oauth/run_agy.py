"""Run bounded native agy sessions using account credentials, never API keys."""
import argparse
import json
import os
import subprocess
import time
import shutil
import uuid
import re
import hashlib
from contextlib import ExitStack
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def find_cli():
    import os, shutil
    candidates = [
        os.environ.get('AGY_BIN'),
        str(Path.home() / 'chatgpt-antigravity-bridge/bin/agy.exe'),
        str(Path.home() / 'AppData/Local/agy/bin/agy.exe'),
        shutil.which('agy.exe'),
        shutil.which('agy'),
    ]
    for c in candidates:
        if c and Path(c).is_file():
            return Path(c)
    return Path.home() / 'AppData/Local/agy/bin/agy.exe'

DEFAULT_CLI = find_cli()


def bind_native_session(events_path):
    """Bind live artifacts to the observed CLI conversation, never a guessed folder."""
    from native_oauth.session_monitor import SessionMonitor
    monitor = SessionMonitor._instance
    if monitor is None or os.environ.get('ANTIGRAVITY_ARTIFACT_DIR'):
        return False
    try:
        for line in Path(events_path).read_text(encoding='utf-8').splitlines():
            event = json.loads(line)
            session = event.get('conversation_id')
            if event.get('event') == 'init' and isinstance(session, str) and re.fullmatch(r'[A-Za-z0-9_-]+', session):
                monitor.artifact_dir = Path.home()/'.gemini/antigravity/brain'/session
                monitor.native_artifact_dirs.add(monitor.artifact_dir)
                if monitor.artifact_dir not in monitor.native_session_order:
                    monitor.native_session_order.append(monitor.artifact_dir)
                while len(monitor.native_session_order)>6:
                    monitor.native_artifact_dirs.discard(monitor.native_session_order.pop(0))
                monitor.sync_session_artifacts()
                return True
    except (OSError, ValueError):
        pass
    return False


class IncompleteNativeOutput(ValueError):
    """A bounded native call ended while generation was still in progress."""


def completed_json_proof(events, diagnostics):
    """Only an actual terminal, tool-free JSON turn may outlive its CLI client."""
    if 'returning partial output' in diagnostics.lower() or 'print timeout' in diagnostics.lower():
        return None
    inits=[e for e in events if e.get('event')=='init']
    ends=[e for e in events if e.get('event')=='result']
    if len(inits)!=1 or len(ends)!=1 or not events or events[-1].get('event')!='result':
        return None
    init,result=inits[0],ends[0].get('result',{})
    session=init.get('conversation_id');model=init.get('init',{}).get('model')
    responses=[e['step_update'] for e in events if e.get('event')=='step_update'
               and e.get('step_update',{}).get('step_type')=='agent_response']
    if (not session or not model or result.get('conversation_id')!=session
            or result.get('status')!='SUCCESS' or result.get('denied_actions')
            or str(result.get('finish_reason','')).lower() in ('length','max_tokens','safety','content_filter')
            or not responses or responses[-1].get('state')!='DONE'
            or any(e.get('step_update',{}).get('step_type')=='tool' for e in events)):
        return None
    response=result.get('response')
    try:
        payload=json.loads(response)
    except (ValueError,TypeError):
        return None
    if not isinstance(payload,dict):
        return None
    encoded=json.dumps(events,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode('utf-8')
    return {'events_sha256':hashlib.sha256(encoded).hexdigest(),
            'response_sha256':hashlib.sha256(response.encode('utf-8')).hexdigest(),
            'conversation_id':session,'model':model}


def verified_cleanup(events, diagnostics, cleanup):
    proof=completed_json_proof(events,diagnostics)
    return (proof is not None and isinstance(cleanup,dict)
            and cleanup.get('action')=='terminate_after_verified_done'
            and cleanup.get('transport')=='finite_stdin_json_no_tools'
            and isinstance(cleanup.get('input_sha256'),str) and re.fullmatch(r'[0-9a-f]{64}',cleanup['input_sha256']) is not None
            and isinstance(cleanup.get('grace_seconds'),(int,float)) and cleanup['grace_seconds']>=10
            and all(cleanup.get(key)==value for key,value in proof.items()))


def classify_completion(events, diagnostics, exit_code, timed_out=False, completed_cleanup=None):
    """CLI SUCCESS may describe partial --print-timeout output, not completion."""
    result = next((e.get('result', e) for e in reversed(events) if e.get('event') == 'result'), {})
    init = next((e.get('init', {}) for e in events if e.get('event') == 'init'), {})
    partial = 'returning partial output' in diagnostics.lower() or 'print timeout' in diagnostics.lower()
    responses = [e['step_update'] for e in events if e.get('event') == 'step_update'
                 and e.get('step_update', {}).get('step_type') == 'agent_response']
    unfinished = bool(responses and responses[-1].get('state') == 'ACTIVE')
    status = result.get('status', 'NO_RESULT')
    if timed_out:
        status = 'TIMEOUT'
    elif partial:
        status = 'PARTIAL_TIMEOUT'
    elif result.get('denied_actions'):
        status = 'BLOCKED_PERMISSION'
    elif exit_code != 0:
        status = ('COMPLETED_CLI_CLEANUP' if verified_cleanup(events,diagnostics,completed_cleanup) else 'ERROR')
    elif status == 'SUCCESS' and unfinished:
        status = 'INCOMPLETE_STEP'
    elif status == 'SUCCESS' and not result.get('response', '').strip():
        status = 'EMPTY_RESPONSE'
    return {'status': status, 'partial_output': partial or timed_out or unfinished,
            'actual_model': init.get('model'), 'result': result}


def require_complete_runtime(runtime, expected_model):
    if not isinstance(runtime, dict) or not isinstance(runtime.get('result'), dict):
        raise ValueError('Invalid native runtime')
    if type(runtime.get('exit_code')) is not int:
        raise ValueError('Actual native process exit code is required')
    status = runtime.get('status')
    if status not in ('SUCCESS', 'COMPLETED_CLI_CLEANUP', 'TIMEOUT', 'PARTIAL_TIMEOUT', 'INCOMPLETE_STEP'):
        raise ValueError(f'Native execution failed: {status}')
    if status in ('TIMEOUT', 'PARTIAL_TIMEOUT', 'INCOMPLETE_STEP') or runtime.get('partial_output'):
        raise IncompleteNativeOutput(f'Native output incomplete: {status}; partial text retained as evidence only')
    cleanup=runtime.get('completed_cleanup',{})
    cleanup_record=(status=='COMPLETED_CLI_CLEANUP' and isinstance(cleanup,dict)
                    and cleanup.get('action')=='terminate_after_verified_done'
                    and cleanup.get('transport')=='finite_stdin_json_no_tools'
                    and isinstance(cleanup.get('grace_seconds'),(int,float)) and cleanup['grace_seconds']>=10
                    and cleanup.get('model')==expected_model
                    and cleanup.get('conversation_id')==runtime['result'].get('conversation_id')
                    and all(isinstance(cleanup.get(k),str) and re.fullmatch(r'[0-9a-f]{64}',cleanup[k])
                            for k in ('events_sha256','response_sha256','input_sha256')))
    if runtime.get('exit_code') != 0 and not cleanup_record:
        raise ValueError(f'Native execution failed: {status}')
    if status=='COMPLETED_CLI_CLEANUP' and not cleanup_record:
        raise ValueError('Invalid completed CLI cleanup record')
    if runtime.get('actual_model') != expected_model:
        raise ValueError('Native runtime model missing or different from requested model')
    result = runtime['result']
    if (result.get('status', 'SUCCESS') != 'SUCCESS' or result.get('denied_actions')
            or str(result.get('finish_reason','')).lower() in ('length','max_tokens','safety','content_filter')):
        raise ValueError('Native response blocked or truncated')
    response = runtime.get('result', {}).get('response', '')
    if not isinstance(response, str) or not response.strip():
        raise ValueError('Native response is empty')
    return response


def run(prompt_file, run_dir, model='gemini-3.8-flash-high', agent=None, timeout=600, workspace=None, approve_tools=False,
        stdin_prompt=False):
    run_dir = Path(run_dir).resolve()
    if (run_dir/'events.jsonl').exists():
        history=run_dir.with_name(run_dir.name+'.history.'+uuid.uuid4().hex[:8])
        history.mkdir(parents=True,exist_ok=False)
        for file in run_dir.iterdir():
            if file.is_file():
                shutil.copy2(file,history/file.name)
    run_dir.mkdir(parents=True, exist_ok=True)
    prompt = Path(prompt_file).read_text(encoding='utf-8')
    env = os.environ.copy()
    for name in ('GEMINI_API_KEY','GOOGLE_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY','OPENROUTER_API_KEY'):
        env.pop(name, None)
    env.pop('GOOGLE_GEMINI_BASE_URL', None)
    argv = [str(DEFAULT_CLI), '-p', prompt, '--model', model, '--mode', 'accept-edits',
            '--sandbox', '--output-format', 'stream-json', '--print-timeout', f'{timeout}s']
    if stdin_prompt:
        argv = [str(DEFAULT_CLI), '--input-format', 'stream-json', '--output-format', 'stream-json',
                '--disable-slash-commands', '--model', model, '--print-timeout', f'{timeout}s',
                '--log-file',os.devnull]
    if agent:
        argv += ['--agent', agent]
    if approve_tools:
        if workspace is None or not Path(workspace).resolve().is_relative_to(ROOT / 'native_oauth'):
            raise ValueError('Tool approval only supported for isolated native_oauth workspaces')
        argv += ['--dangerously-skip-permissions']
    start = time.time()
    timed_out = False
    session_bound = False
    completed_cleanup=None
    completed_at=None
    completion_proof=None
    with ExitStack() as streams:
        output=streams.enter_context((run_dir/'events.jsonl').open('w',encoding='utf-8'))
        errors=streams.enter_context((run_dir/'diagnostics.txt').open('w',encoding='utf-8'))
        input_stream=subprocess.DEVNULL
        if stdin_prompt:
            # A finite regular stdin file gives the CLI an unambiguous EOF on
            # Windows; no pipe writer can remain inherited by another worker.
            input_file=run_dir/'input.jsonl'
            input_file.write_text(json.dumps({'event':'user','message':{'content':prompt}},ensure_ascii=False)+'\n',encoding='utf-8')
            input_stream=streams.enter_context(input_file.open('rb'))
        process = subprocess.Popen(argv, cwd=Path(workspace).resolve() if workspace else ROOT, env=env,
                                   stdin=input_stream, stdout=output, stderr=errors,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            deadline = time.time() + timeout + 30
            code = None
            timed_out = False
            while time.time() < deadline:
                if not session_bound:
                    session_bound = bind_native_session(run_dir/'events.jsonl')
                poll = process.poll()
                if poll is not None:
                    code = poll
                    break
                if stdin_prompt and agent is None and not approve_tools:
                    try:
                        snapshot=[json.loads(line) for line in (run_dir/'events.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
                        proof=completed_json_proof(snapshot,(run_dir/'diagnostics.txt').read_text(encoding='utf-8'))
                    except (OSError,ValueError):
                        proof=None
                    if proof is not None and proof==completion_proof:
                        if time.time()-completed_at>=10:
                            completed_cleanup={**proof,'action':'terminate_after_verified_done',
                                               'grace_seconds':round(time.time()-completed_at,2),
                                               'transport':'finite_stdin_json_no_tools',
                                               'input_sha256':hashlib.sha256(input_file.read_bytes()).hexdigest()}
                            process.terminate()
                            code=process.wait(timeout=10)
                            break
                    else:
                        completion_proof=proof
                        completed_at=time.time() if proof is not None else None
                time.sleep(0.5)
                # Wait for process exit. A substring in a partially flushed JSON
                # event is not a completion signal and must not force exit code 0.
            if code is None:
                timed_out = True
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)
                code = process.returncode
        except Exception:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            code = process.returncode
    events = []
    for line in (run_dir / 'events.jsonl').read_text(encoding='utf-8').splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    completion = classify_completion(events, (run_dir / 'diagnostics.txt').read_text(encoding='utf-8'), code, timed_out,
                                     completed_cleanup=completed_cleanup)
    result = completion['result']
    manifest = {'authentication': 'cached_account; GEMINI_API_KEY unset',
                'requested_model': model, 'agent': agent, 'exit_code': code,
                'workspace': str(Path(workspace).resolve() if workspace else ROOT),
                'duration_seconds': round(time.time() - start, 2),
                'status': completion['status'], 'partial_output': completion['partial_output'],
                'actual_model': completion['actual_model'],
                'conversation_id': result.get('conversation_id'), 'usage': result.get('usage'),
                'result': result, 'event_count': len(events)}
    if completed_cleanup is not None:
        manifest['completed_cleanup']=completed_cleanup
    (run_dir / 'runtime.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({k:v for k,v in manifest.items() if k != 'result'}, ensure_ascii=False), flush=True)
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--prompt-file', required=True)
    parser.add_argument('--run-dir', required=True)
    parser.add_argument('--model', default='gemini-3.8-flash-high')
    parser.add_argument('--agent')
    parser.add_argument('--timeout', type=int, default=600)
    parser.add_argument('--workspace')
    parser.add_argument('--approve-workspace-tools', action='store_true')
    args = parser.parse_args()
    run(args.prompt_file, args.run_dir, args.model, args.agent, args.timeout, args.workspace, args.approve_workspace_tools)
