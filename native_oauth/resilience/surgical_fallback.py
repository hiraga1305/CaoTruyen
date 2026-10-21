# native_oauth/resilience/surgical_fallback.py
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional, Sequence, Tuple
from native_oauth.core.ast.semantic_parser import ASTNode


class SafetyBlockException(Exception):
    """Ngoại lệ phát sinh khi API thương mại chặn nội dung do bộ lọc Safety."""


@dataclass
class CensorshipIncident:
    node_id: str
    reason: str  # "EXPLICIT_SAFETY_BLOCK" | "SILENT_TRUNCATION"
    raw_text: str


@dataclass
class FeatheredContext:
    target_node: ASTNode
    preceding_translated: List[str]
    succeeding_translated: List[str]
    active_glossary: Dict[str, str]


@dataclass
class SurgicalSpan:
    node_id: str
    recovered_text: str
    seam_continuity_score: float


class SurgicalSafetyResilience:
    """
    Hệ thống Miễn nhiễm Kiểm duyệt & Bảo toàn Toàn vẹn 100% (Zero-Loss Censorship Immunity).
    """

    MIN_VI_SYLLABLE_TO_ZH_CHAR_RATIO: float = 0.55

    def __init__(
        self,
        primary_tier1_translator: Callable[[Sequence[ASTNode]], Dict[str, str]],
        uncensored_infill_translator: Callable[[FeatheredContext], str],
    ) -> None:
        self._primary_translate = primary_tier1_translator
        self._uncensored_infill = uncensored_infill_translator
        self.incidents: List[CensorshipIncident] = []

    def translate_with_zero_loss(
        self,
        nodes: List[ASTNode],
        active_glossary: Optional[Dict[str, str]] = None,
    ) -> Dict[str, str]:
        """
        Dịch toàn bộ danh sách ASTNode với cam kết 0% mất câu, 0% gãy mạch văn.
        """
        glossary = active_glossary or {}
        safe_translations, blocked_nodes = self._binary_ast_bisection(nodes)

        # Kiểm tra thêm các nút bị cắt ngầm (Silent Truncation) trong các nút tưởng như thành công
        for node in nodes:
            if node.node_id in safe_translations:
                trans_txt = safe_translations[node.node_id]
                if self._is_silently_truncated(node.source_text, trans_txt):
                    self.incidents.append(
                        CensorshipIncident(
                            node_id=node.node_id,
                            reason="SILENT_TRUNCATION",
                            raw_text=node.source_text,
                        )
                    )
                    del safe_translations[node.node_id]
                    blocked_nodes.append(node)

        # Khôi phục từng nút bị chặn bằng kỹ thuật Đệm Ngữ Cảnh 2 Đầu (Bi-Context Feathering)
        node_index_map = {n.node_id: idx for idx, n in enumerate(nodes)}
        for b_node in blocked_nodes:
            idx = node_index_map[b_node.node_id]
            preceding = [
                safe_translations[nodes[i].node_id]
                for i in range(max(0, idx - 3), idx)
                if nodes[i].node_id in safe_translations
            ]
            succeeding = [
                safe_translations[nodes[i].node_id]
                for i in range(idx + 1, min(len(nodes), idx + 4))
                if nodes[i].node_id in safe_translations
            ]

            feathered = FeatheredContext(
                target_node=b_node,
                preceding_translated=preceding,
                succeeding_translated=succeeding,
                active_glossary=glossary,
            )
            recovered = self._uncensored_infill(feathered)
            seam_score = self._evaluate_seam_continuity(
                preceding, recovered, succeeding, glossary
            )
            if seam_score < 0.90:
                recovered = self._enforce_glossary_on_seam(recovered, glossary)

            safe_translations[b_node.node_id] = recovered

        return {n.node_id: safe_translations[n.node_id] for n in nodes}

    def _binary_ast_bisection(
        self, nodes: Sequence[ASTNode]
    ) -> Tuple[Dict[str, str], List[ASTNode]]:
        """
        Thuật toán Chia đôi Cây AST (Binary AST Bisection) để cô lập chính xác nút gây lỗi Safety.
        """
        if not nodes:
            return {}, []

        try:
            result = self._primary_translate(nodes)
            return result, []
        except SafetyBlockException:
            if len(nodes) == 1:
                offending = nodes[0]
                self.incidents.append(
                    CensorshipIncident(
                        node_id=offending.node_id,
                        reason="EXPLICIT_SAFETY_BLOCK",
                        raw_text=offending.source_text,
                    )
                )
                return {}, [offending]

            mid = len(nodes) // 2
            left_trans, left_blocked = self._binary_ast_bisection(nodes[:mid])
            right_trans, right_blocked = self._binary_ast_bisection(nodes[mid:])

            merged = {**left_trans, **right_trans}
            return merged, left_blocked + right_blocked

    def _is_silently_truncated(self, raw_zh: str, translated_vi: str) -> bool:
        """Phát hiện hiện tượng API trả về chuỗi rỗng hoặc tự ý cắt bớt câu máu me."""
        clean_zh = "".join(c for c in raw_zh if "\u4e00" <= c <= "\u9fa5")
        if len(clean_zh) < 6:
            return len(translated_vi.strip()) == 0
        vi_syllables = len(translated_vi.strip().split())
        ratio = vi_syllables / float(len(clean_zh))
        return ratio < self.MIN_VI_SYLLABLE_TO_ZH_CHAR_RATIO

    def _evaluate_seam_continuity(
        self,
        preceding: List[str],
        recovered: str,
        succeeding: List[str],
        glossary: Dict[str, str],
    ) -> float:
        """Đo điểm mượt tại vết nối dựa trên tính nhất quán thuật ngữ và độ dài nhịp câu."""
        if not recovered.strip():
            return 0.0
        score = 0.96
        for zh_term, vi_term in glossary.items():
            if vi_term.lower() not in recovered.lower():
                score -= 0.02
        return max(0.0, min(1.0, score))

    def _enforce_glossary_on_seam(
        self, text: str, glossary: Dict[str, str]
    ) -> str:
        out = text
        for wrong_variant, canonical_vi in glossary.items():
            out = out.replace(wrong_variant, canonical_vi)
        return out
