# -*- coding: utf-8 -*-
"""Source-first, advisory preprocessing for bounded translation scenes.

Complexity, rhythm, numeric and idiom hints are heuristic. Dialogue routing
recognizes only explicit local constructions and abstains otherwise. No semantic
roles or permanent relationships are inferred from entity order or sentiment.
"""

from __future__ import annotations
import math
import re
import sqlite3
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple

from native_oauth.numeric_lock import DeterministicNumericExtractor
from native_oauth.semantic_context import dialogue_cues, scoped_rules, entity_aliases
from native_oauth.meaning_anchors import source_anchors
from native_oauth.scene_contract import (
    EntityRecord,
    PronounRule,
    HardMetric,
    IdiomHint,
    SceneContract,
)

# ===========================================================================
# 1. TỪ ĐIỂN VĂN NGÔN, THÀNH NGỮ & DẤU HIỆU NGỮ DỤNG
# ===========================================================================

IDIOM_HINTS_DEFAULT: Dict[str, Tuple[str, str]] = {
    # raw_zh: (BNS suggestions, forbidden convert phrase)
    "不以為然": ("không tán đồng / không cho là phải; đối chiếu thái độ trong nguồn", ""),
    "不以为然": ("không tán đồng / không cho là phải; đối chiếu thái độ trong nguồn", ""),
    "不以為意": ("chẳng chút bận tâm / không để trong lòng / bỏ ngoài tai", "không cho là ý"),
    "不以为意": ("chẳng chút bận tâm / không để trong lòng / bỏ ngoài tai", "không cho là ý"),
    "色厲內荏": ("ngoài mạnh trong yếu / miệng hùm gan sứa", "sắc lệ nội nhẫn"),
    "色厉内荏": ("ngoài mạnh trong yếu / miệng hùm gan sứa", "sắc lệ nội nhẫn"),
    "差強人意": ("cũng tàm tạm chấp nhận được / coi như tạm ổn", "kém cỏi làm người không vừa ý"),
    "差强人意": ("cũng tàm tạm chấp nhận được / coi như tạm ổn", "kém cỏi làm người không vừa ý"),
    "不足為道": ("chẳng đáng nhắc tới / nhỏ nhặt không đáng kể", "không đủ vì đạo"),
    "不足为道": ("chẳng đáng nhắc tới / nhỏ nhặt không đáng kể", "không đủ vì đạo"),
    "微不足道": ("nhỏ bé không đáng kể / không bõ bèn gì", "vi bất túc đạo"),
    "見獵心喜": ("ngứa nghề nổi hứng / thấy mồi ngon mà lòng khấp khởi", "thấy săn lòng vui"),
    "见猎心喜": ("ngứa nghề nổi hứng / thấy mồi ngon mà lòng khấp khởi", "thấy săn lòng vui"),
    "風光霽月": ("phong thái quang minh lỗi lạc / như trăng thanh gió mát", "phong quang tễ nguyệt"),
    "风光霁月": ("phong thái quang minh lỗi lạc / như trăng thanh gió mát", "phong quang tễ nguyệt"),
    "敬酒不吃吃罰酒": ("rượu mời không uống lại muốn uống rượu phạt", "kính tửu bất ngật ngật phạt tửu"),
    "敬酒不吃吃罚酒": ("rượu mời không uống lại muốn uống rượu phạt", "kính tửu bất ngật ngật phạt tửu"),
    "殺人奪寶": ("giết người đoạt bảo", "sát nhân đoạt bảo"),
    "杀人夺宝": ("giết người đoạt bảo", "sát nhân đoạt bảo"),
    "斬草除根": ("nhổ cỏ tận gốc", "trảm thảo trừ căn"),
    "斩草除根": ("nhổ cỏ tận gốc", "trảm thảo trừ căn"),
    "魂飛魄散": ("hồn phi phách tán / sợ đến vỡ mật; phân biệt hồn phách tan thật với nghĩa bóng", ""),
    "魂飞魄散": ("hồn phi phách tán / sợ đến vỡ mật; phân biệt hồn phách tan thật với nghĩa bóng", ""),
    "灰飛煙滅": ("tan thành mây khói / hóa thành tro bụi", "hôi phi yên diệt"),
    "灰飞烟灭": ("tan thành mây khói / hóa thành tro bụi", "hôi phi yên diệt"),
    "不是個東西": ("thứ không ra gì / đồ khốn nạn", "không phải là cái đông tây"),
    "不是个东西": ("thứ không ra gì / đồ khốn nạn", "không phải là cái đông tây"),
    "見怪不怪": ("chuyện thường ngày ở huyện / thấy mãi thành quen", "thấy quái không quái"),
    "见怪不怪": ("chuyện thường ngày ở huyện / thấy mãi thành quen", "thấy quái không quái"),
    "狗眼看人低": ("mắt chó nhìn người thấp / khinh người ra mặt", "cẩu nhãn khán nhân đê"),
    "打臉": ("vả mặt bôm bốp / tự vả", "đả kiểm"),
    "打脸": ("vả mặt bôm bốp / tự vả", "đả kiểm"),
    "翻車": ("lật xe / bể mánh / toang", "phiên xa"),
    "翻车": ("lật xe / bể mánh / toang", "phiên xa"),
    "帶節奏": ("dắt mũi dư luận / kích động chia rẽ", "đới tiết tấu"),
    "带节奏": ("dắt mũi dư luận / kích động chia rẽ", "đới tiết tấu"),
    "老實人": ("người thật thà chất phác / kẻ chịu trận", "lão thực nhân"),
    "老实人": ("người thật thà chất phác / kẻ chịu trận", "lão thực nhân"),
    "連麥": ("nối máy / kết nối mic / gọi video", "liên mạch"),
    "连麦": ("nối máy / kết nối mic / gọi video", "liên mạch"),
}

