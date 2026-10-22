"""Offline regressions for attribution, identity and scoped address defaults.

UNKNOWN is an intentional abstention, never a correct semantic translation score.
"""
import contextlib
from dataclasses import replace
import importlib
import io
import itertools
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

from semantic_gate import digest
from native_oauth.bns_prepass import UnifiedSemanticPreprocessor
from native_oauth.chapter_runner import run_chapter, split_scenes
from native_oauth.quality_gate import QualityGate4A
from native_oauth.scene_contract import EntityRecord, PronounRule, SceneContract
from native_oauth.semantic_context import (UNKNOWN, alias_index, dialogue_cues,
                                          normalize_profile, scoped_rules, context_tail)
from native_oauth.spot_auditor import SpotAuditor4B

ROOT = Path(__file__).resolve().parents[1]


class SemanticContextTests(unittest.TestCase):
    def setUp(self):
        self.module = importlib.import_module('native_oauth.book_49736.batch_pipeline_runner')
        self.entities = self.module.BASE_ENTITIES
        self.rules = self.module.BASE_PRONOUNS
        self.pre = UnifiedSemanticPreprocessor()

    def cue(self, source, **kwargs):
        return dialogue_cues(source, self.entities, **kwargs)[0]

    def test_explicit_three_person_routing_is_independent_of_roster_order(self):
        selected = [e for e in self.entities if e.zh in ('云千峰', '姜柔甲', '秦疏影')]
        for order in itertools.permutations(selected):
            cue = dialogue_cues('姜柔甲对秦疏影说：“你先坐。”', order)[0]
            self.assertEqual((cue['speaker'], cue['listener']), ('姜柔甲', '秦疏影'))

    def test_traditional_aliases_route_to_same_canonical_people(self):
        cue = self.cue('薑柔甲對秦疏影說：“你先坐。”')
        self.assertEqual((cue['speaker'], cue['listener']), ('姜柔甲', '秦疏影'))
        cue = self.cue('秦疏影對雲千峰說：“我去接孩子。”')
        self.assertEqual((cue['speaker'], cue['listener']), ('秦疏影', '云千峰'))
        self.assertNotEqual(cue['speaker_id'], cue['listener_id'])

    def test_simplified_qin_is_not_replaced_by_protagonist(self):
        cue = self.cue('秦疏影对云千峰说：“我去接孩子。”')
        self.assertEqual((cue['speaker'], cue['listener']), ('秦疏影', '云千峰'))

    def test_unattributed_dialogue_stays_unknown(self):
        for text in ('“我的哥哥消失了，我想知道他在哪。”',
                     '“小臻聽話，跟著周阿姨去睡覺，我在加班，晚一些回去，乖。”'):
            cue = self.cue(text)
            self.assertEqual((cue['speaker'], cue['listener']), (UNKNOWN, UNKNOWN))
            self.assertTrue(cue['review_required'])

    def test_speaker_only_never_selects_other_roster_member_as_listener(self):
        cue = self.cue('秦疏影說：“我去接孩子。”')
        self.assertEqual((cue['speaker'], cue['listener']), ('秦疏影', UNKNOWN))

    def test_named_recipient_of_unnamed_subject_is_not_the_speaker(self):
        for before in ('那年輕女人聽完這話，先是笑了，緊接著又哭了，然後又哭又笑的對雲千峰說道：',
                       '那女人對著雲千峰說道：', '她向雲千峰問道：'):
            cue = self.cue('“我有個哥哥。”', source_before=before)
            self.assertEqual(cue['speaker'], UNKNOWN)

    def test_person_being_looked_at_is_not_the_speaker(self):
        before = '緊接著，就看到薑柔甲快步走出去，很快又回來，手裡拎著一捆傘兵繩，然後看著雲千峰語速極快的說道：'
        self.assertEqual(self.cue('“從現在開始，你要和我形影不離。”', source_before=before)['speaker'], UNKNOWN)

    def test_accompanying_someone_is_not_explicit_addressee(self):
        cue = self.cue('“他們追上來了嗎？”', source_before='過了好一會，秦疏影一邊跟著雲千峰跑，一邊低聲問道：')
        self.assertEqual(cue['listener'], UNKNOWN)

    def test_possessive_relative_is_not_named_person(self):
        for text in ('秦疏影的儿子说：“你好。”', '秦疏影的儿子对云千峰说：“你好。”'):
            self.assertEqual(self.cue(text)['speaker'], UNKNOWN)

    def test_nested_quote_remains_one_complete_outer_utterance(self):
        raw = '“因為我們倆在這個空間的因果“祂”無法影響，所以我們是新人。”'
        cue = self.cue(raw, source_before='羅琳娜也轉了轉身，面對著雲千峰，說道：')
        self.assertEqual(cue['end'], len(raw))
        self.assertEqual(len(dialogue_cues(raw, self.entities)), 1)

    def test_post_quote_attribution(self):
        cue = self.cue('“我去接孩子。”秦疏影說道。')
        self.assertEqual(cue['speaker'], '秦疏影')
        self.assertEqual(cue['evidence'][0]['side'], 'suffix')

    def test_following_quote_attribution_does_not_leak_backwards(self):
        cues = dialogue_cues('“你好。”秦疏影說：“我去接孩子。”', self.entities)
        self.assertEqual(cues[0]['speaker'], UNKNOWN)
        self.assertEqual(cues[1]['speaker'], '秦疏影')

    def test_completed_prior_sentence_does_not_attribute_quote(self):
        self.assertEqual(self.cue('云千峰說他見過她。秦疏影走了。“你好。”')['speaker'], UNKNOWN)

    def test_attribution_with_negation_abstains(self):
        for text in ('秦疏影没有说：“我去。”', '秦疏影沒說：“我去。”',
                     '秦疏影并不是对云千峰说：“我去。”', '秦疏影想说：“我去。”'):
            self.assertEqual(self.cue(text)['speaker'], UNKNOWN)

    def test_conflicting_attributions_abstain(self):
        self.assertEqual(self.cue('云千峰說：“你好。”秦疏影說道。')['speaker'], UNKNOWN)

    def test_cross_paragraph_explicit_attribution(self):
        contract, _ = self.pre.build_scene_contract(1, 1,
            ['秦疏影对雲千峰说道：', '“我去接孩子。”'], self.entities, self.rules)
        cue = contract.semantic_context['dialogues'][0]
        self.assertEqual((cue['speaker'], cue['listener']), ('秦疏影', '云千峰'))
        self.assertEqual(cue['paragraph_id'], 2)

    def test_source_overlap_preserves_attribution_at_chunk_boundary(self):
        cue = self.cue('“我去接孩子。”', source_before='秦疏影对雲千峰说道：')
        self.assertEqual((cue['speaker'], cue['listener']), ('秦疏影', '云千峰'))

    def test_does_not_carry_speaker_after_completed_quote(self):
        cue = self.cue('“那就好。”', source_before='秦疏影說：“我去接孩子。”')
        self.assertEqual(cue['speaker'], UNKNOWN)

    def test_warning_or_threat_never_creates_ta_nguoi_rule(self):
        for text in ('云千峰对姜柔甲说：“别找死，快回来！”',
                     '云千峰对姜柔甲说：“找死！受死！”'):
            tagged, shifted, new_rules = self.pre.route_dialogues(text, self.entities)
            self.assertNotIn('HOSTILE_SHIFT', tagged)
            self.assertFalse(shifted)
            self.assertEqual(new_rules, [])

    def test_physical_reaction_never_asserts_arbitrary_other_subject(self):
        text = '云千峰一震，臉色微微一白，吐血，倒退，跌落，閉眼。'
        annotated, center = self.pre.process_comma_splice(text, list(reversed(self.entities)))
        self.assertNotIn('Ø', annotated)
        self.assertIsNone(center)
        self.assertEqual(annotated.replace(' [||] ', ''), text)

    def test_registry_has_one_identity_for_sc_tc_aliases(self):
        index = alias_index(self.entities)
        self.assertIs(index['云千峰'], index['雲千峰'])
        self.assertIs(index['姜柔甲'], index['薑柔甲'])
        self.assertEqual(len({e.entity_id for e in self.entities}), len(self.entities))

    def test_title_alias_preserves_form_of_address(self):
        mod = importlib.import_module('native_oauth.book_14713.batch_pipeline_runner')
        index = alias_index(mod.BASE_ENTITIES)
        self.assertIs(index['萧羽'], index['萧大师'])
        self.assertEqual(mod.BASE_GLOSSARY['萧大师'][0], 'Tiêu đại sư')
        self.assertEqual(mod.BASE_GLOSSARY['萧羽'][0], 'Tiêu Vũ')

    def test_equal_vi_names_alone_do_not_merge_identities(self):
        a = EntityRecord('甲', 'Cùng Tên', 'N', '', '', '')
        b = replace(a, zh='乙')
        entities, _, _ = normalize_profile('fixture', [a, b], [], {})
        self.assertEqual(len(entities), 2)
        self.assertNotEqual(entities[0].entity_id, entities[1].entity_id)

    def test_alias_collision_is_rejected(self):
        with self.assertRaises(ValueError):
            alias_index([EntityRecord('甲', 'A', 'N', '', '', '', aliases=('丙',)),
                         EntityRecord('乙', 'B', 'N', '', '', '', aliases=('丙',))])

    def test_same_person_address_rule_is_rejected(self):
        rule = PronounRule('云千峰', '雲千峰', 'DEFAULT', 'tôi', 'anh', '')
        with self.assertRaises(ValueError):
            normalize_profile('49736', self.entities, [rule], {})

    def test_foreign_names_have_one_current_editorial_form(self):
        glossary = self.module.BASE_GLOSSARY
        for name in ('罗琳娜', '羅琳娜'):
            self.assertEqual(glossary[name][0], 'La Lâm Na')
        self.assertEqual(glossary['法緹娜'][0], 'Fatina')
        self.assertEqual(glossary['蘇菲.鍾'][0], 'Sophie Chung')

    def test_known_name_variant_is_source_bound_review_warning_without_rewrite(self):
        contract, _ = self.pre.build_scene_contract(84, 1, ['羅琳娜走了。'], self.entities, self.rules)
        result = QualityGate4A().verify_paragraphs('§1 Lorina đi rồi.', 1, contract)
        self.assertIn('CHARACTER_NAME_VARIANT_REVIEW', [v.error_code for v in result.violations])
        self.assertEqual(result.sanitized_paragraphs[1], 'Lorina đi rồi.')
        unrelated, _ = self.pre.build_scene_contract(84, 1, ['她念出另一個名字。'], self.entities, self.rules)
        result = QualityGate4A().verify_paragraphs('§1 Cô đọc một cái tên khác: Lorina.', 1, unrelated)
        self.assertNotIn('CHARACTER_NAME_VARIANT_REVIEW', [v.error_code for v in result.violations])

    def test_unscoped_biography_and_wrong_elder_lock_not_forwarded(self):
        index = alias_index(self.entities)
        self.assertEqual(index['姜玉林'].narr_lock, '')
        self.assertTrue(all(not e.realm_title and not e.archetype for e in self.entities))

    def test_rule_range_scene_and_evidence_filtering(self):
        rule = PronounRule('秦疏影', '云千峰', 'INTIMATE', 'em', 'anh', '',
                           scope='source_local', valid_from_chapter=3, valid_to_chapter=4,
                           scene_id=2, evidence='原文證據')
        self.assertEqual(scoped_rules([rule], 3, 2, '原文證據'), [rule])
        for chapter, scene, source in ((2, 2, '原文證據'), (5, 2, '原文證據'),
                                      (3, 1, '原文證據'), (3, 2, '別的內容')):
            self.assertEqual(scoped_rules([rule], chapter, scene, source), [])

    def test_rule_known_by_paragraph_and_direction_do_not_leak(self):
        raw = ['秦疏影对云千峰说：“你好。”', '云千峰对秦疏影说：“你好。”']
        rule = PronounRule('秦疏影', '云千峰', 'DEFAULT', 'tôi', 'anh', '',
                           paragraph_id=1, known_by='秦疏影')
        contract, _ = self.pre.build_scene_contract(1, 1, raw, self.entities, [rule])
        cues = contract.semantic_context['dialogues']
        self.assertEqual(len(cues[0]['address_candidates']), 1)
        self.assertEqual(cues[1]['address_candidates'], [])
        rule = replace(rule, known_by='49736:qin_shuying')
        contract, _ = self.pre.build_scene_contract(1, 1, raw, self.entities, [rule])
        self.assertEqual(len(contract.semantic_context['dialogues'][0]['address_candidates']), 1)
        rule = replace(rule, known_by='姜柔甲')
        contract, _ = self.pre.build_scene_contract(1, 1, raw, self.entities, [rule])
        self.assertEqual(contract.semantic_context['dialogues'][0]['address_candidates'], [])

    def test_modern_school_friend_and_teacher_defaults_survive(self):
        mod = importlib.import_module('native_oauth.book_16014.batch_pipeline_runner')
        contract, _ = self.pre.build_scene_contract(1, 1,
            ['张羽对周伟说：“你好。”', '张羽对赵天行说：“您好。”'],
            mod.BASE_ENTITIES, mod.BASE_PRONOUNS, genre='XIANXIA_MODERN_SCHOOL')
        addresses = [q['address_candidates'][0] for q in contract.semantic_context['dialogues']]
        self.assertEqual([(r['self'], r['target']) for r in addresses], [('tôi', 'ông'), ('em', 'thầy')])

    def test_contract_roundtrip_preserves_semantic_evidence_and_scope(self):
        rule = replace(self.rules[0], valid_to_chapter=7, paragraph_id=1, evidence='quote|colon:')
        contract, _ = self.pre.build_scene_contract(1, 1, ['姜柔甲对秦疏影说：“你先坐。”'],
            self.entities, [rule], source_before='前文\n第二段', source_after='後文')
        parsed = SceneContract.from_pipe_dsl(contract.to_pipe_dsl())
        self.assertEqual(parsed.semantic_context, contract.semantic_context)
        self.assertEqual(parsed.entities, contract.entities)
        self.assertEqual(parsed.pronouns, contract.pronouns)

    def test_unresolved_roles_are_warnings_not_semantic_approval(self):
        contract, _ = self.pre.build_scene_contract(1, 1, ['“你好。”'], self.entities, self.rules)
        result = QualityGate4A().verify_paragraphs('§1 “Xin chào.”', 1, contract)
        self.assertTrue(result.is_pass)
        self.assertTrue(contract.semantic_context['review_required'])
        self.assertIn('DIALOGUE_ATTRIBUTION_UNRESOLVED', [v.error_code for v in result.violations])

    def test_regex_repair_cannot_change_disagreement_into_indifference(self):
        contract, _ = self.pre.build_scene_contract(1, 1, ['他不以為然。'], [], [])
        result = QualityGate4A().verify_paragraphs('§1 Anh ấy không cho là đúng.', 1, contract)
        after = SpotAuditor4B().apply_deterministic_repair(result, contract)
        self.assertEqual(after.sanitized_paragraphs[1], 'Anh ấy không cho là đúng.')
        self.assertTrue(result.is_pass)
        self.assertIn('không tán đồng', contract.idiom_hints[0].suggestions)

    def test_legacy_16_samples_remain_exactly_bound_to_current_source(self):
        audit = json.loads((ROOT / 'audit/semantic_address_review_20261021.evidence.json').read_text(encoding='utf-8'))
        self.assertEqual(len(audit['samples']), 16)
        for sample in audit['samples']:
            source = json.loads((self.module.SOURCES_DIR / f"source_chapter_{sample['chapter']:04d}.json").read_text(encoding='utf-8'))
            self.assertIn(sample['source'], [p['source'] for p in source['segments']])
            # Replaying only an isolated quote must not assert the protagonist.
            if sample['source'].startswith('“') and sample['source'].endswith('”'):
                self.assertEqual(self.cue(sample['source'])['speaker'], UNKNOWN)

    def test_both_49736_entrypoints_use_same_profiles_and_prompt(self):
        other = importlib.import_module('native_oauth.book_49736.wujian_pipeline_runner')
        self.assertEqual(other.get_base_entities_and_pronouns(), (self.entities, self.rules))
        self.assertEqual(other.SYSTEM_PROMPT, self.module.SYSTEM_PROMPT)

    def test_overlap_contains_whole_nearest_source_paragraphs(self):
        self.assertEqual(context_tail(['甲' * 5, '乙' * 5, '丙' * 5], limit=10), '乙乙乙乙乙\n丙丙丙丙丙')
        self.assertEqual(context_tail(['甲' * 20], limit=10), '')

    def test_scene_boundary_keeps_quote_introduction_when_budget_allows(self):
        paragraphs = ['甲。', '乙。', '秦疏影說：', '“我去。”', '丙。']
        chunks = split_scenes(paragraphs, max_paragraphs=3, max_characters=100)
        self.assertEqual(chunks[0], paragraphs[:2])
        self.assertEqual(chunks[1][:2], paragraphs[2:4])
        self.assertEqual([p for chunk in chunks for p in chunk], paragraphs)
        self.assertTrue(all(len(chunk) <= 3 for chunk in chunks))

    def test_scene_boundary_never_exceeds_budget_to_keep_dialogue_together(self):
        paragraphs = ['甲。', '秦疏影說：', '“' + '我' * 20 + '”']
        chunks = split_scenes(paragraphs, max_paragraphs=2, max_characters=23)
        self.assertEqual([p for chunk in chunks for p in chunk], paragraphs)
        self.assertTrue(all(sum(map(len, chunk)) <= 23 for chunk in chunks))

    def test_all_four_real_scene_builders_use_source_first_profile_and_overlap(self):
        for name in ('book_14713.batch_pipeline_runner', 'book_16014.batch_pipeline_runner',
                     'book_49736.batch_pipeline_runner', 'book_49736.wujian_pipeline_runner'):
            module = importlib.import_module('native_oauth.' + name)
            with tempfile.TemporaryDirectory() as temp, contextlib.ExitStack() as stack:
                stack.enter_context(patch.object(module, 'RUNS_DIR', Path(temp)))
                if 'wujian' in name:
                    transport = stack.enter_context(patch.object(module, 'invoke_llm', return_value='§1 “Xin chào.”'))
                else:
                    transport = stack.enter_context(patch.object(module, 'run', return_value={
                        'status': 'SUCCESS', 'exit_code': 0, 'actual_model': 'fixture',
                        'result': {'response': '§1 “Xin chào.”'}}))
                kwargs = {'preprocessor': self.pre, 'gate': QualityGate4A(), 'auditor': SpotAuditor4B(),
                          'chap_num': 1, 'scene_idx': 1, 'raw_paras': ['“你好。”'],
                          'prev_vi_context': 'Bản nháp cũ.', 'target_model': 'fixture',
                          'prev_source_context': '前文只讀', 'next_source_context': '後文只讀'}
                if 'wujian' in name:
                    kwargs['cartridge'] = None
                _, _, passed = module.translate_scene(**kwargs)
                self.assertTrue(passed)
                if 'wujian' in name:
                    prompt = transport.call_args.args[0]
                else:
                    prompt = transport.call_args.kwargs['prompt_file'].read_text(encoding='utf-8')
                self.assertIn('SOURCE_FIRST_V2', prompt)
                self.assertIn('前文只讀', prompt)
                self.assertIn('後文只讀', prompt)
                self.assertIn('loc=UNKNOWN', prompt)
                self.assertNotIn('Trưởng bối Khương gia', prompt)
                gate = json.loads((Path(temp) / 'chapter_0001/scene_1/gate.json').read_text(encoding='utf-8'))
                self.assertTrue(gate['semantic_context']['review_required'])
                self.assertEqual(gate['semantic_context']['dialogues'][0]['speaker'], UNKNOWN)

    def test_adaptive_split_gets_source_overlap_with_no_duplicate_owned_ids(self):
        from native_oauth.run_agy import IncompleteNativeOutput
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sources = root / 'sources'
            sources.mkdir()
            paragraphs = ['標題', '秦疏影对云千峰说：', '“我去接孩子。”', '云千峰點頭。']
            source = {'book_id': 'fixture', 'chapter': 1, 'title': '標題',
                      'segments': [{'id': f'c0001p{i:04d}', 'source': t} for i, t in enumerate(paragraphs, 1)]}
            source['package_hash'] = digest(source)
            (sources / 'source_chapter_0001.json').write_text(json.dumps(source), encoding='utf-8')
            calls = []
            def callback(scene, chunk, context):
                calls.append((chunk, context))
                if len(chunk) > 2:
                    raise IncompleteNativeOutput('fixture timeout')
                return {i: 'Thử.' for i in range(1, len(chunk) + 1)}, '', True
            with patch('native_oauth.chapter_runner.get_session_monitor', return_value=Mock()), contextlib.redirect_stdout(io.StringIO()):
                self.assertTrue(run_chapter(1, 'fixture', 'Fixture', 'URBAN', sources,
                    root / 'output_dich', callback, 'fixture'))
            self.assertEqual([len(c[0]) for c in calls], [4, 2, 2])
            self.assertTrue(calls[2][1]['prev_zh'].endswith(paragraphs[1]))
            self.assertEqual(calls[1][1]['next_zh'], '\n'.join(paragraphs[2:]))
            candidate = json.loads((root / 'drafts/chuong_0001.dich.json').read_text(encoding='utf-8'))
            self.assertEqual([r['raw_zh'] for r in candidate['bilingual_alignment']], paragraphs)
            self.assertEqual(candidate['status'], 'DRAFT_STRUCTURAL_PASS_UNREVIEWED')


if __name__ == '__main__':
    unittest.main()
