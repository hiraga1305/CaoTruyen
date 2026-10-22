"""
tests/test_wave_orchestrator.py - Unit tests for 5-Chapter Wave Orchestrator,
Multi-Epoch Pronoun Morphing, Seam Verifier, and Dashboard Telemetry.
Co-engineered with Gemini 4 Argon.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import native_oauth.session_monitor as monitor_module

from native_oauth.global_vault import GlobalEntityVault
from native_oauth.zipper_coordinator import TwoPhaseZipperCoordinator
from native_oauth.delta_gatekeeper import DeterministicDeltaGatekeeper
from native_oauth.wave_orchestrator import (
    WaveOrchestrator,
    WorldEpoch,
    LexicalDensityClassifier,
    SeamVerifier,
    SubagentWorkerTask,
)


class TestWaveOrchestrator(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        for setting in (patch.object(monitor_module, 'ROOT', Path(self.temp_dir.name)),
                        patch.object(monitor_module, 'get_active_artifact_dir', return_value=Path(self.temp_dir.name)),
                        patch.object(monitor_module.SessionMonitor, '_instance', None)):
            setting.start()
            self.addCleanup(setting.stop)
        self.db_path = os.path.join(self.temp_dir.name, "test_vault.sqlite")
        self.vault = GlobalEntityVault(self.db_path)
        self.coordinator = TwoPhaseZipperCoordinator(
            vault=self.vault,
            protagonist_zh="李凡",
            protagonist_vi="Lý Phàm",
            llm_micro_caller=lambda p, s: "ENT|mock",
        )
        self.gatekeeper = DeterministicDeltaGatekeeper(self.vault)
        self.orchestrator = WaveOrchestrator(
            novel_id="test_novel_01",
            vault=self.vault,
            coordinator=self.coordinator,
            gatekeeper=self.gatekeeper,
            initial_epoch=WorldEpoch.URBAN_MODERN,
        )

    def tearDown(self):
        self.vault.close()
        self.temp_dir.cleanup()

    def test_01_partition_5_chapters_per_subagent(self):
        """50 chapters must be partitioned into exactly 10 Subagents of 5 chapters each."""
        mock_chapters = [
            {"chapter_number": i, "title_zh": f"第{i}章", "raw_text_zh": f"这是第{i}章的内容。"}
            for i in range(1, 51)
        ]
        waves = self.orchestrator.partition_into_waves(mock_chapters, workers_per_wave=5)
        # 10 workers total, 5 per wave = 2 waves
        self.assertEqual(len(waves), 2)
        total_workers = sum(len(w) for w in waves)
        self.assertEqual(total_workers, 10)

        # Every worker has exactly 5 chapters
        for wave in waves:
            for worker in wave:
                self.assertEqual(worker.chapter_count, 5)
                self.assertEqual(len(worker.raw_chapters), 5)

        # Verify contiguous chapter boundaries
        self.assertEqual(waves[0][0].start_chapter, 1)
        self.assertEqual(waves[0][0].end_chapter, 5)
        self.assertEqual(waves[0][1].start_chapter, 6)
        self.assertEqual(waves[0][1].end_chapter, 10)
        self.assertEqual(waves[1][-1].start_chapter, 46)
        self.assertEqual(waves[1][-1].end_chapter, 50)

    def test_02_lexical_density_classifier_detects_epoch_shift(self):
        """LexicalDensityClassifier accurately detects world transition from Urban to Xianxia."""
        urban_text = "李明在公司写字楼里，拿起手机给老板发了一条微信，然后开着汽车回家。"
        shift_score_urban, epoch_urban = LexicalDensityClassifier.calculate_shift_score(urban_text)
        self.assertEqual(epoch_urban, WorldEpoch.URBAN_MODERN)

        # Text with cultivation keywords + spatial teleportation + power breakthrough
        cultivation_text = (
            "林枫站在古老传送阵中央，四周灵气轰然爆发。他运转玄天功，吞下一枚筑基丹，"
            "丹田气海沸腾，冲破桎梏，成功突破到了筑基期！"
        )
        shift_score_xianxia, epoch_xianxia = LexicalDensityClassifier.calculate_shift_score(cultivation_text)
        self.assertEqual(epoch_xianxia, WorldEpoch.XIANXIA_IMMORTAL)
        self.assertGreaterEqual(shift_score_xianxia, 0.35)

    def test_03_pronoun_matrix_morphs_across_epochs(self):
        """Directed pronoun rules automatically adapt surfaces when epoch changes."""
        urban_pronouns = self.orchestrator.get_resolved_pronouns_for_epoch(WorldEpoch.URBAN_MODERN)
        self.assertIn("PEER_STRANGER", urban_pronouns)
        self.assertEqual(urban_pronouns["PEER_STRANGER"], ("tôi", "anh/cô"))
        self.assertEqual(urban_pronouns["HOSTILE_SUPERIOR"], ("tao", "mày"))

        # Transition to XIANXIA_IMMORTAL
        xianxia_pronouns = self.orchestrator.get_resolved_pronouns_for_epoch(WorldEpoch.XIANXIA_IMMORTAL)
        self.assertEqual(xianxia_pronouns["PEER_STRANGER"], ("tại hạ", "đạo hữu"))
        self.assertEqual(xianxia_pronouns["HOSTILE_SUPERIOR"], ("bản tọa/lão tổ", "nghiệt súc/tiểu tử"))
        self.assertEqual(xianxia_pronouns["MASTER_DISCIPLE"], ("vi sư/bản tôn", "đồ nhi"))

    def test_04_seam_verifier_and_micro_surgical_stitch(self):
        """SeamVerifier detects boundary drift between Ch 5 and Ch 6 and micro-stitches successfully."""
        task_1 = SubagentWorkerTask(worker_id="SUB_01", wave_id=1, start_chapter=1, end_chapter=5)
        task_2 = SubagentWorkerTask(worker_id="SUB_02", wave_id=1, start_chapter=6, end_chapter=10)

        # Worker 1 ending of Chapter 5 in Xianxia tone
        task_1.result_chapters = [{
            "chapter_number": 5,
            "text_vn": "Lâm Phong nhìn sang đối phương, lạnh lùng nói: 'Ta sẽ đến tìm đạo hữu.'",
            "entities_observed": {"林枫": "Lâm Phong", "李华": "Lý Hoa"},
            "active_pronouns": {"PEER_STRANGER": "ta / đạo hữu"},
        }]

        # Worker 2 beginning of Chapter 6 with slight pronoun drift (e.g. translated as 'tôi / anh')
        task_2.result_chapters = [{
            "chapter_number": 6,
            "text_vn": "Tôi nhìn quanh sơn cốc, cảm thấy anh ta vẫn chưa rời đi.",
            "entities_observed": {"林枫": "Lâm Phong", "李华": "Lý Hoa"},
            "active_pronouns": {"PEER_STRANGER": "tôi / anh"},
        }]

        drift_score, action = self.orchestrator.execute_seam_verification(task_1, task_2)
        # Pronoun conflict should produce drift score in (0.15, 0.50]
        self.assertGreater(drift_score, 0.15)
        self.assertEqual(action, "MICRO_SURGICAL_STITCHED")

        # Verify that Chapter 6 was micro-stitched deterministically
        stitched_text = task_2.result_chapters[0]["text_vn"]
        self.assertIn("Ta", stitched_text)
        self.assertIn("đạo hữu", stitched_text)
        self.assertNotIn("Tôi", stitched_text)

    def test_05_dashboard_state_schema(self):
        """Exported dashboard state must contain all fields required for Generative UI."""
        mock_chapters = [
            {"chapter_number": i, "title_zh": f"第{i}章", "raw_text_zh": f"内容{i}"}
            for i in range(1, 11)
        ]
        self.orchestrator.partition_into_waves(mock_chapters, workers_per_wave=2)
        state = self.orchestrator.export_dashboard_state(
            current_wave_idx=1,
            total_waves=2,
            novel_title="Kiểm Thử Bá Chủ Đô Thị"
        )

        self.assertIn("session_id", state)
        self.assertIn("wave_metadata", state)
        self.assertIn("context_anchor", state)
        self.assertIn("subagents", state)
        self.assertIn("drift_alerts", state)
        self.assertEqual(len(state["subagents"]), 2)
        self.assertEqual(state["subagents"][0]["assigned_range"], [1, 5])
        self.assertEqual(state["subagents"][1]["assigned_range"], [6, 10])


if __name__ == "__main__":
    unittest.main()
