# native_oauth/autonomous/self_healing_engine.py
from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Dict, List, Optional, Tuple

from native_oauth.core.ast.semantic_parser import ASTNode, DiscourseType
from native_oauth.core.graph.retroactive_tekg import PronounState, RetroactiveTEKG


class AnomalyType(str, Enum):
    OMISSION = "OMISSION"
    HALLUCINATION = "HALLUCINATION"
    POLARITY_INVERSION = "POLARITY_INVERSION"
    PRONOUN_DRIFT = "PRONOUN_DRIFT"
    NUMERIC_DISTORTION = "NUMERIC_DISTORTION"
    CALQUE_LEAK = "CALQUE_LEAK"


class RepairTier(str, Enum):
    TIER_1_SYMBOLIC_ZERO_TOKEN = "TIER_1_SYMBOLIC_ZERO_TOKEN"
    TIER_2_CONSTRAINED_MICRO_SURGERY = "TIER_2_CONSTRAINED_MICRO_SURGERY"
    TIER_3_ENSEMBLE_TOURNAMENT = "TIER_3_ENSEMBLE_TOURNAMENT"


@dataclass(frozen=True)
class AnomalyReport:
    node_id: str
    anomaly_type: AnomalyType
    detected_by: str  # "WHITE_BOX_AUDITOR" | "BLACK_BOX_CRITIC"
    severity: float   # 0.0 -> 1.0
    description: str
    offending_span_vi: str = ""
    expected_constraint: str = ""


@dataclass(frozen=True)
class RepairDirective:
    node_id: str
    source_zh: str
    current_draft_vi: str
    anomalies: Tuple[AnomalyReport, ...]
    mandatory_keep_terms: Tuple[str, ...] = field(default_factory=tuple)
    forbidden_spans: Tuple[str, ...] = field(default_factory=tuple)
    enforced_polarity: Optional[int] = None  # +1 (Khẳng định) hoặc -1 (Phủ định)


@dataclass(frozen=True)
class HealingReceipt:
    node_id: str
    tier_used: RepairTier
    original_draft: str
    healed_text: str
    pre_healing_confidence: float
    post_healing_confidence: float
    anomalies_resolved: Tuple[AnomalyType, ...]
    timestamp_ms: int


@dataclass
class AutonomousAuditLedger:
    chapter_id: str
    initial_confidence: float
    final_confidence: float
    publication_approved: bool
    receipts: List[HealingReceipt] = field(default_factory=list)
    unresolved_anomalies: List[AnomalyReport] = field(default_factory=list)


