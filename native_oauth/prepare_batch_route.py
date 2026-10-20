"""Reusable Gemini low/medium batch draft route with source-only SQLite memory."""
import argparse
import copy
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from semantic_gate import read_json,write_json,digest
from native_oauth.batch_contract import build_story_state,plan_parallel_block
from native_oauth.batch_source_prepass import extract_ledger,RELATION_CUES
from native_oauth.batch_policy import apply_prevention,choose_model,bind_approved_style_seed
from native_oauth.story_store import StoryStore


def store_projection(package):
    result={k:copy.deepcopy(package[k]) for k in ('chapter','title','source_ref','glossary') if k in package}
    result['version']='source-store-projection-1'
    result['segments']=[{'id':s['id'],'source':s['source']} for s in package['segments']]
    result['upstream_source_package_hash']=package['package_hash']
    result['package_hash']=digest({k:v for k,v in result.items() if k!='package_hash'})
    return result


def index_sources(store,packages,analyses):
    entries=extract_ledger(packages,analyses)
    for package in packages:
        ids={s['id'] for s in package['segments']}
        store.index_package(store_projection(package),ledger_entries=[e for e in entries if e['references'][0]['source_id'] in ids],
                            expected_revision=store.revision)
    return entries


def bind_store_memory(contract,store,glossary):
    result=copy.deepcopy(contract)
    rows=result['owned_segments']+result['neighbor_segments']
    source='\n'.join(s['source'] for s in rows)
    keys=sorted(set([k for k in glossary if k in source]+[k for k in RELATION_CUES if k in source]))
    memory=store.retrieve_capsule([s['id'] for s in result['owned_segments']],keys,revision=store.revision,
                                pronoun_recent=3,max_entries=15,max_chars=6500)
    result['context_capsule']['ledger']=[{'keys':[e['retrieved_by']],
                  'references':[{'source_id':e['source_id'],'source_quote':e['source_quote']}]} for e in memory['evidence']]
    result['context_capsule']['omitted_optional_entries']=memory['omitted_evidence_candidates']
    result['story_store_snapshot']={k:memory[k] for k in ('revision','revision_hash','capsule_hash')}
    return apply_prevention(result)


def prepare(sources,analyses,genre,book_id,store_path,out,scene_end_ids=None,through_chapter=0,model='auto',style_evidence=None,style_ids=None):
    if model not in ('auto','gemini-3.8-flash-low','gemini-3.8-flash-medium'):
        raise ValueError('Batch route pins Gemini3.8 Flash low/medium')
    packages=[read_json(p) for p in sources];parsed=[read_json(p) for p in analyses]
    profiles=read_json(ROOT/'native_oauth/genre_profiles.json')
    style={'version':profiles['version'],'genre':genre,'common':profiles['common'],
           'rules':profiles['profiles'][genre],'certification':profiles['certification']}
    with StoryStore(store_path,book_id) as store:
        entries=index_sources(store,packages,parsed)
        glossary={k:v for p in packages for k,v in p.get('glossary',{}).items()}
        source_pool=([store.get_source_package(through_chapter)] if through_chapter else [])+packages
        state=build_story_state(source_pool,entries,glossary,style,version=store.revision+1,through_chapter=through_chapter)
        state['scope']='DRAFT source prepass; predecessor index is not approved translation evidence'
        state['state_hash']=digest({k:v for k,v in state.items() if k!='state_hash'})
        plan=plan_parallel_block(state,packages,scene_end_ids=scene_end_ids,max_owned_paragraphs=32,
                                 overlap=3,max_capsule_chars=6500,max_capsule_entries=15)
        folder=Path(out).resolve();folder.mkdir(parents=True,exist_ok=False)
        jobs=[]
        parse_index={s['id']:s for a in parsed for s in a['segments']}
        for contract in plan['jobs']:
            contract['parser_hints']=[{'id':s['id'],'ner':parse_index[s['id']]['ner'],
                         'srl':parse_index[s['id']]['srl'],
                         'idiom_candidates':parse_index[s['id']].get('idiom_candidates',[])} for s in contract['owned_segments']]
            contract=bind_store_memory(contract,store,glossary)
            if style_evidence:
                contract=bind_approved_style_seed(contract,read_json(style_evidence),style_ids or [])
            routing=choose_model(contract)
            path=folder/(contract['job_id']+'.json');write_json(path,contract)
            jobs.append({'contract':str(path),'model':routing['model'] if model=='auto' else model,'routing':routing})
        # Binding store/retry policy changes job hashes: reseal the plan.
        plan['jobs']=[read_json(j['contract']) for j in jobs]
        plan['plan_hash']=digest({k:v for k,v in plan.items() if k!='plan_hash'})
        write_json(folder/'state.json',state);write_json(folder/'plan.json',plan)
        write_json(folder/'manifest.json',{'jobs':jobs,'max_concurrency':2,'timeout':240,'max_reported_tokens':600000,
            'workspace':str(folder/'workers'),'result_path':str(folder/'results.json'),
            'policy_version':'source-contract-v2','mode':'DRAFTS_ONLY; no unverified chapter publication',
            'source_store_snapshot':store.snapshot(),
            'notes':'Use explicit scene_end_ids for coupled dialogue. Fixed32 fallback is experimental segmentation. Throughchapter is coordinator barrier, not self-certified PASS.'})
    return folder/'manifest.json'


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',action='append',required=True)
    parser.add_argument('--analysis',action='append',required=True)
    parser.add_argument('--genre',choices=['tien_hiep','hien_dai','hybrid_cyberpunk_tu_tien'],required=True)
    parser.add_argument('--book-id',required=True);parser.add_argument('--store',required=True)
    parser.add_argument('--out',required=True);parser.add_argument('--scene-end-ids',nargs='*')
    parser.add_argument('--through-chapter',type=int,default=0)
    parser.add_argument('--model',default='auto')
    parser.add_argument('--style-evidence');parser.add_argument('--style-ids',nargs='*')
    args=parser.parse_args()
    print(prepare(args.source,args.analysis,args.genre,args.book_id,args.store,args.out,args.scene_end_ids,args.through_chapter,args.model,args.style_evidence,args.style_ids))
