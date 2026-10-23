"""Five-chapter windows: bounded draft workers, ordered reviews, wave gate."""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import time
from semantic_gate import read_json
from native_oauth.approved_context import retrieve_context
from native_oauth.book_publication import read_manifest, read_approval
from native_oauth.semantic_context import normalize_profile
from native_oauth.session_monitor import get_session_monitor
from native_oauth.workflow_io import atomic_json, file_lock
from native_oauth.wave_drafts import generate_draft
from native_oauth.wave_review import begin_wave, review_wave, validate_wave_gates


def matching_approval(book, job, chapter, options):
    from native_oauth.revise_book import prepare_revision
    if str(chapter) not in read_manifest(book)['chapters']:
        return False
    try:
        old = read_approval(book,chapter)['evidence']
        expected = ['native/'+options.get('reviewer_model','gemini-3.8-flash-high'),
                    'native/'+options.get('auditor_model','gemini-3.8-flash-medium')]
        return (old['package']==prepare_revision(book,job,chapter)[2]
                and [r['model'] for r in old['reviews']]==expected)
    except (ValueError, OSError, KeyError, TypeError):
        return False


def draft_anchor(book, chapters):
    through = chapters[0]-1
    context = {}
    if through:
        prior = read_approval(book,through)
        lore_file = book/'lore.json'
        lore = read_json(lore_file) if lore_file.exists() else {}
        sources = [read_json(book/'sources'/f'source_chapter_{ch:04d}.json') for ch in chapters]
        entities,_,_ = normalize_profile(sources[0]['book_id'],[],[],lore)
        context = retrieve_context(book,chapters[0],prior['evidence_path'],entities,
                                   '\n'.join(s['source'] for source in sources for s in source['segments']))
    return {'through_chapter':through, 'chapter_range':f'{chapters[0]}–{chapters[-1]}',
            'book_dir':str(book.resolve()),
            'prefix_entry':read_manifest(book)['chapters'].get(str(through)),
            'approved_context':context,
            'rule':'Only this prefix is approved. Original Chinese supplies local context; drafts are not facts.'}


def run_wave_campaign(book, job, through=325, *, max_workers=3, **options):
    from native_oauth.revise_book import revise_chapter
    book,job = Path(book).resolve(),Path(job).resolve()
    if not 2 <= max_workers <= 6 or through < 1:
        raise ValueError('Use 2..6 native slots and a positive chapter range')
    state = {'book_id':book.name.removeprefix('book_'),'range':[1,through],
             'mode':'wave','wave_size':5,'max_workers':max_workers,
             'translation_workers':max_workers-1,'status':'RUNNING','approved_chapters':[], 'job':str(job)}
    model = options.get('translator_model','gemini-3.8-flash-high')
    timeout = options.get('timeout',600)
    with file_lock(job/'campaign.lock',timeout=1):
        started=time.monotonic()
        try:
            for start in range(1,through+1,5):
                if (job/'restart_requested.json').exists():
                    state['status']='STOPPED_AT_WAVE_BOUNDARY'
                    return state
                chapters = list(range(start,min(start+5,through+1)))
                state.update(current_wave=(start-1)//5+1, wave_range=chapters)
                # Revalidate consecutively. Once a predecessor is stale, every
                # following chapter must be reviewed again under the new prefix.
                reusable=[]
                for chapter in chapters:
                    if not matching_approval(book,job,chapter,options):
                        break
                    reusable.append(chapter)
                gate = read_manifest(book).get('wave_gates',{}).get(str(start))
                if reusable==chapters and gate is None:
                    # Existing sequential approvals remain intact on migration.
                    state['approved_chapters'].extend(chapters)
                    atomic_json(job/'campaign.json',state)
                    continue
                if reusable==chapters and gate and gate.get('status')=='PASS':
                    try:
                        validate_wave_gates(book,{'wave_gates':{str(start):gate}})
                    except (ValueError,OSError,KeyError,TypeError):
                        pass
                    else:
                        state['approved_chapters'].extend(chapters)
                        atomic_json(job/'campaign.json',state)
                        continue
                begin_wave(book,chapters)
                state['approved_chapters'].extend(reusable)
                pending = chapters[len(reusable):]
                anchor = draft_anchor(book, chapters)
                first_source = read_json(book/'sources'/f'source_chapter_{start:04d}.json')
                lore_file=book/'lore.json';lore=read_json(lore_file) if lore_file.exists() else {}
                mon = get_session_monitor(first_source['book_id'],lore.get('book_title_vi',book.name),
                    len(read_json(book/'toc.json')) if (book/'toc.json').exists() else through)
                mon.genre=lore.get('genre','Theo nguồn');mon.chapter_range=f'{start}–{chapters[-1]}'
                worker=f'wave-{start:04d}'
                mon.record_worker_active(worker,start,(start-1)//5+1,message='Parallel drafts + ordered reviews')
                print(mon.render_markdown_badge(),flush=True)
                futures={}
                try:
                    # One reserved lane for the two serial, isolated reviewers.
                    # Draft generation overlaps their work without spawning an
                    # unbounded number of native processes.
                    with ThreadPoolExecutor(max_workers=max_workers-1) as pool:
                        futures={ch:pool.submit(generate_draft,book,job,ch,anchor,model=model,timeout=timeout,
                                 max_repairs=options.get('max_repairs',1)) for ch in pending}
                        try:
                            for chapter in pending:
                                if (job/'restart_requested.json').exists():
                                    state['status']='STOPPED_AT_CHAPTER_BOUNDARY'
                                    mon.record_stage_result(start,'wave',worker,'STOPPED')
                                    print(mon.render_markdown_badge(),flush=True)
                                    return state
                                state['current_chapter']=chapter
                                atomic_json(job/'campaign.json',state)
                                seed=futures[chapter].result()
                                revise_chapter(book,job,chapter,draft_seed=seed,**options)
                                state['approved_chapters'].append(chapter)
                                atomic_json(job/'campaign.json',state)
                        finally:
                            for future in futures.values():
                                future.cancel()
                    review_wave(book,job,chapters,model=options.get('auditor_model','gemini-3.8-flash-medium'),timeout=timeout)
                except Exception:
                    mon.record_stage_result(start,'wave',worker,'BLOCKED')
                    print(mon.render_markdown_badge(),flush=True)
                    raise
                else:
                    mon.record_stage_result(start,'wave',worker,'STAGE_COMPLETE')
                    print(mon.render_markdown_badge(),flush=True)
            state['status']='APPROVED_RANGE_COMPLETE'
        except Exception as error:
            state.update(status='BLOCKED',reason=str(error),error_type=type(error).__name__)
            raise
        finally:
            # Wall time for this invocation, distinct from summed worker time.
            state['elapsed_seconds']=round(time.monotonic()-started,2)
            atomic_json(job/'campaign.json',state)
    return state
