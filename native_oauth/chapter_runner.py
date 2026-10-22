"""Bounded chapter drafts shared by every book-specific runner.

Only complete drafts are committed, receipt last. Existing production output is
never used as a cache or overwritten. Independent semantic review is still needed.
"""
import inspect
from contextlib import ExitStack
from native_oauth.workflow_io import file_lock
import json
import os
import time
from pathlib import Path
from semantic_gate import digest
from native_oauth.chapter_integrity import atomic_json, atomic_text, inspect_chapter, render_text, validate_source, read_verified_draft
from native_oauth.run_agy import IncompleteNativeOutput, require_complete_runtime
from native_oauth.session_monitor import get_session_monitor
from native_oauth.semantic_context import context_tail, continuation_boundary


def split_scenes(paragraphs, max_paragraphs=20, max_characters=3200):
    chunks, current, chars = [], [], 0
    for paragraph in paragraphs:
        if len(paragraph) > max_characters:
            raise ValueError('One source paragraph exceeds scene budget; split with auditable offsets first')
        if current and (len(current) >= max_paragraphs or chars + len(paragraph) > max_characters):
            # Prefer keeping an attribution and its quote together, within the
            # same strict budgets. Preserve every whole owned source paragraph.
            cut = len(current)
            if continuation_boundary(current, paragraph):
                for candidate in range(len(current) - 1, max(0, len(current) - 5), -1):
                    tail = current[candidate:]
                    if (len(tail) + 1 <= max_paragraphs
                            and sum(map(len, tail)) + len(paragraph) <= max_characters
                            and not continuation_boundary(current[:candidate], current[candidate])):
                        cut = candidate
                        break
            chunks.append(current[:cut])
            current = current[cut:]
            chars = sum(map(len, current))
        current.append(paragraph)
        chars += len(paragraph)
    if current:
        chunks.append(current)
    return chunks


def recipe_hash(callback, model, genre, book_dir):
    files = [Path(__file__), Path(inspect.getsourcefile(callback)),
             Path(__file__).with_name('quality_gate.py'), Path(__file__).with_name('bns_prepass.py'),
             Path(__file__).with_name('run_agy.py'), Path(__file__).with_name('spot_auditor.py'),
             Path(__file__).with_name('chapter_integrity.py'),
             Path(__file__).with_name('scene_contract.py'),
             Path(__file__).with_name('semantic_context.py'),
             Path(__file__).with_name('semantic_profiles.json'),
             Path(__file__).parent / 'book_49736/batch_pipeline_runner.py',
             Path(__file__).parent / 'cartridges/urban_suspense.py',
             Path(book_dir) / 'lore.json', Path(__file__).parent / 'prompts/bns_system_cache_v1.md']
    return digest({'model': model, 'genre': genre,
                   'files': {str(p): digest(p.read_text(encoding='utf-8')) for p in files if p.exists()}})


