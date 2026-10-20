"""Deterministic, source-grounded contracts for bounded parallel translation.

This module checks provenance/ownership/commit order, not translation semantics.
No generated summary, parser prediction, or worker self-score is authority.
"""
import copy
import re

from semantic_gate import digest

VERSION = 'batch-contract-1'
ID_PATTERN = re.compile(r'^c(\d+)p(\d+)$')
KINDS = {'entity', 'relation', 'event', 'concept'}
ANCHOR_PATTERN = re.compile(r'[0-9零〇一二三四五六七八九十百千万亿两]+(?:[.,点][0-9]+)?|至少|至多|不得|不能|没有|并非|不再|尚未|未曾|超过')


def source_anchor_candidates(source):
    """Lexical evidence to inspect; never a Chinese-to-Vietnamese truth oracle.

    Chinese number characters occur in idioms too. These candidates therefore
    MUST NOT automatically reject a translation or substitute for semantic checks.
    """
    return [{'quote': m.group(), 'start': m.start(), 'end': m.end(),
             'context': source[max(0, m.start()-12):m.end()+12],
             'status': 'lexical_candidate_requires_context'} for m in ANCHOR_PATTERN.finditer(source)]


def _sealed(value, key):
    result = copy.deepcopy(value)
    result[key] = digest(result)
    return result


def _check_seal(value, key):
    if value.get(key) != digest({k: v for k, v in value.items() if k != key}):
        raise ValueError('Changed or unsealed ' + key)


def _sources(packages):
    """Accept source-bound packages without requiring a previous VN translation."""
    index, registry, chapters = {}, {}, []
    for package in packages:
        _check_seal(package, 'package_hash')
        chapter = package['chapter']
        if type(chapter) is not int or chapter < 1 or chapter in chapters:
            raise ValueError('Invalid or duplicate chapter')
        chapters.append(chapter)
        registry[str(chapter)] = package['package_hash']
        segments = package.get('segments', [])
        if not segments:
            raise ValueError('Empty chapter')
        for ordinal, segment in enumerate(segments, 1):
            identifier, source = segment['id'], segment['source']
            match = ID_PATTERN.fullmatch(identifier)
            if (not match or tuple(map(int, match.groups())) != (chapter, ordinal)
                    or identifier in index or not isinstance(source, str) or not source.strip()):
                raise ValueError('Invalid source paragraph ownership/order')
            index[identifier] = {'id': identifier, 'chapter': chapter, 'source': source,
                                 'source_hash': digest(source), 'package_hash': package['package_hash']}
    if chapters != sorted(chapters):
        raise ValueError('Chapters must be in source order')
    return index, registry, chapters


