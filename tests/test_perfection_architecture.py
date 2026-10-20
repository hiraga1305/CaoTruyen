# -*- coding: utf-8 -*-
"""Unit tests for Perfection Architecture (Global Entity Vault, Delta Gatekeeper, Two-Phase Zipper)."""

import os
import tempfile
import unittest
from pathlib import Path

from native_oauth.global_vault import GlobalEntityVault
from native_oauth.delta_gatekeeper import DeterministicDeltaGatekeeper, DeltaAuditReport
from native_oauth.zipper_coordinator import TwoPhaseZipperCoordinator


class TestPerfectionArchitecture(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_vault.db"
        self.vault = GlobalEntityVault(db_path=self.db_path)
        self.gatekeeper = DeterministicDeltaGatekeeper(vault=self.vault)

    def tearDown(self):
        self.vault.close()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_01_vault_boomerang_wake_up(self):
        """Characters missing for 200 chapters are immediately awakened with exact locked attributes in O(N)."""
        # Register Protagonist
        self.vault.upsert_locked_entity(
            canonical_zh="萧羽",
            canonical_vi="Tiêu Vũ",
            category="PERSON",
            gender="M",
            narr_lock="hắn",
            persona_tag="Chủ phòng livestream",
            bio_capsule="Nhân vật chính",
            chap_id=1,
            is_locked=1
        )

        # Register secondary character at Chapter 12
        self.vault.upsert_locked_entity(
            canonical_zh="陈建国",
            canonical_vi="Trần Kiến Quốc",
            category="PERSON",
            gender="M",
            narr_lock="gã",
            persona_tag="Khách buôn đồ cổ",
            bio_capsule="Chủ tiệm đồ cổ ở Phan Gia Viên, từng được cứu mạng",
            chap_id=12,
            is_locked=1
        )

        # Register pronoun rule
        with self.vault.conn:
            self.vault.conn.execute(
                """
                INSERT INTO vault_pronouns (src_zh, dst_zh, rel_state, self_vi, target_vi, speech_tone, is_locked, updated_chap)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                ("萧羽", "陈建国", "DEFAULT", "tôi", "chú Trần", "kính trọng, ôn hòa", 12)
            )

        # Simulate Chapter 280 (268 chapters later) where 陈建国 suddenly reappears
        raw_scene_ch280 = "萧羽坐在桌前喝茶，忽然门外传来了急促的敲门声。只见陈建国满头大汗的跑了进来。"

        payload = self.vault.hydrate_for_scene(chap_id=280, raw_zh_scene=raw_scene_ch280)

        # Verification
        self.assertEqual(len(payload.active_entities), 2)
        ent = next(e for e in payload.active_entities if e["zh"] == "陈建国")
        self.assertEqual(ent["vi"], "Trần Kiến Quốc")
        self.assertEqual(ent["narr_lock"], "gã")
        self.assertTrue(any("Trần Kiến Quốc" in b for b in payload.awakened_boomerangs))

        # Check pronoun preservation
        self.assertEqual(len(payload.pronoun_matrix), 1)
        pr = payload.pronoun_matrix[0]
        self.assertEqual(pr["self_vi"], "tôi")
        self.assertEqual(pr["target_vi"], "chú Trần")

    def test_02_pending_omen_trigger(self):
        """Divination predictions emitted earlier are triggered when disaster keywords appear."""
        # Add pending omen at Chapter 5
        with self.vault.conn:
            self.vault.conn.execute(
                """
                INSERT INTO pending_omens (
                    target_zh, target_vi, source_chap, expire_chap,
                    raw_omen_zh, locked_phrasing_vi, trigger_keywords_zh,
                    echo_keywords_vi, status
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'PENDING')
                """,
                (
                    "王大锤", "Vương Đại Chùy", 5, 50,
                    "印堂发黑，三日之内必有血光之灾",
                    "Ấn đường u tối, trong ba ngày ắt có họa huyết quang",
                    "血光,印堂,车祸",
                    "ấn đường u tối / họa huyết quang"
                )
            )

        # Chapter 8 disaster scene
        raw_scene_ch8 = "王大锤在路上出了车祸，头破血流，果然应验了之前萧大师说的血光之灾！"

        payload = self.vault.hydrate_for_scene(chap_id=8, raw_zh_scene=raw_scene_ch8)
        self.assertEqual(len(payload.triggered_omens), 1)
        om = payload.triggered_omens[0]
        self.assertEqual(om["target_vi"], "Vương Đại Chùy")
        self.assertIn("họa huyết quang", om["locked_phrasing_vi"])

    def test_03_delta_gatekeeper_blocks_phantom_entity(self):
        """Delta Gatekeeper must reject ungrounded phantom entities invented by LLM hallucinations."""
        raw_scene = "萧羽站在窗前，看着远处的风景。"

        # Proposed delta contains a phantom entity not in raw text
        bad_deltas = [
            {
                "type": "NEW_ENT",
                "zh": "李逍遥",  # Does NOT exist in raw_scene
                "vi": "Lý Tiêu Dao",
                "narr_lock": "hắn"
            }
        ]

        result = self.gatekeeper.verify_and_commit(chap_id=1, raw_zh_scene=raw_scene, proposed_deltas=bad_deltas)
        self.assertFalse(result.is_pass)
        self.assertEqual(len(result.violations), 1)
        item, reason = result.violations[0]
        self.assertIn("ERR_HALLUCINATED_ZH", reason)

    def test_04_delta_gatekeeper_blocks_locked_pronoun_mutation(self):
        """Delta Gatekeeper must prevent LLM from arbitrarily overwriting locked pronouns without hostile rupture."""
        # Lock pronoun first
        with self.vault.conn:
            self.vault.conn.execute(
                """
                INSERT INTO vault_pronouns (src_zh, dst_zh, rel_state, self_vi, target_vi, speech_tone, is_locked, updated_chap)
                VALUES (?, ?, ?, ?, ?, ?, 1, ?)
                """,
                ("萧羽", "唐小小", "HOSTILE", "tôi", "cô", "ôn hòa", 1)
            )

        # Peaceful raw scene
        raw_scene = "萧羽微笑着对唐小小说话。"

        # LLM tries to mutate pronoun to hostile ta-ngươi without hostile triggers in raw text
        mutated_deltas = [
            {
                "type": "REL_SHIFT",
                "src_zh": "萧羽",
                "dst_zh": "唐小小",
                "state": "HOSTILE",
                "self_vi": "ta",
                "target_vi": "ngươi",
                "reason": "cãi nhau"
            }
        ]

        result = self.gatekeeper.verify_and_commit(chap_id=2, raw_zh_scene=raw_scene, proposed_deltas=mutated_deltas)
        self.assertFalse(result.is_pass)
        item, reason = result.violations[0]
        self.assertTrue("ERR_LOCKED_MATRIX_PROTECTED" in reason or "ERR_FALSE_HOSTILE_SHIFT" in reason)

    def test_05_zipper_prescan_extracts_candidates(self):
        """TwoPhaseZipperCoordinator Phase 1 pre-scans raw chapters and extracts new candidate terms."""
        zipper = TwoPhaseZipperCoordinator(
            vault=self.vault,
            protagonist_zh="萧羽",
            protagonist_vi="Tiêu Vũ",
            llm_micro_caller=None
        )

        test_chapters = [
            (51, "萧羽微笑着连麦下一位水友【爱吃香菜】。对方送出了超级火箭，请教关于《天机宝典》的秘密。"),
            (52, "萧羽拿出了《天机宝典》，准备制符。"),
        ]

        candidates = zipper.phase1_scan_batch_0_token(test_chapters)
        candidate_zhs = [c.zh for c in candidates]
        # Should extract 【爱吃香菜】 (GUEST), 超级火箭 (GIFT), 《天机宝典》 (SKILL)
        self.assertIn("爱吃香菜", candidate_zhs)
        self.assertIn("超级火箭", candidate_zhs)
        self.assertIn("天机宝典", candidate_zhs)


if __name__ == "__main__":
    unittest.main()
