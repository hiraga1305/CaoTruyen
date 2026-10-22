# -*- coding: utf-8 -*-
"""CAOTRUYEN - MODULE 3.1: QUALITY GATE 4A (0 TOKEN API LINTER & GATE)
File: native_oauth/quality_gate.py

Functions:
1. Structural & Alignment Check: 1:1 match of §1..§N paragraph markers.
2. Tag Stripping & Leak Sanitizer: Detect and strip any leaked vi thẻ ([Ø=...], [||], [Qk:...]).
3. Deterministic Lock Verification: Validate [Mk:...] (metrics/units) and [Ik:...] (idioms).
4. Zero-CJK Verification: Disallow any leftover Chinese characters (\\u4e00-\\u9fff).
5. BNS Convert Smell Linter: Scans for forbidden calques ("không cho là đúng", "sắc mặt ngưng lại", "hướng về... chém", "đem...").
6. Advisory register warnings; pronouns require independent source-grounded review.
7. A mechanical pass only permits an unreviewed draft; never publication approval.
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set

from native_oauth.scene_contract import SceneContract, HardMetric, IdiomHint
from native_oauth.numeric_lock import DeterministicNumericExtractor


# ===========================================================================
# 1. BẢNG BIỂU THỨC CHÍNH QUY QUÉT "MÙI CONVERT" (CALQUE PATTERNS)
# ===========================================================================

FORBIDDEN_CONVERT_PATTERNS: List[Tuple[str, str, str]] = [
    # (pattern_regex, error_code, suggestion)
    (r"\bkhông cho là đúng\b", "CALQUE_KHONG_CHO_LA_DUNG", "đối chiếu nguồn: có thể đúng khi diễn đạt không tán đồng"),
    (r"\bkhông cho là ý\b", "CALQUE_KHONG_CHO_LA_Y", "chẳng chút bận tâm / không để trong lòng"),
    (r"\bsắc mặt\s+(?:một\s+)?ngưng lại\b", "CALQUE_SAC_MAT_NGUNG_LAI", "sắc mặt trầm xuống / vẻ mặt chợt đanh lại / chợt nghiêm mặt"),
    (r"\bánh mắt\s+(?:một\s+)?ngưng lại\b", "CALQUE_ANH_MAT_NGUNG_LAI", "ánh mắt sắc lạnh / ánh mắt lạnh đi"),
    (r"\bthần sắc\s+(?:một\s+)?ngưng lại\b", "CALQUE_THAN_SAC_NGUNG_LAI", "thần sắc ngưng trọng / vẻ mặt đanh lại"),
    (r"\bhít ngược một ngụm khí lạnh\b", "CALQUE_HIT_NGUOC_KHI_LANH", "đối chiếu nguồn và diễn đạt tự nhiên; không thêm cảm giác hay phản ứng"),
    (r"\bngược lại hít một ngụm khí lạnh\b", "CALQUE_HIT_NGUOC_KHI_LANH", "đối chiếu nguồn; không tự thêm cảm giác lạnh"),
    (r"\bhướng về\s+[^,.?!]+(?:\s+chém|\s+đánh|\s+bắn|\s+lao|\s+ném|\s+quát|\s+nói)\b", "CALQUE_HUONG_VE_DONG_TU", "nhằm thẳng... chém xuống / lao vút về phía... / quát lớn"),
    (r"\bđối với\s+[^,.?!]+\s+cười lạnh\b", "CALQUE_DOI_VOI_CUOI_LANH", "quay sang cười lạnh với... / cười khẩy"),
    (r"\bđem\s+[^,.?!]+\s+(?:thu vào|ném ra|đánh bay|chém thành|phá vỡ|cất đi)\b", "CALQUE_DEM_TAN_NGU_DONG_TU", "thu... vào / ném... ra / đánh văng... / chém nát..."),
    (r"\bbị\s+[^,.?!]+\s+sở\s+(?:thương|giết|hại|phá|diệt)\b", "CALQUE_BI_SO_DONG_TU", "bị... làm thương tổn / chết dưới tay... / bị... phá hủy"),
    (r"\btại\s+[^,.?!]+\s+(?:bên trong|bên trên|bên dưới|trên người)\b", "CALQUE_TAI_BEN_TRONG", "trong... / dưới... / trên... (bỏ chữ tại và phương vị)"),
    (r"\bmột cái\s+(?:nụ cười|cái tát|thanh âm|tiếng nổ|nắm đấm)\b", "CALQUE_MOT_CAI_LUONG_TU", "một nụ cười / một cái tát / một tiếng nổ"),
    (r"\bmột đạo\s+(?:thanh âm|tiếng hét|thanh quang|cầu vồng)\b", "CALQUE_MOT_DAO_LUONG_TU", "một giọng nói / một tiếng nổ / một tia sáng xanh / một luồng cầu vồng"),
    (r"\bmột cỗ\s+(?:sát khí|uy áp|hàn ý|nhiệt lãng)\b", "CALQUE_MOT_CO_LUONG_TU", "một luồng sát khí / một trận uy áp / luồng khí lạnh"),
    (r"\bkhông khỏi\b.{1,100}\bkhông khỏi\b", "CALQUE_LAP_KHONG_KHOI", "lặp từ không khỏi quá nhiều, hãy thay bằng bất giác, chợt, hoặc lược bỏ"),
    (r"\bsắc lệ nội nhẫn\b", "CALQUE_SAC_LE_NOI_NHAN", "ngoài mạnh trong yếu / miệng hùm gan sứa"),
    (r"\bvi bất túc đạo\b", "CALQUE_VI_BAT_TUC_DAO", "nhỏ bé không đáng kể / chẳng đáng nhắc tới"),
    (r"\bthấy săn lòng vui\b", "CALQUE_THAY_SAN_LONG_VUI", "ngứa nghề nổi hứng / thấy mồi ngon mà lòng khấp khởi"),
]

# Leaked Tag Patterns
LEAKED_TAG_PATTERN = re.compile(
    r"(\[Ø=[^\]]+\]|\[Ø_SHIFT=[^\]]+\]|\[\|\|\]|\[Q\d+:[^\]]+\]|\[M\d+:[^\]]+\]|\[I\d+\]|<delta>.*?</delta>)",
    re.DOTALL | re.IGNORECASE
)

# CJK Character Pattern
CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]")


# ===========================================================================
# 1.1 BẢNG BẪY HƯ TỪ & TỪ ĐA NGHĨA ĐÔ THỊ (URBAN FALSE FRIENDS & REGISTER)
# ===========================================================================

# Banned archaic pronouns and mannerisms in modern livestream barrage/chat
BARRAGE_ARCHAIC_BANLIST: List[str] = [
    "tại hạ", "các hạ", "đạo hữu", "bần đạo", "tiểu nhân",
    "lão phu", "huynh đài", "bản tọa", "tiểu bối", "đem... đặt ở"
]

# Patterns for detecting barrage / comments
BARRAGE_LINE_PATTERN = re.compile(
    r"(?:^|[\s“\"「])(?:【[^】]+】|\[[^\]]+\]|Hahaha|Ha ha|Đại sư|Chủ bá|Streamer|Cứu mạng|Quỳ rồi|666|Ngọa tào)",
    re.IGNORECASE
)

# Urban false friends dictionary with detection regex and recommended replacement
URBAN_FALSE_FRIENDS: List[Tuple[str, str, str, str]] = [
    # (pattern_regex, error_code, suggestion, replacement)
    (r"\bthủy hữu\b", "URBAN_THUY_HUU", "người xem / cư dân mạng / khán giả", "người xem"),
    (r"\bđại tỷ Bảng Nhất\b", "URBAN_DAI_TY_BANG_NHAT", "chị đại Top 1 / phú bà Top 1", "chị đại Top 1"),
    (r"\bđại ca Bảng Nhất\b", "URBAN_DAI_CA_BANG_NHAT", "đại ca Top 1 / anh lớn Top 1", "đại ca Top 1"),
    (r"\bBảng Nhất\b", "URBAN_BANG_NHAT", "Top 1 / đầu bảng / top 1 donate", "Top 1"),
    (r"\bbảng nhất\b", "URBAN_BANG_NHAT", "Top 1 / đầu bảng / top 1 donate", "Top 1"),
    (r"\bquét lễ vật\b", "URBAN_QUET_LE_VAT", "tặng quà / nạp quà / bắn donate", "tặng quà"),
    (r"\bliên mạch\b", "URBAN_LIEN_MACH", "nối máy / kết nối mic", "nối máy"),
    (r"\bgiảng cứu\b", "URBAN_GIANG_CUU", "cầu kỳ / có quy củ / sành sỏi", "cầu kỳ"),
    (r"\bkhông phải là cái đông tây\b", "URBAN_KHONG_PHAI_DONG_TAY", "thứ không ra gì / đồ khốn nạn", "thứ không ra gì"),
    (r"\bkhông phải cái đông tây\b", "URBAN_KHONG_PHAI_DONG_TAY", "thứ không ra gì / đồ khốn nạn", "thứ không ra gì"),
    (r"\bcái đông tây gì\b", "URBAN_CAI_DONG_TAY_GI", "thứ gì / cái quái gì", "thứ gì"),
    (r"\bđông tây gì\b", "URBAN_CAI_DONG_TAY_GI", "thứ gì / cái quái gì", "thứ gì"),
    (r"\bSiêu Cấp Hỏa Tiễn\b", "URBAN_SIEU_CAP_HOA_TIEN", "Tên Lửa Siêu Cấp", "Tên Lửa Siêu Cấp"),
    (r"\bsiêu cấp hỏa tiễn\b", "URBAN_SIEU_CAP_HOA_TIEN", "tên lửa siêu cấp", "tên lửa siêu cấp"),
]


def heal_urban_anomalies(text: str) -> Tuple[str, List[str]]:
    """Compatibility helper: semantic edits require sourced review, never regex."""
    return text, []


@dataclass
class GateViolation:
    paragraph_idx: int
    error_code: str
    message: str
    matched_snippet: str
    suggestion: str = ""
    severity: str = "ERROR"   # ERROR | WARNING


@dataclass
class GateResult:
    is_pass: bool
    violations: List[GateViolation]
    sanitized_paragraphs: Dict[int, str] = field(default_factory=dict)
    delta_block: Optional[str] = None
    quarantine: bool = False
    expected_paragraph_count: int = 0

    @property
    def has_critical_errors(self) -> bool:
        return any(v.severity == "ERROR" for v in self.violations)


class QualityGate4A:
    """Quality Gate 4A: Pure Python 0-Token Deterministic Gate & Linter."""

    def __init__(self, numeric_extractor: Optional[DeterministicNumericExtractor] = None):
        self.numeric_extractor = numeric_extractor or DeterministicNumericExtractor()

    def sanitize_leaked_tags(self, text: str) -> Tuple[str, List[str]]:
        """Bóc tách và làm sạch các vi thẻ nội bộ bị LLM in rò rỉ vào bản dịch."""
        found_tags: List[str] = []
        for m in LEAKED_TAG_PATTERN.finditer(text):
            found_tags.append(m.group(0))
        cleaned = LEAKED_TAG_PATTERN.sub("", text).strip()
        # Clean extra spaces
        cleaned = re.sub(r"[ \t]+", " ", cleaned)
        return cleaned, found_tags

    def verify_paragraphs(
        self,
        raw_worker_output: str,
        expected_paragraph_count: int,
        contract: SceneContract,
    ) -> GateResult:
        """Thực thi toàn diện 5 bộ kiểm định của Gate 4A."""
        violations: List[GateViolation] = []
        sanitized_map: Dict[int, str] = {}

        # 1. Structural Check & Parse Paragraphs
        extracted_paras: Dict[int, str] = {}
        order = []
        current_id = None
        for line in raw_worker_output.splitlines():
            line = line.strip()
            if not line:
                continue
            m = re.match(r"^§(\d+)(?:\s+(.*))?$", line)
            if m:
                p_id = int(m.group(1))
                order.append(p_id)
                if p_id in extracted_paras:
                    violations.append(GateViolation(p_id, "DUPLICATE_PARAGRAPH", "ID đoạn bị lặp", line))
                    current_id = None
                else:
                    extracted_paras[p_id] = (m.group(2) or "").strip()
                    current_id = p_id
            elif current_id is not None and not line.startswith(("§", "```")):
                # Continuations belong to the current paragraph; never discard them.
                extracted_paras[current_id] += "\n" + line
            else:
                violations.append(GateViolation(0, "UNPARSED_OUTPUT", "Nội dung ngoài schema đoạn", line[:120]))
        if expected_paragraph_count < 1 or order != list(range(1, expected_paragraph_count + 1)):
            violations.append(GateViolation(0, "PARAGRAPH_ORDER", "Tập/thứ tự ID không khớp nguồn", str(order)))

        # Check alignment
        if len(extracted_paras) != expected_paragraph_count:
            violations.append(GateViolation(
                paragraph_idx=0,
                error_code="ALIGNMENT_MISMATCH",
                message=f"Số lượng đoạn dịch ({len(extracted_paras)}) không khớp với nguồn ({expected_paragraph_count})",
                matched_snippet=f"Expected {expected_paragraph_count}, got {len(extracted_paras)}",
                severity="ERROR"
            ))

        for p_id in range(1, expected_paragraph_count + 1):
            if p_id not in extracted_paras:
                violations.append(GateViolation(
                    paragraph_idx=p_id,
                    error_code="MISSING_PARAGRAPH",
                    message=f"Thiếu hẳn đoạn dịch §{p_id}",
                    matched_snippet=f"§{p_id} not found",
                    severity="ERROR"
                ))

        # Check each paragraph
        for p_id, p_text in extracted_paras.items():
            # 2. Tag Leak Sanitizer
            cleaned_text, leaked_tags = self.sanitize_leaked_tags(p_text)
            if leaked_tags:
                violations.append(GateViolation(
                    paragraph_idx=p_id,
                    error_code="LEAKED_DSL_TAG",
                    message=f"Đoạn §{p_id} bị rò rỉ vi thẻ nội bộ: {', '.join(leaked_tags)}",
                    matched_snippet=", ".join(leaked_tags),
                    suggestion="Đã tự động làm sạch khỏi bản dịch",
                    severity="WARNING"
                ))
            sanitized_map[p_id] = cleaned_text
            if not cleaned_text:
                violations.append(GateViolation(p_id, "EMPTY_PARAGRAPH", "Đoạn dịch rỗng", f"§{p_id}"))

            # 3. Zero-CJK Check
            cjk_matches = CJK_PATTERN.findall(cleaned_text)
            if cjk_matches:
                violations.append(GateViolation(
                    paragraph_idx=p_id,
                    error_code="CJK_CONTAMINATION",
                    message=f"Đoạn §{p_id} còn sót ký tự chữ Hán: {''.join(cjk_matches)}",
                    matched_snippet="".join(cjk_matches),
                    severity="ERROR"
                ))

            # 4. Convert Smell Linter
            for regex_pat, err_code, sugg in FORBIDDEN_CONVERT_PATTERNS:
                for match in re.finditer(regex_pat, cleaned_text, re.IGNORECASE):
                    violations.append(GateViolation(
                        paragraph_idx=p_id,
                        error_code=err_code,
                        message=f"Phát hiện cấu trúc convert lỗi '{match.group(0)}' ở đoạn §{p_id}",
                        matched_snippet=match.group(0),
                        suggestion=sugg,
                        severity="WARNING"
                    ))

            # 5. Rhythm Check (COMBAT_FAST run-on sentence check)
            if contract.pacing == "COMBAT_FAST":
                sentences = re.split(r"[.!?。！？\n]", cleaned_text)
                for s in sentences:
                    words = s.strip().split()
                    if len(words) > 65:
                        violations.append(GateViolation(
                            paragraph_idx=p_id,
                            error_code="COMBAT_RUNON_SENTENCE",
                            message=f"Cảnh COMBAT_FAST chứa câu quá dài ({len(words)} từ) không ngắt nhịp",
                            matched_snippet=s.strip()[:60] + "...",
                            suggestion="Cần ngắt thành đoản cú 5-14 từ dứt khoát",
                            severity="WARNING"
                        ))

            # Pronouns/register need source, speaker and viewpoint. Genre alone
            # cannot certify them or reject a valid narrator/quoted register.

            # 6.1 Urban False Friends & Barrage Register Check
            is_urban = contract.genre.startswith("URBAN") or "URBAN" in contract.genre
            if is_urban:
                for regex_pat, err_code, sugg, _ in URBAN_FALSE_FRIENDS:
                    for match in re.finditer(regex_pat, cleaned_text, re.IGNORECASE):
                        violations.append(GateViolation(
                            paragraph_idx=p_id,
                            error_code=err_code,
                            message=f"Cần đối chiếu ngữ vực đô thị '{match.group(0)}' ở đoạn §{p_id}",
                            matched_snippet=match.group(0),
                            suggestion=sugg,
                            severity="WARNING"
                        ))

                # Check archaic in barrage / comment
                is_barrage = bool(BARRAGE_LINE_PATTERN.search(cleaned_text)) or "bình luận" in cleaned_text.lower() or "đạn mạc" in cleaned_text.lower()
                if is_barrage:
                    for archaic in BARRAGE_ARCHAIC_BANLIST:
                        if re.search(rf"\b{re.escape(archaic)}\b", cleaned_text, re.IGNORECASE):
                            violations.append(GateViolation(
                                paragraph_idx=p_id,
                                error_code="BARRAGE_ARCHAIC_LEAK",
                                message=f"Lẫn lộn từ ngữ cổ trang '{archaic}' trong kênh chat/bình luận ở đoạn §{p_id}",
                                matched_snippet=archaic,
                                suggestion="Trong kênh chat đạn mạc đô thị, cần dùng đại từ hiện đại (tôi, em, anh em, các bác...)",
                                severity="WARNING"
                            ))

        # 7. Deterministic Metric Verification
        for metric in contract.hard_metrics:
            found = False
            for p_id, p_clean in sanitized_map.items():
                if self.numeric_extractor.verify_vietnamese(p_clean, metric):
                    found = True
                    break
            if not found:
                violations.append(GateViolation(
                    paragraph_idx=0,
                    error_code="HARD_METRIC_DRIFT",
                    message=f"Số liệu bắt buộc '{metric.locked_vi}' ({metric.raw_zh}) không xuất hiện trong bản dịch",
                    matched_snippet=f"{metric.tag_id}:{metric.locked_vi}",
                    suggestion=f"Bắt buộc giữ nguyên cụm từ '{metric.locked_vi}'",
                    severity="ERROR"
                ))

        # Surface checks do not establish semantic approval. Surface-form
        # uncertainty is visible to a reviewer without mutating the text.
        for cue in contract.semantic_context.get("dialogues", []):
            if cue.get("review_required"):
                violations.append(GateViolation(
                    cue.get("paragraph_id", 0), "DIALOGUE_ATTRIBUTION_UNRESOLVED",
                    "Nguồn chưa đủ căn cứ xác định người nói/nghe; cần duyệt ngữ nghĩa",
                    f"{cue.get('speaker')}->{cue.get('listener')}", severity="WARNING"))

        by_id = {e.entity_id: e for e in contract.entities}
        for mention in contract.semantic_context.get("name_mentions", []):
            entity = by_id.get(mention['entity_id'])
            paragraph_id = mention['paragraph_id']
            if entity is None:
                continue
            for variant in entity.legacy_vi_variants:
                if re.search(rf"\b{re.escape(variant)}\b", sanitized_map.get(paragraph_id, ""), re.IGNORECASE):
                    violations.append(GateViolation(
                        paragraph_id, "CHARACTER_NAME_VARIANT_REVIEW",
                        f"Tên '{variant}' khác tên biên tập '{entity.vi}'; đối chiếu nguồn và cách gọi",
                        variant, suggestion="Duyệt tên riêng; không thay hàng loạt bằng regex", severity="WARNING"))

        is_pass = not any(v.severity == "ERROR" for v in violations)
        return GateResult(
            is_pass=is_pass,
            violations=violations,
            sanitized_paragraphs=sanitized_map,
            quarantine=not is_pass,
            expected_paragraph_count=expected_paragraph_count,
        )

    def heal_paragraphs(self, paragraphs: Dict[int, str]) -> Dict[int, str]:
        """Tự động vá lỗi tất định cho các đoạn văn."""
        res = {}
        for p_id, p_text in paragraphs.items():
            healed, _ = heal_urban_anomalies(p_text)
            res[p_id] = healed
        return res