def run_chapter(chapter, book_id, book_title, genre, source_dir, output_dir, callback,
                model, force=False, total_chapters=325, runtime_root=None):
    source_file = Path(source_dir) / f'source_chapter_{chapter:04d}.json'
    mon = get_session_monitor(book_id=str(book_id), book_title=book_title, total_chapters=total_chapters)
    mon.genre = genre
    mon.chapter_range = f'{chapter}–{chapter}'
    wave = (chapter - 1) // 5 + 1
    worker = f'Worker-{os.getpid()}-{chapter}'
    mon.record_worker_active(worker, chapter, wave)
    print(mon.render_markdown_badge(), flush=True)
    draft_dir = Path(output_dir).parent / 'drafts'
    stem = f'chuong_{chapter:04d}'
    receipt_file = draft_dir / (stem + '.receipt.json')
    lock = draft_dir / (stem + '.generation.lock')
    locks = ExitStack()
    claimed = False
    started = time.time()
    try:
        source = json.loads(source_file.read_text(encoding='utf-8'))
        segments = validate_source(source)
        from native_oauth.chapter_integrity import validate_source_archive
        validate_source_archive(source)
        source_paragraphs = [segment['source'] for segment in segments]
        if source.get('chapter') != chapter or str(source.get('book_id')) != str(book_id):
            raise ValueError('Source book/chapter identity mismatch')
        predecessor_hash, predecessor = None, ''
        if chapter > 1:
            previous = json.loads((Path(source_dir) / f'source_chapter_{chapter-1:04d}.json').read_text(encoding='utf-8'))
            previous_segments = validate_source(previous)
            if previous.get('chapter') != chapter - 1 or str(previous.get('book_id')) != str(book_id):
                raise ValueError('Predecessor source identity mismatch')
            predecessor_hash = previous['package_hash']
            # Whole original paragraphs only; no unreviewed prior translation as facts.
            selected, size = [], 0
            for segment in reversed(previous_segments):
                if size + len(segment['source']) > 1600:
                    break
                selected.insert(0, segment['id'] + ': ' + segment['source'])
                size += len(segment['source'])
                if len(selected) == 4:
                    break
            predecessor = '\n'.join(selected)
        recipe = digest({'pipeline': recipe_hash(callback, model, genre, Path(source_dir).parent),
                         'predecessor_source_hash': predecessor_hash})
        draft_dir.mkdir(parents=True, exist_ok=True)
        locks.enter_context(file_lock(lock, timeout=1))
        claimed = True
        txt_file, json_file = draft_dir / (stem + '.txt'), draft_dir / (stem + '.dich.json')
        if receipt_file.exists() and not force:
            receipt = json.loads(receipt_file.read_text(encoding='utf-8'))
            candidate = json.loads(json_file.read_text(encoding='utf-8'))
            text = txt_file.read_text(encoding='utf-8')
            if (receipt.get('status') != 'DRAFT_STRUCTURAL_PASS_UNREVIEWED'
                    or receipt.get('recipe_hash') != recipe
                    or receipt.get('candidate_hash') != digest(candidate)
                    or receipt.get('text_hash') != digest(text)
                    or inspect_chapter(source, candidate, text)
                    or read_verified_draft(Path(source_dir).parent, chapter) is None):
                raise ValueError('Draft cache stale/changed/blocked; use --force for an explicit new draft')
            print(f'[CACHE] Verified original draft {chapter}; semantic review still pending')
        else:
            # Keep prior evidence immutable when an explicit rerun is requested.
            if force and receipt_file.exists():
                history = draft_dir / 'history' / f'{stem}_{time.time_ns()}'
                history.mkdir(parents=True)
                for file in (txt_file, json_file, receipt_file):
                    if file.exists():
                        (history / file.name).write_bytes(file.read_bytes())
            chapter_map, scene_receipts = {}, []
            call_count = 0

            def translate(chunk, offset, context, depth=0):
                nonlocal call_count
                call_count += 1
                if call_count > 32:
                    raise ValueError('Chapter scene call budget exhausted')
                try:
                    # Context is recomputed by owned offsets, also for adaptive retries.
                    # Never infer the speaker from previous unreviewed Vietnamese.
                    before = context_tail(source_paragraphs[:offset]) if offset else predecessor
                    following, size = [], 0
                    for paragraph in source_paragraphs[offset + len(chunk):offset + len(chunk) + 2]:
                        if size + len(paragraph) > 1000:
                            break
                        following.append(paragraph)
                        size += len(paragraph)
                    translated, _, passed = callback(call_count, chunk, {
                        'prev_vi': context, 'prev_zh': before, 'next_zh': '\n'.join(following)})
                    if (set(translated) != set(range(1, len(chunk) + 1))
                            or any(not isinstance(t, str) or not t.strip() for t in translated.values())):
                        raise IncompleteNativeOutput('Scene coverage incomplete; discarded entire attempt')
                    if not passed:
                        raise ValueError('Scene quality gate failed; draft quarantined')
                except IncompleteNativeOutput:
                    if depth >= 2 or len(chunk) < 2:
                        raise
                    middle = len(chunk) // 2
                    tail = translate(chunk[:middle], offset, context, depth + 1)
                    return translate(chunk[middle:], offset + middle, tail, depth + 1)
                for local_id, text in translated.items():
                    chapter_map[offset + local_id] = text.strip()
                scene_receipt = {'first': offset + 1, 'last': offset + len(chunk), 'gate': 'STRUCTURAL_PASS'}
                if runtime_root is not None:
                    runtime_file = Path(runtime_root) / f'chapter_{chapter:04d}' / f'scene_{call_count}' / 'runtime/runtime.json'
                    runtime = json.loads(runtime_file.read_text(encoding='utf-8'))
                    response = require_complete_runtime(runtime, model)
                    from native_oauth.chapter_integrity import native_scene_texts
                    if native_scene_texts(response, len(chunk)) != [translated[i] for i in range(1,len(chunk)+1)]:
                        raise ValueError('Draft differs from completed native response')
                    scene_receipt.update(runtime_file=str(runtime_file.resolve()), runtime_hash=digest(runtime))
                scene_receipts.append(scene_receipt)
                return translated[len(chunk)][-800:]

            offset, context = 0, ''
            for chunk in split_scenes([s['source'] for s in segments]):
                context = translate(chunk, offset, context)
                offset += len(chunk)
            alignment = [{'para_id': s['id'], 'index': i, 'raw_zh': s['source'],
                          'translated_vi': chapter_map[i]} for i, s in enumerate(segments, 1)]
            candidate = {'chapter_num': chapter, 'title': alignment[0]['translated_vi'],
                         'source_hash': source['package_hash'], 'total_paragraphs': len(segments),
                         'translated_paragraphs': len(alignment), 'model_used': model,
                         'status': 'DRAFT_STRUCTURAL_PASS_UNREVIEWED', 'bilingual_alignment': alignment}
            text = render_text(alignment)
            current_source = json.loads(source_file.read_text(encoding='utf-8'))
            if current_source != source:
                raise ValueError('Source changed during generation; discard stale draft')
            if chapter > 1:
                current_previous = json.loads((Path(source_dir) / f'source_chapter_{chapter-1:04d}.json').read_text(encoding='utf-8'))
                validate_source(current_previous)
                if current_previous['package_hash'] != predecessor_hash:
                    raise ValueError('Predecessor source changed during generation')
            errors = inspect_chapter(source, candidate, text)
            if errors:
                raise ValueError('Final chapter verification failed: ' + ', '.join(errors))
            atomic_text(txt_file, text)
            atomic_json(json_file, candidate)
            atomic_json(receipt_file, {'status': candidate['status'], 'recipe_hash': recipe,
                                      'candidate_hash': digest(candidate), 'text_hash': digest(text),
                                      'source_hash': source['package_hash'], 'predecessor_source_hash': predecessor_hash,
                                      'scenes': scene_receipts})
        if json.loads(source_file.read_text(encoding='utf-8')) != source:
            raise ValueError('Source changed before completion acknowledgement')
        if recipe != digest({'pipeline': recipe_hash(callback, model, genre, Path(source_dir).parent),
                             'predecessor_source_hash': predecessor_hash}):
            raise ValueError('Pipeline/lore changed during execution; draft needs a new run')
        mon.record_chapter_done(chapter, candidate['title'], wave, worker, len(segments),
                                len(text.split()), time.time() - started, gate_pass=True)
        print(f'[DRAFT] {chapter}: complete structure; independent semantic review pending')
        print(mon.render_markdown_badge(), flush=True)
        return True
    except Exception as error:
        # BLOCKED receipt invalidates any older TXT/JSON surviving an interrupted write.
        if claimed:
            if receipt_file.exists():
                previous_receipt = receipt_file.with_name(receipt_file.name + f'.history.{time.time_ns()}.json')
                previous_receipt.write_bytes(receipt_file.read_bytes())
            atomic_json(receipt_file, {'status': 'BLOCKED', 'reason': str(error), 'chapter': chapter})
        mon.record_chapter_done(chapter, f'BLOCKED: {error}', wave, worker, 0, 0,
                                time.time() - started, gate_pass=False)
        print(f'[BLOCKED] Chapter {chapter}: {error}', flush=True)
        print(mon.render_markdown_badge(), flush=True)
        return False
    finally:
        locks.close()
