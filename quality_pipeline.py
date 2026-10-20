"""Bounded translation -> independent review -> repair -> re-review."""
import argparse
import json
import uuid
from pathlib import Path
from multi_llm_client import ask_ai, load_config
from semantic_gate import (read_json, write_json, validate_package, translation_prompt,
                           review_prompt, parse_model_json, evaluate, publish)


def preflight(config):
    roles = config.get('quality_roles', {})
    for role in ('translator', 'reviewer', 'auditor'):
        cfg = roles.get(role, {})
        if not cfg.get('provider') or not cfg.get('models'):
            raise ValueError('Configure quality_roles.' + role + ' with explicit provider/models')
    pools = [{(roles[r]['provider'], m) for m in roles[r]['models']}
             for r in ('translator', 'reviewer', 'auditor')]
    if any(pools[i] & pools[j] for i in range(3) for j in range(i + 1, 3)):
        raise ValueError('Role model pools must be disjoint; no silent downgrade')


def run_package(package, run_root='quality_runs', approved_dir='approved_output',
                max_repairs=1, client=ask_ai, config=None):
    if not 0 <= max_repairs <= 2:
        raise ValueError('max_repairs must be 0..2')
    validate_package(package)
    config = config if config is not None else load_config()
    preflight(config)
    # Bound cumulative context before the first paid generation; never truncate it.
    limit = config.get('settings', {}).get('max_quality_input_chars', 120000)
    if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
        raise ValueError('max_quality_input_chars must be a positive integer')
    if len(translation_prompt(package)) > limit:
        raise ValueError('Package/context exceeds input budget; compact sourced facts explicitly')
    run_dir = Path(run_root) / (f"c{package['chapter']:04d}_{package['package_hash'][:12]}_" + uuid.uuid4().hex[:8])
    write_json(run_dir / 'package.json', package)
    calls = []

    def call(role, prompt, artifact):
        if len(prompt) > limit:
            raise ValueError('Review/repair prompt exceeds input budget; no API call made')
        text, usage, model = client(prompt, system_instruction='Follow the supplied translation/review protocol. Return JSON only.', role=role)
        calls.append({'role': role, 'model': model, 'usage': usage})
        write_json(run_dir / 'calls.json', calls)
        if usage.get('model_reported') is False:
            raise ValueError('API did not report actual model identity; approval blocked')
        (run_dir / (artifact + '.response.txt')).write_text(text, encoding='utf-8')
        payload = parse_model_json(text)
        payload['model'] = model  # transport identity, never a self-reported model field
        payload['identity_basis'] = 'api_transport'
        write_json(run_dir / (artifact + '.json'), payload)
        return payload

    candidate = None
    report = None
    try:
        for attempt in range(max_repairs + 1):
            prompt = translation_prompt(package)
            if attempt:
                prompt += ('\nSửa draft theo lỗi bên dưới; nguồn là chuẩn, không tự đổi glossary/context. '
                           'Xuất lại đủ mọi id, không chỉ đoạn sửa.\nPREVIOUS:\n' +
                           json.dumps(candidate, ensure_ascii=False) + '\nFINDINGS:\n' +
                           json.dumps(report, ensure_ascii=False))
            candidate = call('translator', prompt, f'draft_{attempt}')
            # Malformed coverage cannot be sent to reviewers as if complete.
            from semantic_gate import mechanical_findings
            mechanical = mechanical_findings(package, candidate)
            reviews = []
            if not mechanical:
                for role in ('reviewer', 'auditor'):
                    # Each review sees source/draft, never the other review.
                    reviews.append(call(role, review_prompt(package, candidate), f'{role}_{attempt}'))
            report = evaluate(package, candidate, reviews)
            write_json(run_dir / f'qa_{attempt}.json', report)
            if report['status'] == 'PASS':
                output = publish(package, candidate, reviews, approved_dir)
                write_json(run_dir / 'state.json', {'status': 'PASS', 'calls': len(calls), 'output': str(output.resolve())})
                return output
        write_json(run_dir / 'state.json', {'status': 'BLOCKED', 'calls': len(calls), 'reason': 'Repair budget exhausted'})
        raise ValueError('Semantic QA blocked; inspect ' + str(run_dir))
    except Exception as error:
        if not (run_dir / 'state.json').exists():
            write_json(run_dir / 'state.json', {'status': 'BLOCKED', 'calls': len(calls), 'reason': type(error).__name__})
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--package', required=True)
    parser.add_argument('--max-repairs', type=int, default=1)
    parser.add_argument('--preflight', action='store_true')
    args = parser.parse_args()
    package = read_json(args.package)
    validate_package(package)
    preflight(load_config())
    if args.preflight:
        print('READY: package and role configuration valid; no API call made')
    else:
        print(run_package(package, max_repairs=args.max_repairs))


if __name__ == '__main__':
    main()