WENYAN_PARTICLES: Set[str] = {
    "之", "乎", "者", "也", "矣", "焉", "哉", "其", "乃", "遂",
    "豈", "岂", "莫", "勿", "毋", "何以", "未嘗", "未尝", "不亦", "而已", "耳",
}

REACTIVE_PATIENT_MARKERS: Tuple[str, ...] = (
    "吐血", "噴出", "喷出", "鮮血", "鲜血", "逆血", "倒飛", "倒飞", "暴退", "連退", "连退",
    "跌落", "砸落", "悶哼", "闷哼", "慘叫", "惨叫", "哀嚎", "痛呼", "身軀一震", "身躯一震",
    "渾身一顫", "浑身一颤", "虎口發麻", "虎口发麻", "氣血翻湧", "气血翻涌", "氣血一陣翻湧", "气血一阵翻涌",
    "臉色大變", "脸色大变", "面色劇變", "面色剧变", "面色一白", "臉色微白", "脸色微白", "臉色微微一白", "脸色微微一白",
    "臉色蒼白", "脸色苍白", "駭然", "骇然", "大驚", "大惊", "驚駭", "惊骇", "心驚", "心惊",
    "不敢怠慢", "慌忙", "急忙", "倉促", "仓促", "招架", "抵擋", "抵挡", "避開", "避开", "閃避", "闪避",
    "重傷", "重伤", "隕落", "陨落", "倒地", "昏死", "氣息萎靡", "气息萎靡", "寸寸碎裂", "崩潰", "崩溃",
)

PIVOT_DISCOURSE_MARKERS: Tuple[str, ...] = (
    "頓時", "顿时", "剎那間", "刹那间", "頃刻間", "顷刻间", "轟的一聲", "轰的一声", "轟隆", "轰隆",
    "只聽", "只听", "只見", "只见", "卻見", "却见", "陡然", "猛然", "突然", "忽然",
    "緊接著", "紧接着", "下一刻", "便在此時", "便在此时", "就在這時", "就在这时", "一聲巨響", "一声巨响",
)

