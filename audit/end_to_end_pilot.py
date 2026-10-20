"""Small live end-to-end sample, isolated from production chapters."""
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from semantic_gate import read_json, write_json, build_package, flatten_lore
from multi_llm_client import load_config, call_gemini
from quality_pipeline import run_package


def main():
    cases = read_json(ROOT / 'audit/semantic_regression_cases.json')['cases']
    raw = [case['source_quote'] + (('\nNguyên văn bối cảnh: ' + case['context_quote']) if case.get('context_quote') else '') for case in cases]
    package = build_package(1, 'REGRESSION EXCERPTS - NOT A PRODUCTION CHAPTER', raw,
                            flatten_lore(read_json(ROOT / 'novel_lore.json')),
                            'audit/semantic_regression_cases.json; mixed chapters 1,32,70 and canonical terms')
    # Chinese source contains a labelled context sentence only in the tournament case.
    # The sample is deliberately kept outside approved_output.
    config = load_config()
    models = {'translator': 'gemini-3.6-flash', 'reviewer': 'gemini-3.8-flash', 'auditor': 'gemini-3.7-flash'}
    config['quality_roles'] = {role: {'provider': 'gemini', 'models': [model]} for role, model in models.items()}
    def client(prompt, system_instruction=None, role=None):
        cfg = dict(config['providers']['gemini'])
        cfg.update({'models': [models[role]], 'api_keys': cfg['api_keys'][:1], 'temperature': 0,
                    'thinking_budget': None})
        print('Calling ' + role + '/' + models[role], flush=True)
        return call_gemini(prompt, system_instruction, cfg, {'max_retries': 2, 'timeout': 60})
    try:
        output = run_package(package, ROOT/'audit/pilot_runs', ROOT/'audit/pilot_approved',
                             max_repairs=0, client=client, config=config)
        write_json(ROOT/'audit/end_to_end_pilot_report.json', {'status': 'PASS', 'output': str(output),
                   'scope': '8 mixed-chapter excerpts only; not production or full continuity validation', 'models': models})
        print(output)
    except Exception as error:
        write_json(ROOT/'audit/end_to_end_pilot_report.json', {'status': 'BLOCKED', 'error_kind': type(error).__name__,
                   'scope': '8 excerpts; inspect pilot_runs for failure evidence', 'models': models})
        print('BLOCKED: ' + type(error).__name__, flush=True)


if __name__ == '__main__':
    main()
