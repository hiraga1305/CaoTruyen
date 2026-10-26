"""Controlled LOW/MEDIUM/HIGH pilot using the real wave runner in isolated books.

prepare/report/seal are offline. Only run invokes native models, in Antigravity.
Never imports the old draft-only pilot or changes the production book.
"""
import argparse
import csv
import hashlib
import json
import shutil
import random
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from semantic_gate import read_json
from native_oauth.chapter_integrity import validate_source, validate_source_archive
from native_oauth.workflow_io import atomic_json, atomic_text, file_lock

ROOT = Path(__file__).resolve().parents[1]
ARMS = {'A': 'gemini-3.8-flash-low', 'B': 'gemini-3.8-flash-medium',
        'C': 'gemini-3.8-flash-high'}
REVIEW_MODEL = 'gemini-3.8-flash-medium'
STRESS_CHAPTERS = (1622,1975,1978)
SCHEMA = 'antigravity-final-pilot-2'


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def code_snapshot():
    files = [ROOT/'semantic_gate.py', *sorted((ROOT/'native_oauth').glob('*.py')),
             ROOT/'native_oauth/semantic_profiles.json', ROOT/'native_oauth/genre_profiles.json',
             *sorted((ROOT/'native_oauth/prompts').glob('*.md')),
             *sorted((ROOT/'.agents/agents').glob('novel-*.md'))]
    return {str(p.relative_to(ROOT)): sha(p) for p in files}


def prepare(book, out, chapters=20, first_arm='B'):
    """Freeze one continuous prefix; no invented approvals for distant ranges."""
    book, out = Path(book).resolve(), Path(out).resolve()
    if out.exists():
        raise ValueError('Pilot already exists; do not overwrite or silently reset a run')
    if out.is_relative_to(book) or book.is_relative_to(out):
        raise ValueError('Pilot and production book must be separate directories')
    if chapters not in (10,20) or first_arm not in ARMS:
        raise ValueError('Use 10 or 20 consecutive chapters starting at 1 and arm A/B/C')
    sources = []
    for ch in range(1,chapters+1):
        path = book/'sources'/f'source_chapter_{ch:04d}.json'
        source = read_json(path)
        validate_source(source)
        validate_source_archive(source)
        sources.append((path,source))
    if len({s['book_id'] for _,s in sources}) != 1:
        raise ValueError('Pilot mixes book identities')
    # Verify title support before creating any live campaign.
    from native_oauth.book_publication import title_ids
    from native_oauth.title_selection import metadata_title_source
    for _,source in sources:
        if not title_ids(source):
            metadata_title_source(source)
    frozen = {str(p):sha(p) for p,_ in sources}
    archive_root = ROOT/'source_archive'/('book_'+sources[0][1]['book_id'])
    for _,source in sources:
        if source.get('raw_archive'):
            path = archive_root/source['raw_archive']
            frozen[str(path)] = sha(path)
    for name in ('toc.json','lore.json'):
        if (book/name).exists():
            frozen[str(book/name)] = sha(book/name)
    stress_sources=[]
    for ch in sorted({n for target in STRESS_CHAPTERS for n in range(target-2,target+1)}):
        path=book/'sources'/f'source_chapter_{ch:04d}.json'
        if not path.exists():
            continue  # Small offline fixtures do not contain distant chapters.
        source=read_json(path);validate_source(source);validate_source_archive(source)
        if ch in STRESS_CHAPTERS and not title_ids(source):metadata_title_source(source)
        stress_sources.append((path,source));frozen[str(path)]=sha(path)
        if source.get('raw_archive'):
            archive=archive_root/source['raw_archive'];frozen[str(archive)]=sha(archive)
    spec = {'schema':SCHEMA, 'created_utc':now(), 'production_book':str(book),
            'chapters':list(range(1,chapters+1)), 'models':ARMS,
            'execution_order':[first_arm, *[arm for arm in ARMS if arm!=first_arm]],
            'reviewer_model':REVIEW_MODEL, 'auditor_model':REVIEW_MODEL,
            'mode':'wave', 'wave_size':5, 'max_workers':3, 'max_repairs':2,
            'timeout':600, 'source_files':frozen, 'code_files':code_snapshot(),
            'source_characters':sum(len(r['source']) for _,s in sources for r in s['segments']),
            'source_paragraphs':sum(len(s['segments']) for _,s in sources),
            'stress_chapters':[ch for ch in STRESS_CHAPTERS if any(s['chapter']==ch for _,s in stress_sources)],
            'interpretation':'Only translator model differs. Timed through final approval and wave gate. '
                             'A small prefix is not a full-book quality or throughput guarantee.'}
    out.mkdir(parents=True)
    for arm in ARMS:
        target = out/arm/'book'
        for path,_ in sources:
            (target/'sources').mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,target/'sources'/path.name)
        for name in ('toc.json','lore.json'):
            if (book/name).exists():
                shutil.copy2(book/name,target/name)
        for path,_ in stress_sources:
            directory=out/arm/'stress_book/sources';directory.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,directory/path.name)
        if stress_sources:
            for name in ('toc.json','lore.json'):
                if (book/name).exists():shutil.copy2(book/name,out/arm/'stress_book'/name)
    for name in spec['code_files']:
        path=out/'workflow_snapshot'/name;path.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/name,path)
    for path,_ in [*sources,*stress_sources]:
        source=read_json(path)
        if source.get('raw_archive'):
            target=out/'input_archives'/source['raw_archive'];target.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(archive_root/source['raw_archive'],target)
    atomic_json(out/'experiment.json',spec)
    atomic_text(out/'experiment.sha256',sha(out/'experiment.json')+'\n')
    assert_frozen(out)
    return spec


