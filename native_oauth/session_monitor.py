# -*- coding: utf-8 -*-
"""native_oauth/session_monitor.py - Antigravity Live Session Translation Monitor & Generative UI Bridge.
Co-engineered with Gemini 4 Argon & CaoTruyen Sovereign Architecture.

Mandatory module for ALL future translation pipelines and wave orchestrators:
1. Real-time Chapter & Wave Progress Tracking.
2. In-Session Markdown Dashboard & Inline Badges.
3. Interactive Generative UI HTML Artifacts (auto-synced to Antigravity brain/conversation-id).
4. Persisted JSON state for multi-subagent coordination.
"""
from __future__ import annotations

import json
import html as html_escape
import os
import re
import sys
import time
import threading
import warnings
from contextlib import contextmanager
from native_oauth.chapter_integrity import atomic_json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]


def get_active_artifact_dir() -> Path:
    """Discovers the active Antigravity conversation artifact directory."""
    # 1. Check explicit environment variables
    env_dir = os.environ.get("ANTIGRAVITY_ARTIFACT_DIR")
    if env_dir:
        return Path(env_dir)

    # Bind the actual session explicitly; directory mtime cannot identify it.
    conversation = os.environ.get("ANTIGRAVITY_CONVERSATION_ID")
    if conversation and re.fullmatch(r"[A-Za-z0-9_-]+", conversation):
        return Path.home() / ".gemini" / "antigravity" / "brain" / conversation

    # 3. Fallback to repository local artifacts directory
    fallback = ROOT / "audit" / "session_dashboards"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


@contextmanager
def _file_lock(path):
    """Serialize JSON read/modify/write across worker processes."""
    path = Path(str(path) + ".lock")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a+b") as handle:
        handle.seek(0, 2)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


@dataclass
class ChapterExecutionRecord:
    chapter_num: int
    title: str
    wave_num: int
    worker_id: str
    status: str  # "COMPLETED" | "TRANSLATING" | "RETRYING" | "FAILED"
    paragraphs: int
    words: int
    duration_seconds: float
    gate_pass: bool
    prosody_anomalies: int
    timestamp: float = field(default_factory=time.time)


