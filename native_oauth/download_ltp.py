"""Fetch pinned official LTP/small safetensors and tokenizer, verify sizes/hash."""
import hashlib
import json
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / 'native_oauth/models/LTP-small'


def main():
    meta = json.loads((ROOT/'native_oauth/research/ltp_model_manifest.json').read_text(encoding='utf-8'))
    MODEL.mkdir(parents=True, exist_ok=True)
    files = ['config.json', 'model.safetensors', 'tokenizer.json', 'tokenizer_config.json',
             'special_tokens_map.json', 'added_tokens.json', 'vocab.txt']
    records = []
    for filename in files:
        info = next(f for f in meta['siblings'] if f['rfilename'] == filename)
        expected_hash = (info.get('lfs') or {}).get('sha256')
        expected_size = info.get('size')
        target = MODEL / filename
        if not target.exists() or target.stat().st_size != expected_size:
            url = 'https://huggingface.co/LTP/small/resolve/' + meta['sha'] + '/' + filename
            temporary = target.with_suffix(target.suffix + '.download')
            with urllib.request.urlopen(url, timeout=40) as response, temporary.open('wb') as output:
                while chunk := response.read(1024 * 1024):
                    output.write(chunk)
                    if output.tell() > 200_000_000:
                        raise ValueError('Model download size limit exceeded')
            temporary.replace(target)
        sha = hashlib.file_digest(target.open('rb'), 'sha256').hexdigest()
        if target.stat().st_size != expected_size or (expected_hash and sha != expected_hash):
            raise ValueError('Model size/hash mismatch: ' + filename)
        records.append({'file': filename, 'size': expected_size, 'sha256': sha})
        print(filename, expected_size, 'VERIFIED', flush=True)
    (MODEL/'verified_files.json').write_text(json.dumps({'repo':'LTP/small','revision':meta['sha'],'files':records},indent=2),encoding='utf-8')


if __name__ == '__main__':
    main()
