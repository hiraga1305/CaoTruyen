"""Run/resume source-frozen draft blocks under a shared between-wave budget."""
import argparse
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from semantic_gate import read_json,write_json,digest
from native_oauth.batch_experiment import run_manifest
from native_oauth.run_agy import require_complete_runtime


def verified_cached_result(spec,workspace):
    contract=read_json(spec['contract'])
    if contract['contract_hash']!=digest({k:v for k,v in contract.items() if k!='contract_hash'}):
        raise ValueError('Changed contract')
    work=Path(workspace)/contract['job_id']
    if not (work/'worker_result.json').exists():return None
    result=read_json(work/'worker_result.json')
    if result.get('status')!='DRAFT_COMPLETE_UNREVIEWED':
        raise ValueError('Prior attempt blocked; use a fresh workspace for explicit retry')
    candidate=read_json(work/'candidate.json');runtime=read_json(work/'runtime/runtime.json')
    require_complete_runtime(runtime, spec['model'])
    if (digest(candidate)!=result.get('candidate_hash') or digest(runtime)!=digest(result['runtime'])
        or runtime['status']!='SUCCESS' or result['actual_model']!=spec['model']
        or any(candidate.get(k)!=contract[k] for k in ('job_id','contract_hash','state_hash'))
        or [s['id'] for s in candidate['segments']]!=[s['id'] for s in contract['owned_segments']]
        or any(not isinstance(s.get('text'), str) or not s['text'].strip() for s in candidate['segments'])
        or candidate.get('provenance',{}).get('conversation_id')!=runtime.get('conversation_id')):
        raise ValueError('Cached output/runtime/state/model mismatch')
    result['reused_verified_original_session']=True
    return result


def execute(manifest,resume=False):
    specs=manifest['jobs']
    if len(specs)>200 or not 1<=manifest.get('max_concurrency',2)<=2:
        raise ValueError('One source-frozen block limited to200 jobs and2 concurrentworkers')
    results={};pending=[];usage=0
    for spec in specs:
        contract=read_json(spec['contract']);identifier=contract['job_id']
        if identifier in results or any(read_json(p['contract'])['job_id']==identifier for p in pending):
            raise ValueError('Duplicate ownership')
        cached=verified_cached_result(spec,manifest['workspace']) if resume else None
        if cached:results[identifier]=cached
        else:pending.append(spec)
    # Resume budget applies only to new calls; original cache retains its usage.
    unknown=False
    for start in range(0,len(pending),16):
        budget=manifest.get('max_reported_tokens',600000)-usage
        if budget<=0 or unknown:break
        wave={**manifest,'jobs':pending[start:start+16], 'max_reported_tokens':budget,
              'result_path':str(Path(manifest['result_path']).with_name(f'wave_{start//16}.json'))}
        part=run_manifest(wave)
        for result in part['results']:
            if result.get('job_id'):results[result['job_id']]=result
        usage+=part['reported_total_tokens'];unknown=part['usage_unknown']
        write_json(manifest['result_path'],{'status':'RUNNING','results':list(results.values()),'new_reported_tokens':usage})
        if part['status']=='BLOCKED':break
    ordered=[results[read_json(s['contract'])['job_id']] for s in specs if read_json(s['contract'])['job_id'] in results]
    complete=len(ordered)==len(specs) and all(r['status']=='DRAFT_COMPLETE_UNREVIEWED' for r in ordered)
    report={'status':'DRAFTS_COMPLETE_UNREVIEWED' if complete else 'BLOCKED', 'results':ordered,
            'pending_job_ids':[read_json(s['contract'])['job_id'] for s in specs if read_json(s['contract'])['job_id'] not in results],
            'new_reported_tokens':usage,'usage_unknown':unknown,'publish':False,
            'budget_note':'Between-wave new-call budget; a running call may exceed it. Cache reuse is original provenance, not a new session.'}
    write_json(manifest['result_path'],report);return report


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--manifest',required=True)
    parser.add_argument('--resume',action='store_true');args=parser.parse_args(argv)
    report=execute(read_json(args.manifest),args.resume);print(report['status'])
    raise SystemExit(0 if report['status']=='DRAFTS_COMPLETE_UNREVIEWED' else 2)


if __name__=='__main__':main()
