"""OAuth CLI drafts with parser/genre support; final review belongs to Codex GPT."""
import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from semantic_gate import (read_json, write_json, digest, validate_package, mechanical_findings,
                           translation_prompt, review_prompt, evaluate, publish, LITERARY_CHECKS)
from native_oauth.run_agy import run
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
    if result['status'] != 'SUCCESS' or not (data/output_file).exists():
        raise ValueError('Native role incomplete: ' + role + ' (' + result['status'] + ')')
    events = [json.loads(line) for line in (data/(role+'.runtime')/'events.jsonl').read_text(encoding='utf-8').splitlines() if line.startswith('{')]
    init = next(e for e in events if e.get('event') == 'init')
    actual = init['init']['model']
    if actual != model:
        raise ValueError('Native model differs from requested role')
    artifact=data/output_file
    original=artifact.read_text(encoding='utf-8')
    payload,repaired=repair_text_fields(original)
    if repaired:
        artifact.with_suffix('.invalid-original.json').write_text(original,encoding='utf-8')
        payload['format_repair']={'kind':'escape_unescaped_quotes_only','original_text_hash':digest(original)}
    payload['model'] = 'native/' + actual
    payload['identity_basis'] = 'native_cli_init'
    payload['conversation_id'] = result['conversation_id']
    payload['runtime_hash'] = digest(result)
    write_json(artifact,payload)
    return payload


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',required=True)
    parser.add_argument('--analysis',required=True)
    parser.add_argument('--genre',default='hybrid_cyberpunk_tu_tien')
    parser.add_argument('--workspace',default=str(ROOT/'native_oauth/pilot_workspace'))
    parser.add_argument('--translator-model',default='gemini-3.8-flash-low')
    parser.add_argument('--reviewer-model',default='claude-opus-4-6-thinking')
    parser.add_argument('--auditor-model',default='gemini-3.8-flash-medium')
    parser.add_argument('--timeout',type=int,default=420)
    parser.add_argument('--resume-draft',action='store_true',help='Reuse only a source-bound draft with verified native runtime')
    parser.add_argument('--native-review-experiment',action='store_true',help='Explicit historical experiment; default final review is Codex GPT')
    args = parser.parse_args()
    package,data = prepare_inputs(args.source,args.analysis,args.genre,args.workspace)
    state = {'status':'RUNNING','source_package_hash':package['package_hash'],'genre':args.genre}
    write_json(data/'state.json',state)
    try:
        if args.resume_draft:
            candidate = read_json(data/'draft.json')
            runtime = read_json(data/'translator.runtime/runtime.json')
            if runtime['status'] != 'SUCCESS' or candidate.get('runtime_hash') != digest(runtime):
                raise ValueError('Cannot resume unverified native draft')
        else:
            candidate = run_stage(data,args.workspace,'translator',args.translator_model,
                                  translation_prompt(package),'draft.json',args.timeout)
        findings = mechanical_findings(package,candidate)
        write_json(data/'mechanical.json',{'findings':findings})
        if findings:
            raise ValueError('Draft failed mechanical gate')
        if not args.native_review_experiment:
            codex_protocol = review_prompt(package,candidate) + (
                '\nFinal reviews belong to two separate actual GPT/Codex subagent sessions. '
                'Each reviewer reads all source and target paragraphs without seeing peer findings. '
                'Use model codex/gpt-inherited unless the actual GPT model version is known; '
                'identity_basis must be codex_subagent and agent_session must be the actual task path. '
                'The literary reviewer also inspects the bound genre profile, natural Vietnamese, '
                'spelling/grammar, address consistency and dialogue format. Include literary_checks '
                'with exactly these boolean fields: ' + json.dumps(LITERARY_CHECKS) + '. '
                'true means inspected; real defects still require FAIL and paragraph evidence. '
                'After edits, both sessions must review the final candidate hash before publication.')
            (data/'codex.review.protocol.txt').write_text(codex_protocol,encoding='utf-8')
            state.update({'status':'DRAFT_READY_FOR_CODEX','candidate_hash':digest(candidate),
                          'draft':str(data/'draft.json'),'review_backend':'Codex GPT independent sessions'})
            write_json(data/'state.json',state)
            print(json.dumps(state,ensure_ascii=False),flush=True)
            return
        protocol = review_prompt(package,candidate)
        protocol += ('\nAlso assess the bound genre style_profile and natural Vietnamese prose; '
                     'mention literary/style defects in issues with paragraph ids. '
                     'Use short exact source/target quotes and one concise Vietnamese reason per paragraph; '
                     'inspect each complete source/draft paragraph even though evidence quotes are short. '
                     'Include literary_checks with exactly these boolean fields: ' +
                     json.dumps(LITERARY_CHECKS) + '. true means inspected, not error-free. '
                     'Set verdict FAIL and traceable issues for actual defects. Never approve by a numerical self-score.')
        reviews = []
        for role,model in [('reviewer',args.reviewer_model),('auditor',args.auditor_model)]:
            reviews.append(run_stage(data,args.workspace,role,model,protocol,role+'.json',args.timeout))
            validate_literary_review(reviews[-1])
        report = evaluate(package,candidate,reviews)
        write_json(data/'qa.json',report)
        if report['status'] != 'PASS':
            raise ValueError('Semantic/literary review rejected draft; inspect qa.json')
        output = publish(package,candidate,reviews,data/'approved')
        state.update({'status':'PASS','output':str(output),'models':report['models']})
    except Exception as error:
        state.update({'status':'BLOCKED','reason':str(error),'error_type':type(error).__name__})
    write_json(data/'state.json',state)
    print(json.dumps(state,ensure_ascii=False),flush=True)


if __name__ == '__main__':
    main()
