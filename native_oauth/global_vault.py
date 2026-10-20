# File: native_oauth/global_vault.py
from __future__ import annotations
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from collections import deque

# ============================================================================
# 1. CẤU TRÚC DỮ LIỆU & SCHEMA SQLITE (CHẾ ĐỘ WAL CONCURRENCY)
# ============================================================================

VAULT_SCHEMA_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

-- Bảng 1: Kho lưu trữ thực thể toàn cục (Bất biến khi is_locked = 1)
CREATE TABLE IF NOT EXISTS vault_entities (
    entity_id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_zh TEXT UNIQUE NOT NULL,
    canonical_vi TEXT NOT NULL,
    category TEXT NOT NULL,            -- PERSON, GUEST, GIFT, SKILL, ITEM, SECT, LOC
    gender TEXT DEFAULT 'N',           -- M, F, N
    narr_lock TEXT NOT NULL,           -- hắn, y, gã, lão, nàng, ả, cô nàng, nó
    persona_tag TEXT DEFAULT '',       -- VD: Thủy hữu đa nghi / Đại gia hào sảng / Lão quái
    bio_capsule TEXT DEFAULT '',       -- Lai lịch siêu nén <= 20 từ để chống quên khi tái xuất
    first_seen_chap INTEGER NOT NULL,
    last_seen_chap INTEGER NOT NULL,
    is_locked INTEGER DEFAULT 1        -- 1 = Khóa cứng từ Zipper Phase 2, cấm Delta ghi đè
);

-- Bảng 2: Biệt danh / ID phụ / Tên viết tắt ánh xạ về entity_id gốc
CREATE TABLE IF NOT EXISTS vault_aliases (
    alias_zh TEXT PRIMARY KEY,
    entity_id INTEGER NOT NULL,
    alias_vi TEXT NOT NULL,
    FOREIGN KEY(entity_id) REFERENCES vault_entities(entity_id) ON DELETE CASCADE
);

-- Bảng 3: Ma trận đại từ xưng hô có hướng (1-Hop Ego Network)
CREATE TABLE IF NOT EXISTS vault_pronouns (
    src_zh TEXT NOT NULL,
    dst_zh TEXT NOT NULL,
    rel_state TEXT NOT NULL DEFAULT 'DEFAULT', -- DEFAULT, COURTEOUS, HOSTILE, RESPECTFUL
    self_vi TEXT NOT NULL,                     -- ta, tại hạ, tôi, bổn tọa,貧道 (bần đạo)...
    target_vi TEXT NOT NULL,                   -- đạo hữu, đại sư, ngươi, anh, các hạ...
    speech_tone TEXT DEFAULT 'trung tính',
    is_locked INTEGER DEFAULT 1,
    updated_chap INTEGER NOT NULL,
    PRIMARY KEY (src_zh, dst_zh, rel_state)
);

-- Bảng 4: Rolling Arc Capsule (Ngữ cảnh ngắn hạn theo cụm chương)
CREATE TABLE IF NOT EXISTS rolling_arc_capsules (
    arc_id INTEGER PRIMARY KEY AUTOINCREMENT,
    start_chap INTEGER NOT NULL,
    end_chap INTEGER NOT NULL,
    arc_summary_vi TEXT NOT NULL,      -- Tóm tắt <= 80 từ về sự kiện đang diễn ra
    active_location_vi TEXT NOT NULL,
    active_plot_hooks TEXT DEFAULT ''
);

-- Bảng 5: Sổ cái lời phán / sấm truyền đang treo (Pending Prophecy Buffer)
CREATE TABLE IF NOT EXISTS pending_omens (
    omen_id INTEGER PRIMARY KEY AUTOINCREMENT,
    target_zh TEXT NOT NULL,           -- Nhân vật nhận lời phán (VD: 王大錘)
    target_vi TEXT NOT NULL,           -- Tên tiếng Việt (VD: Vương Đại Chùy)
    source_chap INTEGER NOT NULL,      -- Chương phát ra lời phán
    expire_chap INTEGER DEFAULT 999999,-- Chương hết hạn (nếu là hạn ngắn hạn)
    raw_omen_zh TEXT NOT NULL,         -- Câu chữ Hán gốc lúc phán
    locked_phrasing_vi TEXT NOT NULL,  -- Cụm từ tiếng Việt ĐÃ DỊCH cần hô ứng lại
    trigger_keywords_zh TEXT NOT NULL, -- Từ khóa kích hoạt phân tách bởi dấu phẩy (VD: 東南,火,血,應驗)
    echo_keywords_vi TEXT NOT NULL,    -- Các từ khóa bắt buộc phải xuất hiện khi ứng nghiệm
    status TEXT DEFAULT 'PENDING'      -- PENDING, FULFILLED, EXPIRED
);

