"""Immutable book approvals with an atomic manifest as the publication commit point.

Combines the G-copy revision/manifest design with the source-bound native review
gate. No file-existence or legacy sidecar may grant approval.
"""
import hashlib
import json
import re
from pathlib import Path
from semantic_gate import candidate_hash, digest, read_json
from native_oauth.workflow_io import atomic_json, atomic_text, file_lock
from native_oauth.chapter_integrity import require_approved, validate_source, validate_source_archive
from native_oauth.title_selection import chapter_number, validate_selection

SCHEMA = 'antigravity-book-publication-1'
TITLE_RE = re.compile(r'^(?:\d+\s*[.．]\s*)?第\s*[零一二三四五六七八九十百千\d]+\s*[章回節节]')


def sha_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_manifest(book_dir):
    path = Path(book_dir)/'approved/manifest.json'
    if not path.exists():
        return {'schema': SCHEMA, 'chapters': {}}
    manifest = read_json(path)
    if manifest.get('schema') != SCHEMA or not isinstance(manifest.get('chapters'), dict):
        raise ValueError('Invalid book approval manifest')
    if any(not re.fullmatch(r'[1-9]\d*', key) for key in manifest['chapters']):
        raise ValueError('Invalid chapter key in manifest')
    return manifest


def contained_file(book_dir, name):
    book = Path(book_dir).resolve()
    path = (book/name).resolve()
    if not path.is_relative_to(book):
        raise ValueError('Approval path escapes book')
    return path


def title_ids(source):
    from native_oauth.source_adapters import clean_title as canonical
    expected = canonical(source['title'])
    # V2 reconstructs paragraphs from the actual .content HTML. TOC metadata
    # can be truncated or lose a caret; it must not overrule that article title.
    if source.get('version')=='bns-source-v2' and chapter_number(source['segments'][0]['source'])==source['chapter']:
        expected=canonical(source['segments'][0]['source'])
    result = []
    for row in source['segments'][:2]:
        title = canonical(row['source'])
        if TITLE_RE.match(row['source'].strip()) and title == expected:
            result.append(row['id'])
        else:
            break
    return result


def rendered_chapter(source, aligned):
    selection=aligned.get('render_title_ownership')
    if selection is not None:
        validate_selection(source,selection)
        excluded=selection['title_segment_ids'];primary=selection['primary_title_id']
    else:
        excluded=title_ids(source);primary=excluded[0] if excluded else None
    targets = {row['para_id']: row['translated_vi'] for row in aligned['bilingual_alignment']}
    title = targets[primary] if primary else aligned.get('title_vi')
    if not isinstance(title, str) or not title.strip():
        raise ValueError('No source title segment: an independently reviewed title_vi is required')
    title = re.sub(r'^Chương\s+\d+\s*:?\s*', '', title.strip(), flags=re.I)
    title = f"Chương {source['chapter']}: {title}" if title else f"Chương {source['chapter']}"
    body = [row for row in aligned['bilingual_alignment'] if row['para_id'] not in excluded]
    return {'num': source['chapter'], 'title': title,
            'paragraphs': [row['translated_vi'] for row in body],
            'segment_ids': [row['para_id'] for row in body], 'title_segment_ids': excluded}


