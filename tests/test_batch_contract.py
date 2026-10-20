"""Locked integrity tests: these never claim machine checks prove fluent meaning."""
import copy
import json
import unittest

from semantic_gate import digest
from native_oauth.batch_contract import (build_story_state, plan_parallel_block,
    validate_and_merge, commit_block, source_anchor_candidates, make_scene_contract)


def package(chapter, paragraphs):
    value = {'version': 'raw-source-benchmark-1', 'chapter': chapter, 'title': 'fixture',
             'segments': [{'id': f'c{chapter:04d}p{i:04d}', 'source': text}
                          for i, text in enumerate(paragraphs, 1)]}
    value['package_hash'] = digest(value)
    return value


def ledger(identifier, source_id, quote, keys, **extras):
    return {'ledger_id': identifier, 'kind': 'event', 'keys': keys,
            'references': [{'source_id': source_id, 'source_quote': quote}], **extras}


def fixture():
    sources = [package(1, ['张羽没有杀死周伟。', '至少900克，两万。', '周伟说：“我不知道。”', '最后他离开。'])]
    state = build_story_state(sources, [ledger('e1', 'c0001p0001', '张羽没有杀死周伟', ['张羽', '周伟'])],
                              {'张羽': 'Trương Vũ'}, {'genre': 'hien_dai'})
    plan = plan_parallel_block(state, sources, max_owned_paragraphs=2, overlap=1)
    candidates = [{'job_id': job['job_id'], 'contract_hash': job['contract_hash'],
                   'state_hash': job['state_hash'],
                   'segments': [{'id': s['id'], 'text': 'fixture:' + s['source']}
                                for s in job['owned_segments']]} for job in plan['jobs']]
    return sources, state, plan, candidates