class BilingualWhiteBoxAuditor:
    """
    MẮT 1: Kiểm toán viên Đối chiếu Song ngữ Trắng (White-Box Auditor).
    So sánh trực tiếp Raw Tiếng Trung và Bản dịch Tiếng Việt để bắt lỗi:
    1. Đảo ngược phủ định (Polarity Inversion)
    2. Sai số học / phương vị (Numeric & Spatial Distortion)
    3. Sót ý / Bịa đặt (Omission / Hallucination)
    """

    ZH_NEGATION_TOKENS: Tuple[str, ...] = ("不", "没", "未", "莫", "勿", "非", "毫无", "绝不")
    ZH_DOUBLE_POSITIVE_PATTERNS: Tuple[str, ...] = ("未尝不", "非不", "莫非不", "无不")

    VI_NEGATION_TOKENS: Tuple[str, ...] = (
        "không", "chẳng", "chưa", "chớ", "đừng", "vô", "chưa từng", "tuyệt nhiên không",
    )

    ZH_NUMBER_MAP: Dict[str, str] = {
        "一": "một", "二": "hai", "两": "hai", "三": "ba", "四": "bốn",
        "五": "năm", "六": "sáu", "七": "bảy", "八": "tám", "九": "chín",
        "十": "mười", "百": "trăm", "千": "ngàn", "万": "vạn",
    }

    ZH_DIRECTION_MAP: Dict[str, Tuple[str, ...]] = {
        "东北": ("đông bắc",),
        "西北": ("tây bắc",),
        "东南": ("đông nam",),
        "西南": ("tây nam",),
    }

    def inspect(
        self, node: ASTNode, draft_vi: str, glossary: Dict[str, str]
    ) -> List[AnomalyReport]:
        anomalies: List[AnomalyReport] = []
        raw_zh = node.source_text
        lower_vi = draft_vi.lower()

        # 1. Kiểm tra tỷ lệ độ dài (Omission / Hallucination)
        zh_chars = [c for c in raw_zh if "\u4e00" <= c <= "\u9fa5"]
        vi_words = draft_vi.strip().split()
        if len(zh_chars) >= 8:
            ratio = len(vi_words) / float(len(zh_chars))
            if ratio < 0.60:
                anomalies.append(
                    AnomalyReport(
                        node_id=node.node_id,
                        anomaly_type=AnomalyType.OMISSION,
                        detected_by="WHITE_BOX_AUDITOR",
                        severity=0.95,
                        description=f"Tỷ lệ âm tiết/Hán tự quá thấp ({ratio:.2f} < 0.60), nghi ngờ sót ý.",
                    )
                )
            elif ratio > 2.20:
                anomalies.append(
                    AnomalyReport(
                        node_id=node.node_id,
                        anomaly_type=AnomalyType.HALLUCINATION,
                        detected_by="WHITE_BOX_AUDITOR",
                        severity=0.85,
                        description=f"Tỷ lệ âm tiết/Hán tự phình đại ({ratio:.2f} > 2.20), nghi ngờ bịa đặt.",
                    )
                )

        # 2. Kiểm tra Đảo ngược Phủ định (Negation Polarity Check)
        zh_polarity = self._compute_zh_polarity(raw_zh)
        vi_polarity = self._compute_vi_polarity(lower_vi)
        if zh_polarity != vi_polarity:
            anomalies.append(
                AnomalyReport(
                    node_id=node.node_id,
                    anomaly_type=AnomalyType.POLARITY_INVERSION,
                    detected_by="WHITE_BOX_AUDITOR",
                    severity=1.0,
                    description=(
                        f"Đảo ngược cực tính phủ định: Raw mang cực ({zh_polarity}) "
                        f"nhưng bản dịch mang cực ({vi_polarity})."
                    ),
                    expected_constraint="POSITIVE" if zh_polarity > 0 else "NEGATIVE",
                )
            )

        # 3. Kiểm tra Phương vị & Số liệu (Numeric & Spatial Parity)
        for zh_dir, vi_dirs in self.ZH_DIRECTION_MAP.items():
            if zh_dir in raw_zh and not any(vd in lower_vi for vd in vi_dirs):
                anomalies.append(
                    AnomalyReport(
                        node_id=node.node_id,
                        anomaly_type=AnomalyType.NUMERIC_DISTORTION,
                        detected_by="WHITE_BOX_AUDITOR",
                        severity=0.95,
                        description=f"Sai lệch phương vị '{zh_dir}', thiếu '{vi_dirs[0]}' trong bản dịch.",
                        expected_constraint=vi_dirs[0],
                    )
                )

        # 4. Kiểm tra bảo toàn Thuật ngữ Bắt buộc (Glossary Enforcement)
        for zh_term, vi_term in glossary.items():
            if zh_term in raw_zh and vi_term.lower() not in lower_vi:
                anomalies.append(
                    AnomalyReport(
                        node_id=node.node_id,
                        anomaly_type=AnomalyType.PRONOUN_DRIFT,
                        detected_by="WHITE_BOX_AUDITOR",
                        severity=0.90,
                        description=f"Thiếu thuật ngữ/đại từ chuẩn '{vi_term}' cho '{zh_term}'.",
                        expected_constraint=vi_term,
                    )
                )

        return anomalies

    def _compute_zh_polarity(self, raw_zh: str) -> int:
        if any(dp in raw_zh for dp in self.ZH_DOUBLE_POSITIVE_PATTERNS):
            return 1
        pattern = "|".join(re.escape(tok) for tok in sorted(self.ZH_NEGATION_TOKENS, key=len, reverse=True))
        matches = re.findall(pattern, raw_zh)
        return -1 if (len(matches) % 2 == 1) else 1

    def _compute_vi_polarity(self, lower_vi: str) -> int:
        if "không phải là không" in lower_vi or "chẳng phải không" in lower_vi:
            return 1
        words = re.findall(r"\w+", lower_vi)
        neg_count = sum(1 for w in words if w in ("không", "chẳng", "chưa", "chớ", "đừng"))
        return -1 if (neg_count % 2 == 1) else 1


