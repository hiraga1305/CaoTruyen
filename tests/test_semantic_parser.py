# tests/test_semantic_parser.py
import unittest
from native_oauth.core.ast.semantic_parser import DiscourseType, SemanticASTParser


class TestSemanticParser(unittest.TestCase):
    def test_ts01_zero_punctuation_chaos_and_state_isolation(self):
        """
        TS-01: Xóa sạch 100% dấu ngoặc kép, trộn lẫn Trần thuật + Thoại trực tiếp +
        Độc thoại nội tâm ẩn (FID) + Bảng hệ thống.
        Đảm bảo phân tách chuẩn 100% và 0% đảo cực trạng thái.
        """
        dirty_raw = (
            "韩立看着地上的断剑，这老家伙果然在骗自己，今日怕是难逃此劫了。\n"
            "黑衣人冷笑道交出掌天瓶，本座留你全尸，否则让你神魂俱灭。韩立转身袖袍一甩，剑光一闪刺向对方。\n"
            "【境界：筑基初期】"
        )

        parser = SemanticASTParser()
        doc = parser.parse(dirty_raw, chapter_id="ch_test_01")

        # Đoạn 1: "韩立看着地上的断剑，" (NARRATION) + "这老家伙果然在骗自己，今日怕是难逃此劫了。" (FID)
        self.assertEqual(doc.nodes[0].discourse_type, DiscourseType.NARRATION)
        self.assertIn("看着地上的断剑", doc.nodes[0].source_text)

        self.assertEqual(doc.nodes[1].discourse_type, DiscourseType.FREE_INDIRECT_DISCOURSE)
        self.assertIn("果然", doc.nodes[1].source_text)
        self.assertTrue(doc.nodes[1].normalized_text.startswith("『"))

        # Đoạn 2: Cụm dẫn thoại (NARRATION) -> Lời thoại không ngoặc kép (DIRECT_SPEECH)
        # -> Hành động vật lý kế tiếp tự động thoát khỏi trạng thái thoại (NARRATION)
        self.assertEqual(doc.nodes[2].discourse_type, DiscourseType.NARRATION)
        self.assertEqual(doc.nodes[2].speaker_id, "黑衣人")

        self.assertEqual(doc.nodes[3].discourse_type, DiscourseType.DIRECT_SPEECH)
        self.assertIn("本座留你全尸", doc.nodes[3].source_text)
        self.assertTrue(doc.nodes[3].normalized_text.startswith("“"))

        # Chốt chặn quan trọng nhất: Câu hành động ngay sau lời thoại (dù không có dấu đóng ngoặc)
        # PHẢI quay về NARRATION, tuyệt đối không bị kẹt trong DIRECT_SPEECH
        self.assertEqual(doc.nodes[4].discourse_type, DiscourseType.NARRATION)
        self.assertIn("韩立转身袖袍一甩", doc.nodes[4].source_text)

        # Đoạn 3: Bảng hệ thống
        self.assertEqual(doc.nodes[5].discourse_type, DiscourseType.SYSTEM_LORE)


if __name__ == "__main__":
    unittest.main()