def assert_frozen(out):
    out = Path(out).resolve()
    spec = read_json(out/'experiment.json')
    if sha(out/'experiment.json') != (out/'experiment.sha256').read_text(encoding='utf-8').strip():
        raise ValueError('Experiment configuration changed after freeze')
    if spec.get('schema') != SCHEMA:
        raise ValueError('Unsupported experiment')
    if code_snapshot() != spec['code_files']:
        raise ValueError('Workflow code changed after freeze; create a new experiment, never relabel a run')
    for name,expected in spec['code_files'].items():
        if sha(out/'workflow_snapshot'/name)!=expected:
            raise ValueError('Frozen workflow snapshot changed')
    for name,expected in spec['source_files'].items():
        if sha(name) != expected:
            raise ValueError('Production source/canon changed: '+name)
    original = Path(spec['production_book'])
    for arm in ARMS:
        book = out/arm/'book'
        if (book/'output_dich').exists():
            raise ValueError('Old translations must not enter the controlled pilot')
        if sorted(p.name for p in (book/'sources').glob('*.json')) != [
                f'source_chapter_{ch:04d}.json' for ch in spec['chapters']]:
            raise ValueError('Pilot source range changed')
        for ch in spec['chapters']:
            name = f'sources/source_chapter_{ch:04d}.json'
            if sha(book/name) != spec['source_files'][str(original/name)]:
                raise ValueError('Isolated arm source changed')
        for name in ('toc.json','lore.json'):
            expected = spec['source_files'].get(str(original/name))
            if (sha(book/name) if (book/name).exists() else None) != expected:
                raise ValueError('Isolated arm canon/TOC changed')
        if spec.get('stress_chapters'):
            stress=out/arm/'stress_book'
            expected_chapters=sorted({n for ch in spec['stress_chapters'] for n in range(ch-2,ch+1)})
            if sorted(p.name for p in (stress/'sources').glob('*.json')) != [f'source_chapter_{ch:04d}.json' for ch in expected_chapters]:
                raise ValueError('Stress source range changed')
            for ch in expected_chapters:
                name=f'sources/source_chapter_{ch:04d}.json'
                if sha(stress/name)!=spec['source_files'][str(original/name)]:raise ValueError('Stress source changed')
            for name in ('toc.json','lore.json'):
                expected=spec['source_files'].get(str(original/name))
                if (sha(stress/name) if (stress/name).exists() else None)!=expected:raise ValueError('Stress canon changed')
    return spec


