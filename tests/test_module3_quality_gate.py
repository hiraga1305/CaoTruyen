"""Unit Test Suite for Module 3: Quality Gate 4A & Spot-Audit 4B.
Tests structural alignment, CJK detection, leaked tag sanitization,
BNS convert smell linter, numeric drift, pronoun enforcement, and surgical repair.
"""

import unittest
from native_oauth.scene_contract import EntityRecord, PronounRule, HardMetric, SceneContract
from native_oauth.quality_gate import QualityGate4A
from native_oauth.spot_auditor import SpotAuditor4B


class TestModule3QualityGate(unittest.TestCase):
    def setUp(self):
        self.gate = QualityGate4A()
        self.auditor = SpotAuditor4B(gate=self.gate)
        self.contract = SceneContract(
            chap_id=245,
            scene_id=2,
            route_tier="MED",
            genre="XIANXIA",
            pacing="COMBAT_FAST",
            location_vi="Huyết Sắc Cấm Địa",
            mood="sát phạt",
            active_effect="vận chuyển kiếm quyết",
            prev_vi="Hàn Lập lùi lại một bước.",
            last_actor_vi="Hàn Lập",
            spatial_vec="cách mười trượng",
            entities=[
                EntityRecord("韓立", "Hàn Lập", "M", "hắn", "Luyện Khí tầng 12", "Cẩn trọng"),
                EntityRecord("封岳", "Phong Nhạc", "M", "gã", "Luyện Khí tầng 13", "Tàn độc"),
            ],
            pronouns=[
                PronounRule("韓立", "封岳", "HOSTILE", "ta", "ngươi", "lạnh băng"),
            ],
            hard_metrics=[
                HardMetric("M1", "三萬六千斤", "ba vạn sáu ngàn cân"),
                HardMetric("M2", "十丈", "mười trượng"),
            ],
        )

    def test_01_clean_translation_passes_gate(self):
        """Clean BNS translation should PASS 100% with zero errors."""
        clean_output = """§1 Sắc mặt Hàn Lập trầm xuống, hắn vung tay bấm pháp quyết tung Thanh Trúc Phong Vân Kiếm lên.
§2 Thanh kiếm nặng tới ba vạn sáu ngàn cân, xé gió rít gào trong phạm vi mười trượng, nhằm thẳng đầu con yêu thú chém phập xuống!
"""
        result = self.gate.verify_paragraphs(clean_output, expected_paragraph_count=2, contract=self.contract)
        self.assertTrue(result.is_pass)
        self.assertEqual(len(result.violations), 0)
        self.assertFalse(result.quarantine)

    def test_02_leaked_dsl_tags_sanitized(self):
        """Leaked DSL tags should be detected and automatically sanitized."""
        leaked_output = """§1 [Ø=韓立] Sắc mặt Hàn Lập trầm xuống, [||] hắn vung kiếm nặng ba vạn sáu ngàn cân.
§2 “Đạo hữu chết đi!”[Q1:韓立->封岳|state:HOSTILE] Phạm vi mười trượng kiếm khí rền vang.
"""
        result = self.gate.verify_paragraphs(leaked_output, expected_paragraph_count=2, contract=self.contract)
        # Should flag WARNING for leak but sanitize
        self.assertIn("Sắc mặt Hàn Lập", result.sanitized_paragraphs[1])
        self.assertNotIn("[Ø=韓立]", result.sanitized_paragraphs[1])
        self.assertNotIn("[||]", result.sanitized_paragraphs[1])
        self.assertNotIn("[Q1:", result.sanitized_paragraphs[2])

    def test_03_cjk_contamination_blocked(self):
        """Leftover Chinese characters must trigger CJK_CONTAMINATION error."""
        cjk_output = """§1 Hàn Lập vung kiếm 斬 ra một luồng kiếm khí nặng ba mươi sáu ngàn cân.
§2 Kiếm khí bao phủ mười trượng.
"""
        result = self.gate.verify_paragraphs(cjk_output, expected_paragraph_count=2, contract=self.contract)
        self.assertFalse(result.is_pass)
        err_codes = [v.error_code for v in result.violations]
        self.assertIn("CJK_CONTAMINATION", err_codes)

    def test_04_convert_smell_linter_detection(self):
        """Detect classic convert calques (không cho là đúng, sắc mặt ngưng lại, đem... ném)."""
        convert_output = """§1 Hàn Lập sắc mặt ngưng lại, đối với hắn uy hiếp không cho là đúng.
§2 Hắn đem thanh kiếm ném ra xa mười trượng, nặng ba mươi sáu ngàn cân, khiến đối phương hít ngược một ngụm khí lạnh.
"""
        result = self.gate.verify_paragraphs(convert_output, expected_paragraph_count=2, contract=self.contract)
        self.assertFalse(result.is_pass)
        err_codes = [v.error_code for v in result.violations]
        self.assertIn("CALQUE_SAC_MAT_NGUNG_LAI", err_codes)
        self.assertIn("CALQUE_KHONG_CHO_LA_DUNG", err_codes)
        self.assertIn("CALQUE_DEM_TAN_NGU_DONG_TU", err_codes)
        self.assertIn("CALQUE_HIT_NGUOC_KHI_LANH", err_codes)

    def test_05_numeric_drift_detection(self):
        """Missing locked metrics triggers HARD_METRIC_DRIFT."""
        drift_output = """§1 Sắc mặt Hàn Lập trầm xuống, hắn vung kiếm nặng hàng vạn cân.
§2 Kiếm khí bao phủ mười trượng.
"""
        result = self.gate.verify_paragraphs(drift_output, expected_paragraph_count=2, contract=self.contract)
        self.assertFalse(result.is_pass)
        err_codes = [v.error_code for v in result.violations]
        self.assertIn("HARD_METRIC_DRIFT", err_codes)

    def test_06_pronoun_discipline_enforcement(self):
        """Modern pronouns outside quotes trigger MODERN_PRONOUN_IN_NARRATIVE."""
        modern_output = """§1 Anh ta khẽ nheo mắt, vung kiếm nặng ba mươi sáu ngàn cân.
§2 Kiếm khí bao phủ mười trượng.
"""
        result = self.gate.verify_paragraphs(modern_output, expected_paragraph_count=2, contract=self.contract)
        self.assertFalse(result.is_pass)
        err_codes = [v.error_code for v in result.violations]
        self.assertIn("MODERN_PRONOUN_IN_NARRATIVE", err_codes)

    def test_07_spot_auditor_deterministic_repair(self):
        """Spot-Auditor deterministic heal fixes simple convert smells and passes re-verification."""
        flawed_output = """§1 Hàn Lập sắc mặt ngưng lại, đối với lời đe dọa không cho là đúng.
§2 Kiếm khí bao phủ mười trượng, nặng ba vạn sáu ngàn cân.
"""
        init_res = self.gate.verify_paragraphs(flawed_output, expected_paragraph_count=2, contract=self.contract)
        self.assertFalse(init_res.is_pass)

        # Apply deterministic heal
        healed_res = self.auditor.apply_deterministic_repair(init_res, self.contract)
        self.assertTrue(healed_res.is_pass)
        self.assertIn("trầm xuống", healed_res.sanitized_paragraphs[1])
        self.assertIn("chẳng mảy may để tâm", healed_res.sanitized_paragraphs[1])


if __name__ == "__main__":
    unittest.main()