SPEECH_VERBS: Set[str] = {
    "道", "說", "说", "說道", "说道", "問", "问", "問道", "问道", "答", "答道",
    "喝", "喝道", "吼", "怒吼", "叱", "叱道", "笑", "笑道", "冷笑", "大笑",
    "獰笑", "狞笑", "苦笑", "微笑", "嗤笑", "哼", "冷哼", "嘆", "叹", "嘆道", "叹道",
    "傳音", "传音", "開口", "开口", "沉聲", "沉声", "厲聲", "厉声", "寒聲", "寒声",
    "喃喃", "自語", "自语", "低語", "低语", "喝問", "喝问", "質問", "质问", "恭聲", "恭声",
}

LISTENER_PREPOSITIONS: Set[str] = {"對", "对", "向", "朝", "朝著", "朝着", "衝", "冲", "望著", "望着", "看著", "看着"}

HOSTILE_MANNER_MARKERS: Tuple[str, ...] = (
    "冷笑", "獰笑", "狞笑", "嗤笑", "譏諷", "讥讽", "嘲諷", "嘲讽", "森然", "殺機", "杀机", "殺意", "杀意",
    "臉色一沉", "脸色一沉", "面色一寒", "面色鐵青", "面色铁青", "寒聲", "寒声", "厲聲", "厉声", "厲喝", "厉喝", "怒喝",
    "暴喝", "冷哼", "拂袖", "眼中寒芒", "眸中殺機", "眸中杀机", "聲音冰冷", "声音冰冷", "語氣森寒", "语气森寒",
)

HOSTILE_QUOTE_LEXICON: Tuple[str, ...] = (
    "找死", "敬酒不吃吃罰酒", "敬酒不吃吃罚酒", "老狗", "老匹夫", "小畜生", "小雜種", "小杂种",
    "豎子", "竖子", "小輩", "小辈", "滾", "滚", "納命來", "纳命来", "受死", "休怪",
    "不知死活", "不知天高地厚", "癡心妄想", "痴心妄想", "憑你也配", "凭你也配",
    "自尋死路", "自寻死路", "留你不得", "送你上路", "狂妄",
)

COMBAT_LEXICON: Set[str] = {
    "斬", "斩", "殺", "杀", "轟", "轰", "刺", "劈", "掠", "爆", "碎", "破", "砸", "射", "遁",
    "祭出", "掐訣", "掐诀", "催動", "催动", "劍光", "剑光", "刀芒", "法寶", "法宝", "神通", "飛劍", "飞剑",
    "倒飛", "倒飞", "吐血", "罡風", "罡风", "雷霆", "血霧", "血雾", "一拳", "一掌", "一劍", "一剑",
}

AURA_LEXICON: Set[str] = {
    "威壓", "威压", "天地", "法相", "蒼穹", "苍穹", "大道", "浩瀚", "神識", "神识", "靈氣", "灵气",
    "道韻", "道韵", "法則", "法则", "虛空", "虚空", "萬古", "万古", "滄桑", "沧桑", "金丹", "元嬰", "元婴",
    "化神", "天劫", "異象", "异象", "紫氣", "紫气", "仙音",
}

# ===========================================================================
# 1.1 PHÂN TÁCH TAM TRÙNG KHÔNG GIAN & NHÂN THÂN KHÁCH (URBAN / LIVESTREAM)
# ===========================================================================

def detect_spatial_plane(text: str) -> str:
    """Xác định mặt phẳng không gian trong ngữ cảnh Đô thị / Livestream: HOST | GUEST | CHAT | AMBIENT."""
    if any(m in text for m in ["弹幕", "水友", "公屏", "刷屏", "礼物", "打赏", "火箭", "房管", "【", "】"]):
        return "PLANE:CHAT"
    if any(m in text for m in ["连麦", "屏幕对面", "镜头对面", "对面那头", "视频中", "视频那头", "那头"]):
        return "PLANE:GUEST"
    return "PLANE:HOST"