def run_stress(out,arm):
    """Distant scenes: repair/review with source-only history, NEVER book approval.

    This supplementary quality probe cannot simulate an approved 1600-chapter
    prefix. Its runtime is reported separately from production-path throughput.
    """
    out=Path(out).resolve();spec=assert_frozen(out)
    import os
    if not (os.environ.get('ANTIGRAVITY_ARTIFACT_DIR') or os.environ.get('ANTIGRAVITY_CONVERSATION_ID')):
        raise ValueError('Bind the actual Antigravity conversation')
    from native_oauth.revise_book import create_campaign, prepare_revision, revision_protocol
    from native_oauth.pipeline_native import run_stage
    from native_oauth.native_review import run_independent_reviews
    from native_oauth.native_evidence import validate_provenance
    from semantic_gate import mechanical_findings, validate_review, digest
    with file_lock(out/'experiment.lock',timeout=1):
        require_prior_arms(out,spec,arm,stress=True)
        book,job=out/arm/'stress_book',out/arm/'stress_job'
        if not spec.get('stress_chapters'):raise ValueError('No distant sources were frozen')
        if (out/arm/'stress_result.json').exists():raise ValueError('Stress run exists; preserve it without stochastic retries')
        create_campaign(book,job)
        result={'status':'RUNNING','approval_eligible':False,'scope':'Distant source-only diagnostic; no approved predecessor',
                'started_utc':now(),'chapters':[]}
        atomic_json(out/arm/'stress_result.json',result);started=time.monotonic()
        try:
            for ch in spec['stress_chapters']:
                prior=[read_json(book/'sources'/f'source_chapter_{n:04d}.json') for n in range(ch-2,ch)]
                anchor={'through_chapter':0,'approved_context':{},'chapter_range':str(ch),
                        'source_context_read_only':[{'chapter':s['chapter'],'source_hash':s['package_hash'],'segments':s['segments']} for s in prior],
                        'rule':'Only literal Chinese from earlier chapters. No translated prefix is approved. Diagnostic only.'}
                source,legacy,package=prepare_revision(book,job,ch,draft_anchor=anchor)
                findings=None;candidate=None;passed=False
                for attempt in range(spec['max_repairs']+1):
                    work=job/'diagnostics'/f'chapter_{ch:04d}'/f'attempt_{attempt}'
                    data=work/'native_oauth/runs/chapter1';atomic_json(data/'source.json',package)
                    candidate=run_stage(data,work,'translator',ARMS[arm],
                        revision_protocol(package,legacy,findings,candidate), 'draft.json',spec['timeout'])
                    sessions=set(validate_provenance(candidate))
                    findings=mechanical_findings(package,candidate)
                    if not findings:
                        reviews=run_independent_reviews(package,candidate,data,work,REVIEW_MODEL,REVIEW_MODEL,spec['timeout'])
                        for review in reviews:
                            validate_review(package,candidate,review)
                            current=set(validate_provenance(review))
                            if sessions.intersection(current):raise ValueError('Diagnostic native sessions are not independent')
                            sessions.update(current)
                            if review['verdict']!='PASS':findings.extend(review['issues'] or [{'kind':'review_failed_without_diagnosis'}])
                    if prepare_revision(book,job,ch,draft_anchor=anchor)!=(source,legacy,package):
                        raise ValueError('Diagnostic source/context changed')
                    passed=not findings
                    atomic_json(work/'qa.json',{'status':'DIAGNOSTIC_PASS_NOT_APPROVAL' if passed else 'BLOCKED',
                        'approval_eligible':False,'candidate_hash':digest(candidate),'findings':findings})
                    if passed:break
                result['chapters'].append({'chapter':ch,'status':'DIAGNOSTIC_PASS_NOT_APPROVAL' if passed else 'BLOCKED',
                    'attempts':attempt+1,'candidate':str(data/'draft.json'),'candidate_hash':digest(candidate)})
                atomic_json(out/arm/'stress_result.json',result)
                if not passed:raise ValueError(f'Diagnostic chapter {ch} blocked after bounded repairs')
            assert_frozen(out)
            result['status']='DIAGNOSTIC_PASS_NOT_APPROVAL'
        except Exception as error:
            result.update(status='BLOCKED',reason=str(error));raise
        finally:
            result.update(ended_utc=now(),wall_seconds=time.monotonic()-started)
            atomic_json(out/arm/'stress_result.json',result)


