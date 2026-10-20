# File: native_oauth/delta_gatekeeper.py
from __future__ import annotations
import re
from dataclasses import dataclass
from typing import List, Tuple
from native_oauth.global_vault import GlobalEntityVault

ALLOWED_NARR_LOCKS = {
    "hắn", "y", "gã", "lão", "nàng", "ả", "thị", "cô nàng", "nó",
    "anh", "cô", "ông", "bà", "cậu", "chị"  # Hỗ trợ thêm profile Đô thị
}

FORBIDDEN_CONVERT_SUBSTRINGS = (
    "không cho là đúng", "sắc mặt ngưng", "đem ", "bị ", "sở ", "một cái "
)

# Bộ từ khóa chữ Hán xác thực có sự kiện "Trở mặt / Sát phạt thật sự" trong nguyên tác
HOSTILE_RUPTURE_TRIGGERS_ZH = (
    "找死", "受死", "去死", "殺機", "殺意", "動手", "偷襲",
    "老賊", "小輩", "小畜生", "狗賊", "不知死活", "敬酒不吃",
    "抽魂", "滅口", "滾開", "拿命來", "翻臉"
)


@dataclass
class DeltaAuditReport:
    accepted_deltas: List[dict]
    rejected_deltas: List[Tuple[dict, str]]  # (delta_item, lý_do_từ_chối)

    @property
    def is_pass(self) -> bool:
        return len(self.rejected_deltas) == 0

    @property
    def violations(self) -> List[Tuple[dict, str]]:
        return self.rejected_deltas


