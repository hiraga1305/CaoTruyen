"""Shared source/coverage boundary for draft cache, audit and book export."""
import json
from pathlib import Path
from semantic_gate import digest, evaluate
from native_oauth.workflow_io import atomic_json, atomic_text


def source_content_hash(source):
    return digest({key: source[key] for key in ('book_id', 'chapter', 'source_ref', 'segments')})


def validate_source(source):
    if not isinstance(source, dict):
        raise ValueError('Invalid source object')
    if source.get('package_hash') != digest({k: v for k, v in source.items() if k != 'package_hash'}):
        raise ValueError('Source package hash mismatch')
    segments = source.get('segments', [])
    if not isinstance(segments, list) or any(not isinstance(s, dict) for s in segments):
        raise ValueError('Invalid source segments')
    ids = [s.get('id') for s in segments]
    if (not segments or any(not isinstance(i, str) or not i for i in ids)
            or len(set(ids)) != len(ids)
            or any(not isinstance(s.get('source'), str) or not s['source'].strip() for s in segments)):
        raise ValueError('Empty/duplicate/invalid source segments')
    if source.get('version') in ('bns-source-v1', 'bns-source-v2'):
        chapter = source.get('chapter')
        if type(chapter) is not int or chapter < 1 or not source.get('book_id') or not source.get('source_ref'):
            raise ValueError('Invalid source identity')
        if ids != [f'c{chapter:04d}p{i:04d}' for i in range(1,len(segments)+1)] or source.get('paragraph_count') != len(segments):
            raise ValueError('Source IDs/order/count mismatch')
    if source.get('version') == 'bns-source-v2':
        if source.get('content_hash') != source_content_hash(source):
            raise ValueError('Source content hash mismatch')
        mapping = source.get('normalization', {})
        rows = mapping.get('segment_map', [])
        if not mapping.get('parser_version') or [r.get('id') for r in rows] != ids:
            raise ValueError('Invalid source normalization map')
        indices = [i for row in rows for i in row.get('raw_indices', [])]
        removed = [row.get('raw_index') for row in mapping.get('excluded', [])]
        if (any(type(i) is not int or i < 1 for i in indices+removed)
                or len(set(indices)) != len(indices)
                or sorted(set(indices+removed)) != list(range(1,mapping.get('raw_paragraph_count',0)+1))):
            raise ValueError('Normalization loses/duplicates original source paragraphs')
    return segments


def validate_source_archive(source):
    """V2 source rows/mapping must be reproducible from the archived raw HTML."""
    if source.get('version') != 'bns-source-v2':
        return
    import hashlib
    from native_oauth.source_adapters import extract_paragraphs, normalize_paragraphs, PARSER_VERSION
    name = source.get('raw_archive', '')
    if not name or Path(name).name != name:
        raise ValueError('Invalid raw source archive path')
    archive = Path(__file__).resolve().parents[1]/'source_archive'/('book_'+str(source['book_id']))/name
    raw = archive.read_bytes()
    if hashlib.sha256(raw).hexdigest() != source.get('raw_sha256'):
        raise ValueError('Raw source archive hash mismatch')
    rows, mapping = normalize_paragraphs(extract_paragraphs(raw.decode('utf-8', errors='strict')), source['chapter'])
    if source['normalization'].get('parser_version') != PARSER_VERSION or rows != source['segments'] or mapping != source['normalization']:
        raise ValueError('Source cannot be reproduced from raw HTML/normalization mapping')


def render_text(alignment):
    return '\n\n'.join(s['translated_vi'] for s in alignment) + '\n'


def inspect_chapter(source, candidate, text=None):
    """Collect actual defects; self-declared paragraph totals are not evidence."""
    findings = []
    try:
        segments = validate_source(source)
    except (ValueError, KeyError, TypeError) as error:
        return ['SOURCE_INVALID: ' + str(error)]
    alignment = candidate.get('bilingual_alignment', [])
    if not isinstance(alignment, list) or any(not isinstance(s, dict) for s in alignment):
        return ['INVALID_ALIGNMENT']
    expected = [s['id'] for s in segments]
    if [s.get('para_id') for s in alignment] != expected:
        findings.append('COVERAGE_IDS')
    if [s.get('raw_zh') for s in alignment] != [s['source'] for s in segments]:
        findings.append('SOURCE_ALIGNMENT')
    if any(not isinstance(s.get('translated_vi'), str) or not s['translated_vi'].strip() for s in alignment):
        findings.append('EMPTY_TRANSLATION')
    if candidate.get('source_hash') != source['package_hash']:
        findings.append('SOURCE_HASH')
    if candidate.get('chapter_num') != source.get('chapter'):
        findings.append('CHAPTER_IDENTITY')
    if (candidate.get('total_paragraphs') != len(segments)
            or candidate.get('translated_paragraphs') != len(alignment)):
        findings.append('DECLARED_COUNTS')
    if text is not None and not findings and text != render_text(alignment):
        findings.append('TEXT_ALIGNMENT')
    return findings


