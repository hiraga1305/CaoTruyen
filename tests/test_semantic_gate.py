import copy
import json
import tempfile
import unittest
from pathlib import Path
from semantic_gate import (build_package, candidate_hash, CHECKS, evaluate, publish,
                           make_context, write_json, parse_model_json, mechanical_findings)
from source_integrity import extract_paragraphs, terminology_hint
from quality_pipeline import run_package, preflight


def fixture():
    p = build_package(1, 'test', ['张羽没有杀死他。', '至少900克。'], {'张羽': 'Trương Vũ'}, 'fixture')
    c = {'package_hash': p['package_hash'], 'model': 'fixture/translator',
         'segments': [{'id': p['segments'][0]['id'], 'text': 'Trương Vũ không giết anh ta.'},
                      {'id': p['segments'][1]['id'], 'text': 'Ít nhất 900 gram.'}]}
    reviews = []
    for name in ('reviewer', 'auditor'):
        reviews.append({'model': 'fixture/' + name, 'package_hash': p['package_hash'],
                        'candidate_hash': candidate_hash(c), 'verdict': 'PASS',
                        'checks': dict.fromkeys(CHECKS, True), 'issues': [],
                        'segments': [{'id': s['id'], 'source_quote': s['source'],
                                      'target_quote': t['text'], 'verdict': 'PASS',
                                      'reason': 'Fixture only; assertions supplied by test'}
                                     for s, t in zip(p['segments'], c['segments'])]})
    return p, c, reviews


CONFIG = {'quality_roles': {r: {'provider': 'fixture', 'models': [r]}
                           for r in ('translator', 'reviewer', 'auditor')}}


