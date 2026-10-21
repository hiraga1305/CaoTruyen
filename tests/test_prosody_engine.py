"""
tests/test_prosody_engine.py - Unit tests for Vietnamese Literary Prosody Engine.
CaoTruyen v2.5 - Co-engineered with Gemini 4 Argon.
"""

import unittest
from native_oauth.prosody_engine import (
    VietnameseProsodyEngine,
    StreamType,
    CadenceAnomaly,
)


class TestProsodyEngine(unittest.TestCase):

    def test_01_classify_dual_stream_segments(self):
        """Classify paragraph into Dialogue and Narrative streams accurately."""
        paragraph = 'Lâm Phong nhìn chằm chằm kiếm trong tay, cười lạnh: "Muốn lấy mạng ta, các ngươi còn chưa đủ tư cách!" Nói đoạn, kiếm quang lóe lên.'
        segments = VietnameseProsodyEngine.classify_stream_segments(paragraph)

        self.assertEqual(len(segments), 3)
        self.assertEqual(segments[0][0], StreamType.NARRATIVE)
        self.assertIn("Lâm Phong nhìn chằm chằm", segments[0][1])

        self.assertEqual(segments[1][0], StreamType.DIALOGUE)
        self.assertEqual(segments[1][1], "Muốn lấy mạng ta, các ngươi còn chưa đủ tư cách!")

        self.assertEqual(segments[2][0], StreamType.NARRATIVE)
        self.assertIn("kiếm quang lóe lên", segments[2][1])

    def test_02_detect_clunky_conjunctions(self):
        """Flag clunky westernized/bureaucratic conjunctions."""
        bad_text = (
            "Cùng với việc linh khí khôi phục, dưới tình huống này, "
            "vô luận như thế nào thì hắn không thể nghi ngờ là kẻ mạnh nhất."
        )
        anomalies = VietnameseProsodyEngine.audit_cadence_and_rhythm(bad_text)
        codes = [a.error_code for a in anomalies]

        self.assertIn("CLUNKY_CUNG_VOI_VIEC", codes)
        self.assertIn("CLUNKY_DUOI_TINH_HUONG", codes)
        self.assertIn("CLUNKY_VO_LUAN_NHU_THE_NAO", codes)
        self.assertIn("CLUNKY_KHONG_THE_NGHI_NGO", codes)

    def test_03_detect_run_on_clause(self):
        """Detect overly long run-on clauses without comma/punctuation."""
        # 42 words without punctuation
        run_on = (
            "Hắn đứng ở trên đỉnh núi cao nhìn về phương xa thấy mây trôi nước chảy "
            "nhớ lại những năm tháng tu hành gian khổ đã qua trong lòng bỗng dấy lên "
            "muôn vàn cảm xúc không biết phải nói làm sao cho hết nỗi lòng của mình lúc này."
        )
        anomalies = VietnameseProsodyEngine.audit_cadence_and_rhythm(run_on)
        codes = [a.error_code for a in anomalies]
        self.assertIn("RUN_ON_CLAUSE_TOO_LONG", codes)

    def test_04_heal_clunky_phrases(self):
        """Deterministic healing replaces clunky phrases with natural literary Vietnamese."""
        raw_vn = "Cùng với việc tu vi đột phá, dưới tình huống này hắn đã trở thành đệ nhất nhân."
        healed_vn = VietnameseProsodyEngine.heal_clunky_phrases(raw_vn)

        self.assertNotIn("Cùng với việc", healed_vn)
        self.assertNotIn("dưới tình huống này", healed_vn)
        self.assertIn("đồng thời", healed_vn.lower())
        self.assertIn("trong tình thế này", healed_vn.lower())


if __name__ == "__main__":
    unittest.main()
