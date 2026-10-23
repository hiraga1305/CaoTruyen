"""Runtime-bound provenance for independent Antigravity worker sessions."""
import json
import hashlib
from pathlib import Path
from semantic_gate import digest
from native_oauth.run_agy import require_complete_runtime, classify_completion

TRANSPORT_KEYS = {'model', 'identity_basis', 'conversation_id', 'runtime_hash',
                  'native_runtimes', 'native_artifact', 'format_repair', 'native_response_binding',
                  'native_generation_package'}


def artifact_record(path, payload):
    path = Path(path).resolve()
    from native_oauth.json_format_repair import repair_text_fields
    original, _ = repair_text_fields(path.read_text(encoding='utf-8'))
    core = lambda value: {k:v for k,v in value.items() if k not in TRANSPORT_KEYS}
    if not isinstance(original, dict) or core(original) != core(payload):
        raise ValueError('Native artifact differs from the completed worker output')
    return {'file': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'payload_hash': digest({k:v for k,v in payload.items() if k not in TRANSPORT_KEYS})}


def runtime_record(path, model):
    path = Path(path).resolve()
    runtime = json.loads(path.read_text(encoding='utf-8'))
    require_complete_runtime(runtime, model)
    if not runtime.get('conversation_id'):
        raise ValueError('Native conversation id missing')
    events = [json.loads(line) for line in path.with_name('events.jsonl').read_text(encoding='utf-8').splitlines() if line.strip()]
    inits = [e for e in events if e.get('event') == 'init']
    ends = [e for e in events if e.get('event') == 'result']
    if (len(inits) != 1 or len(ends) != 1 or inits[0].get('init', {}).get('model') != model
            or inits[0].get('conversation_id') != runtime['conversation_id']
            or ends[0].get('result') != runtime['result']
            or runtime['result'].get('conversation_id') != runtime['conversation_id']):
        raise ValueError('Native init/result/session evidence mismatch')
    diagnostics = path.with_name('diagnostics.txt')
    classified = classify_completion(events, diagnostics.read_text(encoding='utf-8') if diagnostics.exists() else '', runtime['exit_code'],
                                     completed_cleanup=runtime.get('completed_cleanup'))
    if runtime.get('status')!=classified['status'] or bool(runtime.get('partial_output'))!=classified['partial_output']:
        raise ValueError('Native completion classification changed')
    if runtime.get('completed_cleanup') is not None:
        from native_oauth.run_agy import verified_cleanup
        if not verified_cleanup(events,diagnostics.read_text(encoding='utf-8') if diagnostics.exists() else '',runtime['completed_cleanup']):
            raise ValueError('Invalid native cleanup proof')
        cleanup=runtime['completed_cleanup'];request=path.with_name('input.jsonl')
        if (not request.is_file() or hashlib.sha256(request.read_bytes()).hexdigest()!=cleanup['input_sha256']
                or not isinstance(runtime.get('duration_seconds'),(int,float))
                or runtime['duration_seconds']<cleanup['grace_seconds']):
            raise ValueError('Completed CLI cleanup input/timing evidence changed')
        message=json.loads(request.read_text(encoding='utf-8'))
        if message.get('event')!='user' or not isinstance(message.get('message',{}).get('content'),str):
            raise ValueError('Invalid native stdin request evidence')
    require_complete_runtime(dict(classified, exit_code=runtime['exit_code'],completed_cleanup=runtime.get('completed_cleanup')), model)
    return {'file': str(path), 'hash': digest(runtime),
            'model': model, 'conversation_id': runtime['conversation_id']}


def validate_provenance(payload):
    if not isinstance(payload, dict):
        raise ValueError('Native payload must be an object')
    records = payload.get('native_runtimes', [])
    model = payload.get('model', '')
    if not isinstance(model, str) or not model.startswith('native/') or not isinstance(records, list) or not records:
        raise ValueError('Native runtime provenance required')
    sessions = []
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get('file'), str):
            raise ValueError('Invalid native runtime record')
        actual = runtime_record(record['file'], model.removeprefix('native/'))
        if actual != record:
            raise ValueError('Native runtime changed or belongs to another model/session')
        sessions.append(actual['conversation_id'])
    if 'native_artifact' in payload:
        proof = payload['native_artifact']
        if not isinstance(proof, dict) or artifact_record(proof['file'], payload) != proof:
            raise ValueError('Native artifact changed after execution')
        if payload.get('native_response_binding') == 'json':
            if len(records) != 1:
                raise ValueError('One native response per JSON artifact required')
            runtime = json.loads(Path(records[0]['file']).read_text(encoding='utf-8'))
            original = json.loads(runtime['result']['response'])
            core = lambda value: {k:v for k,v in value.items() if k not in TRANSPORT_KEYS}
            if not isinstance(original, dict) or core(original) != core(payload):
                raise ValueError('Artifact differs from actual native JSON response')
    elif 'native_scene_ownership' in payload:
        from native_oauth.chapter_integrity import native_scene_texts
        owned = payload['native_scene_ownership']
        if len(owned) != len(records):
            raise ValueError('Native scene ownership missing')
        generated = []
        for record, scene in zip(records, owned):
            runtime = json.loads(Path(record['file']).read_text(encoding='utf-8'))
            texts = native_scene_texts(runtime['result']['response'], len(scene['ids']))
            generated.extend({'id':sid,'text':text} for sid,text in zip(scene['ids'],texts))
        if generated != payload.get('segments'):
            raise ValueError('Candidate differs from native generation responses')
    else:
        raise ValueError('Native artifact or generation response binding required')
    return sessions


def validate_native_reviews(candidate, reviews):
    translator_sessions = set(validate_provenance(candidate))
    review_sessions = []
    for review in reviews:
        if review.get('identity_basis') != 'native_cli_init':
            raise ValueError('Review must be executed by Antigravity')
        sessions = validate_provenance(review)
        if len(sessions) != 1 or review.get('conversation_id') != sessions[0]:
            raise ValueError('One independent native session per reviewer required')
        review_sessions.extend(sessions)
    if len(review_sessions) != 2 or len(set(review_sessions)) != 2 or translator_sessions.intersection(review_sessions):
        raise ValueError('Translator and both reviewers must use independent native sessions')


def validate_bound_files(package):
    files = package.get('native_bound_files', {})
    if not isinstance(files, dict):
        raise ValueError('Invalid bound source/canon files')
    for filename, expected in files.items():
        if expected is None:
            if Path(filename).exists():
                raise ValueError('Previously absent canon file was added: ' + filename)
            continue
        if hashlib.sha256(Path(filename).read_bytes()).hexdigest() != expected:
            raise ValueError('Bound source/canon changed: ' + filename)