class MonolingualBlackBoxCritic:
    """
    MẮT 2: Nhà Phê bình Văn học Việt Độc lập Mắt Đen (Black-Box Critic).
    HOÀN TOÀN KHÔNG NHÌN TIẾNG TRUNG. Đánh giá bản dịch như một độc giả Việt Nam khắt khe.
    """

    STIFF_CALQUE_PATTERNS: Tuple[Tuple[re.Pattern, str, str], ...] = (
        (
            re.compile(r"\btrong mắt hiện lên một tia\b", re.IGNORECASE),
            "trong mắt hiện lên một tia",
            "trong đáy mắt thoáng hiện nét",
        ),
        (
            re.compile(r"\bcười lạnh một tiếng nói\b", re.IGNORECASE),
            "cười lạnh một tiếng nói",
            "cười khẩy rồi cất giọng",
        ),
        (
            re.compile(r"\bhít sâu một hơi khí lạnh\b", re.IGNORECASE),
            "hít sâu một hơi khí lạnh",
            "hít vào một ngụm khí lạnh",
        ),
        (
            re.compile(r"\bđem\s+([^\s,]+)\s+cho\s+giết\b", re.IGNORECASE),
            "cấu trúc chữ ĐEM (把) dịch thô",
            "",
        ),
    )

    def inspect_monolingual(self, node_id: str, draft_vi: str) -> List[AnomalyReport]:
        anomalies: List[AnomalyReport] = []

        # 1. Quét các cụm từ sượng mùi Convert
        for pattern, bad_phrase, replacement_hint in self.STIFF_CALQUE_PATTERNS:
            match = pattern.search(draft_vi)
            if match:
                anomalies.append(
                    AnomalyReport(
                        node_id=node_id,
                        anomaly_type=AnomalyType.CALQUE_LEAK,
                        detected_by="BLACK_BOX_CRITIC",
                        severity=0.75,
                        description=f"Phát hiện cụm từ sượng văn convert: '{match.group(0)}'.",
                        offending_span_vi=match.group(0),
                        expected_constraint=replacement_hint,
                    )
                )

        # 2. Phát hiện lỗi nhập nhằng đại từ đồng nhất ("hắn nhìn hắn", "nàng giết nàng")
        ambiguous_pronoun = re.search(
            r"\b(hắn|nàng|gã|y)\s+(?:nhìn|đâm|giết|hỏi|đánh|chặn)\s+\1\b",
            draft_vi,
            re.IGNORECASE,
        )
        if ambiguous_pronoun:
            anomalies.append(
                AnomalyReport(
                    node_id=node_id,
                    anomaly_type=AnomalyType.PRONOUN_DRIFT,
                    detected_by="BLACK_BOX_CRITIC",
                    severity=0.88,
                    description=(
                        f"Nhập nhằng đại từ cho người đọc Việt: '{ambiguous_pronoun.group(0)}' "
                        f"(không rõ ai tác động lên ai)."
                    ),
                    offending_span_vi=ambiguous_pronoun.group(0),
                    expected_constraint="đối phương",
                )
            )

        return anomalies