class DeterministicDeltaGatekeeper:
    """
    Tường lửa 0-Token kiểm duyệt mọi bản ghi trong khối <delta> trước khi
    cho phép chạm vào SQLite Global Entity Vault.
    """
    def __init__(self, vault: GlobalEntityVault) -> None:
        self.vault = vault

    @staticmethod
    def has_hostile_rupture_in_raw(raw_zh_scene: str) -> bool:
        """Kiểm tra tất định xem văn bản gốc có chứa từ vựng trở mặt/sát phạt thật không."""
        return any(trig in raw_zh_scene for trig in HOSTILE_RUPTURE_TRIGGERS_ZH)

    def verify_and_commit(
        self,
        chap_id: int,
        raw_zh_scene: str,
        proposed_deltas: List[dict]
    ) -> DeltaAuditReport:
        accepted: List[dict] = []
        rejected: List[Tuple[dict, str]] = []
        rupture_verified = self.has_hostile_rupture_in_raw(raw_zh_scene)

        cur = self.vault.conn.cursor()

        for d in proposed_deltas:
            dtype = d.get("type")

            # ================================================================
            # TRƯỜNG HỢP 1: KIỂM DUYỆT THỰC THỂ MỚI (NEW_ENT)
            # ================================================================
            if dtype in ["NEW_ENT", "NEW_ENTITY"]:
                zh = d.get("zh", "").strip()
                vi = d.get("vi", "").strip()
                gender = d.get("gender", "N").strip().upper()
                narr_lock = d.get("narr_lock", "").strip().lower()
                role = d.get("role", "").strip()

                # Chốt 1: Chuỗi chữ Hán gốc bắt buộc phải tồn tại nguyên văn trong raw_zh_scene
                if not zh or len(zh) < 2 or zh not in raw_zh_scene:
                    rejected.append((d, "ERR_HALLUCINATED_ZH: Chuỗi chữ Hán không tồn tại trong văn bản gốc"))
                    continue

                # Chốt 2: Không được phép ghi đè thực thể đã khóa trong Global Vault
                existing = cur.execute(
                    "SELECT is_locked, canonical_vi FROM vault_entities WHERE canonical_zh = ?",
                    (zh,)
                ).fetchone()
                if existing and int(existing["is_locked"]) == 1:
                    rejected.append((d, f"ERR_IMMUTABLE_LOCK: Thực thể '{zh}' đã được khóa cứng là '{existing['canonical_vi']}'"))
                    continue

                # Chốt 3: Kiểm tra chuẩn đại từ ngôi kể (narr_lock) và vệ sinh từ vựng
                if narr_lock not in ALLOWED_NARR_LOCKS:
                    rejected.append((d, f"ERR_INVALID_NARR_LOCK: '{narr_lock}' không nằm trong tập đại từ chuẩn BNS"))
                    continue
                if any(bad in vi.lower() for bad in FORBIDDEN_CONVERT_SUBSTRINGS):
                    rejected.append((d, f"ERR_CONVERT_TAINT: Tên dịch '{vi}' chứa cấu trúc convert cấm"))
                    continue

                # Hợp lệ -> Ghi vào Vault
                self.vault.upsert_locked_entity(
                    canonical_zh=zh,
                    canonical_vi=vi,
                    category="PERSON",
                    gender=gender if gender in ("M", "F", "N") else "N",
                    narr_lock=narr_lock,
                    persona_tag=role[:60],
                    bio_capsule=role[:80],
                    chap_id=chap_id,
                    is_locked=1
                )
                accepted.append(d)

            # ================================================================
            # TRƯỜNG HỢP 2: KIỂM DUYỆT CHUYỂN ĐỔI XƯNG HÔ (REL_SHIFT)
            # ================================================================
            elif dtype in ["REL_SHIFT", "UPDATE_PRONOUN"]:
                src_zh = d.get("src_zh", "").strip()
                dst_zh = d.get("dst_zh", "").strip()
                new_state = d.get("state", "HOSTILE").strip().upper()
                self_vi = d.get("self_vi", "").strip()
                target_vi = d.get("target_vi", "").strip()
                reason = d.get("reason", "").strip()

                # Chốt 1: Cả 2 thực thể phải xuất hiện trong văn bản gốc của Scene
                if not src_zh or not dst_zh or src_zh not in raw_zh_scene or dst_zh not in raw_zh_scene:
                    rejected.append((d, "ERR_UNGROUNDED_REL: Nhân vật nguồn/đích không có mặt trong Scene gốc"))
                    continue

                # Chốt 2: Cấm ghi đè trạng thái DEFAULT/COURTEOUS đã khóa nếu không có cờ HOSTILE_RUPTURE
                locked_rel = cur.execute(
                    """
                    SELECT is_locked FROM vault_pronouns
                    WHERE src_zh = ? AND dst_zh = ? AND rel_state = ?
                    """,
                    (src_zh, dst_zh, new_state)
                ).fetchone()

                if locked_rel and int(locked_rel["is_locked"]) == 1 and not rupture_verified:
                    rejected.append((
                        d,
                        "ERR_LOCKED_MATRIX_PROTECTED: Cấm ghi đè ma trận xưng hô đã khóa khi nguyên tác không có tín hiệu HOSTILE_RUPTURE"
                    ))
                    continue

                if new_state.startswith("HOSTILE") and not rupture_verified:
                    rejected.append((
                        d,
                        "ERR_FALSE_HOSTILE_SHIFT: Không phát hiện từ khóa sát phạt/trở mặt trong văn bản chữ Hán gốc"
                    ))
                    continue

                # Hợp lệ -> Lưu vào bảng vault_pronouns dưới trạng thái tương ứng (không xóa DEFAULT cũ)
                normalized_state = "HOSTILE" if new_state.startswith("HOSTILE") else new_state
                with self.vault.conn:
                    self.vault.conn.execute(
                        """
                        INSERT INTO vault_pronouns (
                            src_zh, dst_zh, rel_state, self_vi, target_vi,
                            speech_tone, is_locked, updated_chap
                        )
                        VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                        ON CONFLICT(src_zh, dst_zh, rel_state) DO UPDATE SET
                            self_vi = excluded.self_vi,
                            target_vi = excluded.target_vi,
                            speech_tone = excluded.speech_tone,
                            updated_chap = excluded.updated_chap
                        """,
                        (src_zh, dst_zh, normalized_state, self_vi, target_vi, reason[:40], chap_id)
                    )
                accepted.append(d)

            else:
                rejected.append((d, f"ERR_UNKNOWN_DELTA_TYPE: '{dtype}'"))

        if any(d.get("type") == "NEW_ENT" for d in accepted):
            self.vault.rebuild_automaton()

        return DeltaAuditReport(accepted_deltas=accepted, rejected_deltas=rejected)
