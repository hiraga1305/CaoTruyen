"""Offline native provenance fixtures. No subprocess/model calls."""
import uuid
import json
from semantic_gate import build_package, candidate_hash, CHECKS, LITERARY_CHECKS, write_json
from native_oauth.native_evidence import runtime_record, artifact_record


def native_runtime(root, model='fixture', session=None):
    session = session or uuid.uuid4().hex
    path = root/session/'runtime.json'
    write_json(path, {'status':'SUCCESS', 'exit_code':0, 'actual_model':model,
                     'conversation_id':session, 'result':{'status':'SUCCESS','conversation_id':session,'response':'offline artifact'}})
    runtime = json.loads(path.read_text(encoding='utf-8'))
    events = [{'event':'init','conversation_id':session,'init':{'model':model}}, {'event':'result','result':runtime['result']}]
    path.with_name('events.jsonl').write_text('\n'.join(json.dumps(e) for e in events),encoding='utf-8')
    return runtime_record(path, model)


def native_reviews(package, candidate, root):
    reviews = []
    for role in ('reviewer', 'auditor'):
        record = native_runtime(root)
        reviews.append({'model':'native/fixture', 'identity_basis':'native_cli_init',
                        'native_runtimes':[record], 'conversation_id':record['conversation_id'],
                        'package_hash':package['package_hash'], 'candidate_hash':candidate_hash(candidate),
                        'verdict':'PASS', 'checks':dict.fromkeys(CHECKS, True), 'issues':[],
                        'literary_checks':dict.fromkeys(LITERARY_CHECKS, True),
                        'segments':[{'id':s['id'], 'source_quote':s['source'], 'target_quote':t['text'],
                                     'verdict':'PASS', 'reason':'Offline fixture, not a model review'}
                                    for s,t in zip(package['segments'], candidate['segments'])]})
    for i, review in enumerate(reviews):
        bind_artifact(root/f'review_{i}_{uuid.uuid4().hex}.json',review)
    return reviews


def native_fixture(root):
    package = build_package(1, 'fixture', ['他走了。', '她沒有來。'], {}, 'fixture')
    candidate = {'package_hash':package['package_hash'], 'model':'native/fixture',
                 'native_runtimes':[native_runtime(root)],
                 'segments':[{'id':'c0001p0001','text':'Anh ấy đi rồi.'},
                             {'id':'c0001p0002','text':'Cô ấy không đến.'}]}
    bind_artifact(root/'candidate.json', candidate)
    return package, candidate, native_reviews(package, candidate, root)


def bind_artifact(path, payload):
    write_json(path, payload)
    payload['native_artifact'] = artifact_record(path, payload)
    return payload
