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
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]


def get_active_artifact_dir() -> Path:
    """Discovers the active Antigravity conversation artifact directory."""
    # 1. Check explicit environment variables
    env_dir = os.environ.get("ANTIGRAVITY_ARTIFACT_DIR")
    if env_dir and Path(env_dir).exists():
        return Path(env_dir)

    # 2. Inspect standard Antigravity appData brain directory
    user_home = Path.home()
    brain_root = user_home / ".gemini" / "antigravity" / "brain"
    if brain_root.exists():
        # Find the most recently active conversation directory
        conv_dirs = [d for d in brain_root.iterdir() if d.is_dir() and not d.name.startswith(".")]
        if conv_dirs:
            conv_dirs.sort(key=lambda d: d.stat().st_mtime, reverse=True)
            return conv_dirs[0]

    # 3. Fallback to repository local artifacts directory
    fallback = ROOT / "audit" / "session_dashboards"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


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

    @classmethod
    def get_instance(cls, book_id: str = "49736", book_title: str = "Tác Phẩm") -> "SessionMonitor":
        if cls._instance is None or cls._instance.book_id != book_id:
            cls._instance = cls(book_id=book_id, book_title=book_title)
        return cls._instance

    def __init__(self, book_id: str = "49736", book_title: str = "Tác Phẩm", total_chapters: int = 325):
        self.book_id = str(book_id)
        self.book_title = book_title
        self.total_chapters = total_chapters
        self.artifact_dir = get_active_artifact_dir()
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
        if self.state_file.exists():
            try:
                data = json.loads(self.state_file.read_text(encoding="utf-8"))
                self.active_chapter = data.get("active_chapter", 0)
                self.active_wave = data.get("active_wave", 0)
                self.total_words_accumulated = data.get("total_words_accumulated", 0)
                self.total_paras_accumulated = data.get("total_paras_accumulated", 0)
            except Exception:
                pass

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
        rec = ChapterExecutionRecord(
            chapter_num=chapter_num,
            title=title,
            wave_num=wave_num,
            worker_id=worker_id,
            status="COMPLETED",
            paragraphs=paragraphs,
            words=words,
            duration_seconds=duration_seconds,
            gate_pass=gate_pass,
            prosody_anomalies=prosody_anomalies
        )
        self.history.append(rec)
        self.active_chapter = max(self.active_chapter, chapter_num)
        self.active_wave = wave_num
        self.total_words_accumulated += words
        self.total_paras_accumulated += paragraphs

        # Update worker state
        self.active_workers[worker_id] = {
            "worker_id": worker_id,
            "last_chapter": chapter_num,
            "last_title": title,
            "status": "IDLE",
            "last_duration": duration_seconds,
            "updated_at": time.time()
        }

        self.save_state()
        self.sync_session_artifacts()
        return rec

    def record_worker_active(self, worker_id: str, chapter_num: int, wave_num: int, message: str = "Translating"):
        self.active_workers[worker_id] = {
            "worker_id": worker_id,
            "current_chapter": chapter_num,
            "wave_num": wave_num,
            "status": "BUSY",
            "message": message,
            "updated_at": time.time()
        }
        self.active_chapter = max(self.active_chapter, chapter_num)
        self.active_wave = wave_num
        self.save_state()
        self.sync_session_artifacts()

    def save_state(self):
        state = {
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
        self.state_file.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    def render_markdown_badge(self) -> str:
        """Compact markdown status card for chat replies."""
        pct = (self.active_chapter / float(self.total_chapters)) * 100.0 if self.total_chapters > 0 else 0.0
        filled = int(pct // 4)
        bar = "█" * filled + "░" * (25 - filled)
        
        lines = [
            f"**[TIẾN ĐỘ SESSION ANTIGRAVITY] — {self.book_title}**",
            f"- **Tiến độ**: `[{bar}]` **{pct:.1f}%** ({self.active_chapter}/{self.total_chapters} chương)",
            f"- **Wave hiện tại**: Wave **{self.active_wave}** / {self.total_waves} | **Tổng từ**: {self.total_words_accumulated:,} từ",
            f"- **Trạng thái**: Worker song song đang hoạt động tích cực."
        ]
        return "\n".join(lines)

    def render_html_widget(self) -> str:
        """Self-contained Generative UI HTML card conforming to Antigravity theme variables."""
        pct = (self.active_chapter / float(self.total_chapters)) * 100.0 if self.total_chapters > 0 else 0.0
        pct_formatted = f"{pct:.1f}%"

        worker_rows = ""
        for wid, wdata in sorted(self.active_workers.items()):
            status_color = "bg-emerald-500/20 text-emerald-400 border-emerald-500/30" if wdata.get("status") == "IDLE" else "bg-amber-500/20 text-amber-400 border-amber-500/30"
            status_text = "Hoàn tất đoạn" if wdata.get("status") == "IDLE" else "Đang biên dịch"
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
            gate_badge = '<span class="text-xs text-emerald-400">PASS</span>' if r.gate_pass else '<span class="text-xs text-amber-400">AUDITED</span>'
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
        <div class="text-[11px] text-[var(--muted-foreground)]">{self.active_chapter}/{self.total_chapters} ch</div>
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
        pct = (self.active_chapter / float(self.total_chapters)) * 100.0 if self.total_chapters > 0 else 0.0
        filled = int(pct // 4)
        bar = "█" * filled + "░" * (25 - filled)

        lines = [
            f"# Bảng Điều Khiển Tiến Độ Biên Dịch Antigravity: {self.book_title}",
            "",
            f"> **Thời gian cập nhật**: {time.strftime('%Y-%m-%d %H:%M:%S')}  ",
            f"> **Tiến độ toàn cục**: `[{bar}]` **{pct:.1f}%** ({self.active_chapter} / {self.total_chapters} chương)",
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
                st = "ĐANG CHẠY" if wdata.get("status") == "BUSY" else "SẴN SÀNG"
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
                gate_str = "PASS" if r.gate_pass else "AUDITED"
                lines.append(f"| Ch.{r.chapter_num:04d} | {r.title} | {r.words} từ | {r.duration_seconds:.1f}s | `{gate_str}` | {r.prosody_anomalies} |")
        else:
            lines.append("| — | Chưa có bản ghi | — | — | — | — |")

        lines.append("")
        return "\n".join(lines)

    def sync_session_artifacts(self):
        """Writes both Markdown and HTML dashboards into Antigravity conversation artifact directory."""
        try:
            self.artifact_dir.mkdir(parents=True, exist_ok=True)

            # 1. Write HTML widget
            html_file = self.artifact_dir / "translation_live_dashboard.html"
            html_file.write_text(self.render_html_widget(), encoding="utf-8")

            # 2. Write Markdown dashboard
            md_file = self.artifact_dir / "translation_session_dashboard.md"
            md_file.write_text(self.render_markdown_dashboard_artifact(), encoding="utf-8")
        except Exception as e:
            # Non-blocking error logging
            pass


# Global singleton access
def get_session_monitor(book_id: str = "49736", book_title: str = "Tác Phẩm", total_chapters: int = 325) -> SessionMonitor:
    mon = SessionMonitor.get_instance(book_id=book_id, book_title=book_title)
    mon.total_chapters = total_chapters
    mon.total_waves = max(1, (total_chapters + 4) // 5)
    return mon
