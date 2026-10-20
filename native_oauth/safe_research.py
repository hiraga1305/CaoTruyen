"""Read primary repo metadata and docs; downloaded content is never executed."""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'native_oauth/research'
REPOS = ['chi-vi/hanlp_mt', 'chi-vi/ltp-dep-to-con', 'chi-vi/ltp-onnx', 'hankcs/HanLP', 'HIT-SCIR/ltp']


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'CaoTruyen-research/1'})
    with urllib.request.urlopen(req, timeout=20) as response:
        data = response.read(1_500_000)
    return data


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    records = []
    for name in REPOS:
        row = {'repo': name, 'url': 'https://github.com/' + name}
        try:
            meta = json.loads(fetch('https://api.github.com/repos/' + name))
            branch = meta['default_branch']
            commit = json.loads(fetch('https://api.github.com/repos/' + name + '/commits/' + branch))['sha']
            data = fetch('https://raw.githubusercontent.com/' + name + '/' + commit + '/README.md')
            target = OUT / (name.replace('/', '__') + '.README.md')
            target.write_bytes(data)
            row.update({'status': 'VERIFIED_ONLINE', 'commit': commit, 'default_branch': branch,
                        'license': (meta.get('license') or {}).get('spdx_id'),
                        'readme_sha256': hashlib.sha256(data).hexdigest(), 'snapshot': str(target)})
        except Exception as error:
            row.update({'status': 'BLOCKED', 'error_type': type(error).__name__})
        records.append(row)
        print(name, row['status'], flush=True)
    (OUT / 'repositories.json').write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding='utf-8')


if __name__ == '__main__':
    main()
