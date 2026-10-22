"""Unit Test Suite for Module 2: Tier 1 NLP Pre-processor (bns_prepass.py).
Tests complexity, advisory rhythm, conservative attribution and DSL packaging.
"""

import unittest
from native_oauth.scene_contract import EntityRecord, PronounRule
from native_oauth.bns_prepass import (
    evaluate_scene_complexity,
    UnifiedSemanticPreprocessor,
    compute_syntactic_entropy,
    compute_coreference_ambiguity,
    compute_classical_density,
    compute_state_volatility,
)


class TestModule2Prepass(unittest.TestCase):
    def setUp(self):
        self.preprocessor = UnifiedSemanticPreprocessor()
        self.ent_hanli = EntityRecord("韓立", "Hàn Lập", "M", "hắn", "Luyện Khí tầng 12", "Cẩn trọng")
        self.ent_fengyue = EntityRecord("封岳", "Phong Nhạc", "M", "gã", "Luyện Khí tầng 13", "Tàn độc")

    def test_01_complexity_scoring_and_tier_routing(self):
        """Verify calculation of S_scene and proper tier allocation (LOW, MED, HIGH)."""
        # Low complexity case (simple narration, 1 character)
        low_sents = ["韓立盤膝而坐，閉目調息，運轉大衍決。"]
        m_low = evaluate_scene_complexity(low_sents, ["韓立"], False, 0)
        self.assertLess(m_low.s_scene, 0.45)
        self.assertIn(m_low.route_tier, ["LOW", "MED"])

        # High complexity case (combat, multiple entities, commas, hostile shift, idioms)
        high_sents = [
            "韓立眼神一冷，單手一掐訣，青竹蜂雲劍化為三十六道丈許長的青虹，帶著破空聲朝著那黑衣老者當頭罩下，發出一連串沉悶爆裂聲，震得他氣血一陣翻湧，臉色微微一白。",
            "封岳眼中寒芒一閃，獰笑道：“找死！今日便將你抽魂煉魄！”",
            "二人各施手段，殺得天昏地暗，日月無光，周圍山峰寸寸碎裂，灰飛煙滅。",
        ]
        m_high = evaluate_scene_complexity(high_sents, ["韓立", "封岳"], True, 1)
        self.assertGreater(m_high.s_scene, 0.35)
        self.assertEqual(m_high.pacing_mode, "COMBAT_FAST")

    def test_02_pro_drop_and_comma_splice_breaking(self):
        """Suggest rhythm without inventing an implicit subject."""
        # 8-clause sentence with victim reaction
        raw_text = (
            "韓立單手一拍儲物袋，青竹蜂雲劍飛掠而出，迎風化為丈許長青虹，"
            "將那血色光刃盡數接下，發出一連串爆裂聲，身軀一震，臉色微微一白。"
        )
        entities = [self.ent_hanli, self.ent_fengyue]
        processed, center = self.preprocessor.process_comma_splice(raw_text, entities)

        # Must have rhythm break symbol [||]
        self.assertIn("[||]", processed)
        # A reaction does not prove the other roster member is its subject.
        self.assertNotIn("Ø_SHIFT", processed)
        self.assertIsNone(center)

    def test_03_dialogue_routing_and_hostile_shift(self):
        """Attribute only a supported speaker; words do not create pronoun rules."""
        # Courteous dialogue
        courteous_text = "韓立拱了拱手，淡淡說道：“封道友何必苦苦相逼？”"
        entities = [self.ent_hanli, self.ent_fengyue]
        proc1, rup1, _ = self.preprocessor.route_dialogues(courteous_text, entities)
        self.assertIn("[Q1:韓立->UNKNOWN|state:SOURCE_CONTEXT", proc1)
        self.assertFalse(rup1)

        # Hostile shift dialogue
        hostile_text = "封岳臉色一沉，厲聲獰笑道：“敬酒不吃吃罰酒的小輩，納命來！”"
        proc2, rup2, updated_pronouns = self.preprocessor.route_dialogues(hostile_text, entities)
        self.assertIn("state:SOURCE_CONTEXT", proc2)
        self.assertNotIn("HOSTILE_SHIFT", proc2)
        self.assertFalse(rup2)
        self.assertEqual(updated_pronouns, [])

    def test_04_numeric_lock_and_idiom_annotations(self):
        """Verify extraction of [Mk:...] numeric tags and [Ik:...] idiom hints."""
        text = "韓立對他的威脅不以為然，催動三十六道飛劍，重達三萬六千斤。"
        annotated, metrics, idioms = self.preprocessor.annotate_numerics_and_idioms(text)

        self.assertIn("[I1]", annotated)
        self.assertEqual(len(idioms), 1)
        self.assertEqual(idioms[0].forbidden, "")
        self.assertIn("không tán đồng", idioms[0].suggestions)

        self.assertIn("M1", annotated)
        self.assertIn("M2", annotated)
        m_dict = {m.tag_id: m.locked_vi for m in metrics}
        self.assertEqual(m_dict["M2"], "ba mươi sáu ngàn cân")

    def test_05_end_to_end_scene_contract_pipeline(self):
        """Verify full pipeline: raw paragraphs -> tagged text §1..§N + SceneContract Pipe-DSL."""
        paragraphs = [
            "韓立臉色一凝，對此人的威脅不以為然，單手一掐訣，將青竹蜂雲劍往空中一拋，頓時化為三十六道丈許長的青虹，朝著那黑衣老者當頭罩下，黑衣老者不由得倒吸一口涼氣。",
            "封岳眼中寒芒一閃，獰笑道：“好個不知死活的小輩！今日老夫便將你抽魂煉魄！”",
        ]
        entities = [self.ent_hanli, self.ent_fengyue]
        pronouns = [
            PronounRule("韓立", "封岳", "COURTEOUS", "tại hạ", "đạo hữu", "khách sáo"),
        ]

        contract, tagged_paragraphs = self.preprocessor.build_scene_contract(
            chap_id=245,
            scene_id=2,
            raw_paragraphs=paragraphs,
            entities=entities,
            pronouns=pronouns,
            location_vi="Huyết Sắc Cấm Địa",
        )

        # Check tagged output
        self.assertEqual(len(tagged_paragraphs), 2)
        self.assertTrue(tagged_paragraphs[0].startswith("§1 "))
        self.assertTrue(tagged_paragraphs[1].startswith("§2 "))
        self.assertIn("[I1]", tagged_paragraphs[0])
        self.assertIn("SOURCE_CONTEXT", tagged_paragraphs[1])
        self.assertNotIn("HOSTILE_SHIFT", tagged_paragraphs[1])

        # Check Pipe-DSL roundtrip compatibility
        pipe_dsl = contract.to_pipe_dsl()
        self.assertIn("=== SCENE_CONTRACT_V1 ===", pipe_dsl)
        self.assertIn("@META|chap:0245|scene:02", pipe_dsl)
        self.assertIn("韓立|Hàn Lập|M|hắn", pipe_dsl)
        self.assertIn("M1|", pipe_dsl)


if __name__ == "__main__":
    unittest.main()