def require_prior_arms(out,spec,arm,*,stress=False):
    if arm not in ARMS:
        raise ValueError('Unknown arm')
    order=spec['execution_order']
    prior=order if stress else order[:order.index(arm)]
    for previous in prior:
        path=Path(out)/previous/'measurement.json'
        if not path.exists() or read_json(path).get('status') not in ('COMPLETE','BLOCKED'):
            raise ValueError('Earlier production-path arms must finish or record BLOCKED before continuing: '+previous)
    if stress and read_json(Path(out)/arm/'measurement.json').get('status')!='COMPLETE':
        raise ValueError('Stress requires this production-path arm to be COMPLETE')


def run_arm(out, arm):
    """One fresh process per arm keeps SessionMonitor and native sessions separate."""
    out = Path(out).resolve()
    spec = assert_frozen(out)
    if arm not in ARMS:
        raise ValueError('Unknown arm')
    from native_oauth.session_monitor import get_active_artifact_dir, get_session_monitor
    import os
    if not (os.environ.get('ANTIGRAVITY_ARTIFACT_DIR') or os.environ.get('ANTIGRAVITY_CONVERSATION_ID')):
        raise ValueError('Bind the actual Antigravity conversation before running native models')
    from native_oauth.revise_book import create_campaign, run_campaign
    from native_oauth.book_progress import book_progress
    from native_oauth.wave_review import validate_wave_gates
    with file_lock(out/'experiment.lock',timeout=1):
        require_prior_arms(out,spec,arm)
        book,job = out/arm/'book',out/arm/'job'
        if (out/arm/'measurement.json').exists() and read_json(out/arm/'measurement.json')['status']=='COMPLETE':
            raise ValueError('Arm already complete; report it without another model call')
        invocations_file = out/arm/'invocations.json'
        invocations = read_json(invocations_file) if invocations_file.exists() else []
        if any(v.get('status')=='RUNNING' for v in invocations):
            raise ValueError('Prior process ended without a final timestamp; record interruption, do not invent timing')
        if not job.exists():
            create_campaign(book,job)
        mon = get_session_monitor(read_json(book/'sources/source_chapter_0001.json')['book_id'],
            f"Pilot {arm}: {ARMS[arm]}",len(spec['chapters']))
        mon.chapter_range = f"1–{spec['chapters'][-1]} (pilot {arm})"
        mon.sync_session_artifacts()
        print(mon.render_markdown_badge(),flush=True)
        measurement = {'arm':arm,'model':ARMS[arm], 'status':'RUNNING','started_utc':now()}
        atomic_json(out/arm/'measurement.json',measurement)
        invocation = {'started_utc':now(),'status':'RUNNING'}
        invocations.append(invocation)
        atomic_json(invocations_file,invocations)
        started = time.monotonic()
        try:
            run_campaign(book,job,len(spec['chapters']),mode='wave',max_workers=spec['max_workers'],
                translator_model=ARMS[arm],reviewer_model=REVIEW_MODEL,auditor_model=REVIEW_MODEL,
                max_repairs=spec['max_repairs'],timeout=spec['timeout'])
            assert_frozen(out)
            progress = book_progress(book,len(spec['chapters']))
            validate_wave_gates(book)
            if not progress['export_ready']:
                raise ValueError('Final approvals or wave gates incomplete')
            measurement.update(status='COMPLETE',progress=progress)
        except Exception as error:
            measurement.update(status='BLOCKED',reason=str(error),error_type=type(error).__name__)
            raise
        finally:
            invocation.update(ended_utc=now(),wall_seconds=time.monotonic()-started,status=measurement['status'])
            atomic_json(invocations_file,invocations)
            measurement.update(ended_utc=now(),active_wall_seconds=sum(v['wall_seconds'] for v in invocations),
                               invocations=len(invocations))
            atomic_json(out/arm/'measurement.json',measurement)
            for name in ('translation_live_dashboard.html','translation_session_dashboard.md'):
                path=get_active_artifact_dir()/name
                if path.exists():
                    atomic_text(out/arm/name,path.read_text(encoding='utf-8'))
            print(mon.render_markdown_badge(),flush=True)


