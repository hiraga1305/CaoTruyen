# File: native_oauth/zipper_coordinator.py
from __future__ import annotations
import asyncio
import re
from dataclasses import dataclass, field
from typing import Dict, List, Callable, Awaitable
from native_oauth.global_vault import GlobalEntityVault

# Các mẫu Regex 0-Token bắt đặc trưng Tiểu thuyết Đô thị Huyền học / Livestream & Tiên hiệp
RE_LIVESTREAM_USER = re.compile(r"【([^】]{2,16})】")
RE_GIFT_PATTERN = re.compile(r"(?:送出|打賞|打赏|贈送|赠送)了?(?:[一二三四五六七八九十百千萬\d]+[個座艘架枚朵發條个座艘架枚朵发条]?)?([\u4e00-\u9fff]{2,8})")
RE_BOOK_OR_SKILL = re.compile(r"《([^》]{2,12})》")
RE_SPEAKER_PREFIX = re.compile(r"([\u4e00-\u9fff]{2,5})(?:連忙|连忙|頓時|顿时|冷笑|微微|連聲|连声|顫聲|颤声|開口|开口)?(?:說道|说道|問道|问道|喊道|驚呼|惊呼|冷喝)")


@dataclass
class UnknownCandidate:
    zh: str
    inferred_cat: str             # PERSON, GUEST, GIFT, SKILL
    first_chap: int
    frequency: int = 0
    context_snippets: List[str] = field(default_factory=list)


MICRO_LOCK_SYSTEM_PROMPT = """Bạn là Kiến trúc sư Từ điển của Bạch Ngọc Sách.
Nhiệm vụ: Chuẩn hóa danh sách thực thể mới quét được từ batch 50 chương tiểu thuyết và xác định vai vế xưng hô với Nhân vật chính (PROTAGONIST).
Quy tắc:
1. Tên người (PERSON), công pháp/pháp bảo (SKILL/ITEM): Dịch Hán-Việt chuẩn xác.
2. Nickname khách nối máy / cư dân mạng (GUEST) hoặc quà tặng livestream (GIFT): Dịch nghĩa tiếng Việt tự nhiên, mượt mà, giữ đúng sắc thái hài hước/đặc trưng mạng (VD: 愛吃香菜 -> Hội Ghét Rau Mùi / Thích Ăn Rau Mùi; 穿雲箭 -> Tên Xuyên Mây).
3. Chỉ trả về định dạng Pipe-DSL, mỗi thực thể 1 dòng, KHÔNG giải thích:
ENT|<Raw_ZH>|<Locked_VI>|<CAT>|<Gender:M/F/N>|<narr_lock>|<Self_To_Protag>|<Target_To_Protag>|<Protag_Self>|<Protag_Target>|<Bio_Capsule_10_Tu>
"""


