# tests/test_genre_and_dna.py
import unittest
from native_oauth.cartridges.western_occult import WesternOccultCartridge
from native_oauth.stylometry.author_dna_engine import (
    GU_LONG_PROFILE,
    StylometricCritic,
)


class TestGenreAndDNA(unittest.TestCase):
    def test_ts03_phonetic_lore_restoration_lord_of_mysteries(self):
        """
        TS-03: Kiểm tra khôi phục 100% tên gốc Latin (Klein Moretti, Azik Eggers, Tingen)
        và thuật ngữ ma dược (Nhà Tiên Tri, Kẻ Khờ), đồng thời lọc bỏ từ Hán-Việt kiếm hiệp.
        """
        raw_lotm = "克莱恩·莫雷蒂离开廷根，向阿兹克·艾格斯请教占卜家魔药与愚者的秘密。"
        cartridge = WesternOccultCartridge()

        _, entity_map = cartridge.pre_process_entities(raw_lotm)
        self.assertEqual(entity_map["克莱恩·莫雷蒂"], "Klein Moretti")
        self.assertEqual(entity_map["廷根"], "Tingen")
        self.assertEqual(entity_map["阿兹克·艾格斯"], "Azik Eggers")
        self.assertEqual(entity_map["占卜家"], "Nhà Tiên Tri")
        self.assertEqual(entity_map["愚者"], "Kẻ Khờ")

        flawed_draft = "Khắc Lai Ân gọi tiểu nhị trong khách điếm ở Đình Căn để hỏi về Chiêm Bốc Gia."
        polished = cartridge.post_process_register(flawed_draft)
        self.assertIn("Klein", polished)
        self.assertIn("bồi bàn", polished)
        self.assertIn("nhà trọ", polished)
        self.assertIn("Tingen", polished)
        self.assertIn("Nhà Tiên Tri", polished)
        self.assertNotIn("Khắc Lai Ân", polished)

    def test_ts05_author_stylometric_gu_long_blind_test(self):
        """
        TS-05: Kiểm định hồ sơ Cổ Long — đảm bảo độ dài câu trung bình dưới 9.5 từ
        và tỷ lệ dòng đơn (One-sentence paragraphs) đạt từ 60% trở lên.
        """
        verbose_draft = (
            "Gió đêm rất lạnh, nhưng mà rượu trong bầu còn lạnh hơn. "
            "Đao đã rút khỏi vỏ, rồi sau đó máu tươi nhỏ xuống tuyết trắng."
        )
        critic = StylometricCritic()
        report = critic.audit_and_imprint(verbose_draft, GU_LONG_PROFILE)

        self.assertTrue(report.passed)
        self.assertLessEqual(report.avg_sentence_words, 9.5)
        self.assertGreaterEqual(report.single_sentence_para_ratio, 0.60)
        self.assertIn("\n", report.enforced_rewrite)


if __name__ == "__main__":
    unittest.main()
