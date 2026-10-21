"""
tests/test_idiom_engine.py - Unit tests for IdiomEngine and Aho-Corasick Automaton.
Co-engineered with Gemini 4 Argon.
"""

import unittest
from native_oauth.idiom_engine import IdiomEngine, IdiomTier, IdiomEntry


class TestIdiomEngine(unittest.TestCase):

    def setUp(self):
        self.engine = IdiomEngine()

    def test_01_aho_corasick_finds_idioms_o_n(self):
        """Aho-Corasick automaton matches multiple idioms in O(N) linear time."""
        raw_text = (
            "修仙之人切忌半途而废，唯有领悟道法自然，方能达到返璞归真之境。"
            "敌人若是声东击西，我等万剑归宗自可破之。"
        )
        matches = self.engine.scan_idioms_in_scene(raw_text, active_genre="CULTIVATION")
        matched_idioms = [m["chinese"] for m in matches]

        self.assertIn("半途而废", matched_idioms)
        self.assertIn("道法自然", matched_idioms)
        self.assertIn("返璞归真", matched_idioms)
        self.assertIn("声东击西", matched_idioms)
        self.assertIn("万剑归宗", matched_idioms)
        self.assertEqual(len(matched_idioms), 5)

    def test_02_tier_separation(self):
        """Tier 1 preserves archaic Xianxia, Tier 2 converts to natural Vietnamese, Tier 3 expands allusion."""
        # Tier 1
        m_tier1 = self.engine.scan_idioms_in_scene("万剑归宗，毁天灭地！")
        for m in m_tier1:
            self.assertEqual(m["tier"], IdiomTier.TIER1_ARCHAIC.value)
            self.assertEqual(m["recommended_vn"], m["sino_vietnamese"])

        # Tier 2: '半途而废' should recommend 'Bỏ dở giữa chừng' instead of convert 'Bán đồ nhi phế'
        m_tier2 = self.engine.scan_idioms_in_scene("你做事情总是半途而废，得寸进尺。")
        t2_dict = {m["chinese"]: m["recommended_vn"] for m in m_tier2}
        self.assertEqual(t2_dict["半途而废"], "Bỏ dở giữa chừng")
        self.assertEqual(t2_dict["得寸进尺"], "Được đằng chân lân đằng đầu")

        # Tier 3: Allusion
        m_tier3 = self.engine.scan_idioms_in_scene("这般行为简直是东施效颦。")
        self.assertEqual(m_tier3[0]["tier"], IdiomTier.TIER3_ALLUSION.value)
        self.assertIn("Đông Thi bắt chước", m_tier3[0]["recommended_vn"])

    def test_03_format_for_scene_contract_dsl(self):
        """DSL serialization into @IDIOM_HINTS block for SceneContract."""
        matches = self.engine.scan_idioms_in_scene("道法自然，不可半途而废。")
        dsl = self.engine.format_for_scene_contract_dsl(matches)

        self.assertTrue(dsl.startswith("@IDIOM_HINTS"))
        self.assertIn("IDIOM|道法自然|Đạo pháp tự nhiên|ARCHAIC_XIANXIA|Đạo pháp tự nhiên", dsl)
        self.assertIn("IDIOM|半途而废|Bán đồ nhi phế|COLLOQUIAL_VIETNAMESE|Bỏ dở giữa chừng", dsl)


if __name__ == "__main__":
    unittest.main()
