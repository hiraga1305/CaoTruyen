# -*- coding: utf-8 -*-
"""Unit tests for Urban Metaphysics & Livestream quality gate upgrades."""

import unittest
from native_oauth.scene_contract import EntityRecord, PronounRule, HardMetric, SceneContract
from native_oauth.quality_gate import QualityGate4A, heal_urban_anomalies


class TestUrbanGate(unittest.TestCase):
    def setUp(self):
        self.gate = QualityGate4A()
        self.contract = SceneContract(
            chap_id=1,
            scene_id=1,
            route_tier="LOW",
            genre="URBAN_LIVESTREAM",
            pacing="EXPOSITION_SMOOTH",
            location_vi="Phòng livestream",
            mood="hài hước",
            active_effect="xem tướng",
            prev_vi="",
            last_actor_vi="Tiêu Vũ",
            spatial_vec="qua màn hình",
            entities=[
                EntityRecord("蕭羽", "Tiêu Vũ", "M", "hắn", "Đại sư", "Tự tin"),
                EntityRecord("唐小小", "Đường Tiểu Tiểu", "F", "cô", "Khách mời", "Hào hứng"),
            ],
            pronouns=[
                PronounRule("蕭羽", "唐小小", "COURTEOUS", "tôi", "cô", "ôn hòa"),
            ],
            hard_metrics=[
                HardMetric("M1", "220万", "hai triệu hai trăm ngàn"),
            ],
        )

    def test_01_urban_false_friends_flagged(self):
        """Urban calques like 'thủy hữu', 'bảng nhất' must be flagged when genre is URBAN."""
        bad_output = """§1 Các thủy hữu trong phòng livestream nhao nhao gửi lời chúc đến đại tỷ Bảng Nhất với số tiền hai triệu hai trăm ngàn.
"""
        res = self.gate.verify_paragraphs(bad_output, expected_paragraph_count=1, contract=self.contract)
        self.assertTrue(res.is_pass)
        self.assertTrue(all(v.severity == "WARNING" for v in res.violations))
        codes = [v.error_code for v in res.violations]
        self.assertIn("URBAN_THUY_HUU", codes)
        self.assertIn("URBAN_DAI_TY_BANG_NHAT", codes)

    def test_02_barrage_archaic_banlist(self):
        """Archaic pronouns in barrage like 'tại hạ', 'đạo hữu' must be flagged in URBAN."""
        bad_barrage = """§1 【Bình luận】 Tại hạ xin bái phục đại sư, nạp hẳn hai triệu hai trăm ngàn!
"""
        res = self.gate.verify_paragraphs(bad_barrage, expected_paragraph_count=1, contract=self.contract)
        self.assertTrue(res.is_pass)
        self.assertTrue(all(v.severity == "WARNING" for v in res.violations))
        codes = [v.error_code for v in res.violations]
        self.assertIn("BARRAGE_ARCHAIC_LEAK", codes)

    def test_03_heal_urban_anomalies(self):
        """Semantic suggestions must not mutate literal jokes or quoted speech."""
        raw_text = "Các thủy hữu đều khen ngợi đại tỷ Bảng Nhất đã tặng Siêu Cấp Hỏa Tiễn. 【Bình luận】 Hahaha, tại hạ quỳ rồi!"
        healed, patches = heal_urban_anomalies(raw_text)
        self.assertEqual(healed, raw_text)
        self.assertEqual(patches, [])

    def test_04_clean_urban_passes_gate(self):
        """Clean urban text should pass QualityGate4A cleanly."""
        clean_text = """§1 Các khán giả trong phòng livestream nhao nhao gửi lời chúc đến chị đại Top 1 với số tiền hai triệu hai trăm ngàn.
"""
        res = self.gate.verify_paragraphs(clean_text, expected_paragraph_count=1, contract=self.contract)
        self.assertTrue(res.is_pass)
        self.assertEqual(len(res.violations), 0)


if __name__ == "__main__":
    unittest.main()
