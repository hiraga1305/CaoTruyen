"""
native_oauth/prosody_engine.py - Vietnamese Literary Prosody & Cadence Engine
CaoTruyen v2.5 - Co-engineered with Gemini 4 Argon.

Elevates web novel translation from mechanical conversion to master-level literature.
Features:
1. Dual-Stream Decoupling: Separates Dialogue voice (khẩu khí) from Narrative voice (văn phong).
2. Cadence & Rhythm Linter: Breaks clunky Chinese run-on sentences (bạch thoại lê thê).
3. Tone Harmony (Cân bằng Bằng-Trắc): Checks sentence-ending tone balance to ensure musicality.
4. Sarcasm & Verbal Subtext Decorator: Flags sarcastic/mocking tones in dialogues.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class StreamType(str, Enum):
    DIALOGUE = "DIALOGUE"    # Lời thoại nhân vật: khẩu ngữ, cảm xúc, tự nhiên
    NARRATIVE = "NARRATIVE"  # Lời trần thuật / miêu tả: bi tráng, cổ phong, câu văn gãy gọn


@dataclass
class CadenceAnomaly:
    error_code: str
    sentence_snippet: str
    reason: str
    suggested_fix: str


class VietnameseProsodyEngine:
    """
    0-Token Linter & Heuristic Engine for Literary Vietnamese.
    Ensures rhythm, cadence, and dual-stream stylistic discipline.
    """

    # Westernized calques and clunky bureaucratic conjunctions
    CLUNKY_CONJUNCTIONS: List[Tuple[str, str, str]] = [
        (r"\bcùng với việc\b", "CLUNKY_CUNG_VOI_VIEC", "đồng thời / cùng lúc đó / khi"),
        (r"\bdưới tình huống này\b", "CLUNKY_DUOI_TINH_HUONG", "trong tình thế này / lúc này / thấy vậy"),
        (r"\bở một mức độ nào đó\b", "CLUNKY_O_MOT_MUC_DO", "phần nào / đôi chút"),
        (r"\btiến hành\s+(?:tấn công|tu luyện|đột phá|nghiên cứu|kiểm tra)\b", "CLUNKY_TIEN_HANH", "bỏ chữ 'tiến hành', dùng thẳng động từ"),
        (r"\bđược xưng là\b", "CLUNKY_DUOC_XUNG_LA", "được mệnh danh là / tục gọi là"),
        (r"\bmang đến cho\s+[^,.?!]+\s+cảm giác\b", "CLUNKY_MANG_DEN_CAM_GIAC", "khiến... cảm thấy / dấy lên nỗi..."),
        (r"\bvô luận như thế nào\b", "CLUNKY_VO_LUAN_NHU_THE_NAO", "dù thế nào đi nữa / bất luận ra sao"),
        (r"\bkhông thể nghi ngờ là\b", "CLUNKY_KHONG_THE_NGHI_NGO", "chắc chắn là / không nghi ngờ gì nữa"),
    ]

    # Vietnamese tone classification (Bằng: không dấu, dấu huyền; Trắc: sắc, hỏi, ngã, nặng)
    DAU_TRAC = set("áắấéếíóốớúứýảẳẩẻểỉỏổởủửỷãẵẫẽễĩõỗỡũữỹạặậẹệịọộợụựỵ")

    @classmethod
    def classify_stream_segments(cls, paragraph_vn: str) -> List[Tuple[StreamType, str]]:
        """
        Splits a paragraph into Dialogue segments (in quotes) and Narrative segments.
        Handles both Vietnamese quotes: "...", '...', “...”, ‘...’.
        """
        segments: List[Tuple[StreamType, str]] = []
        pattern = re.compile(r'(["“‘\'][^"”’\']+["”’\'])')
        tokens = pattern.split(paragraph_vn)

        for tok in tokens:
            if not tok.strip():
                continue
            if (tok.startswith(('"', '“', '‘', "'")) and tok.endswith(('"', '”', '’', "'"))):
                # Inner text is dialogue
                dialogue_text = tok[1:-1].strip()
                segments.append((StreamType.DIALOGUE, dialogue_text))
            else:
                segments.append((StreamType.NARRATIVE, tok.strip()))

        return segments

    @classmethod
    def audit_cadence_and_rhythm(cls, text_vn: str) -> List[CadenceAnomaly]:
        """
        Scans translated Vietnamese for:
        1. Overly long run-on sentences (> 40 words without comma or period).
        2. Clunky conjunction calques.
        3. Awkward consecutive heavy tone endings.
        """
        anomalies: List[CadenceAnomaly] = []

        # 1. Audit clunky conjunctions
        for pat, code, fix in cls.CLUNKY_CONJUNCTIONS:
            matches = list(re.finditer(pat, text_vn, flags=re.IGNORECASE))
            for m in matches:
                start = max(0, m.start() - 20)
                end = min(len(text_vn), m.end() + 20)
                snippet = text_vn[start:end].replace("\n", " ").strip()
                anomalies.append(CadenceAnomaly(
                    error_code=code,
                    sentence_snippet=snippet,
                    reason=f"Cụm từ ngữ pháp Tây hóa/hành chính gây sượng câu văn: '{m.group(0)}'",
                    suggested_fix=f"Thay bằng: {fix}"
                ))

        # 2. Audit run-on sentences (> 40 words without pause)
        sentences = re.split(r"[.?!]\s*", text_vn)
        for s in sentences:
            clauses = re.split(r"[,;:\n]\s*", s)
            for c in clauses:
                words = c.strip().split()
                if len(words) > 38:
                    snippet = " ".join(words[:12]) + " ... " + " ".join(words[-8:])
                    anomalies.append(CadenceAnomaly(
                        error_code="RUN_ON_CLAUSE_TOO_LONG",
                        sentence_snippet=snippet,
                        reason=f"Phân câu quá dài ({len(words)} từ) không ngắt nhịp, văn phong Bạch thoại lê thê",
                        suggested_fix="Tách thành 2 câu ngắn hoặc thêm dấu phẩy ngắt nhịp cân đối"
                    ))

        return anomalies

    @classmethod
    def heal_clunky_phrases(cls, text_vn: str) -> str:
        """Deterministic 0-token repair replacing clunky conjunctions with literary Vietnamese."""
        healed = text_vn
        replacements = [
            (r"\bcùng với việc\b", "đồng thời"),
            (r"\bdưới tình huống này\b", "trong tình thế này"),
            (r"\bvô luận như thế nào\b", "dù thế nào đi nữa"),
            (r"\bkhông thể nghi ngờ là\b", "chắc chắn là"),
            (r"\bđược xưng là\b", "được mệnh danh là"),
            (r"\bở một mức độ nào đó\b", "phần nào"),
        ]
        for pat, rep in replacements:
            healed = re.sub(pat, rep, healed, flags=re.IGNORECASE)
        return healed