def _ledger(entries, source_index):
    result, identifiers = [], set()
    for supplied in entries:
        entry = copy.deepcopy(supplied)
        allowed = {'ledger_id', 'kind', 'keys', 'references', 'required', 'global_required',
                   'valid_from', 'previous_entry_hash', 'interpretation'}
        if set(entry) - allowed:
            raise ValueError('Unknown ledger fields; evidence must not hide unsourced assertions')
        identifier = entry.get('ledger_id')
        if not isinstance(identifier, str) or not identifier or identifier in identifiers:
            raise ValueError('Missing or duplicate ledger id')
        identifiers.add(identifier)
        if entry.get('kind') not in KINDS:
            raise ValueError('Unknown ledger kind')
        keys = entry.get('keys', [])
        if not isinstance(keys, list) or not keys or any(not isinstance(k, str) or not k for k in keys):
            raise ValueError('Ledger retrieval keys required')
        references = entry.get('references', [])
        if not isinstance(references, list) or not references:
            raise ValueError('Ledger must have original source evidence')
        bound = []
        for reference in references:
            raw = source_index.get(reference.get('source_id'))
            quote = reference.get('source_quote')
            if not raw or not isinstance(quote, str) or not quote.strip() or quote not in raw['source']:
                raise ValueError('Ledger quote not found in original source')
            if 'chapter' in reference and reference['chapter'] != raw['chapter']:
                raise ValueError('Ledger chapter disagrees with source id')
            bound.append({'chapter': raw['chapter'], 'source_id': raw['id'],
                          'source_quote': quote, 'source_hash': raw['source_hash'],
                          'source_package_hash': raw['package_hash']})
        entry['references'] = bound
        quoted_text = '\n'.join(r['source_quote'] for r in bound)
        if any(k not in quoted_text for k in keys):
            raise ValueError('Retrieval keys must occur in the original evidence quotes')
        earliest = min(bound, key=lambda r: tuple(map(int, ID_PATTERN.fullmatch(r['source_id']).groups())))
        valid_from = entry.get('valid_from', earliest['source_id'])
        if valid_from not in source_index:
            raise ValueError('Ledger valid_from needs a verified source position')
        if tuple(map(int, ID_PATTERN.fullmatch(valid_from).groups())) < tuple(map(int, ID_PATTERN.fullmatch(earliest['source_id']).groups())):
            raise ValueError('Ledger cannot become visible before its evidence')
        entry['valid_from'] = valid_from
        # A generated interpretation may help retrieval, but cannot replace evidence.
        entry['authority'] = 'quoted_original_source_only'
        if 'interpretation' in entry:
            entry['interpretation_status'] = 'advisory_unverified'
        entry.pop('entry_hash', None)
        result.append(_sealed(entry, 'entry_hash'))
    return sorted(result, key=lambda e: e['ledger_id'])


def build_story_state(source_packages, ledger_entries, glossary, style_profile,
                      version=1, through_chapter=0):
    """Create a state from ORIGINAL Chinese evidence and editorial policy.

    Source prepass may include uncommitted chapters. through_chapter represents
    the published barrier, not the furthest chapter the source reader has seen.
    """
    source_index, registry, chapters = _sources(source_packages)
    if type(version) is not int or version < 1 or type(through_chapter) is not int or through_chapter < 0:
        raise ValueError('Invalid state version/barrier')
    if through_chapter and through_chapter not in chapters:
        raise ValueError('Published barrier missing source provenance')
    if not isinstance(glossary, dict) or any(not isinstance(k, str) or not k or
            not isinstance(v, str) or not v for k, v in glossary.items()):
        raise ValueError('Invalid terminology policy')
    return _sealed({'schema': VERSION, 'version': version, 'through_chapter': through_chapter,
                    'source_registry': registry, 'ledger': _ledger(ledger_entries, source_index),
                    'glossary': copy.deepcopy(glossary), 'style_profile': copy.deepcopy(style_profile),
                    'authority': 'original_source; glossary/style are editorial choices',
                    'previous_state_hash': None}, 'state_hash')