def runtime_rows(root):
    """Include all native attempts, including failures, with unknown usage as null."""
    rows=[]
    for path in sorted(Path(root).rglob('runtime.json')):
        value=read_json(path)
        usage=value.get('usage') or (value.get('result') or {}).get('usage') or {}
        source_file=path.parent.parent/'source.json'
        chapter=read_json(source_file).get('chapter') if source_file.exists() else None
        events=path.with_name('events.jsonl')
        tool_calls=None
        if events.exists():
            parsed=[json.loads(line) for line in events.read_text(encoding='utf-8').splitlines() if line.strip()]
            tool_calls=sum(e.get('step_update',{}).get('step_type')=='tool' for e in parsed)
        rows.append({'file':str(path),'role':path.parent.name.removesuffix('.runtime'), 'chapter':chapter,
            'status':value.get('status'), 'requested_model':value.get('requested_model'),
            'actual_model':value.get('actual_model'), 'session':value.get('conversation_id'),
            'partial':value.get('partial_output'), 'worker_seconds':value.get('duration_seconds'),
            'input_tokens':usage.get('input_tokens'), 'output_tokens':usage.get('output_tokens'),
            'thinking_tokens':usage.get('thinking_tokens'), 'total_tokens':usage.get('total_tokens'),
            'tool_calls':tool_calls,'raw_usage':usage})
    return rows


def report(out):
    out=Path(out).resolve();spec=assert_frozen(out)
    from native_oauth.book_progress import book_progress
    from native_oauth.wave_review import validate_wave_gates
    arms={}
    all_rows=[]
    chapter_rows=[]
    for arm in ARMS:
        measurement=read_json(out/arm/'measurement.json') if (out/arm/'measurement.json').exists() else {'status':'NOT_RUN'}
        progress=book_progress(out/arm/'book',len(spec['chapters']))
        wave_valid=False
        if progress['export_ready']:
            from native_oauth.book_publication import read_manifest
            gates=read_manifest(out/arm/'book').get('wave_gates',{})
            wave_valid=all(gates.get(str(ch),{}).get('status')=='PASS' for ch in spec['chapters'][::5])
            validate_wave_gates(out/arm/'book')
        complete=measurement['status']=='COMPLETE' and progress['export_ready'] and wave_valid
        seconds=measurement.get('active_wall_seconds')
        rows=runtime_rows(out/arm/'job')
        for row in rows:row['arm']=arm
        all_rows.extend(rows)
        for ch in spec['chapters']:
            ch_calls=[r for r in rows if r['chapter']==ch and r['role']!='wave-auditor']
            source=read_json(out/arm/'book/sources'/f'source_chapter_{ch:04d}.json')
            chapter_rows.append({'arm':arm,'chapter':ch,'source_hash':source['package_hash'],
                'source_characters':sum(len(r['source']) for r in source['segments']),
                'paragraphs':len(source['segments']), 'approved':ch in progress['approved_chapters'],
                'native_calls_excluding_wave':len(ch_calls),
                'worker_seconds_sum_not_latency':sum(r['worker_seconds'] or 0 for r in ch_calls)})
        arms[arm]={'model':ARMS[arm],'status':'COMPLETE' if complete else ('INCOMPLETE' if measurement['status']=='COMPLETE' else measurement['status']),
            'measurement':measurement,'verified_progress':progress,'all_wave_gates_pass':wave_valid,
            'native_calls_all_attempts':len(rows),
            'native_failed_or_partial':sum(r['status'] not in ('SUCCESS','COMPLETED_CLI_CLEANUP') or bool(r['partial']) for r in rows),
            'worker_seconds_sum':sum(r['worker_seconds'] or 0 for r in rows),
            'token_totals':{key:sum(r[key] for r in rows) if rows and all(isinstance(r[key],(int,float)) for r in rows) else None
                            for key in ('input_tokens','output_tokens','thinking_tokens','total_tokens')},
            'approved_source_chars_per_hour':spec['source_characters']*3600/seconds if complete and seconds else None,
            'projected_full_book_hours':None}
        stress_file=out/arm/'stress_result.json'
        stress_rows=runtime_rows(out/arm/'stress_job')
        for row in stress_rows:row['arm']=arm;row['role']='stress/'+row['role']
        all_rows.extend(stress_rows)
        arms[arm]['stress_diagnostic']={'result':read_json(stress_file) if stress_file.exists() else {'status':'NOT_RUN'},
                                       'native_calls':len(stress_rows),'approval_eligible':False}
    result={'schema':SCHEMA,'created_utc':now(),'arms':arms,
        'quality_conclusion':'UNASSESSED: native PASS is process evidence, not a zero-error guarantee. '
                             'Compare final text against Chinese before selecting a model.',
        'timing_note':'active_wall_seconds includes every completed invocation through final wave validation; '
                      'human pauses between resumes are excluded. started/ended timestamps remain available. '
                      'worker_seconds_sum is not end-to-end time. No automatic full-book estimate from an early prefix.'}
    atomic_json(out/'metrics.json',result)
    with (out/'chapter_metrics.csv').open('w',encoding='utf-8-sig',newline='') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(chapter_rows[0]));writer.writeheader();writer.writerows(chapter_rows)
    if all_rows:
        with (out/'native_calls.csv').open('w',encoding='utf-8-sig',newline='') as handle:
            fields=list(all_rows[0]);writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader()
            writer.writerows({**r,'raw_usage':json.dumps(r['raw_usage'],ensure_ascii=False)} for r in all_rows)
    lines=['# Final LOW/MEDIUM/HIGH pilot','',result['timing_note'],'',
           '| Arm | Model | Status | Wall seconds | Approved | Native calls |',
           '|---|---|---|---:|---:|---:|']
    for arm,item in arms.items():
        lines.append(f"| {arm} | {item['model']} | {item['status']} | {item['measurement'].get('active_wall_seconds','—')} | "
                     f"{item['verified_progress']['approved_count']} | {item['native_calls_all_attempts']} |")
    lines+=['',result['quality_conclusion'],'','Do not publish the full book from this pilot.']
    atomic_text(out/'summary.md','\n'.join(lines)+'\n')
    if all(item['status']=='COMPLETE' for item in arms.values()):
        from native_oauth.book_publication import read_approval
        key_file=out/'comparison_key.json'
        if key_file.exists():
            key=read_json(key_file)
        else:
            order=list(ARMS);random.SystemRandom().shuffle(order)
            key=dict(zip(('X','Y','Z'),order));atomic_json(key_file,key)
        if set(key)!=set(('X','Y','Z')) or sorted(key.values())!=sorted(ARMS):
            raise ValueError('Blinded comparison key must cover all three arms exactly once')
        for chapter in spec['chapters']:
            values={label:read_approval(out/arm/'book',chapter)['evidence'] for label,arm in key.items()}
            source=next(iter(values.values()))['package']
            sample={'chapter':chapter,'source':source['segments'],
                    'metadata_title_source':source.get('metadata_title_source',{}).get('source'),
                    'candidates':{label:{'segments':value['candidate']['segments'],
                                         'title_vi':value['candidate'].get('title_vi')}
                                  for label,value in values.items()},
                    'rule':'Judge equivalent meaning against Chinese; no preference for literal diction or forced pronouns.'}
            atomic_json(out/'blinded_final'/f'chapter_{chapter:04d}.json',sample)
    return result