class TwoPhaseZipperCoordinator:
    def __init__(
        self,
        vault: GlobalEntityVault,
        protagonist_zh: str,
        protagonist_vi: str,
        llm_micro_caller: Callable[[str, str], Awaitable[str]],
        ltp_ner_extractor: Callable[[str], List[Tuple[str, str]]] | None = None
    ) -> None:
        self.vault = vault
        self.protagonist_zh = protagonist_zh
        self.protagonist_vi = protagonist_vi
        self.llm_micro_caller = llm_micro_caller
        self.ltp_ner_extractor = ltp_ner_extractor

    # ------------------------------------------------------------------------
    # PHA 1: QUÉT TIỀN TRẠM 0-TOKEN TRÊN TOÀN BỘ BATCH (VD: 50 CHƯƠNG)
    # ------------------------------------------------------------------------
    def phase1_scan_batch_0_token(
        self, chapters: List[Tuple[int, str]]
    ) -> List[UnknownCandidate]:
        """
        Quét toàn bộ 50 chương không tốn 1 token LLM nào.
        Lọc ra các thực thể mới xuất hiện >= 2 lần (hoặc nằm trong thẻ đặc biệt).
        """
        candidates: Dict[str, UnknownCandidate] = {}

        def _register(zh: str, cat: str, chap_id: int, sentence: str) -> None:
            zh = zh.strip()
            if len(zh) < 2 or zh == self.protagonist_zh or self.vault.has_entity(zh):
                return
            if zh not in candidates:
                candidates[zh] = UnknownCandidate(zh=zh, inferred_cat=cat, first_chap=chap_id)
            cand = candidates[zh]
            cand.frequency += 1
            if len(cand.context_snippets) < 2:
                snippet = sentence.strip()[:45]
                if snippet not in cand.context_snippets:
                    cand.context_snippets.append(snippet)

        for chap_id, raw_text in chapters:
            sentences = re.split(r"[。！？\n]+", raw_text)
            for sent in sentences:
                if not sent:
                    continue
                # 1. Bắt ID khách nối máy / bình luận livestream
                for m in RE_LIVESTREAM_USER.finditer(sent):
                    _register(m.group(1), "GUEST", chap_id, sent)
                # 2. Bắt tên quà tặng livestream
                for m in RE_GIFT_PATTERN.finditer(sent):
                    _register(m.group(1), "GIFT", chap_id, sent)
                # 3. Bắt tên công pháp / điển tịch / pháp bảo
                for m in RE_BOOK_OR_SKILL.finditer(sent):
                    _register(m.group(1), "SKILL", chap_id, sent)
                # 4. Bắt nhân vật phát ngôn bằng mẫu động từ dẫn thoại
                for m in RE_SPEAKER_PREFIX.finditer(sent):
                    _register(m.group(1), "PERSON", chap_id, sent)
                # 5. Kết hợp LTP NER offline (nếu được truyền vào từ .venv_parser)
                if self.ltp_ner_extractor:
                    for ner_zh, ner_tag in self.ltp_ner_extractor(sent):
                        mapped_cat = "PERSON" if ner_tag == "Nh" else ("LOC" if ner_tag == "Ns" else "SECT")
                        _register(ner_zh, mapped_cat, chap_id, sent)

        # Chỉ giữ lại các thực thể đặc biệt (GUEST/SKILL/GIFT) hoặc PERSON xuất hiện >= 2 lần
        filtered = [
            c for c in candidates.values()
            if c.inferred_cat in ("GUEST", "SKILL", "GIFT") or c.frequency >= 2
        ]
        filtered.sort(key=lambda x: (x.first_chap, -x.frequency))
        return filtered

    # ------------------------------------------------------------------------
    # PHA 2: 1 CUỘC GỌI MICRO-LLM DUY NHẤT ĐỂ KHÓA CỨNG VÀO GLOBAL VAULT
    # ------------------------------------------------------------------------
    async def phase2_lock_entities_micro_llm(
        self, candidates: List[UnknownCandidate]
    ) -> int:
        if not candidates:
            return 0

        # Đóng gói siêu nén (~300-500 tokens cho 25-35 thực thể mới)
        prompt_lines = [f"PROTAGONIST: {self.protagonist_zh} ({self.protagonist_vi})"]
        for c in candidates:
            ctx = " / ".join(c.context_snippets)
            prompt_lines.append(f"{c.zh}|{c.inferred_cat}|ch:{c.first_chap}|ctx:{ctx}")

        user_payload = "\n".join(prompt_lines)
        llm_response = await self.llm_micro_caller(MICRO_LOCK_SYSTEM_PROMPT, user_payload)

        locked_count = 0
        cand_map = {c.zh: c for c in candidates}

        for line in llm_response.splitlines():
            line = line.strip()
            if not line.startswith("ENT|"):
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) < 11:
                continue
            _, zh, vi, cat, gender, narr_lock, g_self, g_target, p_self, p_target, bio = parts[:11]
            if zh not in cand_map:
                continue

            first_chap = cand_map[zh].first_chap
            self.vault.upsert_locked_entity(
                canonical_zh=zh,
                canonical_vi=vi,
                category=cat,
                gender=gender,
                narr_lock=narr_lock,
                persona_tag=f"{cat} ({narr_lock})",
                bio_capsule=bio,
                chap_id=first_chap,
                is_locked=1
            )

            # Nếu là nhân vật hoặc khách nối máy, khóa luôn cặp đại từ 2 chiều với Main
            if cat in ("PERSON", "GUEST") and g_self and g_target:
                self.vault.upsert_pronoun_rule(
                    src_zh=zh, dst_zh=self.protagonist_zh, rel_state="DEFAULT",
                    self_vi=g_self, target_vi=g_target, speech_tone="theo ngữ cảnh",
                    chap_id=first_chap, is_locked=1
                )
                self.vault.upsert_pronoun_rule(
                    src_zh=self.protagonist_zh, dst_zh=zh, rel_state="DEFAULT",
                    self_vi=p_self, target_vi=p_target, speech_tone="điềm tĩnh",
                    chap_id=first_chap, is_locked=1
                )
            locked_count += 1

        # Rebuild lại Aho-Corasick Trie trên RAM sau khi khóa xong toàn bộ batch
        self.vault.rebuild_automaton()
        return locked_count

    # ------------------------------------------------------------------------
    # PHA 3: XẢ CÁC SUBAGENTS CHẠY SONG SONG (8-10 CHƯƠNG / SUBAGENT)
    # ------------------------------------------------------------------------
    async def run_zipper_batch(
        self,
        chapters: List[Tuple[int, str]],
        subagent_worker_fn: Callable[[List[Tuple[int, str]]], Awaitable[Dict[int, str]]],
        chunk_size: int = 10
    ) -> Dict[int, str]:
        """
        Thực thi trọn vẹn quy trình Khóa Kéo 2 Pha + Xả Subagents song song.
        """
        # Pha 1: Quét 0-Token
        unknowns = self.phase1_scan_batch_0_token(chapters)
        # Pha 2: Khóa từ điển bằng 1 Micro-Call
        await self.phase2_lock_entities_micro_llm(unknowns)

        # Pha 3: Chia batch 50 chương thành các cụm 8-10 chương và chạy song song
        chunks = [
            chapters[i : i + chunk_size]
            for i in range(0, len(chapters), chunk_size)
        ]
        tasks = [subagent_worker_fn(chunk) for chunk in chunks]
        chunk_results = await asyncio.gather(*tasks)

        merged_translations: Dict[int, str] = {}
        for res in chunk_results:
            merged_translations.update(res)
        return merged_translations
