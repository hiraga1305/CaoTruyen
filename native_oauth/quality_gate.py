# -*- coding: utf-8 -*-
"""CAOTRUYEN - MODULE 3.1: QUALITY GATE 4A (0 TOKEN API LINTER & GATE)
File: native_oauth/quality_gate.py

Functions:
1. Structural & Alignment Check: 1:1 match of §1..§N paragraph markers.
2. Tag Stripping & Leak Sanitizer: Detect and strip any leaked vi thẻ ([Ø=...], [||], [Qk:...]).
3. Deterministic Lock Verification: Validate [Mk:...] (metrics/units) and [Ik:...] (idioms).
4. Zero-CJK Verification: Disallow any leftover Chinese characters (\\u4e00-\\u9fff).
5. BNS Convert Smell Linter: Scans for forbidden calques ("không cho là đúng", "sắc mặt ngưng lại", "hướng về... chém", "đem...").
6. Pronoun Matrix & Narrative Discipline Check: Checks narr_lock and dialogue state transitions.
7. Decision routing: PASS -> commit clean text; FAIL -> trigger Spot-Audit 4B.
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
    (r"\bkhông cho là đúng\b", "CALQUE_KHONG_CHO_LA_DUNG", "chẳng mảy may để tâm / cười khẩy không coi ra gì / không tán đồng"),
    (r"\bkhông cho là ý\b", "CALQUE_KHONG_CHO_LA_Y", "chẳng chút bận tâm / không để trong lòng"),
    (r"\bsắc mặt\s+(?:một\s+)?ngưng lại\b", "CALQUE_SAC_MAT_NGUNG_LAI", "sắc mặt trầm xuống / vẻ mặt chợt đanh lại / chợt nghiêm mặt"),
    (r"\bánh mắt\s+(?:một\s+)?ngưng lại\b", "CALQUE_ANH_MAT_NGUNG_LAI", "ánh mắt sắc lạnh / ánh mắt lạnh đi"),
    (r"\bthần sắc\s+(?:một\s+)?ngưng lại\b", "CALQUE_THAN_SAC_NGUNG_LAI", "thần sắc ngưng trọng / vẻ mặt đanh lại"),
    (r"\bhít ngược một ngụm khí lạnh\b", "CALQUE_HIT_NGUOC_KHI_LANH", "hít vào một hơi lạnh buốt / giật mình kinh hãi / lạnh toát cả sống lưng"),
    (r"\bngược lại hít một ngụm khí lạnh\b", "CALQUE_HIT_NGUOC_KHI_LANH", "hít vào một hơi lạnh buốt / lạnh toát sống lưng"),
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
    """Tự động phát hiện và sửa chữa tất định (0 Token) các bẫy khẩu ngữ Đô thị / Livestream."""
    healed = text
    applied_patches: List[str] = []

    # 1. Archaic in barrage / comment lines
    if "【" in healed or "đạn mạc" in healed.lower() or "bình luận" in healed.lower() or "streamer" in healed.lower() or "hahaha" in healed.lower():
        if "tại hạ" in healed.lower():
            healed = re.sub(r"\btại hạ\b", "tôi", healed, flags=re.IGNORECASE)
            applied_patches.append("tại hạ -> tôi (barrage)")

    # 2. Gift alignment (Hỏa Tiễn -> Tên Lửa in gift / stream context)
    if "Siêu Cấp Hỏa Tiễn" in healed:
        healed = healed.replace("Siêu Cấp Hỏa Tiễn", "Tên Lửa Siêu Cấp")
        applied_patches.append("Siêu Cấp Hỏa Tiễn -> Tên Lửa Siêu Cấp")
    if "siêu cấp hỏa tiễn" in healed:
        healed = healed.replace("siêu cấp hỏa tiễn", "tên lửa siêu cấp")
        applied_patches.append("siêu cấp hỏa tiễn -> tên lửa siêu cấp")
    if re.search(r"\b[Hh]ỏa [Tt]iễn\b", healed) or re.search(r"\bhỏa tiễn\b", healed):
        healed = re.sub(r"\bHỏa [Tt]iễn\b", "Tên Lửa", healed)
        healed = re.sub(r"\bhỏa tiễn\b", "tên lửa", healed)
        applied_patches.append("hỏa tiễn -> tên lửa")

    # 3. Thủy hữu -> người xem / khán giả
    if "đám thủy hữu" in healed.lower():
        healed = re.sub(r"\bđám thủy hữu\b", "đám người xem", healed, flags=re.IGNORECASE)
        applied_patches.append("đám thủy hữu -> đám người xem")
    if "các thủy hữu" in healed.lower():
        healed = re.sub(r"\bcác thủy hữu\b", "các khán giả", healed, flags=re.IGNORECASE)
        applied_patches.append("các thủy hữu -> các khán giả")
    if "thủy hữu" in healed.lower():
        healed = re.sub(r"\bthủy hữu\b", "người xem", healed, flags=re.IGNORECASE)
        applied_patches.append("thủy hữu -> người xem")

    # 4. Bảng Nhất -> Top 1
    healed = re.sub(r"\bđại tỷ [Bb]ảng [Nn]hất\b", "chị đại Top 1", healed)
    healed = re.sub(r"\bđại ca [Bb]ảng [Nn]hất\b", "đại ca Top 1", healed)
    healed = re.sub(r"\b(?:ngôi|vị trí)\s+[Bb]ảng [Nn]hất\b", "vị trí Top 1", healed)
    if re.search(r"\b[Bb]ảng [Nn]hất\b", healed):
        healed = re.sub(r"\b[Bb]ảng [Nn]hất\b", "Top 1", healed)
        applied_patches.append("Bảng Nhất -> Top 1")

    # 5. False friends: quét lễ vật, liên mạch, giảng cứu
    if "quét lễ vật" in healed.lower():
        healed = re.sub(r"\bquét lễ vật\b", "tặng quà", healed, flags=re.IGNORECASE)
        applied_patches.append("quét lễ vật -> tặng quà")
    if "liên mạch" in healed.lower() and any(w in healed.lower() for w in ["phòng", "mic", "live", "nói", "kết nối"]):
        healed = re.sub(r"\bliên mạch\b", "nối máy", healed, flags=re.IGNORECASE)
        applied_patches.append("liên mạch -> nối máy")
    if "giảng cứu" in healed.lower():
        healed = re.sub(r"\bgiảng cứu\b", "cầu kỳ", healed, flags=re.IGNORECASE)
        applied_patches.append("giảng cứu -> cầu kỳ")

    return healed, applied_patches


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
        paragraph_lines = [l.strip() for l in raw_worker_output.splitlines() if l.strip().startswith("§")]
        extracted_paras: Dict[int, str] = {}

        for line in paragraph_lines:
            m = re.match(r"^§(\d+)\s*(.*)$", line)
            if m:
                p_id = int(m.group(1))
                extracted_paras[p_id] = m.group(2).strip()

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
                        severity="ERROR"
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

            # 6. Narrative Pronoun Check (outside quotes)
            if contract.genre == "XIANXIA":
                dialogue_cleaned = re.sub(r'“[^”]*”|"[^"]*"|「[^」]*」', "", cleaned_text)
                for modern_pronoun in ["anh ta", "cô ta", "cậu ấy", "cậu ta", "ông ấy", "bà ấy"]:
                    if modern_pronoun in dialogue_cleaned.lower():
                        violations.append(GateViolation(
                            paragraph_idx=p_id,
                            error_code="MODERN_PRONOUN_IN_NARRATIVE",
                            message=f"Xuất hiện đại từ hiện đại '{modern_pronoun}' trong ngôi kể đoạn §{p_id}",
                            matched_snippet=modern_pronoun,
                            suggestion=f"Bắt buộc dùng narr_lock trong SceneContract ({[e.narr_lock for e in contract.entities]})",
                            severity="ERROR"
                        ))

            # 6.1 Urban False Friends & Barrage Register Check
            is_urban = contract.genre.startswith("URBAN") or "URBAN" in contract.genre
            if is_urban:
                for regex_pat, err_code, sugg, _ in URBAN_FALSE_FRIENDS:
                    for match in re.finditer(regex_pat, cleaned_text, re.IGNORECASE):
                        violations.append(GateViolation(
                            paragraph_idx=p_id,
                            error_code=err_code,
                            message=f"Phát hiện bẫy hư từ / ngữ vực đô thị '{match.group(0)}' ở đoạn §{p_id}",
                            matched_snippet=match.group(0),
                            suggestion=sugg,
                            severity="ERROR"
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
                                severity="ERROR"
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

        # 8. Pronoun Matrix Enforcement after HOSTILE_SHIFT
        # If hostile shift occurs, friendly pronouns should not appear in dialogue
        has_hostile = any(p.state in ["HOSTILE", "HOSTILE_SHIFT"] for p in contract.pronouns)
        if has_hostile:
            for p_id, p_clean in sanitized_map.items():
                quotes = re.findall(r'“([^”]*)”|"([^"]*)"|「([^」]*)」', p_clean)
                for q_tuple in quotes:
                    quote_text = next((q for q in q_tuple if q), "")
                    for forbidden_courteous in ["đạo hữu", "huynh đài", "tiểu đệ", "tại hạ"]:
                        # If the quote is aggressive, shouldn't use overly polite terms
                        if any(w in quote_text.lower() for w in ["chết", "ngươi", "tiểu bối", "súc sinh"]):
                            if forbidden_courteous in quote_text.lower():
                                violations.append(GateViolation(
                                    paragraph_idx=p_id,
                                    error_code="PRONOUN_HOSTILE_VIOLATION",
                                    message=f"Lẫn lộn đại từ xưng hô thân mật '{forbidden_courteous}' trong câu thoại thù địch ở §{p_id}",
                                    matched_snippet=forbidden_courteous,
                                    suggestion="Phải chuyển sang ta - ngươi theo PRONOUN_MATRIX",
                                    severity="ERROR"
                                ))

        is_pass = not any(v.severity == "ERROR" for v in violations)
        return GateResult(
            is_pass=is_pass,
            violations=violations,
            sanitized_paragraphs=sanitized_map,
            quarantine=not is_pass
        )

    def heal_paragraphs(self, paragraphs: Dict[int, str]) -> Dict[int, str]:
        """Tự động vá lỗi tất định cho các đoạn văn."""
        res = {}
        for p_id, p_text in paragraphs.items():
            healed, _ = heal_urban_anomalies(p_text)
            res[p_id] = healed
        return res
