"""Review verified book drafts entirely in Antigravity, then promote approved.

This command makes native model calls. It never edits source or legacy TXT.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from semantic_gate import build_package, digest, evaluate, make_context, publish, write_json
from native_oauth.chapter_integrity import (atomic_json, atomic_text, inspect_chapter,
    read_verified_draft, require_approved, validate_source)
from native_oauth.native_evidence import runtime_record
from native_oauth.native_review import run_independent_reviews, visible_stage
from native_oauth.semantic_context import normalize_profile
from native_oauth.approved_context import retrieve_context
from native_oauth.workflow_io import file_lock


def bound_files(paths):
    return {str(Path(p).resolve()): hashlib.sha256(Path(p).read_bytes()).hexdigest() if Path(p).exists() else None
            for p in paths}


def prepare_review(book_dir, chapter):
    book_dir = Path(book_dir).resolve()
    verified = read_verified_draft(book_dir, chapter)
    if verified is None:
        raise ValueError('A verified complete draft receipt is required; legacy output is not a draft cache')
    aligned, text = verified
    source_file = book_dir/'sources'/f'source_chapter_{chapter:04d}.json'
    source = json.loads(source_file.read_text(encoding='utf-8'))
    validate_source(source)
    if source.get('chapter') != chapter:
        raise ValueError('Chapter identity mismatch')
    context = None
    previous_evidence = None
    if chapter > 1:
        from native_oauth.book_publication import read_approval
        previous_evidence = str(read_approval(book_dir, chapter-1)['evidence_path'])
    lore_file = book_dir/'lore.json'
    lore = json.loads(lore_file.read_text(encoding='utf-8')) if lore_file.exists() else {}
    entities, _, terms = normalize_profile(source['book_id'], [], [], lore)
    if previous_evidence:
        context = retrieve_context(book_dir, chapter, previous_evidence, entities,
                                   '\n'.join(s['source'] for s in source['segments']))
    # Slash alternatives are editorial suggestions, not a literal hard lock.
    glossary = {k: v for k, (v, _) in terms.items() if ' / ' not in v}
    package = build_package(chapter, source['title'], [s['source'] for s in source['segments']],
                            glossary, source.get('source_ref', ''), context)
    package.update(book_id=source['book_id'], book_title=lore.get('book_title_vi', book_dir.name),
                   genre=lore.get('genre', 'Theo nguồn'), origin_source_hash=source['package_hash'],
                   native_bound_files=bound_files([source_file, lore_file,
                                      Path(__file__).with_name('semantic_profiles.json')]))
    package['package_hash'] = digest({k: v for k, v in package.items() if k != 'package_hash'})
    receipt = json.loads((book_dir/'drafts'/f'chuong_{chapter:04d}.receipt.json').read_text(encoding='utf-8'))
    scenes = receipt.get('scenes', [])
    coverage = [i for s in scenes for i in range(s['first'], s['last'] + 1)]
    if coverage != list(range(1, len(source['segments']) + 1)):
        raise ValueError('Native scene receipt coverage mismatch')
    candidate = {'package_hash': package['package_hash'], 'model': 'native/' + aligned['model_used'],
                 'identity_basis': 'native_cli_init',
                 'native_runtimes': [runtime_record(s['runtime_file'], aligned['model_used']) for s in scenes],
                 'native_scene_ownership': [{'ids':[row['id'] for row in source['segments'][s['first']-1:s['last']]]} for s in scenes],
                 'segments': [{'id': s['para_id'], 'text': s['translated_vi']} for s in aligned['bilingual_alignment']]}
    return source, aligned, text, package, candidate


def review_and_promote(book_dir, chapter, reviewer_model='gemini-3.8-flash-high',
                       auditor_model='gemini-3.8-flash-medium', timeout=420):
    book_dir = Path(book_dir).resolve()
    with file_lock(book_dir/f'.review_chapter_{chapter:04d}.lock', timeout=1):
        return _review_and_promote(book_dir, chapter, reviewer_model, auditor_model, timeout)


def _review_and_promote(book_dir, chapter, reviewer_model, auditor_model, timeout):
    book_dir = Path(book_dir).resolve()
    source, aligned, text, package, candidate = prepare_review(book_dir, chapter)
    workspace = book_dir/'native_review_jobs'/uuid.uuid4().hex
    workspace.mkdir(parents=True)
    data = workspace/'inputs'
    data.mkdir()
    write_json(data/'source.json', package)
    write_json(data/'draft.json', candidate)
    policy = {'mode': 'antigravity_sessions', 'version': 1}
    try:
        from semantic_gate import mechanical_findings, review_prompt
        findings = mechanical_findings(package, candidate)
        if findings:
            raise ValueError('Draft mechanical findings: ' + json.dumps(findings, ensure_ascii=False))
        if len(review_prompt(package, candidate)) > 120000:
            raise ValueError('Review context exceeds budget; compact sourced context explicitly')
        reviews = run_independent_reviews(package, candidate, data, workspace,
                                          reviewer_model, auditor_model, timeout)
        report = evaluate(package, candidate, reviews, review_policy=policy)
        write_json(workspace/'qa.json', report)
        if report['status'] != 'PASS':
            raise ValueError('Independent reviews blocked promotion; inspect ' + str(workspace/'qa.json'))
        with visible_stage(package, 'approval'):
            # Check source, candidate and canon again after reviewers finish.
            frozen = prepare_review(book_dir, chapter)
            if frozen[0] != source or frozen[1] != aligned or frozen[3] != package or frozen[4] != candidate:
                raise ValueError('Source/draft/context changed while reviewing')
            output = publish(package, candidate, reviews, workspace/'accepted', review_policy=policy)
            aligned = {**aligned, 'status': 'APPROVED', 'review_evidence': str(output.with_suffix('.evidence.json'))}
            require_approved(source, aligned, text, book_dir)
            from native_oauth.book_publication import commit_approval
            evidence = json.loads(Path(aligned['review_evidence']).read_text(encoding='utf-8'))
            approved_path = commit_approval(book_dir, source, aligned, text, evidence)
        write_json(workspace/'state.json', {'status': 'APPROVED', 'chapter': chapter})
        return approved_path
    except Exception as error:
        write_json(workspace/'state.json', {'status': 'BLOCKED', 'reason': str(error)})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--book-dir', required=True)
    parser.add_argument('--chapter', type=int)
    parser.add_argument('--from-chapter', type=int)
    parser.add_argument('--to-chapter', type=int)
    parser.add_argument('--reviewer-model', default='gemini-3.8-flash-high')
    parser.add_argument('--auditor-model', default='gemini-3.8-flash-medium')
    parser.add_argument('--timeout', type=int, default=420)
    args = parser.parse_args()
    if args.chapter is not None:
        if args.from_chapter is not None or args.to_chapter is not None:
            parser.error('Choose one chapter or a consecutive range')
        chapters = [args.chapter]
    else:
        if args.from_chapter is None or args.to_chapter is None:
            parser.error('Provide --chapter or --from-chapter/--to-chapter')
        if not 1 <= args.to_chapter - args.from_chapter + 1 <= 20:
            parser.error('One review run is limited to 20 consecutive chapters')
        chapters = range(args.from_chapter, args.to_chapter + 1)
    for chapter in chapters:
        if chapter < 1:
            parser.error('Chapter must be positive')
        print(review_and_promote(args.book_dir, chapter, args.reviewer_model, args.auditor_model, args.timeout))


if __name__ == '__main__':
    main()