def _capsule(state, owned_source, neighbors, max_chars, max_entries):
    relevant_source = owned_source + neighbors
    text = '\n'.join(s['source'] for s in relevant_source)
    cutoff = tuple(map(int, ID_PATTERN.fullmatch(owned_source[-1]['id']).groups()))
    visible = []
    for entry in state['ledger']:
        onset = tuple(map(int, ID_PATTERN.fullmatch(entry['valid_from']).groups()))
        if onset > cutoff:
            continue
        # Even an earlier event must not disclose a future confirming quote.
        shown = copy.deepcopy(entry)
        shown['references'] = [r for r in entry['references'] if
                               tuple(map(int, ID_PATTERN.fullmatch(r['source_id']).groups())) <= cutoff]
        if shown['references']:
            shown.pop('interpretation', None)
            shown.pop('interpretation_status', None)
            quoted = '\n'.join(r['source_quote'] for r in shown['references'])
            shown['keys'] = [k for k in shown['keys'] if k in quoted]
            shown['full_entry_hash'] = shown.pop('entry_hash')
            shown['entry_hash'] = digest({k: v for k, v in shown.items() if k != 'entry_hash'})
            visible.append(shown)
    relevant = [e for e in visible if any(k in text for k in e['keys']) or e.get('global_required')]
    mandatory = [e for e in relevant if e.get('required', True)]
    optional = [e for e in relevant if e not in mandatory]
    # Recent source evidence is helpful even without a repeating name.
    recent = sorted((e for e in visible if e not in relevant),
                    key=lambda e: (max(r['chapter'] for r in e['references']), e['ledger_id']), reverse=True)
    base = {'state_hash': state['state_hash'], 'state_version': state['version'],
            'through_chapter': state['through_chapter'],
            'glossary': {k: v for k, v in sorted(state['glossary'].items()) if k in text},
            'style_profile': copy.deepcopy(state['style_profile']), 'ledger': [],
            'source_visibility_through': owned_source[-1]['id'],
            'authority': 'Original source outranks interpretations and parser predictions.',
            'omitted_optional_entries': 0}
    def size(value):
        import json
        return len(json.dumps(value, ensure_ascii=False, sort_keys=True))
    base['ledger'] = copy.deepcopy(mandatory)
    if len(mandatory) > max_entries or size(base) > max_chars:
        raise ValueError('Mandatory story state exceeds capsule budget; narrow the block')
    for entry in optional + recent:
        candidate = copy.deepcopy(base)
        candidate['ledger'].append(copy.deepcopy(entry))
        if len(candidate['ledger']) <= max_entries and size(candidate) <= max_chars:
            base = candidate
        else:
            base['omitted_optional_entries'] += 1
    while size(base) > max_chars and len(base['ledger']) > len(mandatory):
        base['ledger'].pop()
        base['omitted_optional_entries'] += 1
    if size(base) > max_chars:
        raise ValueError('Mandatory story state exceeds capsule budget')
    return base


def make_scene_contract(state, source_packages, owned_ids, overlap=2,
                        max_capsule_chars=12000, max_capsule_entries=80, max_source_chars=20000,
                        job_id=None):
    """Create a source-contiguous experimental scene contract, never a commit plan.

    This permits locked excerpts from later chapters without claiming all prior
    chapters were translated or approved. Production commits require a full plan.
    """
    _check_seal(state, 'state_hash')
    index, registry, _ = _sources(source_packages)
    if type(overlap) is not int or overlap < 0 or not owned_ids:
        raise ValueError('Invalid scene overlap/ownership')
    for chapter, source_hash in registry.items():
        if chapter in state['source_registry'] and state['source_registry'][chapter] != source_hash:
            raise ValueError('Source prepass changed; invalidate the state first')
    identifiers = list(index)
    if any(identifier not in index for identifier in owned_ids):
        raise ValueError('Unknown scene source id')
    positions = [identifiers.index(identifier) for identifier in owned_ids]
    if positions != list(range(positions[0], positions[-1]+1)):
        raise ValueError('Scene ownership must be contiguous and in source order')
    rows = list(index.values())
    start, stop = positions[0], positions[-1]+1
    owned, neighbors = rows[start:stop], rows[max(0, start-overlap):start]+rows[stop:stop+overlap]
    if sum(len(s['source']) for s in owned+neighbors) > max_source_chars:
        raise ValueError('Owned source plus overlap exceeds budget; narrow the scene, never truncate')
    owned = [{**s, 'source_anchor_candidates': source_anchor_candidates(s['source'])} for s in owned]
    return _sealed({'job_id': job_id or f"scene-{owned_ids[0]}-{owned_ids[-1]}",
                    'state_hash': state['state_hash'], 'state_version': state['version'],
                    'owned_segments': copy.deepcopy(owned), 'neighbor_segments': copy.deepcopy(neighbors),
                    'context_capsule': _capsule(state, owned, neighbors, max_capsule_chars, max_capsule_entries),
                    'output_rule': 'Emit exactly owned ids in source order; neighbors are read-only.',
                    'retry_rule': 'Regenerate this whole bounded scene; never patch paragraphs in place.',
                    'experimental_partial_scene': True}, 'contract_hash')