class GateTests(unittest.TestCase):
    def test_fixture_pass_is_machine_contract_only(self):
        self.assertEqual(evaluate(*fixture())['status'], 'PASS')

    def test_deletion_order_duplication_blocked(self):
        for transform in (lambda a: a[:-1], lambda a: a[::-1], lambda a: a + a):
            p, c, r = fixture()
            c['segments'] = transform(c['segments'])
            self.assertEqual(evaluate(p, c, r)['status'], 'BLOCKED')

    def test_stale_review_after_negation_mutation(self):
        p, c, r = fixture()
        c['segments'][0]['text'] = 'Trương Vũ giết anh ta.'
        self.assertEqual(evaluate(p, c, r)['status'], 'BLOCKED')

    def test_missing_or_fake_evidence_blocks(self):
        p, c, r = fixture()
        r[0]['segments'][0]['source_quote'] = 'not in original'
        self.assertEqual(evaluate(p, c, r)['status'], 'BLOCKED')

    def test_unchecked_semantic_dimension_blocks(self):
        p, c, r = fixture()
        r[0]['checks']['negation_modality'] = False
        self.assertEqual(evaluate(p, c, r)['status'], 'BLOCKED')

    def test_review_fail_blocks_and_preserves_original(self):
        p, c, r = fixture()
        r[0]['verdict'] = 'FAIL'
        r[0]['issues'] = [{'id': p['segments'][0]['id'], 'reason': 'changed meaning'}]
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                publish(p, c, r, temp)
            self.assertFalse(list(Path(temp).glob('*.txt')))

    def test_empty_residual_and_glossary_drift(self):
        for text in ('', '张羽 không giết anh ta.', 'Trương Phi giết anh ta.'):
            p, c, r = fixture()
            c['segments'][0]['text'] = text
            self.assertTrue(mechanical_findings(p, c))

    def test_same_model_cannot_self_approve(self):
        p, c, r = fixture()
        r[0]['model'] = c['model']
        self.assertEqual(evaluate(p, c, r)['status'], 'BLOCKED')

    def test_package_glossary_mutation_detected(self):
        p, c, r = fixture()
        p['glossary']['张羽'] = 'changed'
        with self.assertRaises(ValueError):
            evaluate(p, c, r)

    def test_context_requires_approved_hash_and_source(self):
        p, c, r = fixture()
        with tempfile.TemporaryDirectory() as temp:
            output = publish(p, c, r, temp)
            context = make_context(output.with_suffix('.evidence.json'))
            next_p = build_package(2, 'next', ['张羽来了。'], p['glossary'], 'fixture2', context)
            self.assertEqual(next_p['chapter'], 2)
            context['facts'][0]['source_quote'] = 'invented'
            with self.assertRaises(ValueError):
                build_package(2, 'next', ['张羽来了。'], p['glossary'], 'fixture2', context)

    def test_context_evidence_tamper_detected(self):
        p, c, r = fixture()
        with tempfile.TemporaryDirectory() as temp:
            output = publish(p, c, r, temp)
            evidence = output.with_suffix('.evidence.json')
            context = make_context(evidence)
            write_json(evidence, {'changed': True})
            with self.assertRaises(ValueError):
                build_package(2, 'next', ['张羽来了。'], p['glossary'], 'fixture2', context)

    def test_context_missing_blocks_chapter_two(self):
        with self.assertRaises(ValueError):
            build_package(2, 'next', ['他来了。'], {}, 'fixture2')

    def test_source_container_preserves_links_and_marker_narrative(self):
        html = '<aside>广告</aside><div id="content">他想到了下一章。<br>张<a>羽</a>没有杀死他。<script>garbage</script></div>'
        self.assertEqual(extract_paragraphs(html), ['他想到了下一章。', '张羽没有杀死他。'])

    def test_missing_container_blocks(self):
        with self.assertRaises(ValueError):
            extract_paragraphs('<p>他来了。</p>')

    def test_live_template_boundary_excludes_navigation_and_ads(self):
        html = '<div class="toplink">上一章</div><table>广告</table><br>&nbsp;&nbsp;&nbsp;&nbsp;第1章 面试<br /><br />&nbsp;&nbsp;&nbsp;&nbsp;张<a>羽</a>没有杀死他。<br /><br /><div class="bottomlink">下一章</div>广告'
        self.assertEqual(extract_paragraphs(html), ['第1章 面试', '张羽没有杀死他。'])

    def test_fabricated_context_statement_blocks(self):
        p, c, r = fixture()
        with tempfile.TemporaryDirectory() as temp:
            output = publish(p, c, r, temp)
            context = make_context(output.with_suffix('.evidence.json'))
            context['facts'][0]['statement'] = 'Trương Vũ đã giết anh ta.'
            with self.assertRaises(ValueError):
                build_package(2, 'next', ['他来了。'], {}, 'fixture2', context)

    def test_malformed_candidate_yields_blocked_report(self):
        p, c, r = fixture()
        for candidate in (None, [], {'segments': None}, {'segments': ['wrong']}):
            self.assertEqual(evaluate(p, candidate, r)['status'], 'BLOCKED')

    def test_fake_source_ids_and_chapter_one_context_rejected(self):
        from semantic_gate import digest, validate_package
        p, c, r = fixture()
        for mutation in ('id', 'context', 'chapter'):
            package = copy.deepcopy(p)
            if mutation == 'id':
                package['segments'][0]['id'] = 'c0002p0001'
            elif mutation == 'context':
                package['context'] = {'facts': [{'statement': 'invented'}]}
            else:
                package['chapter'] = -1
            package['package_hash'] = digest({k:v for k,v in package.items() if k != 'package_hash'})
            with self.assertRaises(ValueError):
                validate_package(package)

    def test_input_budget_stops_before_api_call(self):
        p, c, r = fixture()
        config = copy.deepcopy(CONFIG)
        config['settings'] = {'max_quality_input_chars': 10}
        calls = []
        with self.assertRaises(ValueError):
            run_package(p, client=lambda *args, **kwargs: calls.append(1), config=config)
        self.assertEqual(calls, [])

    def test_later_review_budget_is_checked_before_api(self):
        from semantic_gate import translation_prompt
        p, c, r = fixture()
        config = copy.deepcopy(CONFIG)
        config['settings'] = {'max_quality_input_chars': len(translation_prompt(p)) + 1}
        calls = []
        def client(*args, **kwargs):
            calls.append(kwargs['role'])
            return json.dumps(c, ensure_ascii=False), {}, 'fixture/translator'
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                run_package(p, Path(temp)/'runs', Path(temp)/'approved', 1, client, config)
            self.assertEqual(calls, ['translator'])

    def test_hints_never_rewrite_negation_or_punctuation(self):
        raw = '他将来不会杀死任何人。她的确不是他的朋友。'
        self.assertEqual(terminology_hint(raw, {}), '')

    def test_partial_model_json_rejected(self):
        with self.assertRaises(json.JSONDecodeError):
            parse_model_json('{"segments": [')

    def test_preflight_missing_overlap_rejected(self):
        with self.assertRaises(ValueError):
            preflight({})
        config = copy.deepcopy(CONFIG)
        config['quality_roles']['reviewer']['models'] = ['translator']
        with self.assertRaises(ValueError):
            preflight(config)

    def test_repair_is_reviewed_again_and_budget_bounded(self):
        p, c, _ = fixture()
        called = []
        def client(prompt, system_instruction=None, role=None):
            called.append(role)
            model = 'fixture/' + role
            if role == 'translator':
                payload = copy.deepcopy(c)
                payload['identity_basis'] = 'api_transport'
                if called.count('translator') == 1:
                    payload['segments'][1]['text'] = 'Hơn 900 gram.'
            else:
                # Build reviewer assertions for this fixture, not a real quality measurement.
                draft = json.loads(prompt.split('\nDRAFT:\n')[1])
                payload = {'package_hash': p['package_hash'], 'candidate_hash': candidate_hash(draft),
                           'verdict': 'FAIL' if 'Hơn' in draft['segments'][1]['text'] else 'PASS',
                           'checks': dict.fromkeys(CHECKS, True),
                           'issues': [{'id': p['segments'][1]['id'], 'reason': '≥ changed to >'}] if 'Hơn' in draft['segments'][1]['text'] else [],
                           'segments': [{'id': s['id'], 'source_quote': s['source'], 'target_quote': t['text'],
                                         'verdict': 'PASS', 'reason': 'fixture assertion'} for s, t in zip(p['segments'], draft['segments'])]}
            return json.dumps(payload, ensure_ascii=False), {}, model
        with tempfile.TemporaryDirectory() as temp:
            output = run_package(p, Path(temp)/'runs', Path(temp)/'approved', 1, client, CONFIG)
            self.assertIn('Ít nhất 900', output.read_text(encoding='utf-8'))
            self.assertEqual(called, ['translator', 'reviewer', 'auditor'] * 2)

    def test_bad_draft_stops_after_budget(self):
        p, c, _ = fixture()
        count = []
        def client(*args, **kwargs):
            count.append(kwargs['role'])
            return json.dumps({'package_hash': p['package_hash'], 'segments': []}), {}, 'fixture/translator'
        with tempfile.TemporaryDirectory() as temp:
            with self.assertRaises(ValueError):
                run_package(p, Path(temp)/'runs', Path(temp)/'approved', 1, client, CONFIG)
            self.assertEqual(count, ['translator', 'translator'])
            self.assertFalse((Path(temp)/'approved').exists())


if __name__ == '__main__':
    unittest.main()