class BatchContractTests(unittest.TestCase):
    def test_source_prepass_accepts_chapter2_without_unapproved_vn_summary(self):
        source = package(1, ['他回家。'])
        next_source = package(2, ['后来他又回家。'])
        state = build_story_state([source, next_source], [], {}, {}, through_chapter=1)
        plan = plan_parallel_block(state, [next_source])
        self.assertEqual(plan['from_chapter'], 2)
        self.assertNotIn('approved_translation', state)

    def test_quotes_and_source_hashes_must_match(self):
        sources, _, _, _ = fixture()
        with self.assertRaisesRegex(ValueError, 'quote'):
            build_story_state(sources, [ledger('bad', 'c0001p0001', '周伟死了', ['周伟'])], {}, {})
        corrupt = copy.deepcopy(sources)
        corrupt[0]['segments'][0]['source'] = 'mutated'
        with self.assertRaisesRegex(ValueError, 'package_hash'):
            build_story_state(corrupt, [], {}, {})
        with self.assertRaisesRegex(ValueError, 'Retrieval keys'):
            build_story_state(sources, [ledger('bad', 'c0001p0001', '张羽没有杀死周伟', ['未来姓名'])], {}, {})

    def test_all_jobs_freeze_same_state_exact_ownership_and_readonly_overlap(self):
        _, state, plan, candidates = fixture()
        self.assertEqual({j['state_hash'] for j in plan['jobs']}, {state['state_hash']})
        self.assertEqual(plan['jobs'][0]['neighbor_segments'][0]['id'], 'c0001p0003')
        merged = validate_and_merge(plan, list(reversed(candidates)), state)
        self.assertEqual([s['id'] for s in merged['segments']], plan['ordered_ids'])
        self.assertEqual(merged['status'], 'DRAFT_MERGED_UNREVIEWED')
        contaminated = copy.deepcopy(candidates)
        contaminated[0]['segments'].append({'id': 'c0001p0003', 'text': 'neighbor'})
        with self.assertRaisesRegex(ValueError, 'neighbor'):
            validate_and_merge(plan, contaminated, state)

    def test_future_quote_and_generated_interpretation_cannot_leak_to_worker(self):
        sources = [package(1, ['甲说他不知。', '乙来了。']), package(2, ['甲其实就是乙。'])]
        entries = [ledger('past', 'c0001p0001', '甲说他不知', ['甲'], interpretation='甲其实就是乙'),
                   ledger('future', 'c0002p0001', '甲其实就是乙', ['甲', '乙'])]
        state = build_story_state(sources, entries, {}, {})
        plan = plan_parallel_block(state, sources, max_owned_paragraphs=1, overlap=0)
        first = plan['jobs'][0]['context_capsule']
        self.assertEqual([e['ledger_id'] for e in first['ledger']], ['past'])
        self.assertNotIn('甲其实就是乙', json.dumps(first, ensure_ascii=False))

    def test_future_confirming_reference_is_stripped_even_for_older_event(self):
        sources = [package(1, ['甲说他不知。']), package(2, ['甲其实就是乙。'])]
        entry = ledger('mixed', 'c0001p0001', '甲说他不知', ['甲', '乙'])
        entry['references'].append({'source_id': 'c0002p0001', 'source_quote': '甲其实就是乙'})
        state = build_story_state(sources, [entry], {}, {})
        first = plan_parallel_block(state, sources, max_owned_paragraphs=1, overlap=0)['jobs'][0]['context_capsule']
        shown = first['ledger'][0]
        self.assertEqual(shown['keys'], ['甲'])
        self.assertEqual(len(shown['references']), 1)

    def test_required_state_budget_never_silently_drops_entity(self):
        sources, state, _, _ = fixture()
        with self.assertRaisesRegex(ValueError, 'capsule budget'):
            plan_parallel_block(state, sources, max_capsule_chars=100)
        with self.assertRaisesRegex(ValueError, 'never truncate'):
            plan_parallel_block(state, sources, max_source_chars=1)

    def test_stale_state_changed_contract_and_missing_result_are_rejected(self):
        sources, state, plan, candidates = fixture()
        newer = build_story_state(sources, [], state['glossary'], state['style_profile'], version=2)
        with self.assertRaisesRegex(ValueError, 'Stale'):
            validate_and_merge(plan, candidates, newer)
        bad = copy.deepcopy(candidates)
        bad[0]['contract_hash'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'another contract'):
            validate_and_merge(plan, bad, state)
        with self.assertRaisesRegex(ValueError, 'Missing'):
            validate_and_merge(plan, candidates[:1], state)

    def test_commit_gate_binding_order_and_new_state_invalidate_every_old_job(self):
        sources, state, plan, candidates = fixture()
        merged = validate_and_merge(plan, candidates, state)
        receipt = {'status': 'PASS', 'merged_hash': merged['merged_hash'],
                   'plan_hash': plan['plan_hash'], 'evidence_hash': 'external-evidence-fixture'}
        with self.assertRaisesRegex(ValueError, 'acceptance'):
            commit_block(state, plan, merged, sources, [], {**receipt, 'merged_hash': 'other'})
        newer = commit_block(state, plan, merged, sources, [], receipt, gate_verifier=lambda *args: True)
        self.assertEqual(newer['through_chapter'], 1)
        self.assertEqual(newer['version'], 2)
        self.assertEqual(newer['previous_state_hash'], state['state_hash'])
        with self.assertRaisesRegex(ValueError, 'Stale'):
            commit_block(newer, plan, merged, sources, [], receipt, gate_verifier=lambda *args: True)
        with self.assertRaisesRegex(ValueError, 'Stale'):
            validate_and_merge(plan, candidates, newer)

    def test_conflicting_ledger_update_requires_exact_entry_predecessor(self):
        sources, state, plan, candidates = fixture()
        merged = validate_and_merge(plan, candidates, state)
        receipt = {'status': 'PASS', 'merged_hash': merged['merged_hash'],
                   'plan_hash': plan['plan_hash'], 'evidence_hash': 'fixture'}
        update = ledger('e1', 'c0001p0003', '周伟说', ['周伟'])
        with self.assertRaisesRegex(ValueError, 'preceding entry'):
            commit_block(state, plan, merged, sources, [update], receipt, gate_verifier=lambda *args: True)
        update['previous_entry_hash'] = state['ledger'][0]['entry_hash']
        newer = commit_block(state, plan, merged, sources, [update], receipt, gate_verifier=lambda *args: True)
        self.assertEqual(newer['ledger'][0]['references'][0]['source_id'], 'c0001p0003')

    def test_numerics_and_negation_are_source_candidates_never_translation_oracle(self):
        anchors = source_anchor_candidates('至少900克，没有超过两万。')
        self.assertEqual([a['quote'] for a in anchors], ['至少', '900', '没有', '超过', '两万'])
        self.assertTrue(all(a['status'] == 'lexical_candidate_requires_context' for a in anchors))

    def test_fake_pass_receipt_cannot_commit_without_verified_external_gate(self):
        sources, state, plan, candidates = fixture()
        merged = validate_and_merge(plan, candidates, state)
        receipt = {'status': 'PASS', 'merged_hash': merged['merged_hash'],
                   'plan_hash': plan['plan_hash'], 'evidence_hash': 'self-claimed'}
        with self.assertRaisesRegex(ValueError, 'trusted external'):
            commit_block(state, plan, merged, sources, [], receipt)
        with self.assertRaisesRegex(ValueError, 'trusted external'):
            commit_block(state, plan, merged, sources, [], receipt, gate_verifier=lambda *args: False)

    def test_scene_excerpt_has_exact_ownership_and_no_publication_claim(self):
        sources, state, _, _ = fixture()
        scene = make_scene_contract(state, sources, ['c0001p0002', 'c0001p0003'], overlap=1)
        self.assertEqual([s['id'] for s in scene['owned_segments']], ['c0001p0002', 'c0001p0003'])
        self.assertEqual([s['id'] for s in scene['neighbor_segments']], ['c0001p0001', 'c0001p0004'])
        self.assertTrue(scene['experimental_partial_scene'])
        with self.assertRaisesRegex(ValueError, 'contiguous'):
            make_scene_contract(state, sources, ['c0001p0001', 'c0001p0003'])

    def test_declared_source_scene_boundaries_preserve_all_paragraphs(self):
        sources, state, _, _ = fixture()
        plan = plan_parallel_block(state, sources, max_owned_paragraphs=3,
                                   scene_end_ids=['c0001p0001', 'c0001p0004'])
        self.assertEqual([len(j['owned_segments']) for j in plan['jobs']], [1, 3])
        with self.assertRaisesRegex(ValueError, 'entire block'):
            plan_parallel_block(state, sources, scene_end_ids=['c0001p0001'])


if __name__ == '__main__':
    unittest.main()
