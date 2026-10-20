"""Freeze comparable worker contracts; never expose locked reviewer obligations."""
import argparse
import copy
import hashlib
import sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from semantic_gate import read_json,write_json,digest
from native_oauth.batch_contract import build_story_state,make_scene_contract
from native_oauth.batch_source_prepass import extract_ledger


def prepare():
    folder=ROOT/'native_oauth/batch_benchmark'
    locked=read_json(folder/'locked_cases.json')
    if locked['corpus_sha256']!=digest({k:v for k,v in locked.items() if k!='corpus_sha256'}):
        raise ValueError('Evaluation corpus lock changed')
    profiles=read_json(ROOT/'native_oauth/genre_profiles.json')
    real=[]
    for chapter in locked['chapters']:
        path=Path(chapter['source_package_path'])
        package=read_json(path)
        if (hashlib.sha256(path.read_bytes()).hexdigest()!=chapter['source_package_file_sha256']
                or package['package_hash']!=chapter['source_package_hash']
                or package['segments']!=chapter['full_source_segments']):
            raise ValueError('Current source differs from locked evaluation corpus')
        original={s['id']:s['source'] for s in package['segments']}
        if any(original.get(s['id'])!=s['source'] for s in chapter['excerpt_segments']):
            raise ValueError('Selected source span changed under corpus lock')
        real.append(package)
    analyses=[read_json(ROOT/'native_oauth/research/chapter1_ltp_analysis.json')]+[
        read_json(folder/f'analysis/chapter_{p["chapter"]:04d}.analysis.json') for p in real[1:]]
    synthetic=[read_json(folder/f'synthetic_{s["chapter"]}.source.json') for s in locked['synthetic_scenarios']]
    for package,scenario in zip(synthetic,locked['synthetic_scenarios']):
        if [s['source'] for s in package['segments']]!=[s['source'] for s in scenario['excerpt_segments']]:
            raise ValueError('Synthetic source changed under corpus lock')
    synthetic_analyses=[read_json(folder/f'analysis/chapter_{p["chapter"]:04d}.analysis.json') for p in synthetic]
    groups=[]
    for packages,parsed,genre in ((real,analyses,'hybrid_cyberpunk_tu_tien'),(synthetic,synthetic_analyses,'hien_dai')):
        ledger=extract_ledger(packages,parsed)
        glossary={k:v for p in packages for k,v in p.get('glossary',{}).items()}
        style={'version':profiles['version'],'genre':genre,'common':profiles['common'],
               'rules':profiles['profiles'][genre],'certification':profiles['certification']}
        state=build_story_state(packages,ledger,glossary,style)
        groups.append((packages,parsed,state))
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    contracts=folder/f'contracts_{stamp}';contracts.mkdir()
    jobs=[];conditions=[]
    # Same owned Chinese, parser candidates, glossary and style in every cell.
    # Variable: readonly source neighbors and retrieved original-source memory.
    for model in ('gemini-3.8-flash-low','gemini-3.8-flash-medium'):
        for route in ('isolated','shared_source'):
            condition=model.rsplit('-',1)[1]+'-'+route
            for group_index,(packages,parsed,state) in enumerate(groups):
                spans=([c['excerpt_segments'] for c in locked['chapters'] if c['split']=='heldout']
                       if group_index==0 else [synthetic[-1]['segments']])
                parse_index={s['id']:s for a in parsed for s in a['segments']}
                for span in spans:
                    identifier=span[0]['id'];job_id=condition+'-'+identifier
                    contract=make_scene_contract(state,packages,[s['id'] for s in span],overlap=3,
                               max_capsule_chars=6500,max_capsule_entries=15,job_id=job_id)
                    contract['parser_hints']=[{'id':s['id'],'ner':parse_index[s['id']]['ner'],
                           'srl':parse_index[s['id']]['srl'],'status':'predictions only'} for s in span]
                    if route=='isolated':
                        contract['neighbor_segments']=[]
                        contract['context_capsule']['ledger']=[]
                        contract['context_capsule']['omitted_optional_entries']=0
                    contract['experiment_condition']=condition
                    contract['contract_hash']=digest({k:v for k,v in contract.items() if k!='contract_hash'})
                    path=contracts/(job_id+'.json');write_json(path,contract)
                    jobs.append({'contract':str(path),'model':model})
                    conditions.append({'condition':condition,'job_id':job_id,'owned_ids':[s['id'] for s in span],
                           'source_context_quote_ids':[r['source_id'] for e in contract['context_capsule']['ledger'] for r in e['references']]})
            write_json(contracts/(condition+'.state.json'),groups[0][2])
    manifest={'schema':'batch-benchmark-1','corpus_hash':locked['corpus_sha256'],
              'policy_version':'source-quote-retrieval-v1','jobs':jobs,'max_concurrency':2,'timeout':240,
              'max_reported_tokens':600000,'workspace':str(ROOT/'native_oauth/batch_jobs'/stamp),
              'result_path':str(folder/f'results_{stamp}.json')}
    write_json(contracts/'manifest.json',manifest)
    write_json(contracts/'conditions.json',{'conditions':conditions,'synthetic_scope':'Only final4 syntheticparas generated; prior8 are readonly source memory, not translated outputs',
                                          'policy':'No gold obligations or referenceVietnamese delivered to workers'})
    print(str(contracts/'manifest.json'))
    return contracts/'manifest.json'


if __name__=='__main__':
    prepare()