class SessionMonitor:
    """
    Centralized Real-Time Progress Monitor for Antigravity Pairing Sessions.
    Guarantees every wave and chapter is visible directly in the user session.
    """

    _instance: Optional["SessionMonitor"] = None
    _instance_lock = threading.RLock()

    @classmethod
    def get_instance(cls, book_id: str = "49736", book_title: str = "Tác Phẩm") -> "SessionMonitor":
        with cls._instance_lock:
            if cls._instance is None or cls._instance.book_id != str(book_id):
                cls._instance = cls(book_id=book_id, book_title=book_title)
            return cls._instance

    def __init__(self, book_id: str = "49736", book_title: str = "Tác Phẩm", total_chapters: int = 325):
        self._lock = threading.RLock()
        self.completed = {}
        self.stage_states = {}
        self.genre = "Chưa khai báo"
        self.chapter_range = f"1–{total_chapters}"
        self.book_id = str(book_id)
        self.book_title = book_title
        self.total_chapters = total_chapters
        self.artifact_dir = get_active_artifact_dir()
        self.native_artifact_dirs = set()
        self.native_session_order = []
        self.history: List[ChapterExecutionRecord] = []
        self.active_chapter: int = 0
        self.active_wave: int = 0
        self.total_waves: int = max(1, (total_chapters + 4) // 5)
        self.active_workers: Dict[str, Dict[str, Any]] = {}
        self.total_words_accumulated: int = 0
        self.total_paras_accumulated: int = 0
        self.start_timestamp: float = time.time()
        self.state_file = ROOT / "native_oauth" / f"book_{self.book_id}" / "session_monitor_state.json"
        self._load_previous_state()

    def _load_previous_state(self):
        if not self.state_file.exists():
            return
        data = json.loads(self.state_file.read_text(encoding="utf-8"))
        # Legacy max(active chapter) and accumulated totals cannot prove completion.
        if data.get("version") != 2:
            return
        self.completed = data.get("completed", {})
        self.stage_states = data.get("stage_states", {})
        self.active_workers = data.get("workers", {})
        self.active_chapter = data.get("active_chapter", 0)
        self.active_wave = data.get("active_wave", 0)
        self.history = [ChapterExecutionRecord(**row) for row in data.get("recent_records", [])]
        self.total_words_accumulated = sum(r["words"] for r in self.completed.values())
        self.total_paras_accumulated = sum(r["paragraphs"] for r in self.completed.values())

    @property
    def completed_count(self):
        return len(self.completed)

    def record_chapter_done(
        self,
        chapter_num: int,
        title: str,
        wave_num: int,
        worker_id: str,
        paragraphs: int,
        words: int,
        duration_seconds: float,
        gate_pass: bool = True,
        prosody_anomalies: int = 0
    ) -> ChapterExecutionRecord:
        """Records the completion of a chapter and synchronizes all session dashboards."""
        with self._lock, _file_lock(self.state_file):
            self._load_previous_state()
            rec = ChapterExecutionRecord(
                chapter_num, title, wave_num, worker_id,
                "COMPLETED" if gate_pass else "FAILED", paragraphs, words,
                duration_seconds, gate_pass, prosody_anomalies)
            self.history.append(rec)
            self.active_chapter = chapter_num
            self.active_wave = wave_num
            if gate_pass:
                self.completed[str(chapter_num)] = asdict(rec)
            else:
                self.completed.pop(str(chapter_num), None)
            self.total_words_accumulated = sum(r["words"] for r in self.completed.values())
            self.total_paras_accumulated = sum(r["paragraphs"] for r in self.completed.values())
            self.active_workers[worker_id] = {
                "worker_id": worker_id, "last_chapter": chapter_num, "last_title": title,
                "status": "IDLE" if gate_pass else "FAILED", "last_duration": duration_seconds,
                "updated_at": time.time()}
            self.save_state()
            self.sync_session_artifacts()
            return rec

    def record_worker_active(self, worker_id: str, chapter_num: int, wave_num: int, message: str = "Translating"):
        with self._lock, _file_lock(self.state_file):
            self._load_previous_state()
            self.active_workers[worker_id] = {
                "worker_id": worker_id,
                "current_chapter": chapter_num,
                "wave_num": wave_num,
                "status": "BUSY",
                "message": message,
                "updated_at": time.time()
            }
            self.active_chapter = chapter_num
            self.active_wave = wave_num
            self.save_state()
            self.sync_session_artifacts()

    def save_state(self):
        state = {
            "version": 2,
            "completed": self.completed,
            "stage_states": self.stage_states,
            "book_id": self.book_id,
            "book_title": self.book_title,
            "total_chapters": self.total_chapters,
            "active_chapter": self.active_chapter,
            "active_wave": self.active_wave,
            "total_waves": self.total_waves,
            "total_words_accumulated": self.total_words_accumulated,
            "total_paras_accumulated": self.total_paras_accumulated,
            "workers": self.active_workers,
            "recent_records": [asdict(r) for r in self.history[-15:]],
            "last_updated": time.strftime("%Y-%m-%dT%H:%M:%S%z")
        }
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        atomic_json(self.state_file, state)

    def record_stage_result(self, chapter_num, stage, worker_id, status):
        """Review/approval stages do not inflate translated chapter totals."""
        with self._lock, _file_lock(self.state_file):
            self._load_previous_state()
            self.stage_states[f'{chapter_num}:{stage}'] = status
            self.active_workers[worker_id] = {
                'worker_id': worker_id, 'last_chapter': chapter_num,
                'status': 'FAILED' if status == 'BLOCKED' else 'IDLE',
                'message': stage + ': ' + status, 'updated_at': time.time()}
            self.save_state()
            self.sync_session_artifacts()

    def render_markdown_badge(self) -> str:
        """Compact markdown status card for chat replies."""
        pct = (self.completed_count / float(self.total_chapters)) * 100.0 if self.total_chapters > 0 else 0.0
        filled = int(pct // 4)
        bar = "█" * filled + "░" * (25 - filled)
        
        lines = [
            f"**[TIẾN ĐỘ SESSION ANTIGRAVITY] — {self.book_title}**",
            f"- **Tiến độ**: `[{bar}]` **{pct:.1f}%** ({self.completed_count}/{self.total_chapters} chương đã qua kiểm tra cấu trúc)",
            f"- **Wave hiện tại**: Wave **{self.active_wave}** / {self.total_waves} | **Tổng từ**: {self.total_words_accumulated:,} từ",
            f"- **Thể loại**: {self.genre} | **Khoảng chương**: {self.chapter_range} | **Chương hiện tại**: {self.active_chapter}",
            f"- **Tổng đoạn**: {self.total_paras_accumulated:,} | **Workers**: " + ", ".join(f"{wid}: {w['status']}" for wid, w in self.visible_workers()),
            "- **Duyệt nghĩa/văn học**: xem evidence riêng; tiến độ này chỉ kiểm cấu trúc."
        ]
        lines.append('- **Các giai đoạn**: ' + (', '.join(f'{k}: {v}' for k, v in list(self.stage_states.items())[-8:]) or 'Chưa chạy review'))
        return "\n".join(lines)

    def visible_workers(self):
        active=[item for item in self.active_workers.items() if item[1].get('status')=='BUSY']
        recent=sorted((item for item in self.active_workers.items() if item[1].get('status')!='BUSY'),
                      key=lambda item:item[1].get('updated_at',0),reverse=True)[:max(0,8-len(active))]
        return sorted(active+recent)

    def render_html_widget(self) -> str:
        """Self-contained Generative UI HTML card conforming to Antigravity theme variables."""
        pct = (self.completed_count / float(self.total_chapters)) * 100.0 if self.total_chapters > 0 else 0.0
        pct_formatted = f"{pct:.1f}%"

        worker_rows = ""
        for wid, wdata in sorted(self.active_workers.items()):
            status_color = "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" if wdata.get("status") == "IDLE" else "bg-amber-500/20 text-amber-400 border-amber-500/30"
            if wdata.get("status") == "FAILED":
                status_color = "bg-red-500/20 text-red-400 border-red-500/30"
            status_text = {"IDLE": "Hoàn tất cấu trúc", "BUSY": "Đang biên dịch", "FAILED": "Bị chặn"}.get(wdata.get("status"), "Chưa rõ")
            ch_info = f"Chương {wdata.get('last_chapter') or wdata.get('current_chapter') or '—'}"
            worker_rows += f"""
            <div class="flex items-center justify-between py-2 border-b border-[var(--border)] last:border-0 text-sm">
              <div class="flex items-center gap-2">
                <span class="w-2.5 h-2.5 rounded-full {'bg-emerald-400 animate-pulse' if wdata.get('status') != 'IDLE' else 'bg-slate-400'}"></span>
                <span class="font-medium text-[var(--foreground)]">{wid}</span>
                <span class="text-xs text-[var(--muted-foreground)]">({ch_info})</span>
              </div>
              <span class="px-2 py-0.5 rounded text-xs border {status_color}">{status_text}</span>
            </div>
            """

        recent_rows = ""
        for r in reversed(self.history[-5:]):
            gate_badge = '<span class="text-xs text-emerald-400">PASS</span>' if r.gate_pass else '<span class="text-xs text-red-400">FAILED</span>'
            recent_rows += f"""
            <tr class="text-xs border-b border-[var(--border)] last:border-0">
              <td class="py-1.5 font-mono text-[var(--foreground)]">Ch.{r.chapter_num:04d}</td>
              <td class="py-1.5 text-[var(--muted-foreground)] truncate max-w-[140px]">{r.title}</td>
              <td class="py-1.5 text-right font-mono text-[var(--foreground)]">{r.words} từ</td>
              <td class="py-1.5 text-right text-[var(--muted-foreground)]">{r.duration_seconds:.1f}s</td>
              <td class="py-1.5 text-center">{gate_badge}</td>
            </tr>
            """

        html = f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <script src="https://www.gstatic.com/antigravity/web/dev/tailwindcss.min.js"></script>
</head>
<body class="bg-transparent text-[var(--foreground)] antialiased p-4">
  <div class="bg-[var(--card)] text-[var(--foreground)] border border-[var(--border)] rounded-xl p-5 shadow-sm max-w-xl mx-auto">
    <!-- Header -->
    <div class="flex items-center justify-between pb-3 border-b border-[var(--border)]">
      <div>
        <div class="flex items-center gap-2">
          <span class="inline-block w-2.5 h-2.5 rounded-full bg-blue-500 animate-ping"></span>
          <h2 class="text-base font-semibold text-[var(--foreground)]">{self.book_title}</h2>
        </div>
        <p class="text-xs text-[var(--muted-foreground)] mt-0.5">Sovereign Translation Wave Orchestrator • Antigravity Live</p>
      </div>
      <div class="text-right">
        <span class="text-lg font-bold text-blue-500">{pct_formatted}</span>
        <div class="text-[11px] text-[var(--muted-foreground)]">{self.completed_count}/{self.total_chapters} ch</div>
      </div>
    </div>

    <!-- Progress Bar -->
    <div class="mt-4">
      <div class="w-full bg-[var(--border)] h-2.5 rounded-full overflow-hidden">
        <div class="bg-gradient-to-r from-blue-500 to-indigo-500 h-2.5 rounded-full transition-all duration-500" style="width: {pct_formatted}"></div>
      </div>
      <div class="flex justify-between items-center text-xs text-[var(--muted-foreground)] mt-1.5">
        <span>Wave hiện tại: <strong>Wave {self.active_wave} / {self.total_waves}</strong></span>
        <span>Tổng số từ: <strong>{self.total_words_accumulated:,}</strong></span>
      </div>
    </div>

    <div class="mt-3 text-xs">{html_escape.escape(self.render_markdown_badge().splitlines()[-1])}</div>
    <!-- Active Workers -->
    <div class="mt-4 bg-[var(--background)]/50 rounded-lg p-3 border border-[var(--border)]">
      <div class="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)] mb-1">Trạng thái Workers song song</div>
      {worker_rows or '<div class="text-xs text-[var(--muted-foreground)] py-1">Sẵn sàng điều phối</div>'}
    </div>

    <!-- Recent Chapters Table -->
    <div class="mt-4">
      <div class="text-xs font-semibold uppercase tracking-wider text-[var(--muted-foreground)] mb-2">Chương hoàn thành gần nhất</div>
      <table class="w-full text-left">
        <thead>
          <tr class="text-[11px] text-[var(--muted-foreground)] border-b border-[var(--border)]">
            <th class="pb-1">Chương</th>
            <th class="pb-1">Tiêu đề</th>
            <th class="pb-1 text-right">Dung lượng</th>
            <th class="pb-1 text-right">Thời gian</th>
            <th class="pb-1 text-center">Gate</th>
          </tr>
        </thead>
        <tbody>
          {recent_rows or '<tr><td colspan="5" class="text-xs text-center py-2 text-[var(--muted-foreground)]">Chưa có dữ liệu</td></tr>'}
        </tbody>
      </table>
    </div>
  </div>
</body>
</html>
"""
        return html

    def render_markdown_dashboard_artifact(self) -> str:
        """Full Markdown dashboard document for saving into brain artifact directory."""
        pct = (self.completed_count / float(self.total_chapters)) * 100.0 if self.total_chapters > 0 else 0.0
        filled = int(pct // 4)
        bar = "█" * filled + "░" * (25 - filled)

        lines = [
            f"# Bảng Điều Khiển Tiến Độ Biên Dịch Antigravity: {self.book_title}",
            "",
            f"> **Thời gian cập nhật**: {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
            f"> **Tiến độ toàn cục**: `[{bar}]` **{pct:.1f}%** ({self.completed_count} / {self.total_chapters} chương)",
            "",
            "## 1. Thông Số Điều Phối Phiên Làm Việc (Session Stats)",
            "",
            f"- **Tác phẩm**: {self.book_title} (ID: `{self.book_id}`)",
            f"- **Wave hiện tại**: Wave **{self.active_wave}** / {self.total_waves}",
            f"- **Tổng số từ tích lũy**: **{self.total_words_accumulated:,}** từ",
            f"- **Tổng số đoạn văn**: **{self.total_paras_accumulated:,}** đoạn",
            f"- **Thời gian khởi động session**: {time.strftime('%H:%M:%S', time.localtime(self.start_timestamp))}",
            "",
            "## 2. Trạng Thái Workers Song Song",
            "",
            "| Worker ID | Trạng Thái | Chương Đang Xử Lý / Vừa Xong | Thời Gian Gần Nhất |",
            "| :--- | :---: | :--- | :---: |"
        ]

        if self.active_workers:
            for wid, wdata in sorted(self.active_workers.items()):
                ch = wdata.get("current_chapter") or wdata.get("last_chapter") or "—"
                dur = f"{wdata.get('last_duration', 0):.1f}s" if "last_duration" in wdata else "Đang chạy..."
                st = {"BUSY": "ĐANG CHẠY", "IDLE": "SẴN SÀNG", "FAILED": "BỊ CHẶN"}.get(wdata.get("status"), "CHƯA RÕ")
                lines.append(f"| `{wid}` | `{st}` | Chương {ch} | {dur} |")
        else:
            lines.append("| `Worker-Pool` | `IDLE` | Sẵn sàng điều phối | — |")

        lines.extend([
            "",
            "## 3. Nhật Ký 10 Chương Vừa Dịch Gần Nhất",
            "",
            "| Chương | Tiêu Đề | Dung Lượng | Thời Gian | Quality Gate | Âm Vận Lỗi |",
            "| :---: | :--- | :---: | :---: | :---: | :---: |"
        ])

        if self.history:
            for r in reversed(self.history[-10:]):
                gate_str = "STRUCTURAL_PASS" if r.gate_pass else "FAILED"
                lines.append(f"| Ch.{r.chapter_num:04d} | {r.title} | {r.words} từ | {r.duration_seconds:.1f}s | `{gate_str}` | {r.prosody_anomalies} |")
        else:
            lines.append("| — | Chưa có bản ghi | — | — | — | — |")

        lines.extend(["", self.render_markdown_badge().splitlines()[-1], ""])
        return "\n".join(lines)

    def sync_session_artifacts(self):
        """Writes both Markdown and HTML dashboards into Antigravity conversation artifact directory."""
        try:
            from native_oauth.workflow_io import atomic_text
            for directory in self.native_artifact_dirs | {self.artifact_dir}:
                directory.mkdir(parents=True, exist_ok=True)
                atomic_text(directory/"translation_live_dashboard.html", self.render_html_widget())
                atomic_text(directory/"translation_session_dashboard.md", self.render_markdown_dashboard_artifact())
        except Exception as e:
            # Non-blocking error logging
            warnings.warn(f"Session dashboard sync failed: {e}", RuntimeWarning)


# Global singleton access
def get_session_monitor(book_id: str = "49736", book_title: str = "Tác Phẩm", total_chapters: int = 325) -> SessionMonitor:
    mon = SessionMonitor.get_instance(book_id=book_id, book_title=book_title)
    mon.total_chapters = total_chapters
    mon.total_waves = max(1, (total_chapters + 4) // 5)
    return mon