class AutonomousSelfHealingEngine:
    """
    Động cơ Tự Can Thiệp, Tự Vi Phẫu & Tự Hội Tụ Hồi Tố Khép Kín (ASTOS Core Engine).
    Heuristic triage/repair only. Scores are not calibrated semantic probabilities
    and never authorize publication; use the independent source-bound gate.
    """

    PUBLICATION_CONFIDENCE_THRESHOLD: float = 0.98

    def __init__(
        self,
        constrained_micro_surgeon: Optional[Callable[[RepairDirective], str]] = None,
    ) -> None:
        self.white_box = BilingualWhiteBoxAuditor()
        self.black_box = MonolingualBlackBoxCritic()
        self._micro_surgeon = constrained_micro_surgeon or self._default_micro_surgeon

    def audit_and_heal_chapter(
        self,
        chapter_id: str,
        nodes: List[ASTNode],
        draft_translations: Dict[str, str],
        glossary: Optional[Dict[str, str]] = None,
    ) -> Tuple[Dict[str, str], AutonomousAuditLedger]:
        """
        Thực thi chu trình khép kín: Kiểm toán 2 Mắt -> Tự Vi phẫu 3 Tầng -> Xuất biên lai kiểm toán.
        """
        active_glossary = glossary or {}
        healed_translations: Dict[str, str] = dict(draft_translations)
        receipts: List[HealingReceipt] = []
        unresolved: List[AnomalyReport] = []

        initial_scores: List[float] = []
        final_scores: List[float] = []

        for node in nodes:
            draft_vi = healed_translations.get(node.node_id, "")
            anomalies = self._run_dual_inspection(node, draft_vi, active_glossary)
            pre_conf = self._calculate_confidence(anomalies)
            initial_scores.append(pre_conf)

            if not anomalies:
                final_scores.append(1.0)
                continue

            # Kích hoạt Quy trình Tự Vi Phẫu Đa Tầng
            healed_vi, tier_used = self._execute_multi_tier_healing(
                node, draft_vi, anomalies, active_glossary
            )
            post_anomalies = self._run_dual_inspection(node, healed_vi, active_glossary)
            post_conf = self._calculate_confidence(post_anomalies)
            final_scores.append(post_conf)

            healed_translations[node.node_id] = healed_vi
            receipts.append(
                HealingReceipt(
                    node_id=node.node_id,
                    tier_used=tier_used,
                    original_draft=draft_vi,
                    healed_text=healed_vi,
                    pre_healing_confidence=pre_conf,
                    post_healing_confidence=post_conf,
                    anomalies_resolved=tuple(a.anomaly_type for a in anomalies),
                    timestamp_ms=int(time.time() * 1000),
                )
            )
            if post_anomalies:
                unresolved.extend(post_anomalies)

        avg_init = sum(initial_scores) / len(initial_scores) if initial_scores else 1.0
        avg_final = sum(final_scores) / len(final_scores) if final_scores else 1.0

        ledger = AutonomousAuditLedger(
            chapter_id=chapter_id,
            initial_confidence=round(avg_init, 4),
            final_confidence=round(avg_final, 4),
            publication_approved=False,
            receipts=receipts,
            unresolved_anomalies=unresolved,
        )
        return healed_translations, ledger

    def autonomous_retroactive_converge(
        self,
        tekg: RetroactiveTEKG,
        revealed_entity_id: str,
        current_chapter: int,
        safe_pre_reveal_narrative_ref: str,
    ) -> List[int]:
        """
        Tự động quay về các chương cũ (1 .. current_chapter - 1) để cập nhật lại đại từ trần thuật
        qua thẻ Standoff mà KHÔNG làm lộ bí mật trong lời thoại nhân vật (Anti-Spoiler Guard).
        """
        retro_state = PronounState(
            chapter_from=1,
            chapter_to=max(1, current_chapter - 1),
            self_pronoun="Ta",
            address_pronoun="Các hạ",
            third_person_ref=safe_pre_reveal_narrative_ref,
            register_tone="RETRO_CONVERGED_SAFE",
        )
        return tekg.retroactive_realign(
            src_id=revealed_entity_id,
            dst_id="NARRATOR",
            new_state=retro_state,
        )

    def _run_dual_inspection(
        self, node: ASTNode, text_vi: str, glossary: Dict[str, str]
    ) -> List[AnomalyReport]:
        wb_issues = self.white_box.inspect(node, text_vi, glossary)
        bb_issues = self.black_box.inspect_monolingual(node.node_id, text_vi)
        return wb_issues + bb_issues

    def _calculate_confidence(self, anomalies: List[AnomalyReport]) -> float:
        if not anomalies:
            return 1.0
        penalty = sum(a.severity * 0.25 for a in anomalies)
        return max(0.0, round(1.0 - penalty, 4))

    def _execute_multi_tier_healing(
        self,
        node: ASTNode,
        draft_vi: str,
        anomalies: List[AnomalyReport],
        glossary: Dict[str, str],
    ) -> Tuple[str, RepairTier]:
        # TẦNG 1: Thử sửa chữa tất định 0-Token trước (Symbolic Patch)
        patched = draft_vi
        for anomaly in anomalies:
            if anomaly.anomaly_type == AnomalyType.CALQUE_LEAK and anomaly.offending_span_vi and anomaly.expected_constraint:
                patched = re.sub(
                    re.escape(anomaly.offending_span_vi),
                    anomaly.expected_constraint,
                    patched,
                    flags=re.IGNORECASE,
                )
            elif anomaly.anomaly_type == AnomalyType.PRONOUN_DRIFT and anomaly.offending_span_vi and anomaly.expected_constraint:
                parts = anomaly.offending_span_vi.split()
                if len(parts) == 3:
                    fixed_span = f"{parts[0]} {parts[1]} {anomaly.expected_constraint}"
                    patched = patched.replace(anomaly.offending_span_vi, fixed_span)

        remaining = self._run_dual_inspection(node, patched, glossary)
        if not remaining:
            return patched, RepairTier.TIER_1_SYMBOLIC_ZERO_TOKEN

        # TẦNG 2: Vi phẫu Cưỡng chế Ràng buộc (Constrained Delta Micro-Surgery)
        enforced_pol = None
        for a in remaining:
            if a.anomaly_type == AnomalyType.POLARITY_INVERSION:
                enforced_pol = 1 if a.expected_constraint == "POSITIVE" else -1

        directive = RepairDirective(
            node_id=node.node_id,
            source_zh=node.source_text,
            current_draft_vi=patched,
            anomalies=tuple(remaining),
            mandatory_keep_terms=tuple(glossary.values()),
            forbidden_spans=tuple(a.offending_span_vi for a in remaining if a.offending_span_vi),
            enforced_polarity=enforced_pol,
        )
        surgically_repaired = self._micro_surgeon(directive)
        return surgically_repaired, RepairTier.TIER_2_CONSTRAINED_MICRO_SURGERY

    def _default_micro_surgeon(self, directive: RepairDirective) -> str:
        """
        Bộ vi phẫu mặc định xử lý các ca đảo ngược cực tính và thiếu phương vị/thuật ngữ.
        """
        repaired = directive.current_draft_vi

        # Khôi phục cực tính phủ định nếu bị đảo ngược
        if directive.enforced_polarity == -1 and self.white_box._compute_vi_polarity(repaired.lower()) == 1:
            repaired = re.sub(r"\b(có thể|được phép|dám)\b", r"không \1", repaired, count=1)
        elif directive.enforced_polarity == 1 and self.white_box._compute_vi_polarity(repaired.lower()) == -1:
            repaired = re.sub(r"\b(?:không|chẳng|chưa)\s+", "", repaired, count=1)

        # Bổ sung phương vị / thuật ngữ bị thiếu
        for anomaly in directive.anomalies:
            if anomaly.anomaly_type in (AnomalyType.NUMERIC_DISTORTION, AnomalyType.PRONOUN_DRIFT):
                if anomaly.expected_constraint and anomaly.expected_constraint.lower() not in repaired.lower():
                    repaired = f"{repaired.rstrip('.')} ({anomaly.expected_constraint})."

        return repaired
