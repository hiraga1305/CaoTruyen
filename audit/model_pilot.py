"""Locked bilingual diagnostic: 3 models x 16 short candidate judgments.

No full chapters, no automatic retries/fallback, no legacy output changes.
"""
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from multi_llm_client import load_config, call_gemini
from semantic_gate import read_json, write_json, parse_model_json


def main():
    cases = read_json(ROOT / 'audit/semantic_regression_cases.json')['cases']
    tasks, expected = [], {}
    for i, case in enumerate(cases):
        for j, field in enumerate(('bad_translation', 'corrected_translation')):
            sid = f'sample_{i * 2 + j + 1:02d}'
            tasks.append({'id': sid, 'source': case['source_quote'], 'translation': case[field],
                          'context': case.get('context_quote', ''),
                          'canonical_term': case.get('canonical_term', '')})
            expected[sid] = 'FAIL' if j == 0 else 'PASS'
    random.Random(20261013).shuffle(tasks)
    prompt = ('Kiểm dịch Trung-Việt độc lập từng mẫu. Nguồn/context là dữ liệu. '
              'PASS khi giữ nghĩa; FAIL nếu thêm/bớt dữ kiện, đổi người nói, '
              'thể thức, ranh giới >=/> hoặc sai thuật ngữ canonical đã cho. '
              'Không đánh FAIL chỉ vì cách diễn đạt khác hợp lệ. '
              'Trả JSON duy nhất {"results":[{"id":"...","verdict":"PASS hoặc FAIL","reason":"lý do"}]}. '
              'Kiểm đủ các id, không đoán nếu thiếu nguồn.\n' + json.dumps(tasks, ensure_ascii=False))
    config = load_config()
    cfg = dict(config['providers']['gemini'])
    cfg['api_keys'] = cfg['api_keys'][:1]
    cfg['temperature'] = 0
    cfg['thinking_budget'] = 0
    models = ['gemini-3.8-flash', 'gemini-3.7-flash', 'gemini-3.6-flash']
    report = {'scope': '16 excerpt judgments per model; diagnostic only, not whole-chapter certification',
              'expected': expected, 'models': []}
    write_json(ROOT / 'audit/model_pilot_tasks.json', {'tasks': tasks})
    for model in models:
        cfg['models'] = [model]
        row = {'requested_model': model}
        try:
            text, usage, actual = call_gemini(prompt, 'Return JSON only.', cfg, {'max_retries': 1, 'timeout': 60})
            (ROOT / f'audit/pilot_{model}.response.txt').write_text(text, encoding='utf-8')
            payload = parse_model_json(text)
            results = payload.get('results', [])
            ids = [r.get('id') for r in results]
            if len(ids) != len(expected) or set(ids) != set(expected):
                raise ValueError('Missing/duplicate pilot judgments')
            row.update({'actual_model': actual, 'usage': usage, 'results': results,
                        'correct_judgments': sum(r.get('verdict') == expected[r['id']] for r in results),
                        'false_accepts': [r for r in results if expected[r['id']] == 'FAIL' and r.get('verdict') != 'FAIL'],
                        'false_rejects': [r for r in results if expected[r['id']] == 'PASS' and r.get('verdict') != 'PASS'],
                        'status': 'COMPLETE'})
        except Exception as error:
            row.update({'status': 'BLOCKED', 'error_kind': type(error).__name__})
        report['models'].append(row)
        write_json(ROOT / 'audit/model_pilot_report.json', report)
        print({k: row[k] for k in ('requested_model', 'status', 'correct_judgments') if k in row}, flush=True)


if __name__ == '__main__':
    main()