def resolve_guest_persona(context_text: str) -> Tuple[str, str, str]:
    """Suy luận vai vế nhân thân của khách nối máy để định hướng đại từ tiếng Việt.
    Returns: (self_vi, guest_vi, tone)
    """
    # Elderly markers
    if any(m in context_text for m in ["大爷", "老人家", "老爷爷", "老太", "老奶奶", "年过六旬", "花白"]):
        return ("cháu", "ông / bà", "kính trọng, lễ phép")
    # Middle-aged markers
    if any(m in context_text for m in ["大叔", "阿姨", "大姐", "大婶", "中年男子", "妇女"]):
        return ("cháu / tôi", "chú / bác / cô", "lịch sự, hòa nhã")
    # Young female
    if any(m in context_text for m in ["小姑娘", "女大学生", "妹子", "学妹", "少女"]):
        return ("tôi", "cô / bạn", "ôn hòa, điềm đạm")
    # Police / Officials
    if any(m in context_text for m in ["警察", "警官", "队长", "同志"]):
        return ("tôi", "đồng chí / cán bộ", "nghiêm túc, phối hợp")
    # Default urban courteous
    return ("tôi", "anh / chị / bạn", "ôn hòa, chuyên nghiệp")


# ===========================================================================
# 2. BỘ ĐO TOÁN HỌC & ĐỊNH LƯỢNG SCENE COMPLEXITY (S_scene)
# ===========================================================================

@dataclass
class SceneMetrics:
    e_syn: float
    a_coref: float
    l_classical: float
    v_state: float
    s_scene: float
    route_tier: str
    pacing_mode: str


def compute_syntactic_entropy(
    sentences: List[str],
    dep_trees: Optional[List[List[Tuple[int, str]]]] = None,
) -> float:
    """Đo độ sâu cú pháp, khoảng cách phụ thuộc và mật độ vế câu lưu thủy (E_syn)."""
    if not sentences:
        return 0.2
    
    total_depth = 0
    total_mdd = 0.0
    total_splices = 0
    
    for s in sentences:
        clauses = [c for c in re.split(r"[，,；;]", s) if c.strip()]
        total_splices += len(clauses)
        
        # Heuristic / LTP depth
        length = len(s)
        estimated_depth = min(12, max(2, int(math.log2(max(length, 2)) * 2)))
        total_depth += estimated_depth
        estimated_mdd = min(7.0, max(1.5, length / max(1, len(clauses) * 4)))
        total_mdd += estimated_mdd
        
    n = len(sentences)
    avg_depth = total_depth / n
    avg_mdd = total_mdd / n
    avg_splices = total_splices / n
    
    score = 0.40 * (avg_depth / 10.0) + 0.30 * (avg_mdd / 6.0) + 0.30 * (avg_splices / 8.0)
    return min(1.0, max(0.05, score))


def compute_coreference_ambiguity(
    sentences: List[str],
    entities_in_scene: List[str],
) -> float:
    """Đo tỷ lệ khuyết chủ ngữ và độ cạnh tranh thực thể cùng xuất hiện (A_coref)."""
    if not sentences:
        return 0.1
    
    num_ent = len(set(entities_in_scene))
    pronoun_3rd_count = sum(sum(s.count(p) for p in ["他", "她", "它", "其", "此人", "二人"]) for s in sentences)
    
    # Tỷ lệ vế câu ẩn chủ ngữ (ước lượng trên dấu phẩy không có chủ thể)
    zero_prone_clauses = 0
    total_clauses = 0
    for s in sentences:
        parts = [p.strip() for p in re.split(r"[，,；;]", s) if p.strip()]
        total_clauses += len(parts)
        for p in parts[1:]:
            if not any(ent in p for ent in entities_in_scene):
                zero_prone_clauses += 1
                
    r_zero = zero_prone_clauses / max(1, total_clauses)
    
    if num_ent <= 1:
        f_comp = 0.2
    else:
        f_comp = min(1.0, (num_ent - 1) / 3.0 + 0.15 * (pronoun_3rd_count / max(1, len(sentences))))
        
    score = 0.55 * r_zero + 0.45 * f_comp
    return min(1.0, max(0.05, score))