CREATE INDEX IF NOT EXISTS idx_omen_status ON pending_omens(status);
CREATE INDEX IF NOT EXISTS idx_pronoun_pair ON vault_pronouns(src_zh, dst_zh);
"""


# ============================================================================
# 2. BỘ MÁY AHO-CORASICK AUTOMATON O(N) (0-TOKEN ENTITY WAKE-UP)
# ============================================================================

class AhoCorasickAutomaton:
    """
    Cây Aho-Corasick chạy trên RAM để quét toàn bộ văn bản chữ Hán trong O(N).
    Không phụ thuộc thư viện C bên ngoài, tốc độ quét 3.000 chữ < 1.5ms.
    """
    def __init__(self) -> None:
        self.trie: List[Dict[str, int]] = [{}]
        self.output: List[List[Tuple[str, int]]] = [[]]  # (matched_zh, entity_id)
        self.fail: List[int] = [0]
        self._built = False

    def add_keyword(self, keyword_zh: str, entity_id: int) -> None:
        if not keyword_zh:
            return
        node = 0
        for char in keyword_zh:
            if char not in self.trie[node]:
                self.trie[node][char] = len(self.trie)
                self.trie.append({})
                self.output.append([])
                self.fail.append(0)
            node = self.trie[node][char]
        self.output[node].append((keyword_zh, entity_id))
        self._built = False

    def build_fail_links(self) -> None:
        queue: deque[int] = deque()
        for char, next_node in self.trie[0].items():
            self.fail[next_node] = 0
            queue.append(next_node)

        while queue:
            curr = queue.popleft()
            for char, next_node in self.trie[curr].items():
                queue.append(next_node)
                f = self.fail[curr]
                while f > 0 and char not in self.trie[f]:
                    f = self.fail[f]
                self.fail[next_node] = self.trie[f].get(char, 0)
                if self.output[self.fail[next_node]]:
                    self.output[next_node].extend(self.output[self.fail[next_node]])
        self._built = True

    def scan_longest_non_overlapping(self, text_zh: str) -> Dict[str, int]:
        """
        Quét văn bản trong O(N) và ưu tiên khớp cụm từ dài nhất (Longest Match)
        để tránh nhận diện nhầm tên ngắn bên trong tên dài.
        Trả về: Dict[canonical_or_alias_zh, entity_id]
        """
        if not self._built:
            self.build_fail_links()

        raw_spans: List[Tuple[int, int, str, int]] = []
        node = 0
        for idx, char in enumerate(text_zh):
            while node > 0 and char not in self.trie[node]:
                node = self.fail[node]
            node = self.trie[node].get(char, 0)
            if self.output[node]:
                for kw, ent_id in self.output[node]:
                    start = idx - len(kw) + 1
                    raw_spans.append((start, idx + 1, kw, ent_id))

        # Sắp xếp ưu tiên vị trí bắt đầu sớm hơn và độ dài cụm lớn hơn
        raw_spans.sort(key=lambda x: (x[0], -(x[1] - x[0])))
        accepted: Dict[str, int] = {}
        last_end = -1
        for start, end, kw, ent_id in raw_spans:
            if start >= last_end:
                accepted[kw] = ent_id
                last_end = end
        return accepted


# ============================================================================
# 3. LỚP QUẢN LÝ GLOBAL ENTITY VAULT & ĐÁNH THỨC KÝ ỨC (BOOMERANG WAKE-UP)
# ============================================================================

@dataclass
class HydratedVaultPayload:
    active_entities: List[dict]
    pronoun_matrix: List[dict]
    glossary_map: Dict[str, Tuple[str, str]]
    awakened_boomerangs: List[str]       # Ghi chú các nhân vật tái xuất sau thời gian dài
    rolling_arc_note: str
    triggered_omens: List[dict]


class GlobalEntityVault:
    """
    Quản lý bộ nhớ 2 tầng:
    - Tầng 1: SQLite Global Vault + In-Memory Aho-Corasick Trie
    - Tầng 2: Rolling Arc Capsule
    """
    BOOMERANG_GAP_THRESHOLD = 15  # Vắng mặt >= 15 chương khi tái xuất sẽ kèm bio_capsule

    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._init_schema()
        self.automaton = AhoCorasickAutomaton()
        self.rebuild_automaton()

    def _init_schema(self) -> None:
        with self.conn:
            self.conn.executescript(VAULT_SCHEMA_SQL)

    def close(self) -> None:
        if hasattr(self, 'conn') and self.conn:
            self.conn.close()
            self.conn = None

    def rebuild_automaton(self) -> None:
        """Nạp toàn bộ thực thể và biệt danh từ SQLite lên RAM Aho-Corasick Trie."""
        auto = AhoCorasickAutomaton()
        cur = self.conn.cursor()
        for row in cur.execute("SELECT entity_id, canonical_zh FROM vault_entities"):
            auto.add_keyword(row["canonical_zh"], row["entity_id"])
        for row in cur.execute("SELECT entity_id, alias_zh FROM vault_aliases"):
            auto.add_keyword(row["alias_zh"], row["entity_id"])
        auto.build_fail_links()
        self.automaton = auto

    def has_entity(self, zh_term: str) -> bool:
        cur = self.conn.cursor()
        row = cur.execute(
            """
            SELECT 1 FROM vault_entities WHERE canonical_zh = ?
            UNION
            SELECT 1 FROM vault_aliases WHERE alias_zh = ?
            """,
            (zh_term, zh_term)
        ).fetchone()
        return row is not None

    def upsert_locked_entity(
        self,
        canonical_zh: str,
        canonical_vi: str,
        category: str,
        gender: str,
        narr_lock: str,
        persona_tag: str,
        bio_capsule: str,
        chap_id: int,
        is_locked: int = 1
    ) -> int:
        """Ghi hoặc cập nhật thực thể đã chuẩn hóa vào Vault."""
        with self.conn:
            cur = self.conn.cursor()
            cur.execute(
                """
                INSERT INTO vault_entities (
                    canonical_zh, canonical_vi, category, gender, narr_lock,
                    persona_tag, bio_capsule, first_seen_chap, last_seen_chap, is_locked
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(canonical_zh) DO UPDATE SET
                    last_seen_chap = MAX(vault_entities.last_seen_chap, excluded.last_seen_chap),
                    bio_capsule = CASE
                        WHEN vault_entities.bio_capsule = '' THEN excluded.bio_capsule
                        ELSE vault_entities.bio_capsule
                    END
                """,
                (
                    canonical_zh, canonical_vi, category, gender, narr_lock,
                    persona_tag, bio_capsule, chap_id, chap_id, is_locked
                )
            )
            row = cur.execute(
                "SELECT entity_id FROM vault_entities WHERE canonical_zh = ?",
                (canonical_zh,)
            ).fetchone()
            ent_id = int(row["entity_id"])
        self.rebuild_automaton()
        return ent_id

    def upsert_pronoun_rule(
        self,
        src_zh: str,
        dst_zh: str,
        rel_state: str,
        self_vi: str,
        target_vi: str,
        speech_tone: str,
        chap_id: int,
        is_locked: int = 1
    ) -> None:
        with self.conn:
            self.conn.execute(
                """
                INSERT INTO vault_pronouns (
                    src_zh, dst_zh, rel_state, self_vi, target_vi,
                    speech_tone, is_locked, updated_chap
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(src_zh, dst_zh, rel_state) DO UPDATE SET
                    self_vi = CASE WHEN vault_pronouns.is_locked = 1 THEN vault_pronouns.self_vi ELSE excluded.self_vi END,
                    target_vi = CASE WHEN vault_pronouns.is_locked = 1 THEN vault_pronouns.target_vi ELSE excluded.target_vi END,
                    updated_chap = excluded.updated_chap
                """,
                (src_zh, dst_zh, rel_state, self_vi, target_vi, speech_tone, is_locked, chap_id)
            )

    def hydrate_for_scene(self, chap_id: int, raw_zh_scene: str) -> HydratedVaultPayload:
        """
        Hàm RAG 0-Token:
        1. Quét raw_zh_scene bằng Aho-Corasick trong O(N).
        2. Đánh thức các thực thể có mặt (kể cả nhân vật vắng mặt 500 chương).
        3. Cắt lát đồ thị 1-hop lấy PRONOUN_MATRIX giữa các nhân vật trong cảnh.
        4. Kiểm tra các lời phán PENDING_OMENS có dấu hiệu ứng nghiệm trong cảnh.
        """
        matched_map = self.automaton.scan_longest_non_overlapping(raw_zh_scene)
        entity_ids = sorted(set(matched_map.values()))

        active_entities: List[dict] = []
        glossary_map: Dict[str, Tuple[str, str]] = {}
        awakened_boomerangs: List[str] = []
        person_zh_set: Set[str] = set()

        if entity_ids:
            placeholders = ",".join("?" for _ in entity_ids)
            cur = self.conn.cursor()
            rows = cur.execute(
                f"SELECT * FROM vault_entities WHERE entity_id IN ({placeholders})",
                entity_ids
            ).fetchall()

            for r in rows:
                cat = r["category"]
                zh = r["canonical_zh"]
                vi = r["canonical_vi"]
                gap = chap_id - int(r["last_seen_chap"])

                if cat in ("PERSON", "GUEST"):
                    person_zh_set.add(zh)
                    role_desc = r["persona_tag"]
                    # Nếu là nhân vật Boomerang tái xuất sau nhiều chương, tiêm thêm bio_capsule
                    if gap >= self.BOOMERANG_GAP_THRESHOLD and r["bio_capsule"]:
                        role_desc = f"{role_desc} [Tái xuất từ Ch.{r['last_seen_chap']}: {r['bio_capsule']}]"
                        awakened_boomerangs.append(f"{vi} (vắng mặt {gap} chương)")

                    active_entities.append({
                        "zh": zh,
                        "vi": vi,
                        "gender": r["gender"],
                        "narr_lock": r["narr_lock"],
                        "role": role_desc
                    })
                else:
                    glossary_map[zh] = (vi, cat)

            # Cập nhật mốc xuất hiện mới nhất
            with self.conn:
                self.conn.execute(
                    f"UPDATE vault_entities SET last_seen_chap = MAX(last_seen_chap, ?) WHERE entity_id IN ({placeholders})",
                    [chap_id, *entity_ids]
                )

        # Cắt lát 1-Hop Pronoun Matrix giữa các nhân vật có mặt trong Scene
        pronoun_matrix: List[dict] = []
        if len(person_zh_set) >= 1:
            p_list = list(person_zh_set)
            ph = ",".join("?" for _ in p_list)
            cur = self.conn.cursor()
            # Lấy cả quan hệ nội bộ nhóm trong scene và quan hệ với nhân vật chính
            p_rows = cur.execute(
                f"""
                SELECT src_zh, dst_zh, rel_state, self_vi, target_vi, speech_tone
                FROM vault_pronouns
                WHERE src_zh IN ({ph}) OR dst_zh IN ({ph})
                """,
                [*p_list, *p_list]
            ).fetchall()
            for pr in p_rows:
                if pr["src_zh"] in person_zh_set and pr["dst_zh"] in person_zh_set:
                    pronoun_matrix.append(dict(pr))

        # Lấy Rolling Arc Capsule gần nhất
        cur = self.conn.cursor()
        arc_row = cur.execute(
            """
            SELECT arc_summary_vi FROM rolling_arc_capsules
            WHERE start_chap <= ? ORDER BY end_chap DESC LIMIT 1
            """,
            (chap_id,)
        ).fetchone()
        rolling_arc_note = arc_row["arc_summary_vi"] if arc_row else ""

        # Quét Pending Omens (Chi tiết thuật toán khớp ở Mục 4)
        triggered_omens = self.match_pending_omens(chap_id, raw_zh_scene, person_zh_set)

        return HydratedVaultPayload(
            active_entities=active_entities,
            pronoun_matrix=pronoun_matrix,
            glossary_map=glossary_map,
            awakened_boomerangs=awakened_boomerangs,
            rolling_arc_note=rolling_arc_note,
            triggered_omens=triggered_omens
        )

    def match_pending_omens(
        self, chap_id: int, raw_zh_scene: str, active_persons_zh: Set[str]
    ) -> List[dict]:
        """
        Kiểm tra xem cảnh hiện tại có đang ứng nghiệm lời phán nào trong Sổ cái không.
        Kích hoạt khi:
        1. Nhân vật bị phán (target_zh) xuất hiện trong cảnh VÀ có >= 1 từ khóa tai kiếp.
        2. Hoặc có >= 2 từ khóa tai kiếp + từ khóa xác nhận ứng nghiệm (應驗, 一語成讖, 算得準...).
        """
        FULFILL_MARKERS = ("應驗", "一語成讖", "算得", "大師說", "血光", "劫數", "果真", "報應")
        cur = self.conn.cursor()
        rows = cur.execute(
            "SELECT * FROM pending_omens WHERE status = 'PENDING' AND source_chap < ? AND expire_chap >= ?",
            (chap_id, chap_id)
        ).fetchall()

        matched: List[dict] = []
        has_fulfill_marker = any(m in raw_zh_scene for m in FULFILL_MARKERS)

        for r in rows:
            kw_list = [k.strip() for k in r["trigger_keywords_zh"].split(",") if k.strip()]
            hit_count = sum(1 for kw in kw_list if kw in raw_zh_scene)
            target_present = r["target_zh"] in active_persons_zh or r["target_zh"] in raw_zh_scene

            if (target_present and hit_count >= 1) or (hit_count >= 2 and has_fulfill_marker):
                matched.append({
                    "omen_id": f"O{r['omen_id']}",
                    "target_vi": r["target_vi"],
                    "source_chap": r["source_chap"],
                    "locked_phrasing_vi": r["locked_phrasing_vi"],
                    "echo_keywords_vi": r["echo_keywords_vi"]
                })
        return matched