def plan_parallel_block(state, source_packages, max_owned_paragraphs=32, overlap=2,
                        max_capsule_chars=12000, max_capsule_entries=80, max_source_chars=20000,
                        scene_end_ids=None):
    """Freeze one state snapshot for every worker; overlap is read-only.

    Parallelism is inside a bounded block of consecutive chapters. All workers
    receive Chinese neighbors, never another worker's unapproved VN draft.
    """
    _check_seal(state, 'state_hash')
    for value, minimum in ((max_owned_paragraphs, 1), (overlap, 0),
                           (max_capsule_chars, 1), (max_capsule_entries, 1)):
        if type(value) is not int or value < minimum:
            raise ValueError('Invalid block budget')
    if type(max_source_chars) is not int or max_source_chars < 1:
        raise ValueError('Invalid source character budget')
    index, registry, chapters = _sources(source_packages)
    if not chapters or chapters != list(range(state['through_chapter'] + 1, chapters[-1] + 1)):
        raise ValueError('Block must begin immediately after published chapter barrier')
    for chapter, package_hash in registry.items():
        if chapter in state['source_registry'] and state['source_registry'][chapter] != package_hash:
            raise ValueError('Source prepass changed; invalidate the state first')
    rows, jobs = list(index.values()), []
    if scene_end_ids is None:
        ranges = [(start, min(start+max_owned_paragraphs, len(rows)))
                  for start in range(0, len(rows), max_owned_paragraphs)]
    else:
        identifiers = list(index)
        if not scene_end_ids or any(identifier not in index for identifier in scene_end_ids):
            raise ValueError('Invalid source scene boundaries')
        ends = [identifiers.index(identifier)+1 for identifier in scene_end_ids]
        if ends != sorted(set(ends)) or ends[-1] != len(rows):
            raise ValueError('Scene boundaries must cover the entire block exactly')
        ranges = list(zip([0]+ends[:-1], ends))
        if any(stop-start > max_owned_paragraphs for start, stop in ranges):
            raise ValueError('Scene exceeds paragraph budget; source prepass must split it safely')
    for start, stop in ranges:
        owned = rows[start:stop]
        neighbors = rows[max(0, start-overlap):start] + rows[stop:stop+overlap]
        if sum(len(s['source']) for s in owned + neighbors) > max_source_chars:
            raise ValueError('Owned source plus overlap exceeds budget; narrow the job, never truncate')
        owned = [{**s, 'source_anchor_candidates': source_anchor_candidates(s['source'])} for s in owned]
        job = {'job_id': f'block-{chapters[0]}-{chapters[-1]}-job-{len(jobs)+1:04d}',
               'state_hash': state['state_hash'], 'state_version': state['version'],
               'owned_segments': copy.deepcopy(owned), 'neighbor_segments': copy.deepcopy(neighbors),
               'context_capsule': _capsule(state, owned, neighbors, max_capsule_chars, max_capsule_entries),
               'output_rule': 'Emit exactly owned ids in source order; neighbors are read-only.',
               'retry_rule': 'Regenerate this whole bounded job; never patch paragraphs in place.'}
        jobs.append(_sealed(job, 'contract_hash'))
    return _sealed({'schema': VERSION, 'state_hash': state['state_hash'],
                    'state_version': state['version'], 'from_chapter': chapters[0],
                    'through_chapter': chapters[-1], 'source_registry': registry,
                    'ordered_ids': list(index), 'jobs': jobs}, 'plan_hash')


