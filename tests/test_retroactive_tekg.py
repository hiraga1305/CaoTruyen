# tests/test_retroactive_tekg.py
import unittest
from native_oauth.core.graph.retroactive_tekg import PronounState, RetroactiveTEKG


class TestRetroactiveTEKG(unittest.TestCase):
    def test_ts02_delayed_gender_rank_reveal_and_retroactive_alignment(self):
        """
        TS-02: Nhân vật xuất hiện ở Chương 1 với danh xưng mập mờ ('那黑衣人' - Hắc y nhân),
        đến Chương 15 mới tiết lộ là Nữ Đế Diệp Khuynh Thành ('正是失踪多年的女帝叶倾城').
        Chứng minh Pha 1 (Lookahead) phát hiện từ Chương 15 và dịch đúng ngay ở Chương 1,
        đồng thời kiểm chứng cơ chế vá hồi tố Standoff.
        """
        raw_batch = {
            1: "那黑衣人站在山巅，冷冷注视着下方的战场。",
            15: "面具滑落，那黑衣人正是失踪多年的女帝叶倾城！",
        }

        tekg = RetroactiveTEKG()
        # Thực thi Pha 1: Quét trước 15 chương
        tekg.run_phase1_lookahead_scan(raw_batch)

        # Khi bắt đầu dịch Chương 1, hỏi đồ thị về "黑衣人"
        ent_id, pron_ch1 = tekg.resolve_pronoun("黑衣人", "NARRATOR", chapter_num=1, role="THIRD_PERSON")
        self.assertEqual(tekg.entities[ent_id].gender, "FEMALE")
        self.assertEqual(tekg.entities[ent_id].social_rank, "ROYAL")
        self.assertEqual(pron_ch1, "nàng")  # Không bị dịch nhầm thành "hắn" hay "gã"

        # Lưu bản dịch Chương 1 có gắn Standoff Tag
        tagged_ch1 = (
            f"Trên đỉnh núi, {tekg.bind_standoff_tag(ent_id, 'NARRATOR', 'THIRD_PERSON', pron_ch1)} "
            f"lạnh lùng nhìn xuống chiến trường."
        )
        tekg.store_translated_chapter(1, tagged_ch1)

        # Giả sử đến Chương 500, tác giả tiết lộ thêm tình tiết buộc đổi cách gọi ở Chương 1 thành "vị Nữ đế bí ẩn ấy"
        modified = tekg.retroactive_realign(
            src_id=ent_id,
            dst_id="NARRATOR",
            new_state=PronounState(
                chapter_from=1,
                chapter_to=10,
                self_pronoun="Bản tọa",
                address_pronoun="Ngươi",
                third_person_ref="vị Nữ đế bí ẩn ấy",
                register_tone="MYSTERIOUS_NOBLE",
            ),
        )

        self.assertIn(1, modified)
        clean_published = tekg.strip_standoff_for_publication(1)
        self.assertEqual(clean_published, "Trên đỉnh núi, vị Nữ đế bí ẩn ấy lạnh lùng nhìn xuống chiến trường.")


if __name__ == "__main__":
    unittest.main()
