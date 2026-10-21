# native_oauth/core/ast/semantic_parser.py
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


class DiscourseType(str, Enum):
    NARRATION = "NARRATION"
    DIRECT_SPEECH = "DIRECT_SPEECH"
    FREE_INDIRECT_DISCOURSE = "FREE_INDIRECT_DISCOURSE"
    SYSTEM_LORE = "SYSTEM_LORE"


@dataclass(frozen=True)
class EDU:
    """Đơn vị mệnh đề cơ sở (Elementary Discourse Unit) độc lập với dấu câu."""
    edu_id: str
    raw_text: str
    char_start: int
    char_end: int
    has_explicit_quote: bool = False
    detected_speech_verb: Optional[str] = None
    detected_speaker_hint: Optional[str] = None
    deictic_markers: Tuple[str, ...] = field(default_factory=tuple)


@dataclass
class ASTNode:
    """Nút cú pháp ngữ nghĩa đã được cô lập trạng thái."""
    node_id: str
    discourse_type: DiscourseType
    source_text: str
    normalized_text: str
    speaker_id: Optional[str] = None
    confidence: float = 1.0
    edus: List[EDU] = field(default_factory=list)
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class SemanticASTDocument:
    """Cây AST hoàn chỉnh của một chương truyện."""
    chapter_id: str
    nodes: List[ASTNode]
    raw_checksum: str

    def get_nodes_by_type(self, dtype: DiscourseType) -> List[ASTNode]:
        return [n for n in self.nodes if n.discourse_type == dtype]