def compute_classical_density(sentences: List[str]) -> float:
    """Đo tỷ lệ thành ngữ 4 chữ, hư từ cổ văn và cấu trúc văn ngôn (L_classical)."""
    if not sentences:
        return 0.1
    
    full_text = "".join(sentences)
    total_chars = max(1, len(full_text))
    
    wenyan_count = sum(full_text.count(w) for w in WENYAN_PARTICLES)
    idiom_count = sum(full_text.count(k) for k in IDIOM_HINTS_DEFAULT)
    
    d_wenyan = (wenyan_count * 2) / (total_chars / 20)
    d_idiom = (idiom_count * 4) / (total_chars / 30)
    
    score = 0.45 * min(1.0, d_idiom) + 0.40 * min(1.0, d_wenyan) + 0.15 * (1.0 if idiom_count > 0 else 0.2)
    return min(1.0, max(0.05, score))


def compute_state_volatility(
    has_hostile_shift: bool,
    quote_count: int,
    sent_count: int,
    new_entity_count: int,
) -> float:
    """Đo mức độ biến thiên quan hệ và trạng thái cốt truyện (V_state)."""
    i_rupture = 1.0 if has_hostile_shift else 0.0
    d_turn = min(1.0, (quote_count / max(1, sent_count)) / 0.5)
    d_delta = min(1.0, new_entity_count / 3.0)
    
    score = 0.45 * i_rupture + 0.30 * d_turn + 0.25 * d_delta
    return min(1.0, max(0.05, score))


def evaluate_scene_complexity(
    sentences: List[str],
    entities_in_scene: List[str],
    has_hostile_shift: bool,
    quote_count: int,
    new_entity_count: int = 0,
) -> SceneMetrics:
    """Tính tổng điểm S_scene và xác định route_tier + PACING_MODE."""
    e_syn = compute_syntactic_entropy(sentences)
    a_coref = compute_coreference_ambiguity(sentences, entities_in_scene)
    l_classical = compute_classical_density(sentences)
    v_state = compute_state_volatility(has_hostile_shift, quote_count, len(sentences), new_entity_count)
    
    s_scene = 0.25 * e_syn + 0.35 * a_coref + 0.25 * l_classical + 0.15 * v_state
    
    # Tier mapping
    if s_scene < 0.35:
        tier = "LOW"
    elif s_scene <= 0.70:
        tier = "MED"
    else:
        tier = "HIGH"
        
    # PACING_MODE determination
    full_text = "".join(sentences)
    combat_hits = sum(full_text.count(w) for w in COMBAT_LEXICON)
    aura_hits = sum(full_text.count(w) for w in AURA_LEXICON)
    
    if combat_hits >= 4 or (combat_hits >= 2 and len(sentences) <= 8):
        pacing = "COMBAT_FAST"
    elif quote_count >= 3 or has_hostile_shift:
        pacing = "DIALOGUE_TENSE"
    elif aura_hits >= 3 or l_classical >= 0.45:
        pacing = "AURA_MAJESTIC"
    else:
        pacing = "EXPOSITION_SMOOTH"
        
    return SceneMetrics(
        e_syn=round(e_syn, 4),
        a_coref=round(a_coref, 4),
        l_classical=round(l_classical, 4),
        v_state=round(v_state, 4),
        s_scene=round(s_scene, 4),
        route_tier=tier,
        pacing_mode=pacing,
    )


# ===========================================================================
# 3. THUẬT TOÁN ZERO-PRONOUN, COMMA-SPLICE BREAKING & DIALOGUE ROUTING
# ===========================================================================

