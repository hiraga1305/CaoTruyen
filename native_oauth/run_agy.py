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
    with (run_dir / 'events.jsonl').open('w', encoding='utf-8') as output, (run_dir / 'diagnostics.txt').open('w', encoding='utf-8') as errors:
        process = subprocess.Popen(argv, cwd=Path(workspace).resolve() if workspace else ROOT, env=env,
                                   stdin=subprocess.DEVNULL, stdout=output, stderr=errors,
                                   creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline = time.time() + timeout + 30
            code = None
            while time.time() < deadline:
                poll = process.poll()
                if poll is not None:
                    code = poll
                    break
                time.sleep(0.5)
                # Check if result event was written
                try:
                    ev_txt = (run_dir / 'events.jsonl').read_text(encoding='utf-8')
                    if '"event":"result"' in ev_txt:
                        time.sleep(0.5)
                        process.terminate()
                        code = 0
                        break
                except Exception:
                    pass
            if code is None:
                process.terminate()
                process.wait(timeout=10)
                code = -1
        except Exception:
            process.terminate()
            process.wait(timeout=10)
            code = -1
    events = []
    for line in (run_dir / 'events.jsonl').read_text(encoding='utf-8').splitlines():
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    result = next((e.get('result', e) for e in reversed(events) if e.get('event') == 'result'), {})
    status = result.get('status', 'NO_RESULT')
    if result.get('denied_actions'):
        status = 'BLOCKED_PERMISSION'
    if code != 0 and status == 'SUCCESS':
        status = 'ERROR'
    manifest = {'authentication': 'cached_account; GEMINI_API_KEY unset',
                'requested_model': model, 'agent': agent, 'exit_code': code,
                'workspace': str(Path(workspace).resolve() if workspace else ROOT),
                'duration_seconds': round(time.time() - start, 2),
                'status': status,
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
