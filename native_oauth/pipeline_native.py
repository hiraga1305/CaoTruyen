"""Antigravity OAuth translation, independent native reviews and publication."""
import argparse
import hashlib
import json
import shutil
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from semantic_gate import (read_json, write_json, digest, validate_package, mechanical_findings,
                           translation_prompt, review_prompt, evaluate, publish, LITERARY_CHECKS)
from native_oauth.run_agy import run, require_complete_runtime
from native_oauth.native_evidence import runtime_record, validate_provenance
from native_oauth.native_review import visible_stage, run_independent_reviews, install_agents
from native_oauth.json_format_repair import repair_text_fields
from native_oauth.batch_policy import CLASSIFIER_POLICY, VERSION as PREVENTION_VERSION

def validate_literary_review(review):
    checks = review.get('literary_checks',{})
    if set(checks) != set(LITERARY_CHECKS) or any(v is not True for v in checks.values()):
        raise ValueError('Missing explicit literary review dimensions')


def prepare_inputs(source_file, analysis_file, genre, workspace):
    source, analysis = read_json(source_file), read_json(analysis_file)
    validate_package(source)
    if analysis['source_package_hash'] != source['package_hash']:
        raise ValueError('Parser belongs to another source package')
    if [s['id'] for s in analysis['segments']] != [s['id'] for s in source['segments']]:
        raise ValueError('Parser coverage/order mismatch')
    for raw, parsed in zip(source['segments'], analysis['segments']):
        if parsed['source_hash'] != digest(raw['source']):
            raise ValueError('Parser source hash mismatch')
    profiles = read_json(ROOT/'native_oauth/genre_profiles.json')
    if genre not in profiles['profiles']:
        raise ValueError('Unknown genre')
    work = Path(workspace).resolve()
    install_agents(work)
    data = work/'native_oauth/runs/chapter1'
    data.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT/'native_oauth/analysis_lookup.py',work/'native_oauth/analysis_lookup.py')
    shutil.copy2(analysis_file, data/'analysis.full.json')
    compact = []
    for s in analysis['segments']:
        compact.append({'id':s['id'], 'srl':[{'predicate':f['predicate'],
                         'arguments':[[a[0],a[1]] for a in f['arguments']]} for f in s['srl']],
                        'dependency_roles':[[n['word'],n['head'],n['relation']] for n in s['dep']
                                            if n['relation'] in ('HED','SBV','VOB','IOB','DBL','FOB','CMP')],
                        'ner':s['ner']})
    write_json(data/'analysis.compact.json', {'provenance':analysis['provenance'],'segments':compact,
                'limits':analysis['limits'],'full_file':'analysis.full.json'})
    source['style_profile'] = {'genre':genre,'version':profiles['version'],
                              'common':profiles['common'],'rules':profiles['profiles'][genre],
                              'certification':profiles['certification']}
    source['style_profile']['preventive_policy'] = {'version':PREVENTION_VERSION,'instructions':CLASSIFIER_POLICY}
    source['parser_evidence'] = {'engine':analysis['provenance'],
                                'full_sha256':hashlib.sha256(Path(analysis_file).read_bytes()).hexdigest(),
                                'compact_hash':digest(read_json(data/'analysis.compact.json')),
                                'full_file':'native_oauth/runs/chapter1/analysis.full.json',
                                'compact_file':'native_oauth/runs/chapter1/analysis.compact.json',
                                'interpretation':'Predictions only; Chinese source outranks parse'}
    source['package_hash'] = digest({k:v for k,v in source.items() if k != 'package_hash'})
    write_json(data/'source.json', source)
    return source, data


def run_stage(data, workspace, role, model, protocol, output_file, timeout):
    with visible_stage(read_json(Path(data) / 'source.json'), role):
        return _run_stage(Path(data), workspace, role, model, protocol, output_file, timeout)