def read_approval(book_dir, chapter):
    book = Path(book_dir).resolve()
    manifest = read_manifest(book)
    entry = manifest['chapters'].get(str(chapter))
    if not entry:
        raise ValueError(f'Chapter {chapter} has no committed independent approval')
    receipt_file = contained_file(book, entry['receipt'])
    receipt = read_json(receipt_file)
    if (digest(receipt) != entry['receipt_hash'] or receipt.get('status') != 'APPROVED'
            or receipt.get('chapter') != chapter):
        raise ValueError('Approval receipt changed')
    directory = receipt_file.parent
    aligned = read_json(directory/'chapter.dich.json')
    source = read_json(book/'sources'/f'source_chapter_{chapter:04d}.json')
    validate_source(source)
    validate_source_archive(source)
    text = (directory/'chapter.txt').read_text(encoding='utf-8')
    evidence = read_json(directory/'evidence.json')
    if (receipt['source_hash'] != source['package_hash'] or receipt['candidate_hash'] != digest(aligned)
            or receipt['text_hash'] != digest(text) or receipt['evidence_hash'] != digest(evidence)
            or Path(aligned['review_evidence']).resolve() != (directory/'evidence.json').resolve()):
        raise ValueError('Approved source/candidate/text/evidence changed')
    require_approved(source, aligned, text, directory)
    if chapter > 1:
        prior = manifest['chapters'].get(str(chapter-1))
        if not prior:
            raise ValueError('Predecessor is not committed')
        prior_path = contained_file(book, prior['receipt'])
        prior_receipt = read_json(prior_path)
        if (digest(prior_receipt) != prior['receipt_hash'] or
                evidence['package']['context']['previous_approved_hash'] != prior_receipt['reviewed_candidate_hash']):
            raise ValueError('Predecessor revision changed')
    return {'source': source, 'aligned': aligned, 'text': text, 'evidence': evidence,
            'evidence_path': directory/'evidence.json', 'path': directory/'chapter.dich.json',
            'receipt': receipt, 'rendered': rendered_chapter(source, aligned)}


def commit_approval(book_dir, source, aligned, text, evidence):
    book = Path(book_dir).resolve()
    chapter = source['chapter']
    revision = digest(evidence)
    target = book/'approved'/f'chuong_{chapter:04d}'/revision
    with file_lock(book/'approved/manifest.lock'):
        current = read_json(book/'sources'/f'source_chapter_{chapter:04d}.json')
        if current != source:
            raise ValueError('Source changed before manifest commit')
        if chapter > 1:
            prior = read_approval(book, chapter-1)
            if evidence['package']['context']['previous_approved_hash'] != candidate_hash(prior['evidence']['candidate']):
                raise ValueError('Predecessor changed during review')
        aligned = {**aligned, 'status': 'APPROVED', 'review_evidence': str(target/'evidence.json')}
        rendered_chapter(source, aligned)
        target.mkdir(parents=True, exist_ok=True)
        artifacts = {'evidence.json': evidence, 'chapter.dich.json': aligned}
        for name, value in artifacts.items():
            path = target/name
            if path.exists() and read_json(path) != value:
                raise ValueError('Immutable revision collision')
            atomic_json(path, value)
        if (target/'chapter.txt').exists() and (target/'chapter.txt').read_text(encoding='utf-8') != text:
            raise ValueError('Immutable text collision')
        atomic_text(target/'chapter.txt', text)
        require_approved(source, aligned, text, target)
        receipt = {'schema': SCHEMA, 'status': 'APPROVED', 'chapter': chapter,
                   'source_hash': source['package_hash'], 'candidate_hash': digest(aligned),
                   'reviewed_candidate_hash': candidate_hash(evidence['candidate']),
                   'text_hash': digest(text), 'evidence_hash': digest(evidence)}
        atomic_json(target/'receipt.json', receipt)
        manifest = read_manifest(book)
        entry = {'receipt': (target/'receipt.json').relative_to(book).as_posix(), 'receipt_hash': digest(receipt)}
        if manifest['chapters'].get(str(chapter)) != entry:
            manifest['chapters'] = {key: val for key, val in manifest['chapters'].items() if int(key) <= chapter}
        manifest['chapters'][str(chapter)] = entry
        atomic_json(book/'approved/manifest.json', manifest)
    return target/'chapter.dich.json'


def load_approved_chapters(book_dir, expected_chapters):
    expected = list(expected_chapters)
    if not expected or expected != list(range(1, expected[-1]+1)):
        raise ValueError('Full-book export requires a continuous range from chapter 1')
    if sorted(map(int, read_manifest(book_dir)['chapters'])) != expected:
        raise ValueError('Approved manifest has missing/extra chapters')
    return [read_approval(book_dir, chapter)['rendered'] for chapter in expected]
