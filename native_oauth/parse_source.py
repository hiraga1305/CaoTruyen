"""Run actual LTP six-task neural analysis, no text reordering or fake AST."""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from semantic_gate import read_json, write_json, validate_package, digest


def load_parser():
    import torch
    import transformers
    import ltp
    from importlib.metadata import version
    from transformers import AutoTokenizer
    from safetensors.torch import load_file
    from ltp.nerual import LTP
    torch.set_num_threads(4)
    folder = ROOT / 'native_oauth/models/LTP-small'
    manifest = read_json(folder/'verified_files.json')
    for row in manifest['files']:
        file = folder / row['file']
        with file.open('rb') as handle:
            if hashlib.file_digest(handle, 'sha256').hexdigest() != row['sha256']:
                raise ValueError('Parser file changed: ' + row['file'])
    parser = LTP(config=read_json(folder/'config.json'))
    parser.tokenizer = AutoTokenizer.from_pretrained(str(folder), config=parser.model.backbone.config,
                                                    use_fast=True, local_files_only=True, trust_remote_code=False)
    weights = load_file(str(folder/'model.safetensors'))
    # Transformers 5 no longer persists this deterministic positional buffer.
    # Validate before omitting it; every learned weight still loads strictly.
    key = 'backbone.embeddings.position_ids'
    compatibility = []
    if key in weights and key not in parser.model.state_dict():
        positions = weights[key]
        if positions.ndim != 2 or positions.shape[0] != 1 or not torch.equal(positions[0], torch.arange(positions.shape[1])):
            raise ValueError('Unexpected positional buffer')
        del weights[key]
        compatibility.append('validated deterministic position_ids buffer omitted because runtime does not persist it')
    parser.load_state_dict(weights, strict=True)
    parser.eval()
    return parser, {'engine':'HIT-SCIR LTP', 'ltp_module_version':getattr(ltp,'__version__',None),
                    'ltp_distribution_version':version('ltp'), 'model':'LTP/small',
                    'revision':manifest['revision'], 'torch':torch.__version__,
                    'transformers':transformers.__version__, 'weights_format':'safetensors',
                    'compatibility':compatibility}


def main():
    args = argparse.ArgumentParser(description=__doc__)
    args.add_argument('--package', required=True)
    args.add_argument('--out', required=True)
    opts = args.parse_args()
    package = read_json(opts.package)
    validate_package(package)
    parser, provenance = load_parser()
    records = []
    start = time.time()
    for i in range(0, len(package['segments']), 8):
        segments = package['segments'][i:i+8]
        texts = [s['source'] for s in segments]
        if any(len(parser.tokenizer.encode(t, truncation=False)) > 512 for t in texts):
            raise ValueError('Source exceeds parser window; split with auditable offsets, never truncate')
        output = parser.pipeline(texts, tasks=['cws','pos','ner','srl','dep','sdp'])
        for j, segment in enumerate(segments):
            words, pos, dep = output.cws[j], output.pos[j], output.dep[j]
            if len(words) != len(pos) or len(words) != len(dep['head']):
                raise ValueError('Parser token/head alignment failed')
            nodes = [{'id':k+1,'word':word,'pos':pos[k],'head':dep['head'][k],'relation':dep['label'][k]}
                     for k,word in enumerate(words)]
            if any(not 0 <= n['head'] <= len(nodes) for n in nodes):
                raise ValueError('Invalid dependency head')
            records.append({'id':segment['id'],'source_hash':digest(segment['source']),
                            'cws':words,'pos':pos,'ner':output.ner[j],'srl':output.srl[j],
                            'dep':nodes,'sdp':output.sdp[j],
                            'derived_tree':{'roots':[n['id'] for n in nodes if n['head']==0],
                                            'edges':[[n['head'],n['id'],n['relation']] for n in nodes if n['head']]}})
        print('Parsed', min(i+8,len(package['segments'])), '/',len(package['segments']), flush=True)
    write_json(opts.out, {'source_package_hash':package['package_hash'],'provenance':provenance,
                         'tasks':['CWS','POS','NER','SRL','DEP','SDP'],
                         'limits':'Predicted sentence analysis, not semantic truth; derived_tree is DEP-derived, not a native constituency parse',
                         'elapsed_seconds':round(time.time()-start,2),'segments':records})


if __name__ == '__main__':
    main()
