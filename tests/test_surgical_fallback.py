# tests/test_surgical_fallback.py
import unittest
from typing import Dict, Sequence
from native_oauth.core.ast.semantic_parser import ASTNode, DiscourseType
from native_oauth.resilience.surgical_fallback import (
    FeatheredContext,
    SafetyBlockException,
    SurgicalSafetyResilience,
)


class TestSurgicalSafetyResilience(unittest.TestCase):
    def test_ts04_extreme_gore_binary_bisection_and_infill(self):
        """
        TS-04: Chương truyện có 5 nút AST, trong đó nút số 3 chứa cảnh luyện huyết đẫm máu
        kích hoạt SafetyBlockException, và nút số 4 bị cắt ngầm (Silent Truncation).
        Chứng minh hệ thống cô lập đúng nút 3 và 4, giữ nguyên bản dịch Tier-1 cho nút 1, 2, 5
        và khôi phục hoàn hảo nút 3, 4 qua Bi-Context Feathering.
        """
        nodes = [
            ASTNode("n1", DiscourseType.NARRATION, "夜色深沉，山谷中寒风呼啸。", "夜色深沉，山谷中寒风呼啸。"),
            ASTNode("n2", DiscourseType.NARRATION, "血魔老祖缓缓抬起右手，眼中杀机毕露。", "血魔老祖缓缓抬起右手，眼中杀机毕露。"),
            ASTNode("n3", DiscourseType.NARRATION, "漫天血雨中，数十具骸骨被生生捏碎，鲜血汇成血池！", "漫天血雨中，数十具骸骨被生生捏碎，鲜血汇成血池！"),
            ASTNode("n4", DiscourseType.NARRATION, "凄厉的惨叫声响彻云霄，令人毛骨悚然。", "凄厉的惨叫声响彻云霄，令人毛骨悚然。"),
            ASTNode("n5", DiscourseType.NARRATION, "韩立面色凝重，悄然退入暗影之中。", "韩立面色凝重，悄然退入暗影之中。"),
        ]

        def mock_tier1_api(batch: Sequence[ASTNode]) -> Dict[str, str]:
            for n in batch:
                if n.node_id == "n3":
                    raise SafetyBlockException("FINISH_REASON_SAFETY: Gore detected")
            out: Dict[str, str] = {}
            for n in batch:
                if n.node_id == "n4":
                    # Giả lập API thương mại tự ý cắt cụt câu máu me (Silent Truncation)
                    out[n.node_id] = "..."
                else:
                    out[n.node_id] = f"Bản dịch Tier-1 chuẩn văn học cho nút {n.node_id} với đầy đủ âm tiết."
            return out

        def mock_uncensored_local_llm(ctx: FeatheredContext) -> str:
            # Đảm bảo nhận đủ ngữ cảnh phía trước và phía sau
            self.assertTrue(len(ctx.preceding_translated) >= 1)
            return f"Bản dịch Uncensored liền mạch cho {ctx.target_node.node_id} khớp ngữ cảnh hai đầu."

        resilience = SurgicalSafetyResilience(mock_tier1_api, mock_uncensored_local_llm)
        final_output = resilience.translate_with_zero_loss(nodes)

        self.assertEqual(len(final_output), 5)
        self.assertIn("Tier-1", final_output["n1"])
        self.assertIn("Tier-1", final_output["n2"])
        self.assertIn("Uncensored liền mạch cho n3", final_output["n3"])
        self.assertIn("Uncensored liền mạch cho n4", final_output["n4"])
        self.assertIn("Tier-1", final_output["n5"])
        self.assertEqual(len(resilience.incidents), 2)


if __name__ == "__main__":
    unittest.main()
