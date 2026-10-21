# native_oauth/core/graph/retroactive_tekg.py
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class EntityNode:
    entity_id: str
    canonical_name_zh: str
    canonical_name_vi: str
    gender: str = "UNKNOWN"  # MALE, FEMALE, NEUTRAL, UNKNOWN
    social_rank: str = "COMMON"  # ROYAL, ELDER, PEER, JUNIOR, SERVANT, COMMON
    aliases_zh: Set[str] = field(default_factory=set)
    first_seen_chapter: int = 1
    revealed_at_chapter: int = 1


@dataclass(frozen=True)
class PronounState:
    chapter_from: int
    chapter_to: int
    self_pronoun: str       # Xưng (VD: Bản cung, Trẫm, Ta, Thiếp)
    address_pronoun: str    # Hô (VD: Khanh, Ngươi, Chàng, Tiểu tử)
    third_person_ref: str   # Đại từ ngôi thứ 3 trong trần thuật (VD: nàng, bà ta, vị nữ đế kia)
    register_tone: str      # RESPECTFUL, HOSTILE, INTIMATE, MYSTERIOUS_NOBLE


@dataclass
class TemporalEdge:
    source_id: str
    target_id: str
    timeline_states: List[PronounState] = field(default_factory=list)

    def get_state_at(self, chapter_num: int) -> Optional[PronounState]:
        for state in reversed(self.timeline_states):
            if state.chapter_from <= chapter_num <= state.chapter_to:
                return state
        return self.timeline_states[-1] if self.timeline_states else None


@dataclass
class StandoffAnnotation:
    annotation_id: str
    chapter_num: int
    node_id: str
    source_entity_id: str
    target_entity_id: str
    role: str  # "THIRD_PERSON", "SELF", "ADDRESS"
    surface_text: str


