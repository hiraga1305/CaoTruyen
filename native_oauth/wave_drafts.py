"""Parallel source-only drafts with explicit, immutable generation provenance."""
import uuid
from pathlib import Path
from semantic_gate import digest, read_json, mechanical_findings
from native_oauth.native_evidence import validate_provenance, validate_bound_files
from native_oauth.workflow_io import atomic_json


def validate_generation_package(package, candidate):
    """Permit final review under new approved context, never rewrite native output."""
    proof = candidate.get('native_generation_package')
    if not isinstance(proof, dict):
        raise ValueError('No explicit parallel generation package')
    generation = read_json(proof['file'])
    if (digest(generation) != proof.get('hash')
            or generation.get('version') != 'antigravity-wave-draft-1'
            or generation.get('approval_eligible') is not False
            or candidate.get('package_hash') != generation.get('package_hash')
            or digest({k:v for k,v in generation.items() if k != 'package_hash'}) != generation['package_hash']):
        raise ValueError('Parallel generation package changed')
    # All source/canon/title/diagnostic inputs must be identical. Only the
    # chronology of approved context differs from the source-only draft anchor.
    excluded = {'version','package_hash','context','draft_anchor','approval_eligible'}
    core = lambda value: {k:v for k,v in value.items() if k not in excluded}
    if core(generation) != core(package):
        raise ValueError('Source/canon/baseline differs from parallel generation')
    validate_bound_files(generation)
    anchor = generation.get('draft_anchor',{})
    through = anchor.get('through_chapter')
    if not isinstance(through,int) or through < 0 or through >= package['chapter']:
        raise ValueError('Invalid parallel draft history boundary')
    if through:
        # The final semantic gate already validates the complete approved
        # ancestry. Do not recursively re-run it per ancestor here (exponential
        # work on long books). Check the recorded prefix against the current
        # manifest; final review validates all source-bound context normally.
        from native_oauth.book_publication import read_manifest
        if read_manifest(anchor['book_dir'])['chapters'].get(str(through)) != anchor.get('prefix_entry'):
            raise ValueError('Approved draft anchor revision changed')
        context=anchor['approved_context']
        if context.get('through_chapter')!=through:
            raise ValueError('Draft anchor context has the wrong history boundary')
        for file,expected in context.get('evidence_hashes',{}).items():
            if digest(read_json(file))!=expected:
                raise ValueError('Approved draft anchor evidence changed')


def generate_draft(book, job, chapter, anchor, *, model, timeout, max_repairs):
    from native_oauth.revise_book import prepare_revision, revision_protocol
    from native_oauth.pipeline_native import run_stage
    source, legacy, package = prepare_revision(book, job, chapter, draft_anchor=anchor)
    pointer = Path(job)/'wave_draft_cache'/f'chapter_{chapter:04d}.json'
    if pointer.exists():
        entry = read_json(pointer)
        cached = Path(entry['candidate']).resolve()
        if not cached.is_relative_to(Path(job).resolve()):
            raise ValueError('Parallel draft cache escapes job')
        value = read_json(cached)
        rejected = Path(job)/'rejected_wave_drafts'/f'chapter_{chapter:04d}.json'
        bad_hash = read_json(rejected).get('candidate_hash') if rejected.exists() else None
        if (entry.get('package_hash') == package['package_hash']
                and entry.get('model') == model and digest(value) == entry.get('candidate_hash')
                and digest(value) != bad_hash):
            validate_provenance(value)
            if not mechanical_findings(package, value):
                return value
    findings, candidate = None, None
    for attempt in range(max_repairs+1):
        work = Path(job)/'wave_drafts'/f'chapter_{chapter:04d}'/uuid.uuid4().hex
        data = work/'native_oauth/runs/chapter1'
        atomic_json(data/'source.json', package)
        candidate = run_stage(data, work, 'translator', model,
            revision_protocol(package, legacy, findings, candidate) +
            '\nSOURCE_ONLY_PARALLEL_DRAFT: draft_anchor contains only already approved history. '
            'Nearby original Chinese is read-only context. No unreviewed draft is canon. '
            'Return this generation package_hash exactly; you are not approving anything.',
            'draft.json', timeout)
        validate_provenance(candidate)
        if prepare_revision(book,job,chapter,draft_anchor=anchor) != (source,legacy,package):
            raise ValueError('Source/canon/baseline changed during parallel generation')
        findings = mechanical_findings(package, candidate)
        if findings:
            atomic_json(work/'qa.json', {'status':'BLOCKED','findings':findings})
            continue
        # The native response remains byte-for-byte preserved. This additional
        # host receipt records WHICH input package actually produced the draft.
        candidate['native_generation_package'] = {'file':str((data/'source.json').resolve()),
                                                   'hash':digest(package)}
        atomic_json(work/'draft.json', candidate)
        atomic_json(pointer, {'candidate':str((work/'draft.json').resolve()),
                             'candidate_hash':digest(candidate), 'package_hash':package['package_hash'], 'model':model})
        return candidate
    raise ValueError(f'Parallel draft chapter {chapter} failed structure checks')
