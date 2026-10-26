"""Source-bound cross-chapter review and durable full-wave export gates."""
import uuid
import json
import hashlib
from pathlib import Path
from semantic_gate import digest, read_json
from native_oauth.book_publication import read_manifest, read_approval, contained_file
from native_oauth.native_evidence import validate_provenance
from native_oauth.workflow_io import atomic_json, file_lock

CHECKS = ('names','address','terminology','timeline','causality','chapter_boundaries','voice','layout')


def chapter_wave_data(chapter, value):
    package, candidate = value['evidence']['package'], value['evidence']['candidate']
    row = {'chapter':chapter, 'source':package['segments'], 'target':candidate['segments']}
    if package.get('metadata_title_source'):
        row.update(metadata_title_source=package['metadata_title_source'],title_vi=candidate['title_vi'])
    return row


def chapter_texts(chapter):
    raw = {s['id']:s['source'] for s in chapter['source']}
    target = {s['id']:s['text'] for s in chapter['target']}
    if chapter.get('metadata_title_source'):
        title = chapter['metadata_title_source']
        raw[title['id']], target[title['id']] = title['source'], chapter['title_vi']
    return raw,target


def begin_wave(book, chapters):
    book = Path(book)
    with file_lock(book/'approved/manifest.lock'):
        manifest = read_manifest(book)
        gate = {'chapters':list(chapters), 'status':'PENDING'}
        manifest.setdefault('wave_gates', {})[str(chapters[0])] = gate
        atomic_json(book/'approved/manifest.json', manifest)


def wave_package(book, chapters):
    manifest = read_manifest(book)
    values = [read_approval(book, ch) for ch in chapters]
    first = values[0]['evidence']['package']
    package = {'version':'antigravity-wave-review-1','chapter':chapters[0],
               'chapter_range':f'{chapters[0]}–{chapters[-1]}',
               'book_id':first.get('book_id'), 'book_title':first.get('book_title'),
               'genre':first.get('genre'), 'total_chapters':first.get('total_chapters'),
               'approved_prefix_context':first.get('context',{}),
               'chapter_entries':{str(ch):manifest['chapters'][str(ch)] for ch in chapters},
               'chapters':[chapter_wave_data(ch,value) for ch,value in zip(chapters,values)]}
    package['package_hash'] = digest(package)
    return package


def validate_wave_review(package, result):
    if (digest({k:v for k,v in package.items() if k!='package_hash'}) != package.get('package_hash')
            or result.get('package_hash') != package['package_hash']):
        raise ValueError('Wave review belongs to different chapter revisions')
    if (result.get('verdict') not in ('PASS','FAIL') or not isinstance(result.get('issues'),list)
            or set(result.get('checks',{})) != set(CHECKS)
            or any(not isinstance(v,bool) for v in result.get('checks',{}).values())):
        raise ValueError('Incomplete cross-chapter review dimensions')
    rows = result.get('chapters', [])
    if [r.get('chapter') for r in rows] != [r['chapter'] for r in package['chapters']]:
        raise ValueError('Wave review must cover every chapter in order')
    source_ids = set()
    for chapter, row in zip(package['chapters'], rows):
        raw,target = chapter_texts(chapter)
        source_ids.update(raw)
        sid = row.get('source_id')
        if (sid not in raw or row.get('verdict') not in ('PASS','FAIL')
                or any(not isinstance(row.get(k),str) or not row[k].strip()
                       for k in ('source_quote','target_quote','reason'))
                or row['source_quote'] not in raw[sid] or row['target_quote'] not in target[sid]):
            raise ValueError('Wave finding/evidence must quote its actual source and draft')
    for issue in result['issues']:
        sid=issue.get('id')
        raw={sid:text for ch in package['chapters'] for sid,text in chapter_texts(ch)[0].items()}
        targets={sid:text for ch in package['chapters'] for sid,text in chapter_texts(ch)[1].items()}
        if (sid not in source_ids or any(not isinstance(issue.get(k),str) or not issue[k].strip()
                                         for k in ('reason','source_quote','target_quote'))
                or issue['source_quote'] not in raw[sid] or issue['target_quote'] not in targets[sid]):
            raise ValueError('Wave issue has no source-owned ID/reason')
    if result['verdict']=='PASS' and (result['issues'] or any(r['verdict']!='PASS' for r in rows)
                                      or any(v is not True for v in result.get('checks',{}).values())):
        raise ValueError('Contradictory wave PASS')
    if result['verdict']=='FAIL' and not result['issues']:
        raise ValueError('Wave FAIL needs source-grounded issues for repair')
    validate_provenance(result)


