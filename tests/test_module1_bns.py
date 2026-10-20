"""Unit Test Suite for Module 1: BNS Literary Prompt & Scene Contract Schema.
Verifies all specifications defined by Gemini 4 Argon.
"""

import unittest
from pathlib import Path
from native_oauth.scene_contract import (
    EntityRecord,
    PronounRule,
    HardMetric,
    IdiomHint,
    SceneContract,
    parse_worker_output,
)
from native_oauth.numeric_lock import (
    DeterministicNumericExtractor,
    parse_chinese_integer,
    int_to_vietnamese,
)


class TestModule1BNS(unittest.TestCase):
    def setUp(self):
        self.prompt_path = Path("native_oauth/prompts/bns_system_cache_v1.md")
        self.extractor = DeterministicNumericExtractor()

    def test_01_system_prompt_integrity(self):
        """Verify that the immutable system cache prompt has all mandatory BNS rules."""
        self.assertTrue(self.prompt_path.exists(), "Prompt file must exist")
        content = self.prompt_path.read_text(encoding="utf-8")
        
        # Check core sections
        self.assertIn("SYSTEM DIRECTIVE: ĐẠI DỊCH GIẢ VĂN HỌC BẠCH NGỌC SÁCH", content)
        self.assertIn("GIAO THỨC ĐỌC HIỂU VI THẺ", content)
        self.assertIn("CƠ CHẾ ĐIỀU KHIỂN NHỊP ĐIỆU VĂN PHONG (`PACING_MODE` ENGINE)", content)
        self.assertIn("COMBAT_FAST", content)
        self.assertIn("AURA_MAJESTIC", content)
        self.assertIn("DIALOGUE_TENSE", content)
        self.assertIn("EXPOSITION_SMOOTH", content)
        self.assertIn("BẢNG CẤM CHỈ CONVERT", content)
        
        # Check forbidden patterns
        self.assertIn("Không cho là đúng", content)
        self.assertIn("Sắc mặt/Ánh mắt ngưng lại", content)
        self.assertIn("Hít ngược một ngụm khí lạnh", content)
        self.assertIn("Hướng về / Đối với", content)
        self.assertIn("Đem / Tương", content)
        
        # Check output format
        self.assertIn("§1 <Nội dung đoạn dịch 1>", content)
        self.assertIn("<delta>", content)

    def test_02_scene_contract_dsl_roundtrip(self):
        """Verify serialization and deserialization of Pipe-DSL Scene Contract."""
        contract = SceneContract(
            chap_id=245,
            scene_id=2,
            route_tier="MED",
            genre="XIANXIA",
            pacing="COMBAT_FAST",
            location_vi="Huyết Sắc Cấm Địa",
            mood="sát phạt",
            active_effect="vận chuyển kiếm quyết",
            prev_vi="Hàn Lập khẽ nheo mắt lùi lại nửa bước.",
            last_actor_vi="Hàn Lập",
            spatial_vec="đối diện Phong Nhạc mười trượng",
            entities=[
                EntityRecord("韓立", "Hàn Lập", "M", "hắn", "Luyện Khí tầng 12", "Cẩn trọng"),
                EntityRecord("封岳", "Phong Nhạc", "M", "gã", "Luyện Khí tầng 13", "Ngạo mạn"),
            ],
            pronouns=[
                PronounRule("韓立", "封岳", "COURTEOUS", "tại hạ", "đạo hữu", "khách sáo"),
                PronounRule("韓立", "封岳", "HOSTILE", "ta", "ngươi", "lạnh băng"),
            ],
            anchor_quotes=[
                ("封岳", "Ngông cuồng", "Chưa một ai sống sót rời khỏi đây!"),
            ],
            hard_metrics=[
                HardMetric("M1", "三萬六千斤", "ba vạn sáu ngàn cân"),
                HardMetric("M2", "十丈", "mười trượng"),
            ],
            glossary={
                "青元劍訣": ("Thanh Nguyên Kiếm Quyết", "SKILL"),
            },
            idiom_hints=[
                IdiomHint("I1", "不以為然", "chẳng mảy may để tâm / cười khẩy", "không cho là đúng"),
            ],
        )

        dsl = contract.to_pipe_dsl()
        self.assertIn("=== SCENE_CONTRACT_V1 ===", dsl)
        self.assertIn("@META|chap:0245|scene:02|route:MED|genre:XIANXIA", dsl)
        self.assertIn("韓立|Hàn Lập|M|hắn|Luyện Khí tầng 12|Cẩn trọng", dsl)
        self.assertIn("韓立->封岳|HOSTILE|ta|ngươi|lạnh băng", dsl)
        self.assertIn("M1|三萬六千斤|ba vạn sáu ngàn cân", dsl)

        # Deserialize
        parsed = SceneContract.from_pipe_dsl(dsl)
        self.assertEqual(parsed.chap_id, 245)
        self.assertEqual(parsed.scene_id, 2)
        self.assertEqual(parsed.pacing, "COMBAT_FAST")
        self.assertEqual(len(parsed.entities), 2)
        self.assertEqual(parsed.entities[0].vi, "Hàn Lập")
        self.assertEqual(len(parsed.pronouns), 2)
        self.assertEqual(parsed.pronouns[1].self_vi, "ta")
        self.assertEqual(len(parsed.hard_metrics), 2)
        self.assertEqual(parsed.hard_metrics[0].locked_vi, "ba vạn sáu ngàn cân")
        self.assertEqual(len(parsed.idiom_hints), 1)
        self.assertEqual(parsed.idiom_hints[0].forbidden, "không cho là đúng")

    def test_03_parse_worker_output(self):
        """Verify parsing of §1..§N and <delta> block from worker output."""
        sample_output = """§1 Sắc mặt Hàn Lập trầm xuống, chẳng mảy may để tâm đến lời đe dọa của kẻ này.
§2 Lão già kia giật mình kinh hãi, lạnh toát cả sống lưng.

<delta>
NEW_ENT|墨居仁|Mặc Cư Nhân|M|lão|Sư phụ đầu tiên của Hàn Lập
REL_SHIFT|韓立->封岳|HOSTILE|ta|ngươi|Chính thức trở mặt sau khi trúng đòn đánh lén
</delta>
"""
        paragraphs, deltas = parse_worker_output(sample_output)
        self.assertEqual(len(paragraphs), 2)
        self.assertEqual(paragraphs[1], "Sắc mặt Hàn Lập trầm xuống, chẳng mảy may để tâm đến lời đe dọa của kẻ này.")
        self.assertEqual(paragraphs[2], "Lão già kia giật mình kinh hãi, lạnh toát cả sống lưng.")

        self.assertEqual(len(deltas), 2)
        self.assertEqual(deltas[0]["type"], "NEW_ENT")
        self.assertEqual(deltas[0]["vi"], "Mặc Cư Nhân")
        self.assertEqual(deltas[1]["type"], "REL_SHIFT")
        self.assertEqual(deltas[1]["state"], "HOSTILE")

    def test_04_numeric_lock_extraction(self):
        """Verify numeric parser and deterministic lock logic."""
        self.assertEqual(parse_chinese_integer("三萬六千"), 36000)
        self.assertEqual(parse_chinese_integer("十萬"), 100000)
        self.assertEqual(parse_chinese_integer("七"), 7)
        self.assertEqual(int_to_vietnamese(100000), "mười vạn")
        self.assertEqual(int_to_vietnamese(36000), "ba mươi sáu ngàn")

        ch_text = "韓立揮動青竹蜂雲劍，重達三萬六千斤，覆蓋十丈方圓，需要一炷香時間消耗七成法力。"
        metrics = self.extractor.extract_metrics(ch_text)
        self.assertEqual(len(metrics), 4)

        m_dict = {m.raw_zh: m.locked_vi for m in metrics}
        self.assertEqual(m_dict["三萬六千斤"], "ba mươi sáu ngàn cân")
        self.assertEqual(m_dict["十丈"], "mười trượng")
        self.assertEqual(m_dict["一炷香"], "thời gian một nén nhang")
        self.assertEqual(m_dict["七成"], "bảy phần")

        # Test verification in translated Vietnamese
        vi_ok = "Hắn vung kiếm nặng tới ba mươi sáu ngàn cân, bao phủ mười trượng, mất thời gian một nén nhang để tiêu hao bảy phần pháp lực."
        for m in metrics:
            self.assertTrue(self.extractor.verify_vietnamese(vi_ok, m), f"Failed for metric: {m.locked_vi}")

        # Test failure case (drift)
        vi_fail = "Hắn vung kiếm nặng hàng vạn cân..."
        self.assertFalse(self.extractor.verify_vietnamese(vi_fail, metrics[0]))


if __name__ == "__main__":
    unittest.main()
