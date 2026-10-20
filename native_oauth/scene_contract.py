"""Scene Contract Schema & Pipe-DSL Serializer / Parser for CaoTruyen.
Implements Module 1 BNS Literary Engine specifications from Gemini 4 Argon.
"""

from __future__ import annotations
import re
from typing import List, Dict, Optional, Tuple, Any
from dataclasses import dataclass, field

@dataclass
class EntityRecord:
    zh: str
    vi: str
    gender: str          # M, F, N
    narr_lock: str       # hắn, y, gã, lão, nàng, ả, nó
    realm_title: str
    archetype: str

@dataclass
class PronounRule:
    src_zh: str
    dst_zh: str
    state: str           # DEFAULT, COURTEOUS, HOSTILE, HOSTILE_SHIFT, INTIMATE, PUBLIC
    self_vi: str
    target_vi: str
    tone: str

@dataclass
class HardMetric:
    tag_id: str          # M1, M2...
    raw_zh: str
    locked_vi: str

@dataclass
class IdiomHint:
    tag_id: str          # I1, I2...
    raw_zh: str
    suggestions: str
    forbidden: str

@dataclass
class SceneContract:
    chap_id: int
    scene_id: int
    route_tier: str      # LOW, MED, HIGH
    genre: str           # XIANXIA, XUANHUAN, WUXIA, URBAN
    pacing: str          # COMBAT_FAST, AURA_MAJESTIC, DIALOGUE_TENSE, EXPOSITION_SMOOTH
    location_vi: str
    mood: str
    active_effect: str
    prev_vi: str
    last_actor_vi: str
    spatial_vec: str
    entities: List[EntityRecord] = field(default_factory=list)
    pronouns: List[PronounRule] = field(default_factory=list)
    anchor_quotes: List[Tuple[str, str, str]] = field(default_factory=list)  # (ent_zh, voice_tag, sample_vi)
    hard_metrics: List[HardMetric] = field(default_factory=list)
    glossary: Dict[str, Tuple[str, str]] = field(default_factory=dict)       # zh: (vi, category)
    idiom_hints: List[IdiomHint] = field(default_factory=list)
    arc_capsule: Optional[str] = None
    pending_omens: List[dict] = field(default_factory=list)

    def to_pipe_dsl(self) -> str:
        """Biên dịch SceneContract thành chuỗi Pipe-DSL siêu nén gửi vào Gemini 3.8 Flash."""
        lines = [
            "=== SCENE_CONTRACT_V1 ===",
            f"@META|chap:{self.chap_id:04d}|scene:{self.scene_id:02d}|route:{self.route_tier}|genre:{self.genre}",
        ]
        if self.arc_capsule:
            lines.append(f"@ARC_CAPSULE|summary={self.arc_capsule}")

        lines.extend([
            f"@PLOT_STATE|pacing={self.pacing}|loc={self.location_vi}|mood={self.mood}|active={self.active_effect}",
            "@MICRO_SEAM",
            f"PREV_VI|{self.prev_vi}",
            f"SEAM_VEC|last_actor={self.last_actor_vi}|spatial={self.spatial_vec}",
            "@ENTITIES"
        ])
        for e in self.entities:
            lines.append(f"{e.zh}|{e.vi}|{e.gender}|{e.narr_lock}|{e.realm_title}|{e.archetype}")

        lines.append("@PRONOUN_MATRIX")
        for p in self.pronouns:
            lines.append(f"{p.src_zh}->{p.dst_zh}|{p.state}|{p.self_vi}|{p.target_vi}|{p.tone}")

        if self.anchor_quotes:
            lines.append("@ANCHOR_QUOTES")
            for ent_zh, style_tag, quote_vi in self.anchor_quotes:
                lines.append(f"{ent_zh}|{style_tag}|\"{quote_vi}\"")

        if self.hard_metrics:
            lines.append("@HARD_METRICS")
            for m in self.hard_metrics:
                lines.append(f"{m.tag_id}|{m.raw_zh}|{m.locked_vi}")

        if self.glossary:
            lines.append("@GLOSSARY")
            for zh, (vi, cat) in self.glossary.items():
                lines.append(f"{zh}={vi}|{cat}")

        if self.idiom_hints:
            lines.append("@IDIOM_HINTS")
            for i in self.idiom_hints:
                lines.append(f"{i.tag_id}|{i.raw_zh}|{i.suggestions}|FORBID:{i.forbidden}")

        if self.pending_omens:
            lines.append("@PENDING_OMENS")
            for om in self.pending_omens:
                omen_id = om.get("omen_id", "O1")
                target = om.get("target_vi", "")
                from_c = om.get("source_chap", 0)
                phrasing = om.get("locked_phrasing_vi", "")
                echos = om.get("echo_keywords_vi", "")
                lines.append(f"{omen_id}|target={target}|from_chap={from_c}|phrasing=\"{phrasing}\"|ECHO_KEYS:{echos}")

        lines.append("=== END_CONTRACT ===")
        return "\n".join(lines)

    @classmethod
    def from_pipe_dsl(cls, dsl_text: str) -> "SceneContract":
        """Parse chuỗi Pipe-DSL thành đối tượng SceneContract."""
        chap_id = 1
        scene_id = 1
        route_tier = "MED"
        genre = "XIANXIA"
        pacing = "COMBAT_FAST"
        loc_vi = ""
        mood = ""
        active_effect = ""
        prev_vi = ""
        last_actor_vi = ""
        spatial_vec = ""
        arc_capsule: Optional[str] = None

        entities: List[EntityRecord] = []
        pronouns: List[PronounRule] = []
        anchor_quotes: List[Tuple[str, str, str]] = []
        hard_metrics: List[HardMetric] = []
        glossary: Dict[str, Tuple[str, str]] = {}
        idiom_hints: List[IdiomHint] = []
        pending_omens: List[dict] = []

        current_block = ""
        for raw_line in dsl_text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            if line.startswith("==="):
                continue
            if line.startswith("@"):
                # Header block line
                parts = line.split("|")
                header_name = parts[0]
                current_block = header_name

                if header_name == "@META":
                    for p in parts[1:]:
                        k, v = p.split(":", 1)
                        if k == "chap":
                            chap_id = int(v)
                        elif k == "scene":
                            scene_id = int(v)
                        elif k == "route":
                            route_tier = v
                        elif k == "genre":
                            genre = v
                elif header_name == "@ARC_CAPSULE":
                    for p in parts[1:]:
                        if "=" in p:
                            k, v = p.split("=", 1)
                            if k == "summary":
                                arc_capsule = v
                elif header_name == "@PLOT_STATE":
                    for p in parts[1:]:
                        if "=" in p:
                            k, v = p.split("=", 1)
                            if k == "pacing":
                                pacing = v
                            elif k == "loc":
                                loc_vi = v
                            elif k == "mood":
                                mood = v
                            elif k == "active":
                                active_effect = v
                continue

            # Within blocks
            if current_block == "@MICRO_SEAM":
                if line.startswith("PREV_VI|"):
                    prev_vi = line.split("|", 1)[1]
                elif line.startswith("SEAM_VEC|"):
                    vec_parts = line.split("|")[1:]
                    for vp in vec_parts:
                        if "=" in vp:
                            vk, vv = vp.split("=", 1)
                            if vk == "last_actor":
                                last_actor_vi = vv
                            elif vk == "spatial":
                                spatial_vec = vv
            elif current_block == "@ENTITIES":
                parts = line.split("|")
                if len(parts) >= 6:
                    entities.append(EntityRecord(
                        zh=parts[0], vi=parts[1], gender=parts[2],
                        narr_lock=parts[3], realm_title=parts[4], archetype=parts[5]
                    ))
            elif current_block == "@PRONOUN_MATRIX":
                parts = line.split("|")
                if len(parts) >= 5:
                    src_dst = parts[0].split("->")
                    src_zh = src_dst[0].strip()
                    dst_zh = src_dst[1].strip() if len(src_dst) > 1 else ""
                    pronouns.append(PronounRule(
                        src_zh=src_zh, dst_zh=dst_zh, state=parts[1],
                        self_vi=parts[2], target_vi=parts[3], tone=parts[4]
                    ))
            elif current_block == "@ANCHOR_QUOTES":
                parts = line.split("|")
                if len(parts) >= 3:
                    ent_zh = parts[0]
                    style_tag = parts[1]
                    quote_text = parts[2].strip('"')
                    anchor_quotes.append((ent_zh, style_tag, quote_text))
            elif current_block == "@HARD_METRICS":
                parts = line.split("|")
                if len(parts) >= 3:
                    hard_metrics.append(HardMetric(
                        tag_id=parts[0], raw_zh=parts[1], locked_vi=parts[2]
                    ))
            elif current_block == "@GLOSSARY":
                parts = line.split("|")
                if len(parts) >= 2:
                    zh_vi = parts[0].split("=")
                    if len(zh_vi) == 2:
                        glossary[zh_vi[0].strip()] = (zh_vi[1].strip(), parts[1].strip())
            elif current_block == "@IDIOM_HINTS":
                parts = line.split("|")
                if len(parts) >= 4:
                    tag_id = parts[0]
                    raw_zh = parts[1]
                    sugg = parts[2]
                    forbid = parts[3].replace("FORBID:", "").strip()
                    idiom_hints.append(IdiomHint(
                        tag_id=tag_id, raw_zh=raw_zh, suggestions=sugg, forbidden=forbid
                    ))
            elif current_block == "@PENDING_OMENS":
                parts = line.split("|")
                if parts:
                    omen_id = parts[0]
                    target_vi = ""
                    source_chap = 0
                    phrasing = ""
                    echos = ""
                    for p in parts[1:]:
                        if p.startswith("target="): target_vi = p.split("=", 1)[1]
                        elif p.startswith("from_chap="):
                            try: source_chap = int(p.split("=", 1)[1])
                            except: pass
                        elif p.startswith("phrasing="): phrasing = p.split("=", 1)[1].strip('"')
                        elif p.startswith("ECHO_KEYS:"): echos = p.split(":", 1)[1]
                    pending_omens.append({
                        "omen_id": omen_id, "target_vi": target_vi,
                        "source_chap": source_chap, "locked_phrasing_vi": phrasing,
                        "echo_keywords_vi": echos
                    })

        return cls(
            chap_id=chap_id,
            scene_id=scene_id,
            route_tier=route_tier,
            genre=genre,
            pacing=pacing,
            location_vi=loc_vi,
            mood=mood,
            active_effect=active_effect,
            prev_vi=prev_vi,
            last_actor_vi=last_actor_vi,
            spatial_vec=spatial_vec,
            entities=entities,
            pronouns=pronouns,
            anchor_quotes=anchor_quotes,
            hard_metrics=hard_metrics,
            glossary=glossary,
            idiom_hints=idiom_hints,
            arc_capsule=arc_capsule,
            pending_omens=pending_omens,
        )