def _run_stage(data, workspace, role, model, protocol, output_file, timeout):
    if len(protocol) > 120000:
        raise ValueError('Complete native protocol exceeds context budget')
    if (data / output_file).exists():
        raise ValueError('Stage artifact already exists; use a fresh attempt workspace')
    original_source = read_json(data/'source.json')
    prompt_file = data/(role + '.prompt.txt')
    (data/(role+'.protocol.txt')).write_text(protocol,encoding='utf-8')
    count=len(read_json(data/'source.json')['segments'])
    prompt = (f'Authorized native OAuth novel worker. Role: {role}.\n'
              'The assigned protocol file includes the complete source/style profile and, for review, the full draft. '
              'Read that protocol completely; do not duplicate full source/draft/tree dumps in the context. '
              'For real parser support on ambiguous sentences, run python -X utf8 native_oauth/analysis_lookup.py --ids ID1 ID2 '
              'with at most eight assigned paragraph ids. Do not read the complete large analysis files. '
              'Original source outranks predicted analysis. '
              'Do not inspect another reviewer output, credentials, global config or unrelated files. '
              'Do not alter source/glossary/style/parser/gate/tests or originals. '
              f'Write only native_oauth/runs/chapter1/{output_file}, UTF-8 JSON, following the exact protocol below. '
              f'Use write_to_file. Never shorten the segment list: cover all {count} source ids. '
              'If tool/runtime/context prevents a complete artifact, report BLOCKED; do not claim completed. '
              'Return final artifact path, not the full JSON in the final message. '
              f'Read native_oauth/runs/chapter1/{role}.protocol.txt COMPLETELY for the exact JSON protocol. '
              'If view_file truncates a long line, read bounded paragraph groups with Python; do not infer missing content.')
    prompt_file.write_text(prompt,encoding='utf-8')
    result = run(prompt_file, data/(role + '.runtime'), model, 'novel-' + role,
                 timeout, workspace, True)
    require_complete_runtime(result, model)
    if read_json(data/'source.json') != original_source:
        raise ValueError('Worker changed its immutable source package')
    if not (data/output_file).exists():
        raise ValueError('Native worker did not write its assigned artifact')
    actual = result['actual_model']
    artifact=data/output_file
    original=artifact.read_text(encoding='utf-8')
    payload,repaired=repair_text_fields(original)
    if repaired:
        artifact.with_suffix('.invalid-original.json').write_text(original,encoding='utf-8')
        payload['format_repair']={'kind':'escape_unescaped_quotes_only','original_text_hash':digest(original)}
    from native_oauth.native_evidence import artifact_record
    original_artifact = artifact.with_suffix('.native-original.json')
    original_artifact.write_text(original, encoding='utf-8')
    payload['native_artifact'] = artifact_record(original_artifact, payload)
    payload['model'] = 'native/' + actual
    payload['identity_basis'] = 'native_cli_init'
    payload['conversation_id'] = result['conversation_id']
    payload['runtime_hash'] = digest(result)
    payload['native_runtimes'] = [runtime_record(data/(role + '.runtime/runtime.json'), model)]
    if payload['native_runtimes'][0]['hash'] != digest(result):
        raise ValueError('Runtime changed after native execution')
    write_json(artifact,payload)
    return payload


def execute_pipeline(source_file, analysis_file, genre, workspace, translator_model,
                     reviewer_model, auditor_model, timeout=420, draft_only=False,
                     max_repairs=1, resume_draft=False):
    if max_repairs not in (0, 1, 2):
        raise ValueError('max_repairs must be 0..2')
    workspace = Path(workspace).resolve()
    package, data = prepare_inputs(source_file, analysis_file, genre, workspace)
    policy = {'mode': 'antigravity_sessions', 'version': 1}
    state = {'status': 'RUNNING', 'source_package_hash': package['package_hash'], 'genre': genre}
    try:
        for attempt in range(max_repairs + 1):
            if attempt:
                workspace_attempt = workspace / f'attempt_{attempt}'
                package, data = prepare_inputs(source_file, analysis_file, genre, workspace_attempt)
            else:
                workspace_attempt = workspace
            if resume_draft and attempt == 0:
                candidate = read_json(data/'draft.json')
                validate_provenance(candidate)
            else:
                protocol = translation_prompt(package)
                if attempt:
                    protocol += ('\nRegenerate the complete source-owned chapter. Original Chinese is authoritative. '
                                 'Do not copy a proposed Vietnamese answer. Findings from prior attempt:\n' +
                                 json.dumps(report['findings'], ensure_ascii=False))
                candidate = run_stage(data, workspace_attempt, 'translator', translator_model,
                                      protocol, 'draft.json', timeout)
            findings = mechanical_findings(package, candidate)
            write_json(data/'mechanical.json', {'findings': findings})
            if findings:
                raise ValueError('Draft failed mechanical gate')
            if draft_only:
                state.update(status='DRAFT_READY_FOR_NATIVE_REVIEW', candidate_hash=digest(candidate),
                             draft=str(data/'draft.json'))
                break
            reviews = run_independent_reviews(package, candidate, data, workspace_attempt,
                                              reviewer_model, auditor_model, timeout)
            report = evaluate(package, candidate, reviews, review_policy=policy)
            write_json(data/'qa.json', report)
            if report['status'] == 'PASS':
                with visible_stage(package, 'approval'):
                    output = publish(package, candidate, reviews, data/'approved', review_policy=policy)
                state.update(status='PASS', output=str(output), models=report['models'])
                break
        else:
            state.update(status='BLOCKED', reason='Native review rejected final attempt', findings=report['findings'])
    except Exception as error:
        state.update(status='BLOCKED', reason=str(error), error_type=type(error).__name__)
    write_json(Path(workspace)/'state.json', state)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True)
    parser.add_argument('--analysis', required=True)
    parser.add_argument('--genre', default='hybrid_cyberpunk_tu_tien')
    parser.add_argument('--workspace', default=str(ROOT/'native_oauth/native_jobs'/uuid.uuid4().hex))
    parser.add_argument('--translator-model', default='gemini-3.8-flash-low')
    parser.add_argument('--reviewer-model', default='gemini-3.8-flash-high')
    parser.add_argument('--auditor-model', default='gemini-3.8-flash-medium')
    parser.add_argument('--timeout', type=int, default=420)
    parser.add_argument('--resume-draft', action='store_true')
    parser.add_argument('--draft-only', action='store_true')
    parser.add_argument('--max-repairs', type=int, choices=(0, 1, 2), default=1)
    args = parser.parse_args()
    state = execute_pipeline(args.source, args.analysis, args.genre, args.workspace,
        args.translator_model, args.reviewer_model, args.auditor_model, args.timeout,
        args.draft_only, args.max_repairs, args.resume_draft)
    print(json.dumps(state, ensure_ascii=False), flush=True)
    raise SystemExit(2 if state['status'] == 'BLOCKED' else 0)


if __name__ == '__main__':
    main()
