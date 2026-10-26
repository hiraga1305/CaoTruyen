"""Honest runtime metrics and sealed, local evidence handover for resilient jobs."""
import csv
import hashlib
import json
import zipfile
from pathlib import Path
from semantic_gate import read_json
from native_oauth.workflow_io import atomic_json, atomic_text, file_lock
from native_oauth.resilient_publication import progress


def report(book,job,total):
    book,job=Path(book).resolve(),Path(job).resolve();calls=[]
    for path in sorted((job/'native_attempts').rglob('runtime.json')):
        runtime=read_json(path);usage=runtime.get('usage') or (runtime.get('result') or {}).get('usage') or {}
        role=path.parent.name.removesuffix('.runtime')
        packet_path=path.parent.parent/'source.json';packet=read_json(packet_path) if packet_path.exists() else {}
        events=path.with_name('events.jsonl')
        blocks=[json.loads(line) for line in events.read_text(encoding='utf8').splitlines() if line.strip()] if events.exists() else []
        calls.append({'file':str(path),'role':role,'chapter':packet.get('chapter'),
            'requested_model':runtime.get('requested_model'),'actual_model':runtime.get('actual_model'),
            'status':runtime.get('status'),'partial':runtime.get('partial_output'),'worker_seconds':runtime.get('duration_seconds'),
            'tool_calls':sum(e.get('step_update',{}).get('step_type')=='tool' for e in blocks),
            **{key:usage.get(key) for key in ('input_tokens','output_tokens','thinking_tokens','total_tokens')}})
    journals=[read_json(p) for p in (job/'recovery').glob('*.json')]
    failures=[a for state in journals for a in state['attempts'] if a['status']!='DONE']
    invocations=read_json(job/'invocations.json') if (job/'invocations.json').exists() else []
    complete_timing=bool(invocations) and all(isinstance(r.get('active_wall_seconds'),(int,float)) for r in invocations)
    wall=sum(r['active_wall_seconds'] for r in invocations) if complete_timing else None
    verified=progress(book,total)
    source_report=read_json(job/'source_preflight.json') if (job/'source_preflight.json').exists() else {}
    scope='diagnostic' if (job/'diagnostic_result.json').exists() else 'publication'
    job_approved=[]
    for chapter in verified['approved_chapters']:
        timing_file=job/'chapter_times'/f'{chapter:04d}.json'
        if timing_file.exists() and isinstance(read_json(timing_file).get('approved_epoch'),(int,float)):
            job_approved.append(chapter)
    chars=sum(len(row['source']) for source in source_report.get('sources',[]) if source['status']=='SOURCE_READY' and source['chapter'] in job_approved
              for row in read_json(source['source_file'])['segments'])
    result={'progress':verified,'job_scope':scope,'job_approved_chapters':job_approved,'job_approved_source_characters':chars,
        'native_calls_with_runtime':len(calls),'logical_attempts':sum(len(r['attempts']) for r in journals),
        'attempt_failures_by_kind':{kind:sum(r.get('kind')==kind for r in failures) for kind in sorted({r.get('kind','INTERRUPTED') for r in failures})},
        'active_wall_seconds':wall,'worker_seconds_sum':sum(r['worker_seconds'] for r in calls) if calls and all(isinstance(r['worker_seconds'],(int,float)) for r in calls) else None,
        'token_totals':{key:sum(r[key] for r in calls) if calls and all(isinstance(r[key],(int,float)) for r in calls) else None
                        for key in ('input_tokens','output_tokens','thinking_tokens','total_tokens')},
        'known_token_sums_lower_bound':{key:sum(r[key] for r in calls if isinstance(r[key],(int,float)))
                                      for key in ('input_tokens','output_tokens','thinking_tokens','total_tokens')},
        'attempts_missing_runtime':[a['workspace'] for state in journals for a in state['attempts']
            if not list((Path(a['workspace'])/'native_oauth/runs/chapter1').glob('*.runtime/runtime.json'))],
        'approved_source_chars_per_hour':chars*3600/wall if wall and scope=='publication' else None,
        'timing_note':'Wall includes each completed run invocation, including source recovery, review and repair. '
                      'Pauses between invocations and separate diagnostics are excluded; their timestamps remain. '
                      'Worker sum is not wall or chapter latency. Rate counts only chapters approved in this job, excluding an inherited prefix. Missing usage/timing stays null.',
        'next_actions':read_json(job/'campaign.json').get('next_actions',[]) if (job/'campaign.json').exists() else []}
    atomic_json(job/'metrics.json',result)
    states=read_json(job/'campaign.json').get('chapters',{}) if (job/'campaign.json').exists() else {}
    source_rows={row['chapter']:row for row in source_report.get('sources',[])}
    approved=set(verified['approved_chapters']);chapters=[]
    for chapter in range(1,total+1):
        row=source_rows.get(chapter,{})
        source=read_json(row['source_file']) if row.get('status')=='SOURCE_READY' else None
        timing_file=job/'chapter_times'/f'{chapter:04d}.json'
        timing=read_json(timing_file) if timing_file.exists() else {}
        state=states.get(str(chapter),{})
        chapters.append({'chapter':chapter,'status':'APPROVED' if chapter in approved else state.get('status','QUEUED'),
            'approved_in_this_job':chapter in job_approved,
            'source_hash':source.get('package_hash') if source else None,
            'source_paragraphs':len(source['segments']) if source else None,
            'source_characters':sum(len(r['source']) for r in source['segments']) if source else None,
            'started_epoch':timing.get('started_epoch'),'approved_epoch':timing.get('approved_epoch') if chapter in approved else None,
            'elapsed_until_approval_seconds':timing.get('elapsed_until_approval_seconds') if chapter in approved else None,
            'next_action':state.get('action'),'reason':state.get('reason')})
    with (job/'chapter_metrics.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(chapters[0]) if chapters else ['chapter','status'])
        writer.writeheader();writer.writerows(chapters)
    if calls:
        with (job/'native_calls.csv').open('w',encoding='utf-8-sig',newline='') as handle:
            writer=csv.DictWriter(handle,fieldnames=list(calls[0]));writer.writeheader();writer.writerows(calls)
    atomic_text(job/'summary.md',f"# Resilient translation\n\nApproved {verified['approved_count']}/{total}; export_ready={verified['export_ready']}.\n\n"
        f"Job scope: {scope}; chapters approved in this job: {len(job_approved)}; source characters approved in this job: {chars}.\n\n"
        f"Native calls: {len(calls)}; active wall seconds: {wall}; worker seconds: {result['worker_seconds_sum']}.\n\n"
        +result['timing_note']+'\n\nSee campaign.json for every queued chapter and next action.\n')
    return result


def evidence_dependencies(evidence):
    """Follow host-owned proof fields, never arbitrary paths in model prose."""
    files=set()
    def packet(value):
        files.update(name for name,expected in value.get('native_bound_files',{}).items() if expected is not None)
    def part(value):
        files.update((value['file'],value['package_file']))
        packet(read_json(value['package_file']))
        result=read_json(value['file'])
        if result.get('native_artifact'):files.add(result['native_artifact']['file'])
        for runtime in result.get('native_runtimes',[]):
            path=Path(runtime['file']);files.add(str(path))
            files.update(str(p) for p in path.parent.iterdir() if p.is_file() and p.suffix!='.lock')
        files.update(str(p) for p in Path(value['package_file']).parent.glob('*.prompt.txt'))
    for item in evidence['package']['chapters']:
        packet(item['source_packet']);files.add(item['candidate_file'])
        for entry in read_json(item['candidate_file'])['components']:part(entry)
    for role in evidence['reviews']:
        for entry in role['parts']:part(entry)
    return files


def seal(book,job,total,out):
    book,job,out=Path(book).resolve(),Path(job).resolve(),Path(out).resolve()
    if out.exists():raise ValueError('Never overwrite a sealed evidence bundle')
    with file_lock(job/'campaign.lock',timeout=1):
        report(book,job,total)
        files={}
        for base,label in ((job,'job'),(book/'approved','approved')):
            if base.exists():
                for path in base.rglob('*'):
                    if path.is_file() and path.suffix not in ('.lock','.zip') and path.name!='bundle_manifest.json':
                        files[label+'/'+path.relative_to(base).as_posix()]=path
        external=set()
        # Imported replacements may be unused in a short pilot but are still
        # handed over with the job; keep their raw archives and old lineage too.
        external.update(str(path) for path in (job/'effective_sources').glob('source_chapter_*.json'))
        for path in (job/'source_packets').glob('*.json'):
            packet=read_json(path)
            external.update(name for name,value in packet.get('native_bound_files',{}).items() if value is not None)
        for path in (book/'approved/batches').glob('*/evidence.json'):
            external.update(evidence_dependencies(read_json(path)))
        config=read_json(job/'configuration.json') if (job/'configuration.json').exists() else {}
        root=Path(__file__).resolve().parents[1]
        for name,expected in config.get('workflow_files',{}).items():
            snapshot=job/'workflow_snapshot'/name
            path=snapshot if snapshot.exists() else root/name
            if hashlib.sha256(path.read_bytes()).hexdigest()!=expected:raise ValueError('Workflow snapshot changed before seal')
            files['workflow/'+Path(name).as_posix()]=path
        pending=list(external);seen=set()
        while pending:
            name=pending.pop()
            if name in seen:continue
            seen.add(name)
            path=Path(name)
            if path.exists():
                files['inputs/'+hashlib.sha256(str(path).encode()).hexdigest()[:16]+'_'+path.name]=path
                if path.suffix=='.json':
                    value=read_json(path)
                    if isinstance(value,dict) and value.get('version')=='bns-source-v2':
                        raw=root/'source_archive'/('book_'+value['book_id'])/value['raw_archive']
                        if not raw.is_file() or hashlib.sha256(raw.read_bytes()).hexdigest()!=value['raw_sha256']:
                            raise ValueError('Source raw archive is missing or changed before seal')
                        files['archives/'+value['raw_archive']]=raw
                        lineage=value.get('recovery_lineage',{})
                        if lineage.get('original_file'):
                            previous=Path(lineage['original_file'])
                            if (not previous.is_file() or hashlib.sha256(previous.read_bytes()).hexdigest()!=lineage.get('original_sha256')):
                                raise ValueError('Source recovery lineage original is missing or changed before seal')
                            pending.append(str(previous))
        manifest={name:{'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'original_path':str(path)} for name,path in files.items()}
        atomic_json(job/'bundle_manifest.json',manifest)
        out.parent.mkdir(parents=True,exist_ok=True)
        with zipfile.ZipFile(out,'x',zipfile.ZIP_DEFLATED) as archive:
            for name,path in files.items():archive.write(path,arcname=name)
            archive.write(job/'bundle_manifest.json',arcname='manifest.json')
    return {'bundle':str(out),'sha256':hashlib.sha256(out.read_bytes()).hexdigest(),'files':len(manifest)+1}
