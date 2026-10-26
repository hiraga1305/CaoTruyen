# tests/test_session_monitor.py
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import native_oauth.session_monitor as monitor_module

from native_oauth.session_monitor import SessionMonitor, ChapterExecutionRecord


class TestSessionMonitor(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        for setting in (patch.object(monitor_module, 'ROOT', Path(self.tmp_dir.name)),
                        patch.object(monitor_module, 'get_active_artifact_dir', return_value=Path(self.tmp_dir.name))):
            setting.start()
            self.addCleanup(setting.stop)
        self.mon = SessionMonitor(book_id="test_book", book_title="Test Novel Title", total_chapters=50)
        self.mon.artifact_dir = Path(self.tmp_dir.name)
        self.mon.state_file = Path(self.tmp_dir.name) / "test_state.json"

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_record_chapter_and_progress_calculation(self):
        self.mon.record_chapter_done(
            chapter_num=1,
            title="Khởi Đầu",
            wave_num=1,
            worker_id="Worker-1",
            paragraphs=50,
            words=1500,
            duration_seconds=12.5,
            gate_pass=True,
            prosody_anomalies=0
        )
        self.assertEqual(self.mon.active_chapter, 1)
        self.assertEqual(self.mon.active_wave, 1)
        self.assertEqual(self.mon.total_words_accumulated, 1500)
        self.assertEqual(self.mon.total_paras_accumulated, 50)
        self.assertTrue(self.mon.state_file.exists())

    def test_markdown_badge_and_dashboard_rendering(self):
        self.mon.record_chapter_done(
            chapter_num=25,
            title="Giữa Trận",
            wave_num=5,
            worker_id="Worker-2",
            paragraphs=80,
            words=2400,
            duration_seconds=15.0,
            gate_pass=True,
            prosody_anomalies=0
        )
        badge = self.mon.render_markdown_badge()
        self.assertIn("TIẾN ĐỘ SESSION ANTIGRAVITY", badge)
        # Completing chapter 25 proves ONE chapter, not chapters 1 through 25.
        self.assertIn("2.0%", badge)
        self.assertIn("1/50 chương", badge)

        doc = self.mon.render_markdown_dashboard_artifact()
        self.assertIn("# Bảng Điều Khiển Tiến Độ Biên Dịch Antigravity", doc)
        self.assertIn("Test Novel Title", doc)
        self.assertIn("Wave **5**", doc)

    def test_html_widget_generative_ui(self):
        self.mon.record_chapter_done(
            chapter_num=10,
            title="Đoán Mệnh",
            wave_num=2,
            worker_id="Worker-1",
            paragraphs=45,
            words=1200,
            duration_seconds=10.0,
            gate_pass=True,
            prosody_anomalies=0
        )
        html = self.mon.render_html_widget()
        self.assertIn("tailwindcss.min.js", html)
        self.assertIn("var(--card)", html)
        self.assertIn("Test Novel Title", html)
        self.assertIn("2.0%", html)

    def test_verified_prefix_counts_without_inventing_latency_or_missing_chapters(self):
        self.mon.sync_approved_prefix([{'chapter_num':1,'title':'Đã duyệt','paragraphs':4,'words':40,'evidence_path':'fixture'}])
        self.assertEqual(self.mon.completed_count,1)
        self.assertEqual(self.mon.total_words_accumulated,40)
        self.assertIsNone(self.mon.completed['1']['duration_seconds'])
        self.assertEqual(self.mon.history,[])
        self.assertNotIn('2',self.mon.completed)
        self.assertIn('2.0%',self.mon.render_markdown_badge())

    def test_sync_artifacts(self):
        self.mon.record_chapter_done(
            chapter_num=5,
            title="Vô Gian",
            wave_num=1,
            worker_id="Worker-1",
            paragraphs=40,
            words=1100,
            duration_seconds=8.0,
            gate_pass=True,
            prosody_anomalies=0
        )
        html_f = self.mon.artifact_dir / "translation_live_dashboard.html"
        md_f = self.mon.artifact_dir / "translation_session_dashboard.md"
        self.assertTrue(html_f.exists())
        self.assertTrue(md_f.exists())
        self.assertGreater(html_f.stat().st_size, 500)
        self.assertGreater(md_f.stat().st_size, 200)

    def test_dashboard_separates_draft_wait_and_approval_without_relabeling_old_records(self):
        self.mon.record_chapter_done(1,'Native approved',1,'batch',3,30,40.0,True,
            draft_seconds=10.0,post_draft_seconds=30.0,approval_mode='native_batch')
        doc=self.mon.render_markdown_dashboard_artifact()
        self.assertIn('Tạo nháp',doc);self.assertIn('Nháp → duyệt',doc);self.assertIn('Đến khi duyệt',doc)
        self.assertIn('10.0s | 30.0s | 40.0s',doc);self.assertIn('NATIVE_BATCH_PASS',doc)
        old=SessionMonitor('test_book','Test',50,state_file=self.mon.state_file)
        self.assertEqual(old.history[-1].draft_seconds,10.0)
        self.mon.record_chapter_done(2,'Legacy structural',1,'legacy',1,10,12.0,True)
        doc=self.mon.render_markdown_dashboard_artifact()
        self.assertIn('— | — | 12.0s',doc);self.assertIn('STRUCTURAL_PASS',doc)


if __name__ == "__main__":
    unittest.main()