def read_verified_draft(book_dir, chapter):
    book_dir = Path(book_dir)
    stem = f'chuong_{chapter:04d}'
    folder = book_dir / 'drafts'
    try:
        receipt = json.loads((folder / (stem + '.receipt.json')).read_text(encoding='utf-8'))
        candidate = json.loads((folder / (stem + '.dich.json')).read_text(encoding='utf-8'))
        text = (folder / (stem + '.txt')).read_text(encoding='utf-8')
        source = json.loads((book_dir / 'sources' / f'source_chapter_{chapter:04d}.json').read_text(encoding='utf-8'))
        validate_source_archive(source)
        if (receipt.get('status') != 'DRAFT_STRUCTURAL_PASS_UNREVIEWED'
                or receipt.get('candidate_hash') != digest(candidate)
                or receipt.get('text_hash') != digest(text)
                or receipt.get('source_hash') != source['package_hash']
                or inspect_chapter(source, candidate, text)):
            return None
        if chapter > 1:
            predecessor = json.loads((book_dir / 'sources' / f'source_chapter_{chapter-1:04d}.json').read_text(encoding='utf-8'))
            validate_source(predecessor)
            if receipt.get('predecessor_source_hash') != predecessor['package_hash']:
                return None
        from native_oauth.run_agy import require_complete_runtime
        for scene in receipt.get('scenes', []):
            if scene.get('runtime_file'):
                runtime = json.loads(Path(scene['runtime_file']).read_text(encoding='utf-8'))
                if digest(runtime) != scene.get('runtime_hash'):
                    return None
                require_complete_runtime(runtime, candidate['model_used'])
                first, last = scene['first'], scene['last']
                expected = [row['translated_vi'] for row in candidate['bilingual_alignment'][first-1:last]]
                if native_scene_texts(runtime['result']['response'], last-first+1) != expected:
                    return None
        return candidate, text
    except (OSError, ValueError, KeyError, TypeError):
        return None


def require_approved(source, candidate, text, directory):
    findings = inspect_chapter(source, candidate, text)
    if findings:
        raise ValueError('Chapter integrity blocked: ' + ', '.join(findings))
    evidence_path = candidate.get('review_evidence')
    if not evidence_path:
        raise ValueError('Publication requires independent source-bound review evidence; structural PASS is a draft')
    evidence_path = Path(evidence_path)
    if not evidence_path.is_absolute():
        evidence_path = Path(directory) / evidence_path
    evidence = json.loads(evidence_path.read_text(encoding='utf-8'))
    package, draft = evidence['package'], evidence['candidate']
    from native_oauth.title_selection import require_reviewed_selection
    require_reviewed_selection(source,candidate,package)
    if (evidence.get('review_policy', {}).get('mode') == 'antigravity_sessions'
            and package.get('origin_source_hash') != source['package_hash']):
        raise ValueError('Review envelope does not bind the original book source package')
    if (package['segments'] != [{key: row[key] for key in ('id','source')} for row in source['segments']] or package['chapter'] != source['chapter']
            or draft['segments'] != [{'id': s['para_id'], 'text': s['translated_vi']}
                                     for s in candidate['bilingual_alignment']]):
        raise ValueError('Review evidence belongs to different source/candidate')
    report = evaluate(package, draft, evidence['reviews'], review_policy=evidence.get('review_policy'))
    if report['status'] != 'PASS':
        raise ValueError('Independent review did not pass')
    return report


def native_scene_texts(response, count):
    """Replay only formatting cleanup on the actual response; never guess meaning."""
    from native_oauth.quality_gate import QualityGate4A
    from native_oauth.scene_contract import SceneContract
    contract = SceneContract(0, 0, 'LOW', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN', 'UNKNOWN',
                             'UNKNOWN', '', 'UNKNOWN', 'UNKNOWN')
    result = QualityGate4A().verify_paragraphs(response, count, contract)
    if not result.is_pass:
        raise ValueError('Recorded native response failed structural replay')
    return [result.sanitized_paragraphs[i] for i in range(1,count+1)]
