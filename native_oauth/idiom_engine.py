"""
native_oauth/idiom_engine.py - High-Fidelity Idiom & Semantic Allusion Engine
CaoTruyen v2.0 - Co-engineered with Gemini 4 Argon.

Handles Chinese 4-character idioms (成语), cultural allusions (典故), and metaphors
using an in-memory Aho-Corasick Automaton for 0-token O(N) detection.
Categorizes idioms into 3 distinct translation tiers:
  1. TIER 1 - ARCHAIC_XIANXIA: Preserves dignified Sino-Vietnamese (Hán-Việt cổ phong).
  2. TIER 2 - COLLOQUIAL_VIETNAMESE: Replaces with natural Vietnamese equivalent idioms.
  3. TIER 3 - CULTURAL_ALLUSION: Contextualized explanation for historical allusions.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple


class IdiomTier(str, Enum):
    TIER1_ARCHAIC = "ARCHAIC_XIANXIA"          # Giữ Hán-Việt cổ phong trang trọng
    TIER2_COLLOQUIAL = "COLLOQUIAL_VIETNAMESE" # Thuần Việt hóa tự nhiên / Thành ngữ tương đương
    TIER3_ALLUSION = "CULTURAL_ALLUSION"       # Điển tích cần diễn giải ngữ cảnh


@dataclass
class IdiomEntry:
    chinese_idiom: str             # e.g., "半途而废"
    pinyin: str                    # e.g., "bàn tú ér fèi"
    sino_vietnamese: str           # e.g., "Bán đồ nhi phế"
    recommended_translation: str   # e.g., "Bỏ dở giữa chừng"
    tier: IdiomTier
    register_hint: str             # e.g., "Dùng cho hội thoại / không dùng convert"
    genre_override: Dict[str, str] = field(default_factory=dict)
    # e.g., {"CULTIVATION": "Bán đồ nhi phế", "URBAN": "Bỏ dở giữa chừng"}


class IdiomAhoCorasick:
    """Trie-based Aho-Corasick Automaton for 0-token O(N) multi-idiom detection."""

    def __init__(self):
        self.trie: List[Dict[str, int]] = [{}]
        self.output: List[List[str]] = [[]]
        self.fail: List[int] = [0]
        self.built = False

    def insert(self, word: str):
        node = 0
        for char in word:
            if char not in self.trie[node]:
                self.trie[node][char] = len(self.trie)
                self.trie.append({})
                self.output.append([])
                self.fail.append(0)
            node = self.trie[node][char]
        self.output[node].append(word)
        self.built = False

    def build_failure_links(self):
        queue = []
        for char, child in self.trie[0].items():
            queue.append(child)
            self.fail[child] = 0

        while queue:
            curr = queue.pop(0)
            for char, child in self.trie[curr].items():
                queue.append(child)
                f = self.fail[curr]
                while f > 0 and char not in self.trie[f]:
                    f = self.fail[f]
                if char in self.trie[f]:
                    self.fail[child] = self.trie[f][char]
                else:
                    self.fail[child] = 0
                self.output[child].extend(self.output[self.fail[child]])
        self.built = True

    def find_all(self, text: str) -> List[Tuple[int, int, str]]:
        """Returns list of (start_index, end_index, matched_idiom)."""
        if not self.built:
            self.build_failure_links()

        node = 0
        results = []
        for i, char in enumerate(text):
            while node > 0 and char not in self.trie[node]:
                node = self.fail[node]
            if char in self.trie[node]:
                node = self.trie[node][char]
            else:
                node = 0

            for word in self.output[node]:
                results.append((i - len(word) + 1, i + 1, word))
        return results


class IdiomEngine:
    """
    Core Idiom & Semantic Allusion Engine.
    Pre-loads extensive lexicon of 4-character idioms and cultural allusions.
    Matches in O(N) and injects hints into SceneContract.
    """

    DEFAULT_IDIOMS: List[IdiomEntry] = [
        # --- TIER 1: ARCHAIC / XIANXIA (Giữ Hán-Việt cổ phong) ---
        IdiomEntry(
            chinese_idiom="道法自然",
            pinyin="dào fǎ zì rán",
            sino_vietnamese="Đạo pháp tự nhiên",
            recommended_translation="Đạo pháp tự nhiên",
            tier=IdiomTier.TIER1_ARCHAIC,
            register_hint="Cổ phong / Chân lý đại đạo",
        ),
        IdiomEntry(
            chinese_idiom="返璞归真",
            pinyin="fǎn pú guī zhēn",
            sino_vietnamese="Phản phác quy chân",
            recommended_translation="Phản phác quy chân",
            tier=IdiomTier.TIER1_ARCHAIC,
            register_hint="Cảnh giới tu hành / Hòa mình vào thiên nhiên",
        ),
        IdiomEntry(
            chinese_idiom="万剑归宗",
            pinyin="wàn jiàn guī zōng",
            sino_vietnamese="Vạn kiếm quy tông",
            recommended_translation="Vạn kiếm quy tông",
            tier=IdiomTier.TIER1_ARCHAIC,
            register_hint="Tuyệt kỹ kiếm đạo",
        ),
        IdiomEntry(
            chinese_idiom="毁天灭地",
            pinyin="huǐ tiān miè dì",
            sino_vietnamese="Hủy thiên diệt địa",
            recommended_translation="Hủy thiên diệt địa",
            tier=IdiomTier.TIER1_ARCHAIC,
            register_hint="Uy lực chiến đấu / Khí thế nghiêng trời lệch đất",
        ),

        # --- TIER 2: COLLOQUIAL (Thuần Việt hóa / Tránh Convert thô) ---
        IdiomEntry(
            chinese_idiom="半途而废",
            pinyin="bàn tú ér fèi",
            sino_vietnamese="Bán đồ nhi phế",
            recommended_translation="Bỏ dở giữa chừng",
            tier=IdiomTier.TIER2_COLLOQUIAL,
            register_hint="Đời thường / Đừng dịch convert là 'bán đồ nhi phế'",
            genre_override={"CULTIVATION": "Bỏ dở giữa chừng", "URBAN": "Bỏ dở giữa chừng"}
        ),
        IdiomEntry(
            chinese_idiom="望风而逃",
            pinyin="wàng fēng ér táo",
            sino_vietnamese="Vọng phong nhi đào",
            recommended_translation="Mới thấy bóng gió đã bỏ chạy",
            tier=IdiomTier.TIER2_COLLOQUIAL,
            register_hint="Tháo chạy thảm hại / Tránh dịch convert 'vọng phong nhi đào'",
        ),
        IdiomEntry(
            chinese_idiom="得寸进尺",
            pinyin="dé cùn jìn chǐ",
            sino_vietnamese="Đắc thốn tiến xích",
            recommended_translation="Được đằng chân lân đằng đầu",
            tier=IdiomTier.TIER2_COLLOQUIAL,
            register_hint="Hành vi tham lam / Dùng thành ngữ Việt tương đương",
        ),
        IdiomEntry(
            chinese_idiom="指鹿为马",
            pinyin="zhǐ lù wéi mǎ",
            sino_vietnamese="Chỉ lộc vi mã",
            recommended_translation="Đổi trắng thay đen",
            tier=IdiomTier.TIER2_COLLOQUIAL,
            register_hint="Bẻ cong sự thật / 'Đổi trắng thay đen' hoặc 'Chỉ hươu bảo ngựa'",
        ),
        IdiomEntry(
            chinese_idiom="声东击西",
            pinyin="shēng dōng jī xī",
            sino_vietnamese="Thanh đông kích tây",
            recommended_translation="Dương đông kích tây",
            tier=IdiomTier.TIER2_COLLOQUIAL,
            register_hint="Chiến thuật nghi binh",
        ),
        IdiomEntry(
            chinese_idiom="狗急跳墙",
            pinyin="gǒu jí tiào qiáng",
            sino_vietnamese="Cẩu cấp khiêu tường",
            recommended_translation="Chó cùng rứt dậu",
            tier=IdiomTier.TIER2_COLLOQUIAL,
            register_hint="Hành động liều lĩnh khi bế tắc",
        ),
        IdiomEntry(
            chinese_idiom="心花怒放",
            pinyin="xīn huā nù fàng",
            sino_vietnamese="Tâm hoa nộ phóng",
            recommended_translation="Mở cờ trong bụng",
            tier=IdiomTier.TIER2_COLLOQUIAL,
            register_hint="Vui mừng khôn xiết",
        ),

        # --- TIER 3: ALLUSIONS (Điển tích cần diễn giải ngữ cảnh) ---
        IdiomEntry(
            chinese_idiom="东施效颦",
            pinyin="dōng shī xiào pín",
            sino_vietnamese="Đông Thi hiệu tần",
            recommended_translation="Bắt chước lố bịch (Đông Thi bắt chước Tây Thi)",
            tier=IdiomTier.TIER3_ALLUSION,
            register_hint="Điển cố: người xấu bắt chước người đẹp chỉ tổ làm trò cười",
        ),
        IdiomEntry(
            chinese_idiom="叶公好龙",
            pinyin="yè gōng hào lóng",
            sino_vietnamese="Diệp Công hào long",
            recommended_translation="Miệng nói thích mà lòng lại sợ (Diệp Công thích rồng)",
            tier=IdiomTier.TIER3_ALLUSION,
            register_hint="Điển cố: giả vờ yêu thích nhưng khi gặp thật thì hoảng sợ",
        ),
        IdiomEntry(
            chinese_idiom="塞翁失马",
            pinyin="sài wēng shī mǎ",
            sino_vietnamese="Tái ông thất mã",
            recommended_translation="Tái ông mất ngựa, họa phúc khôn lường",
            tier=IdiomTier.TIER3_ALLUSION,
            register_hint="Điển cố: trong cái rủi có cái may",
        ),
    ]

    def __init__(self, custom_idioms: Optional[List[IdiomEntry]] = None):
        self.entries: Dict[str, IdiomEntry] = {}
        self.automaton = IdiomAhoCorasick()

        for entry in self.DEFAULT_IDIOMS:
            self.add_entry(entry)

        if custom_idioms:
            for entry in custom_idioms:
                self.add_entry(entry)

        self.automaton.build_failure_links()

    def add_entry(self, entry: IdiomEntry):
        self.entries[entry.chinese_idiom] = entry
        self.automaton.insert(entry.chinese_idiom)

    def scan_idioms_in_scene(
        self,
        raw_chinese_text: str,
        active_genre: str = "URBAN"
    ) -> List[Dict[str, Any]]:
        """
        Scans Chinese raw text in O(N) using Aho-Corasick.
        Returns list of idiom advice tailored to the active genre and tier.
        """
        matches = self.automaton.find_all(raw_chinese_text)
        results = []
        seen_idioms = set()

        for start, end, zh_idiom in matches:
            if zh_idiom in seen_idioms:
                continue
            seen_idioms.add(zh_idiom)

            entry = self.entries.get(zh_idiom)
            if not entry:
                continue

            # Determine appropriate translation based on genre override
            chosen_trans = entry.genre_override.get(active_genre, entry.recommended_translation)

            results.append({
                "chinese": zh_idiom,
                "sino_vietnamese": entry.sino_vietnamese,
                "tier": entry.tier.value,
                "recommended_vn": chosen_trans,
                "register_hint": entry.register_hint,
                "start_idx": start,
                "end_idx": end,
            })

        return results

    def format_for_scene_contract_dsl(
        self,
        idiom_matches: List[Dict[str, Any]]
    ) -> str:
        """Serializes idiom advice into SceneContract Pipe-DSL block: @IDIOM_HINTS."""
        if not idiom_matches:
            return ""
        lines = ["@IDIOM_HINTS"]
        for m in idiom_matches:
            # IDIOM|<ZH>|<SinoVN>|<Tier>|<RecommendedVN>|<Hint>
            lines.append(f"IDIOM|{m['chinese']}|{m['sino_vietnamese']}|{m['tier']}|{m['recommended_vn']}|{m['register_hint']}")
        return "\n".join(lines)