def review_wave(book, job, chapters, *, model, timeout):
    from native_oauth.pipeline_native import run_stage, NativeJSONSchemaError
    package = wave_package(book, chapters)
    schema_error = None
    for attempt in range(2):
        work = Path(job)/'wave_reviews'/f'{chapters[0]:04d}_{chapters[-1]:04d}'/uuid.uuid4().hex
        data = work/'native_oauth/runs/chapter1'
        atomic_json(data/'source.json', package)
        protocol = ('Independently compare ALL chapters below against their complete original Chinese. '
            'Check names, address relationships, terminology, timeline, cause/effect, chapter seams, '
            'Vietnamese voice and preservation/order of titles/paragraphs. Do not turn beliefs into facts, '
            'introduce spoilers, or treat a character statement as objective truth. '
            'This supplements two reviews per chapter; do not rewrite text or infer PASS from existing approvals. '
            'Return strict JSON {package_hash,verdict:PASS|FAIL,checks:'+json.dumps(dict.fromkeys(CHECKS,True))+
            ',chapters:[{chapter,verdict,source_id,source_quote,target_quote,reason}],'
            'issues:[{id,source_quote,target_quote,reason}]}. In checks, true means dimension was verified; if defects found in a dimension, you may set it to false and report the specific issues with verdict FAIL. Every property name and string value must be enclosed in double quotes. '
            'Use short exact contiguous quotes from the SAME assigned source_id. '
            'Also inspect metadata_title_source against title_vi when supplied; report title issues using its title ID. '
            'Cover every chapter in order. Missing context or a cross-chapter inconsistency must FAIL.\n')
        if schema_error:
            protocol += (f'\nYour prior wave review response failed schema validation: {schema_error}. '
                'Please ensure strict valid JSON with double-quoted keys and strings, exact contiguous quotes, and all chapters covered in order.\n')
        protocol += json.dumps(package, ensure_ascii=False)
        try:
            result = run_stage(data, work, 'wave-auditor', model, protocol,
                               'wave-review.json', timeout)
        except NativeJSONSchemaError as error:
            schema_error = str(error)
            continue
        try:
            validate_wave_review(package, result)
        except (ValueError, KeyError, TypeError, AttributeError) as error:
            schema_error = str(error)
            continue
        break
    else:
        raise ValueError('Wave review schema failed after retry: ' + str(schema_error))
    if result['verdict'] != 'PASS':
        atomic_json(work/'blocked.json', {'status':'BLOCKED','issues':result['issues']})
        # Preserve the valid FAIL and bind its grounded findings to the exact
        # approved comparison. Resume must produce/review changed packages,
        # never retry this same failed wave until a stochastic PASS.
        for chapter in chapters:
            owned_ids=set(chapter_texts(next(ch for ch in package['chapters'] if ch['chapter']==chapter))[0])
            issues=[r for r in result['issues'] if r['id'] in owned_ids]
            if not issues:
                continue
            approval=read_approval(book,chapter)
            comparison=approval['path']
            atomic_json(Path(job)/'wave_diagnostics'/f'chapter_{chapter:04d}.json', {
                'source_hash':approval['source']['package_hash'], 'comparison_file':str(comparison),
                'comparison_sha256':hashlib.sha256(comparison.read_bytes()).hexdigest(),
                'findings':[{k:r[k] for k in ('source_quote','target_quote','reason')} | {'id':r['id']} for r in issues]})
        raise ValueError('Cross-chapter wave review failed; inspect '+str(work))
    if wave_package(book,chapters) != package:
        raise ValueError('Chapter revisions changed during wave review')
    previous_sessions=set()
    for chapter in chapters:
        ev=read_approval(book,chapter)['evidence']
        for payload in [ev['candidate'],*ev['reviews']]:
            previous_sessions.update(validate_provenance(payload))
    if previous_sessions.intersection(validate_provenance(result)):
        raise ValueError('Wave auditor must use a separate native session')
    evidence = {'package':package, 'review':result}
    target = Path(book)/'approved/waves'/f'{chapters[0]:04d}_{chapters[-1]:04d}'/digest(evidence)/'evidence.json'
    atomic_json(target, evidence)
    with file_lock(Path(book)/'approved/manifest.lock'):
        manifest = read_manifest(book)
        if any(manifest['chapters'].get(ch)!=entry for ch,entry in package['chapter_entries'].items()):
            raise ValueError('Wave changed before approval commit')
        manifest.setdefault('wave_gates',{})[str(chapters[0])] = {
            'chapters':list(chapters),'status':'PASS',
            'evidence':target.relative_to(book).as_posix(),'evidence_hash':digest(evidence)}
        atomic_json(Path(book)/'approved/manifest.json',manifest)
    return target


def validate_wave_gates(book, manifest=None):
    manifest = read_manifest(book) if manifest is None else manifest
    from native_oauth.resilient_gate import MODE
    if manifest.get('schema')==MODE:
        from native_oauth.resilient_publication import validate_manifest
        validate_manifest(book,manifest)
        return
    gates=manifest.get('wave_gates',{})
    if not isinstance(gates,dict):
        raise ValueError('Invalid wave gates schema')
    for key,gate in gates.items():
        if not isinstance(gate,dict):
            raise ValueError('Invalid wave gate entry')
        chapters = gate.get('chapters',[])
        if (not isinstance(chapters,list) or not chapters
                or any(type(ch) is not int or ch<1 for ch in chapters)
                or str(chapters[0])!=key or chapters!=list(range(chapters[0],chapters[-1]+1))
                or gate.get('status')!='PASS'):
            raise ValueError('Wave cross-chapter review is pending or blocked: '+key)
        evidence = read_json(contained_file(Path(book).resolve(),gate['evidence']))
        if digest(evidence)!=gate.get('evidence_hash') or evidence['package']!=wave_package(book,chapters):
            raise ValueError('Wave evidence is stale or changed: '+key)
        validate_wave_review(evidence['package'],evidence['review'])
        if evidence['review']['verdict']!='PASS':
            raise ValueError('Wave review did not pass: '+key)