DELTA_BLOCK_RE = re.compile(r"<delta>(.*?)</delta>", re.DOTALL | re.IGNORECASE)
PARAGRAPH_RE = re.compile(r"^§(\d+)\s+(.+)$", re.MULTILINE)

def parse_worker_output(raw_llm_output: str) -> Tuple[Dict[int, str], List[Dict[str, Any]]]:
    """
    Tách bản dịch theo từng đoạn §1..§N và bóc tách khối <delta> (nếu có)
    để cập nhật ngược vào SQLite Story Store.
    """
    deltas: List[Dict[str, Any]] = []
    delta_match = DELTA_BLOCK_RE.search(raw_llm_output)
    clean_text = raw_llm_output
    if delta_match:
        delta_content = delta_match.group(1).strip()
        clean_text = raw_llm_output[:delta_match.start()].strip()
        for line in delta_content.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if parts[0] == "NEW_ENT" and len(parts) >= 6:
                deltas.append({
                    "type": "NEW_ENT",
                    "zh": parts[1], "vi": parts[2], "gender": parts[3],
                    "narr_lock": parts[4], "role": parts[5]
                })
            elif parts[0] == "REL_SHIFT" and len(parts) >= 6:
                src_dst = parts[1].split("->")
                src_zh = src_dst[0].strip()
                dst_zh = src_dst[1].strip() if len(src_dst) > 1 else ""
                deltas.append({
                    "type": "REL_SHIFT",
                    "src_zh": src_zh, "dst_zh": dst_zh,
                    "state": parts[2], "self_vi": parts[3],
                    "target_vi": parts[4], "reason": parts[5]
                })

    paragraphs: Dict[int, str] = {}
    for match in PARAGRAPH_RE.finditer(clean_text):
        p_idx = int(match.group(1))
        paragraphs[p_idx] = match.group(2).strip()

    return paragraphs, deltas