class UnifiedSemanticPreprocessor:
    """Gợi ý ngữ nghĩa bảo thủ; không ép phân vai khi chưa có căn cứ nguồn."""

    def __init__(self, numeric_extractor: Optional[DeterministicNumericExtractor] = None):
        self.numeric_extractor = numeric_extractor or DeterministicNumericExtractor()
        self.idiom_hints = dict(IDIOM_HINTS_DEFAULT)

    def process_comma_splice(
        self, raw_sentence: str, active_entities: List[EntityRecord],
        current_center: Optional[str] = None,
    ) -> Tuple[str, Optional[str]]:
        """Rhythm suggestion only. A reaction never proves an implicit subject."""
        parts = re.split(r"([，,；;])", raw_sentence)
        if len(parts) >= 9:
            middle = (len(parts) // 2) | 1
            if middle < len(parts) and parts[middle] in "，,；;":
                parts[middle] += " [||] "
        return "".join(parts), None

    def route_dialogues(
        self, paragraph_text: str, entities: List[EntityRecord],
        default_state: str = "SOURCE_CONTEXT", source_before: str = "",
    ) -> Tuple[str, bool, List[PronounRule]]:
        """Local attribution or UNKNOWN; keywords never create address rules."""
        cues = dialogue_cues(paragraph_text, entities, source_before)
        annotated = paragraph_text
        for cue in reversed(cues):
            tag = (f"[Q{cue['quote_index']}:{cue['speaker']}->{cue['listener']}"
                   f"|state:SOURCE_CONTEXT|evidence:{cue['status']}]")
            annotated = annotated[:cue['end']] + tag + annotated[cue['end']:]
        return annotated, False, []

    def annotate_numerics_and_idioms(
        self,
        text: str,
        start_m_idx: int = 1,
        start_i_idx: int = 1,
    ) -> Tuple[str, List[HardMetric], List[IdiomHint]]:
        """Gắn thẻ số liệu [Mk:...] và thành ngữ [Ik:...], đồng thời xuất danh sách constraints."""
        annotated = text
        hard_metrics: List[HardMetric] = []
        idiom_hints: List[IdiomHint] = []

        # 1. Numerics
        extracted_nums = self.numeric_extractor.extract_metrics(text, start_index=start_m_idx)
        for m in extracted_nums:
            hard_metrics.append(HardMetric(
                tag_id=m.tag_id, raw_zh=m.raw_zh, locked_vi=m.locked_vi
            ))
            annotated = annotated.replace(m.raw_zh, f"{m.raw_zh}[{m.tag_id}:{m.locked_vi}]")

        # 2. Idioms
        i_idx = start_i_idx
        for idiom_zh, (suggestions, forbidden) in self.idiom_hints.items():
            if idiom_zh in annotated:
                tag_id = f"I{i_idx}"
                i_idx += 1
                idiom_hints.append(IdiomHint(
                    tag_id=tag_id, raw_zh=idiom_zh, suggestions=suggestions, forbidden=forbidden
                ))
                annotated = annotated.replace(idiom_zh, f"{idiom_zh}[{tag_id}]")

        return annotated, hard_metrics, idiom_hints

    def build_scene_contract(
        self,
        chap_id: int,
        scene_id: int,
        raw_paragraphs: List[str],
        entities: List[EntityRecord],
        pronouns: List[PronounRule],
        location_vi: str = "UNKNOWN",
        mood: str = "UNKNOWN",
        active_effect: str = "UNKNOWN",
        prev_vi: str = "",
        last_actor_vi: str = "",
        spatial_vec: str = "UNKNOWN",
        glossary: Optional[Dict[str, Tuple[str, str]]] = None,
        anchor_quotes: Optional[List[Tuple[str, str, str]]] = None,
        genre: str = "XIANXIA",
        source_before: str = "",
        source_after: str = "",
    ) -> Tuple[SceneContract, List[str]]:
        """Xử lý toàn diện một Scene và xuất ra SceneContract cùng danh sách đoạn văn đã gắn mã §1..§N."""
        tagged_paragraphs: List[str] = []
        all_hard_metrics: List[HardMetric] = []
        all_idiom_hints: List[IdiomHint] = []
        has_any_rupture = False
        total_quotes = 0
        current_center = None
        source_context = source_before
        cues_all = []
        pronouns = scoped_rules(pronouns, chap_id, scene_id, source_before + "\n" + "\n".join(raw_paragraphs))

        m_idx = 1
        i_idx = 1

        for idx, p_raw in enumerate(raw_paragraphs, start=1):
            p_text = p_raw.strip()
            if not p_text:
                continue

            cues = dialogue_cues(p_raw, entities, source_context)
            for cue in cues:
                cue["paragraph_id"] = idx
                cue["address_candidates"] = [
                    {"self": r.self_vi, "target": r.target_vi, "state": r.state,
                     "scope": r.scope, "evidence": r.evidence}
                    for r in pronouns if r.src_zh == cue["speaker"] and r.dst_zh == cue["listener"]
                    and (r.paragraph_id is None or r.paragraph_id == idx)
                    and (not r.known_by or r.known_by in (cue["speaker"], cue["speaker_id"]))]
            cues_all.extend(cues)

            # 1. Rhythm only; unresolved subjects remain unresolved.
            p_text, current_center = self.process_comma_splice(
                p_text, entities, current_center=current_center
            )

            # 2. Dialogue Routing & Hostile Shift
            p_text, is_rup, new_p_rules = self.route_dialogues(p_text, entities, source_before=source_context)
            if is_rup:
                has_any_rupture = True
            total_quotes += p_text.count("[Q")

            source_context = p_raw

            # 3. Numeric & Idiom Annotation
            p_text, p_metrics, p_idioms = self.annotate_numerics_and_idioms(
                p_text, start_m_idx=m_idx, start_i_idx=i_idx
            )
            m_idx += len(p_metrics)
            i_idx += len(p_idioms)
            all_hard_metrics.extend(p_metrics)
            all_idiom_hints.extend(p_idioms)

            # 4. Attach §ID
            tagged_paragraphs.append(f"§{idx} {p_text}")

        # Compute Scene Complexity & Pacing
        metrics = evaluate_scene_complexity(
            sentences=raw_paragraphs,
            entities_in_scene=[e.zh for e in entities],
            has_hostile_shift=has_any_rupture,
            quote_count=total_quotes,
        )

        contract = SceneContract(
            chap_id=chap_id,
            scene_id=scene_id,
            route_tier=metrics.route_tier,
            genre=genre,
            pacing=metrics.pacing_mode,
            location_vi=location_vi,
            mood=mood,
            active_effect=active_effect,
            prev_vi=prev_vi,
            last_actor_vi=last_actor_vi or "UNKNOWN",
            spatial_vec=spatial_vec,
            entities=entities,
            pronouns=pronouns,
            anchor_quotes=anchor_quotes or [],
            hard_metrics=all_hard_metrics,
            glossary=glossary or {},
            idiom_hints=all_idiom_hints,
            semantic_context={"policy": "SOURCE_FIRST_ADVISORY_V2",
                              "literal_source_anchors": source_anchors([
                                  {'id':f'§{i}','source':raw} for i,raw in enumerate(raw_paragraphs,1)]),
                              "source_before_read_only": source_before,
                              "source_after_read_only": source_after,
                              "dialogues": cues_all,
                              "name_mentions": [
                                  {"paragraph_id": idx, "entity_id": e.entity_id}
                                  for idx, raw in enumerate(raw_paragraphs, 1)
                                  for e in entities if any(alias in raw for alias in entity_aliases(e))],
                              "review_required": True,
                              "scope": "Hints are not semantic approval. Names are editorial; roles, emotions and address defaults must yield to source and viewpoint."},
        )

        return contract, tagged_paragraphs