class RetroactiveTEKG:
    """
    Đồ thị Tri thức Thời gian Đa chiều Hồi tố 2 Pha (Two-Pass Retroactive TEKG).
    Giải quyết triệt để Khởi động nguội và Lệch pha đại từ xuyên 1.000 chương.
    """

    STANDOFF_PATTERN = re.compile(
        r"\[\[PRON:(?P<src>[a-zA-Z0-9_]+)->(?P<dst>[a-zA-Z0-9_]+)\|role:(?P<role>[A-Z_]+)\]\]"
        r"(?P<surface>.+?)"
        r"\[\[/PRON\]\]"
    )

    def __init__(self) -> None:
        self.entities: Dict[str, EntityNode] = {}
        self.alias_to_id: Dict[str, str] = {}
        self.edges: Dict[Tuple[str, str], TemporalEdge] = {}
        self.chapter_store: Dict[int, str] = {}
        self.standoff_index: Dict[str, List[StandoffAnnotation]] = {}

    def register_entity(self, node: EntityNode) -> None:
        self.entities[node.entity_id] = node
        self.alias_to_id[node.canonical_name_zh] = node.entity_id
        for alias in node.aliases_zh:
            self.alias_to_id[alias] = node.entity_id

    def run_phase1_lookahead_scan(self, raw_chapters: Dict[int, str]) -> None:
        """
        Pha 1: Quét trước 10-20 chương để phát hiện danh tính thật, giới tính thật
        và hợp nhất bí danh (Alias Convergence) trước khi dịch Chương 1.
        """
        reveal_regex = re.compile(
            r"(?:那|这)?(?P<alias>黑衣人|神秘人|灰袍人|那人|老者).*?"
            r"(?:竟是|正是|居然是|乃|便是)(?P<reveal_text>[^\s，。！？]{2,25})"
        )

        for chap_num in sorted(raw_chapters.keys()):
            text = raw_chapters[chap_num]
            for match in reveal_regex.finditer(text):
                alias = match.group("alias")
                reveal_text = match.group("reveal_text")

                gender = "UNKNOWN"
                rank = "COMMON"
                if any(f in reveal_text for f in ("女帝", "仙子", "圣女", "女子", "妇人", "娘娘", "公主", "女")):
                    gender = "FEMALE"
                elif any(m in reveal_text for m in ("老祖", "大汉", "青年", "少侠", "魔尊", "男")):
                    gender = "MALE"

                if any(r in reveal_text for r in ("女帝", "陛下", "皇", "老祖", "圣女", "宗主")):
                    rank = "ROYAL"

                cleaned_name = re.sub(r"^(?:.*?)(?:女帝|宗主|圣女|老祖|魔尊|仙子|陛下)", "", reveal_text).strip()
                real_name = cleaned_name if 2 <= len(cleaned_name) <= 4 else reveal_text[-3:]

                ent_id = self.alias_to_id.get(real_name) or f"ent_{len(self.entities) + 1:03d}"
                if ent_id not in self.entities:
                    ent = EntityNode(
                        entity_id=ent_id,
                        canonical_name_zh=real_name,
                        canonical_name_vi=real_name,
                        gender=gender,
                        social_rank=rank,
                        aliases_zh={alias, real_name},
                        first_seen_chapter=1,
                        revealed_at_chapter=chap_num,
                    )
                    self.register_entity(ent)
                else:
                    existing = self.entities[ent_id]
                    existing.aliases_zh.add(alias)
                    if gender != "UNKNOWN":
                        existing.gender = gender
                    if rank != "COMMON":
                        existing.social_rank = rank
                    self.alias_to_id[alias] = ent_id

                # Tự động thiết lập trạng thái đại từ hồi tố về Chương 1
                self._compute_retroactive_pronoun_edge(ent_id, chap_num)

    def _compute_retroactive_pronoun_edge(self, ent_id: str, reveal_chap: int) -> None:
        ent = self.entities[ent_id]
        if ent.gender == "FEMALE" and ent.social_rank == "ROYAL":
            # Trước khi lộ diện (Ch 1 -> reveal_chap - 1): Giữ nét bí ẩn nhưng đúng giới tính nữ quý phái
            pre_state = PronounState(
                chapter_from=1,
                chapter_to=max(1, reveal_chap - 1),
                self_pronoun="Bổn tọa",
                address_pronoun="Ngươi",
                third_person_ref="nàng",
                register_tone="MYSTERIOUS_NOBLE",
            )
            # Sau khi lộ diện Nữ Đế: Chuyển sang Bản đế / Trẫm
            post_state = PronounState(
                chapter_from=reveal_chap,
                chapter_to=9999,
                self_pronoun="Bản đế",
                address_pronoun="Khanh",
                third_person_ref="Nữ đế",
                register_tone="ROYAL_SUPREME",
            )
            edge_key = (ent_id, "NARRATOR")
            self.edges[edge_key] = TemporalEdge(
                source_id=ent_id,
                target_id="NARRATOR",
                timeline_states=[pre_state, post_state],
            )

    def resolve_pronoun(
        self, mention_zh: str, target_id: str, chapter_num: int, role: str = "THIRD_PERSON"
    ) -> Tuple[str, str]:
        """
        Trả về (entity_id, đại_từ_chuẩn) tại chương `chapter_num` dựa trên đồ thị đã hội tụ.
        """
        ent_id = self.alias_to_id.get(mention_zh, mention_zh)
        edge = self.edges.get((ent_id, target_id)) or self.edges.get((ent_id, "NARRATOR"))
        if not edge:
            return ent_id, "người đó"

        state = edge.get_state_at(chapter_num)
        if not state:
            return ent_id, "người đó"

        if role == "SELF":
            return ent_id, state.self_pronoun
        if role == "ADDRESS":
            return ent_id, state.address_pronoun
        return ent_id, state.third_person_ref

    def bind_standoff_tag(
        self, src_id: str, dst_id: str, role: str, surface: str
    ) -> str:
        """Bọc đại từ trong thẻ Standoff để sẵn sàng cho việc vá hồi tố xuyên 1.000 chương."""
        return f"[[PRON:{src_id}->{dst_id}|role:{role}]]{surface}[[/PRON]]"

    def store_translated_chapter(self, chapter_num: int, annotated_text: str) -> None:
        self.chapter_store[chapter_num] = annotated_text
        for match in self.STANDOFF_PATTERN.finditer(annotated_text):
            src_id = match.group("src")
            dst_id = match.group("dst")
            role = match.group("role")
            surface = match.group("surface")
            key = f"{src_id}->{dst_id}"
            self.standoff_index.setdefault(key, []).append(
                StandoffAnnotation(
                    annotation_id=f"ann_c{chapter_num}_{match.start()}",
                    chapter_num=chapter_num,
                    node_id=f"c{chapter_num}",
                    source_entity_id=src_id,
                    target_entity_id=dst_id,
                    role=role,
                    surface_text=surface,
                )
            )

    def retroactive_realign(
        self,
        src_id: str,
        dst_id: str,
        new_state: PronounState,
    ) -> List[int]:
        """
        Cập nhật lại đại từ nhân xưng xuyên suốt dải chương [chapter_from..chapter_to]
        bằng kỹ thuật Micro-Span Re-rendering mà không ảnh hưởng tới bất kỳ câu văn nào khác.
        """
        edge_key = (src_id, dst_id)
        if edge_key not in self.edges:
            self.edges[edge_key] = TemporalEdge(source_id=src_id, target_id=dst_id)
        self.edges[edge_key].timeline_states.append(new_state)

        modified_chapters: List[int] = []
        for chap_num, text in list(self.chapter_store.items()):
            if not (new_state.chapter_from <= chap_num <= new_state.chapter_to):
                continue

            def _replacer(m: re.Match) -> str:
                if m.group("src") == src_id and m.group("dst") == dst_id:
                    role = m.group("role")
                    if role == "SELF":
                        new_surface = new_state.self_pronoun
                    elif role == "ADDRESS":
                        new_surface = new_state.address_pronoun
                    else:
                        new_surface = new_state.third_person_ref
                    return self.bind_standoff_tag(src_id, dst_id, role, new_surface)
                return m.group(0)

            updated_text = self.STANDOFF_PATTERN.sub(_replacer, text)
            if updated_text != text:
                self.chapter_store[chap_num] = updated_text
                modified_chapters.append(chap_num)

        return modified_chapters

    def strip_standoff_for_publication(self, chapter_num: int) -> str:
        """Gỡ bỏ thẻ Standoff ẩn để xuất bản văn bản sạch tuyệt đối cho độc giả."""
        raw = self.chapter_store.get(chapter_num, "")
        return self.STANDOFF_PATTERN.sub(r"\g<surface>", raw)