def seal(out):
    out=Path(out).resolve()
    bundle=out.with_name(out.name+'_bundle.zip')
    if bundle.exists():raise ValueError('Bundle already exists; never overwrite sealed evidence')
    report(out)
    files={str(p.relative_to(out)).replace('\\','/'):sha(p) for p in sorted(out.rglob('*'))
           if p.is_file() and p.name!='manifest.json' and p.suffix not in ('.zip','.lock')}
    atomic_json(out/'manifest.json',files)
    with zipfile.ZipFile(bundle,'x',zipfile.ZIP_DEFLATED) as archive:
        for name in [*files,'manifest.json']:
            archive.write(out/name,arcname=name)
    return bundle


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('prepare','run','stress','report','seal'))
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--book-dir',type=Path,default=ROOT/'native_oauth/book_siwangyouxi')
    parser.add_argument('--chapters',type=int,choices=(10,20),default=20)
    parser.add_argument('--arm',choices=tuple(ARMS))
    args=parser.parse_args()
    if args.action=='prepare':
        prepare(args.book_dir,args.out,args.chapters)
    elif args.action=='run':
        if not args.arm:parser.error('run requires --arm')
        run_arm(args.out,args.arm)
    elif args.action=='stress':
        if not args.arm:parser.error('stress requires --arm')
        run_stress(args.out,args.arm)
    elif args.action=='report':
        report(args.out)
    else:
        print(seal(args.out))


if __name__=='__main__':
    main()