class SemanticASTParser:
    """
    Bộ phân tách Cú pháp Ngữ nghĩa Chịu lỗi Bất bại (Indestructible Semantic-AST Parser).
    Hoạt động chuẩn xác ngay cả khi văn bản raw bị mất 100% dấu ngoặc kép.
    """

    # Động từ phát ngôn trực tiếp (External Speech Verbs)
    EXTERNAL_SPEECH_VERBS: Tuple[str, ...] = (
        "沉声道", "冷笑道", "大喝道", "怒喝道", "轻声道", "缓缓道", "开口道",
        "问道", "答道", "说道", "笑道", "喝道", "喊道", "叫道", "叱道", "叹道",
        "冷哼一声", "淡淡道", "厉声道", "颤声道", "传音道",
    )

    # Động từ nhận thức / độc thoại nội tâm (Internal Cognition Verbs)
    INTERNAL_COGNITION_VERBS: Tuple[str, ...] = (
        "暗道", "心想", "心道", "暗忖", "思忖", "心中一凛", "心头一震",
        "暗自思量", "心中暗骂", "心底升起", "脑海中闪过",
    )

    # Từ chỉ thị dịch chuyển tâm điểm nhận thức (Deictic Shift Markers cho FID)
    DEICTIC_FID_MARKERS: Tuple[str, ...] = (
        "果然", "竟然", "难道", "恐怕", "糟了", "该死", "这老家伙", "这老贼",
        "这小辈", "今日怕是", "岂有此理", "莫非", "想不到", "看来今天",
    )

    # Đại từ nhân xưng ngôi thứ nhất & thứ hai chỉ xuất hiện trong Thoại / Nội tâm
    SPEECH_ONLY_PRONOUNS: Tuple[str, ...] = (
        "老夫", "本座", "本尊", "贫道", "在下", "老衲", "朕", "哀家",
        "尔等", "阁下", "道友", "前辈", "师尊", "晚辈", "你这", "你们",
    )

    # Dấu hiệu bảng hệ thống / thuộc tính (System Lore Markers)
    SYSTEM_PATTERNS: Tuple[re.Pattern, ...] = (
        re.compile(r"^[\[【].+[\]】]$"),
        re.compile(r"^[\[【]?(?:宿主|境界|功法|神通|技能|力量|敏捷|体质|灵根|魔药|序列)\s*[:：]"),
    )

    def __init__(self) -> None:
        # Biểu thức tách mệnh đề dựa trên dấu câu HOẶC động từ phát ngôn/nhận thức
        all_verbs = sorted(
            self.EXTERNAL_SPEECH_VERBS + self.INTERNAL_COGNITION_VERBS,
            key=len,
            reverse=True,
        )
        verb_group = "|".join(re.escape(v) for v in all_verbs)
        self._speech_intro_regex = re.compile(
            rf"(?P<speaker>[^\s，。！？；：“”\"'、]{{1,12}}?)(?P<verb>{verb_group})[:：，,]?"
        )
        self._explicit_quote_regex = re.compile(r"[“\"「『](.+?)[”\"」』]")

    def parse(self, raw_text: str, chapter_id: str = "ch_0001") -> SemanticASTDocument:
        """Phân tích văn bản raw (kể cả văn bản bẩn mất dấu câu) thành SemanticASTDocument."""
        checksum = hashlib.sha256(raw_text.encode("utf-8")).hexdigest()[:16]
        paragraphs = [p.strip() for p in raw_text.splitlines() if p.strip()]
        nodes: List[ASTNode] = []
        node_counter = 0

        for para in paragraphs:
            stripped_para = para.strip()
            # Xử lý nhanh nếu toàn bộ đoạn văn là bảng hệ thống / chú thích
            if (stripped_para.startswith(('【', '[')) and stripped_para.endswith(('】', ']'))) or any(p.match(stripped_para) for p in self.SYSTEM_PATTERNS):
                node_counter += 1
                nodes.append(
                    ASTNode(
                        node_id=f"{chapter_id}_n{node_counter:04d}",
                        discourse_type=DiscourseType.SYSTEM_LORE,
                        source_text=stripped_para,
                        normalized_text=stripped_para,
                        speaker_id="SYSTEM",
                        confidence=1.0,
                    )
                )
                continue

            edus = self._segment_into_edus(para)
            classified_spans = self._classify_edus_with_isolation(edus)

            for dtype, span_edus, speaker in classified_spans:
                node_counter += 1
                combined_raw = "".join(e.raw_text for e in span_edus)
                normalized = self._normalize_node_punctuation(combined_raw, dtype)
                nodes.append(
                    ASTNode(
                        node_id=f"{chapter_id}_n{node_counter:04d}",
                        discourse_type=dtype,
                        source_text=combined_raw,
                        normalized_text=normalized,
                        speaker_id=speaker,
                        confidence=0.98 if span_edus[0].has_explicit_quote else 0.92,
                        edus=span_edus,
                    )
                )

        return SemanticASTDocument(
            chapter_id=chapter_id,
            nodes=nodes,
            raw_checksum=checksum,
        )

    def _segment_into_edus(self, paragraph: str) -> List[EDU]:
        """
        Tách đoạn văn thành các EDU dựa trên cả dấu câu lẫn ranh giới ngữ pháp
        của động từ phát ngôn/nhận thức (hoạt động cả khi mất hết dấu ngoặc kép).
        """
        marked_text = paragraph

        # Tách sơ bộ theo các dấu ngắt mệnh đề tiếng Trung
        raw_clauses = re.split(r"(?<=[，。！？；：、…])", marked_text)
        edus: List[EDU] = []
        cursor = 0
        edu_idx = 0

        for clause in raw_clauses:
            if not clause:
                continue

            # Kiểm tra xem trong mệnh đề có chứa cụm dẫn thoại/nội tâm không
            match = self._speech_intro_regex.search(clause)
            if match and match.end() < len(clause):
                # Tách phần dẫn thoại (Trần thuật) và phần nội dung thoại phía sau
                intro_part = clause[: match.end()]
                content_part = clause[match.end() :]

                speaker_hint = self._clean_speaker_hint(match.group("speaker"))
                verb = match.group("verb")

                edu_idx += 1
                edus.append(
                    EDU(
                        edu_id=f"edu_{edu_idx}",
                        raw_text=intro_part,
                        char_start=cursor,
                        char_end=cursor + len(intro_part),
                        detected_speech_verb=verb,
                        detected_speaker_hint=speaker_hint,
                    )
                )
                cursor += len(intro_part)

                edu_idx += 1
                edus.append(
                    self._build_content_edu(
                        edu_idx, content_part, cursor, speaker_hint
                    )
                )
                cursor += len(content_part)
            else:
                edu_idx += 1
                speaker_hint = None
                verb = None
                if match:
                    speaker_hint = self._clean_speaker_hint(match.group("speaker"))
                    verb = match.group("verb")
                edu = self._build_content_edu(edu_idx, clause, cursor, speaker_hint)
                if verb:
                    edu = EDU(
                        edu_id=edu.edu_id,
                        raw_text=edu.raw_text,
                        char_start=edu.char_start,
                        char_end=edu.char_end,
                        has_explicit_quote=edu.has_explicit_quote,
                        detected_speech_verb=verb,
                        detected_speaker_hint=speaker_hint,
                        deictic_markers=edu.deictic_markers,
                    )
                edus.append(edu)
                cursor += len(clause)

        return edus

    def _build_content_edu(
        self, idx: int, text: str, start: int, speaker_hint: Optional[str]
    ) -> EDU:
        has_quote = any(q in text for q in ('"', "“", "”", "「", "」", "『", "』"))
        markers = tuple(m for m in self.DEICTIC_FID_MARKERS if m in text)
        return EDU(
            edu_id=f"edu_{idx}",
            raw_text=text,
            char_start=start,
            char_end=start + len(text),
            has_explicit_quote=has_quote,
            detected_speaker_hint=speaker_hint,
            deictic_markers=markers,
        )

    def _classify_edus_with_isolation(
        self, edus: List[EDU]
    ) -> List[Tuple[DiscourseType, List[EDU], Optional[str]]]:
        """
        Phân loại từng EDU độc lập (Node-Level Isolation).
        Trạng thái của EDU chỉ kéo dài trong phạm vi mệnh đề phụ thuộc ngữ nghĩa,
        tự động ngắt khi gặp mệnh đề hành động khách quan mới.
        """
        if not edus:
            return []

        results: List[Tuple[DiscourseType, List[EDU], Optional[str]]] = []
        active_mode: DiscourseType = DiscourseType.NARRATION
        active_speaker: Optional[str] = None

        for i, edu in enumerate(edus):
            clean_txt = edu.raw_text.strip()

            # 1. Kiểm tra SYSTEM_LORE trước tiên
            if any(p.search(clean_txt) for p in self.SYSTEM_PATTERNS):
                results.append((DiscourseType.SYSTEM_LORE, [edu], "SYSTEM"))
                active_mode = DiscourseType.NARRATION
                active_speaker = None
                continue

            # 2. Nếu EDU là mệnh đề dẫn thoại hoặc dẫn nội tâm (chứa động từ phát ngôn ở cuối)
            if edu.detected_speech_verb:
                # Bản thân cụm "Hàn Lập trầm giọng nói:" là NARRATION
                results.append((DiscourseType.NARRATION, [edu], edu.detected_speaker_hint))
                if edu.detected_speech_verb in self.INTERNAL_COGNITION_VERBS:
                    active_mode = DiscourseType.FREE_INDIRECT_DISCOURSE
                else:
                    active_mode = DiscourseType.DIRECT_SPEECH
                active_speaker = edu.detected_speaker_hint
                continue

            # 3. Đánh giá độc lập nội dung của EDU hiện tại (Zero State-Bleed)
            has_speech_pronoun = any(p in clean_txt for p in self.SPEECH_ONLY_PRONOUNS)
            has_deictic_fid = len(edu.deictic_markers) > 0
            is_objective_action = self._is_objective_narrative_action(clean_txt)

            if is_objective_action and not has_speech_pronoun and not has_deictic_fid:
                # Ngắt ngay lập tức mọi trạng thái thoại/nội tâm trước đó
                dtype = DiscourseType.NARRATION
                speaker = None
                active_mode = DiscourseType.NARRATION
                active_speaker = None
            elif active_mode == DiscourseType.DIRECT_SPEECH and (
                has_speech_pronoun or not is_objective_action
            ):
                dtype = DiscourseType.DIRECT_SPEECH
                speaker = active_speaker
            elif active_mode == DiscourseType.FREE_INDIRECT_DISCOURSE or has_deictic_fid:
                dtype = DiscourseType.FREE_INDIRECT_DISCOURSE
                speaker = active_speaker
                active_mode = DiscourseType.FREE_INDIRECT_DISCOURSE
            elif has_speech_pronoun:
                # Dù không có động từ dẫn thoại, sự xuất hiện của "Lão phu / Bổn tọa / Các hạ"
                # chứng tỏ đây là lời thoại trực tiếp không ngoặc kép
                dtype = DiscourseType.DIRECT_SPEECH
                speaker = active_speaker
                active_mode = DiscourseType.DIRECT_SPEECH
            else:
                dtype = DiscourseType.NARRATION
                speaker = None
                active_mode = DiscourseType.NARRATION

            # Gộp các EDU liền kề có cùng DiscourseType và Speaker thành một ASTNode
            if results and results[-1][0] == dtype and results[-1][2] == speaker:
                results[-1][1].append(edu)
            else:
                results.append((dtype, [edu], speaker))

        return results

    def _is_objective_narrative_action(self, text: str) -> bool:
        """Nhận diện mệnh đề miêu tả hành động vật lý/cảnh vật khách quan."""
        narrative_patterns = (
            "转身", "抬起手", "看了一眼", "看着", "望向", "袖袍一甩", "剑光一闪",
            "轰隆", "刹那间", "四周", "空气中", "脚步", "身影", "目光落在",
        )
        return any(pat in text for pat in narrative_patterns)

    def _clean_speaker_hint(self, raw_speaker: str) -> str:
        # Loại bỏ các từ nối đầu câu để lấy đúng danh từ chỉ người nói
        cleaned = re.sub(r"^(?:只见|却见|闻言|此时|忽然|顿时|随后)", "", raw_speaker).strip()
        return cleaned or "UNKNOWN_SPEAKER"

    def _normalize_node_punctuation(self, text: str, dtype: DiscourseType) -> str:
        """Tự động khôi phục dấu câu chuẩn hóa cho nút AST."""
        stripped = re.sub(r"^[“\"「『]+|[”\"」』]+$", "", text.strip())
        if dtype == DiscourseType.DIRECT_SPEECH:
            return f"“{stripped}”"
        if dtype == DiscourseType.FREE_INDIRECT_DISCOURSE:
            return f"『{stripped}』"
        return stripped