def validate_and_merge(plan, candidates, current_state):
    """Reject stale results, double ownership, omissions, and mutated contracts."""
    _check_seal(current_state, 'state_hash')
    _check_seal(plan, 'plan_hash')
    if (plan['state_hash'] != current_state['state_hash'] or
            plan['state_version'] != current_state['version']):
        raise ValueError('Stale state: all dependent jobs must be regenerated')
    by_job = {}
    for candidate in candidates:
        identifier = candidate.get('job_id')
        if identifier in by_job:
            raise ValueError('Duplicate worker result')
        by_job[identifier] = candidate
    if set(by_job) != {job['job_id'] for job in plan['jobs']}:
        raise ValueError('Missing or unknown worker result')
    segments, ownership = [], set()
    for job in plan['jobs']:
        _check_seal(job, 'contract_hash')
        candidate = by_job[job['job_id']]
        if (candidate.get('contract_hash') != job['contract_hash'] or
                candidate.get('state_hash') != plan['state_hash']):
            raise ValueError('Worker result belongs to another contract/state')
        expected = [s['id'] for s in job['owned_segments']]
        rows = candidate.get('segments', [])
        if not isinstance(rows, list) or [s.get('id') for s in rows] != expected:
            raise ValueError('Worker emitted missing, extra, neighbor, or reordered ids')
        for row in rows:
            if row['id'] in ownership or not isinstance(row.get('text'), str) or not row['text'].strip():
                raise ValueError('Duplicate ownership or empty translation')
            ownership.add(row['id'])
            segments.append({'id': row['id'], 'text': row['text']})
    if [s['id'] for s in segments] != plan['ordered_ids']:
        raise ValueError('Merged source coverage/order changed')
    return _sealed({'status': 'DRAFT_MERGED_UNREVIEWED', 'plan_hash': plan['plan_hash'],
                    'state_hash': plan['state_hash'], 'source_registry': plan['source_registry'],
                    'segments': segments,
                    'worker_candidate_hashes': {k: digest(v) for k, v in sorted(by_job.items())}}, 'merged_hash')


def commit_block(state, plan, merged, source_packages, ledger_updates, gate_receipt, gate_verifier=None):
    """Return next immutable state AFTER an externally validated acceptance gate.

    A trusted caller-supplied gate_verifier must independently verify evidence,
    source-bound semantic/style/boundary judgments and native runtime identities.
    This is an integrity barrier, not authentication; a PASS dict is insufficient.
    Updates never learn from Vietnamese drafts; every entry points to Chinese.
    """
    _check_seal(state, 'state_hash')
    _check_seal(plan, 'plan_hash')
    _check_seal(merged, 'merged_hash')
    if (state['state_hash'] != plan['state_hash'] or state['version'] != plan['state_version']
            or merged['state_hash'] != state['state_hash'] or merged['plan_hash'] != plan['plan_hash']):
        raise ValueError('Stale commit; regenerate dependent jobs')
    if (plan['from_chapter'] != state['through_chapter'] + 1 or
            [s['id'] for s in merged['segments']] != plan['ordered_ids']):
        raise ValueError('Commit barrier/order mismatch')
    if (gate_receipt.get('status') != 'PASS' or gate_receipt.get('merged_hash') != merged['merged_hash']
            or gate_receipt.get('plan_hash') != plan['plan_hash'] or not gate_receipt.get('evidence_hash')):
        raise ValueError('Missing source-bound external acceptance evidence')
    if not callable(gate_verifier) or gate_verifier(gate_receipt, state, plan, merged) is not True:
        raise ValueError('Commit disabled without a trusted external gate verifier')
    index, registry, _ = _sources(source_packages)
    if registry != plan['source_registry']:
        raise ValueError('Commit source differs from frozen block')
    updates = _ledger(ledger_updates, index)
    existing = {e['ledger_id']: copy.deepcopy(e) for e in state['ledger']}
    for update in updates:
        previous = existing.get(update['ledger_id'])
        if previous and update.get('previous_entry_hash') != previous['entry_hash']:
            raise ValueError('Ledger update needs exact preceding entry hash')
        existing[update['ledger_id']] = update
    next_state = copy.deepcopy(state)
    next_state.pop('state_hash')
    next_state.update({'version': state['version'] + 1, 'through_chapter': plan['through_chapter'],
                       'source_registry': {**state['source_registry'], **registry},
                       'ledger': [existing[k] for k in sorted(existing)],
                       'previous_state_hash': state['state_hash'],
                       'last_commit': {'plan_hash': plan['plan_hash'], 'merged_hash': merged['merged_hash'],
                                       'gate_evidence_hash': gate_receipt['evidence_hash']}})
    return _sealed(next_state, 'state_hash')
