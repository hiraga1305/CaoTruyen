"""Developer-only: rebuild the portable code lock, never launch models."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(root=ROOT):
    tracked = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode('utf-8').split('\0')
    explicit = {'workflow.json', 'translate.py', 'native_oauth/workflow_guard.py', 'tools/update_workflow_release.py',
                'AGENTS.md', 'WORKFLOW.md', 'docs/CONTINUITY_CONVENTIONS.md', 'docs/WORKFLOW_LAUNCH.md',
                'docs/prompts/continue-translation.md', '.agents/rules/standard_workflow.md'}
    files = set(explicit)
    for name in tracked:
        path = Path(name)
        if ((path.suffix == '.py' and (path.parent == Path('.') or path.parent == Path('native_oauth')))
                or name in ('native_oauth/semantic_profiles.json', 'native_oauth/genre_profiles.json')
                or name.startswith('.agents/') and path.suffix == '.md'):
            files.add(path.as_posix())
    workflow = json.loads((root / 'workflow.json').read_text(encoding='utf-8'))
    result = {'schema': 'caotruyen-release-1', 'workflow_id': workflow['id'], 'version': workflow['version'],
              'files': {name: hashlib.sha256((root / name).read_bytes().replace(b'\r\n', b'\n')).hexdigest() for name in sorted(files)}}
    (root / 'workflow_release.json').write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    return len(files)


if __name__ == '__main__':
    print('Workflow release files:', build())
