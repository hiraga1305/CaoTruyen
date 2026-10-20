"""Hide model/route labels for independent GPT evaluation of untouched drafts."""
import argparse
import random
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from semantic_gate import read_json,write_json,digest


def main(manifest_path):
    manifest=read_json(manifest_path)
    results=read_json(manifest['result_path'])
    if results['status']!='DRAFTS_COMPLETE_UNREVIEWED':raise ValueError('All cells must finish before blind comparison')
    conditions=sorted({read_json(s['contract'])['experiment_condition'] for s in manifest['jobs']})
    random.Random(manifest['corpus_hash']).shuffle(conditions)
    mapping={condition:'V1-'+chr(65+i) for i,condition in enumerate(conditions)}
    groups={label:[] for label in mapping.values()}
    for spec,result in zip(manifest['jobs'],results['results']):
        contract=read_json(spec['contract']);candidate=read_json(result['output'])
        groups[mapping[contract['experiment_condition']]].extend([
            {'id':s['id'],'source':s['source'],'target':t['text']} for s,t in zip(contract['owned_segments'],candidate['segments'])])
    folder=Path(manifest_path).parent.parent
    write_json(folder/'blind_mapping.private.json',{'conditions':mapping,'result_path':manifest['result_path'],
                                               'candidate_hashes':[r['candidate_hash'] for r in results['results']]})
    write_json(folder/'blinded_v1.json',{'corpus_hash':manifest['corpus_hash'],'groups':groups,
             'notes':'Untouched native candidates; no model/route labels. Synthetic c0103 ids correspond to locked s103 ids; prior8 syntheticChineseparas readonly only.',
             'source_paths':[c['source_package_path'] for c in read_json(folder/'locked_cases.json')['chapters']]+
                            [str(folder/f'synthetic_{i}.source.json') for i in (101,102,103)]})
    print(folder/'blinded_v1.json')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--manifest',required=True)
    main(parser.parse_args().manifest)
