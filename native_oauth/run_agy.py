"""Run bounded native agy sessions using account credentials, never API keys."""
import argparse
import json
import os
import subprocess
import time
import shutil
import uuid
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


class IncompleteNativeOutput(ValueError):
    """A bounded native call ended while generation was still in progress."""


def classify_completion(events, diagnostics, exit_code, timed_out=False):
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
        status = 'ERROR'
    elif status == 'SUCCESS' and unfinished:
        status = 'INCOMPLETE_STEP'
    elif status == 'SUCCESS' and not result.get('response', '').strip():
        status = 'EMPTY_RESPONSE'
    return {'status': status, 'partial_output': partial or timed_out or unfinished,
            'actual_model': init.get('model'), 'result': result}


def require_complete_runtime(runtime, expected_model):
    if not isinstance(runtime, dict) or not isinstance(runtime.get('result'), dict):
        raise ValueError('Invalid native runtime')
    status = runtime.get('status')
    if status not in ('SUCCESS', 'TIMEOUT', 'PARTIAL_TIMEOUT', 'INCOMPLETE_STEP'):
        raise ValueError(f'Native execution failed: {status}')
    if status in ('TIMEOUT', 'PARTIAL_TIMEOUT', 'INCOMPLETE_STEP') or runtime.get('partial_output'):
        raise IncompleteNativeOutput(f'Native output incomplete: {status}; partial text retained as evidence only')
    if runtime.get('exit_code') != 0:
        raise ValueError(f'Native execution failed: {status}')
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


def run(prompt_file, run_dir, model='gemini-3.8-flash-high', agent=None, timeout=600, workspace=None, approve_tools=False):
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
    env.pop('GEMINI_API_KEY', None)
    env.pop('GOOGLE_GEMINI_BASE_URL', None)
    argv = [str(DEFAULT_CLI), '-p', prompt, '--model', model, '--mode', 'accept-edits',
            '--sandbox', '--output-format', 'stream-json', '--print-timeout', f'{timeout}s']
    if agent:
        argv += ['--agent', agent]
    if approve_tools:
        if workspace is None or not Path(workspace).resolve().is_relative_to(ROOT / 'native_oauth'):
            raise ValueError('Tool approval only supported for isolated native_oauth workspaces')
        argv += ['--dangerously-skip-permissions']
    start = time.time()
    timed_out = False
    with (run_dir / 'events.jsonl').open('w', encoding='utf-8') as output, (run_dir / 'diagnostics.txt').open('w', encoding='utf-8') as errors:
        process = subprocess.Popen(argv, cwd=Path(workspace).resolve() if workspace else ROOT, env=env,
                                   stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                                   creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        try:
            deadline = time.time() + timeout + 30
            code = None
            timed_out = False
            while time.time() < deadline:
                poll = process.poll()
                if poll is not None:
                    code = poll
                    break
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
                code = -1
        except Exception:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)
            code = -1
    events = []
    for line in (run_dir / 'events.jsonl').read_text(encoding='utf-8').splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    completion = classify_completion(events, (run_dir / 'diagnostics.txt').read_text(encoding='utf-8'), code, timed_out)
    result = completion['result']
    manifest = {'authentication': 'cached_account; GEMINI_API_KEY unset',
                'requested_model': model, 'agent': agent, 'exit_code': code,
                'workspace': str(Path(workspace).resolve() if workspace else ROOT),
                'duration_seconds': round(time.time() - start, 2),
                'status': completion['status'], 'partial_output': completion['partial_output'],
                'actual_model': completion['actual_model'],
                'conversation_id': result.get('conversation_id'), 'usage': result.get('usage'),
                'result': result, 'event_count': len(events)}
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
