# tests/test_autonomous_self_healing.py
import unittest
from native_oauth.autonomous.self_healing_engine import (
    AnomalyType,
    AutonomousSelfHealingEngine,
    RepairTier,
)
from native_oauth.core.ast.semantic_parser import ASTNode, DiscourseType


class TestAutonomousSelfHealing(unittest.TestCase):
    def test_ts06_autonomous_dual_inspection_and_self_healing(self):
        """
        TS-06: Mô phỏng một bản dịch thô mắc đồng thời 3 lỗi chí mạng mà người đọc mù chữ Hán
        không thể tự sửa:
        1. Lỗi sượng văn convert ('trong mắt hiện lên một tia') + Nhập nhằng đại từ ('hắn đâm hắn') -> Sửa ở Tầng 1 (0-Token).
        2. Lỗi Đảo ngược Phủ định (Raw: '绝不可能退缩' - Tuyệt đối không thể lùi bước, nhưng dịch nhầm thành 'có thể lùi bước') -> Sửa ở Tầng 2 (Micro-Surgery).
        Đảm bảo hệ thống tự động phát hiện và tự vá lên Confidence = 1.0 (Approved).
        """
        nodes = [
            ASTNode(
                node_id="n_calque",
                discourse_type=DiscourseType.NARRATION,
                source_text="韩立眼中闪过一丝寒芒，一剑刺向对方。",
                normalized_text="韩立眼中闪过一丝寒芒，一剑刺向对方。",
            ),
            ASTNode(
                node_id="n_polarity",
                discourse_type=DiscourseType.DIRECT_SPEECH,
                source_text="面对强敌，本座绝不可能退缩半步！",
                normalized_text="“面对强敌，本座绝不可能退缩半步！”",
            ),
        ]

        flawed_drafts = {
            "n_calque": "Hàn Lập trong mắt hiện lên một tia hàn quang, hắn đâm hắn một kiếm.",
            "n_polarity": "Đối mặt cường địch, bổn tọa có thể lùi bước nửa tấc!",
        }

        engine = AutonomousSelfHealingEngine()
        healed_map, ledger = engine.audit_and_heal_chapter(
            chapter_id="ch_auto_01",
            nodes=nodes,
            draft_translations=flawed_drafts,
            glossary={"本座": "bổn tọa"},
        )

        # 1. Xác nhận trạng thái trước khi tự chữa lành bị đánh trượt (< 0.98)
        self.assertLess(ledger.initial_confidence, 0.90)

        # A heuristic score, even >= 0.98, cannot replace independent review.
        self.assertGreaterEqual(ledger.final_confidence, 0.98)
        self.assertFalse(ledger.publication_approved)
        self.assertEqual(len(ledger.receipts), 2)

        # 3. Kiểm tra nút 1 được sửa bằng Tầng 1 (0-Token Symbolic Patch)
        r1 = ledger.receipts[0]
        self.assertEqual(r1.tier_used, RepairTier.TIER_1_SYMBOLIC_ZERO_TOKEN)
        self.assertIn("trong đáy mắt thoáng hiện nét", healed_map["n_calque"])
        self.assertIn("hắn đâm đối phương", healed_map["n_calque"])

        # 4. Kiểm tra nút 2 được sửa lỗi Đảo ngược Phủ định bằng Tầng 2 (Constrained Micro-Surgery)
        r2 = ledger.receipts[1]
        self.assertEqual(r2.tier_used, RepairTier.TIER_2_CONSTRAINED_MICRO_SURGERY)
        self.assertIn(AnomalyType.POLARITY_INVERSION, r2.anomalies_resolved)
        self.assertIn("không có thể lùi bước", healed_map["n_polarity"])


if __name__ == "__main__":
    unittest.main()
