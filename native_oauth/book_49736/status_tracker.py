"""Live status updater and visual dashboard generator for Book 49736 (200 Chapters Campaign)."""
import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from native_oauth.chapter_integrity import read_verified_draft
BOOK_DIR = ROOT / "native_oauth" / "book_49736"
OUTPUT_DIR = BOOK_DIR / "output_dich"
LIVE_STATUS_FILE = BOOK_DIR / "live_status.json"


def calculate_progress(current_wave: int = 12, active_chapter: int = 0, message: str = "", target_chapters: int = 325) -> dict:
    ch_nums = set()
    total_words = 0
    total_paras = 0

    for num in range(1, target_chapters + 1):
        verified = read_verified_draft(BOOK_DIR, num)
        if verified:
            candidate, txt = verified
            ch_nums.add(num)
            total_words += len(txt.split())
            total_paras += len(candidate['bilingual_alignment'])

    completed_count = len(ch_nums)
    percent = round((completed_count / target_chapters) * 100, 1)

    # 25-character progress bar
    filled = int(percent // 4)
    bar = "█" * filled + "░" * (25 - filled)

    total_waves = (target_chapters + 19) // 20
    waves = {}
    for w in range(1, total_waves + 1):
        w_start = (w - 1) * 20 + 1
        w_end = min(w * 20, target_chapters)
        w_total = w_end - w_start + 1
        w_chaps = [c for c in range(w_start, w_end + 1) if c in ch_nums]
        status = "COMPLETED" if len(w_chaps) == w_total else ("IN_PROGRESS" if len(w_chaps) > 0 or w == current_wave else "PENDING")
        waves[f"wave_{w}"] = {
            "name": f"Wave {w}",
            "range": f"Chương {w_start:03d} -> {w_end:03d}",
            "completed": len(w_chaps),
            "total": w_total,
            "status": status,
            "percent": round((len(w_chaps) / w_total) * 100, 1)
        }

    status_data = {
        "scope": "DRAFT_STRUCTURAL_PASS_UNREVIEWED",
        "book_id": "49736",
        "book_title": "Đi Tìm Vô Gian Địa Ngục",
        "current_wave": current_wave,
        "total_waves": total_waves,
        "completed_chapters_count": completed_count,
        "total_target_chapters": target_chapters,
        "percent_complete": percent,
        "progress_bar": bar,
        "total_words": total_words,
        "total_paragraphs": total_paras,
        "waves": waves,
        "latest_completed": sorted(list(ch_nums))[-8:] if ch_nums else [],
        "active_chapter": active_chapter,
        "message": message,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    try:
        LIVE_STATUS_FILE.write_text(json.dumps(status_data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass

    return status_data


def render_terminal_dashboard(data: dict) -> str:
    lines = []
    lines.append("╔════════════════════════════════════════════════════════════════════════════╗")
    lines.append(f"║ CAOTRUYEN V2.0 - TIẾN ĐỘ DỊCH BỘ TRUYỆN: {data['book_title']}          ║")
    lines.append("╠════════════════════════════════════════════════════════════════════════════╣")
    lines.append(f"║ Tổng tiến độ: [{data['progress_bar']}] {data['percent_complete']:>5}% ({data['completed_chapters_count']:>3}/{data['total_target_chapters']}) ║")
    lines.append(f"║ Draft đủ cấu trúc: {data['total_words']:,} từ | {data['total_paragraphs']:,} đoạn | Chưa duyệt nghĩa/văn học ║")
    lines.append("╠════════════════════════════════════════════════════════════════════════════╣")
    lines.append("║ PHÂN BỐ CÁC WAVE (1 -> 10):                                                ║")
    for w_key, w in data["waves"].items():
        st_icon = "🟢 XONG" if w["status"] == "COMPLETED" else ("🟡 ĐANG CHẠY" if w["status"] == "IN_PROGRESS" else "⚪ CHỜ")
        w_filled = int(w['percent'] // 10)
        w_bar = "■" * w_filled + "□" * (10 - w_filled)
        lines.append(f"║  • {w['name']:<7} ({w['range']}): [{w_bar}] {w['completed']:>2}/{w['total']:<2} ({w['percent']:>5}%)  [{st_icon:<10}]  ║")
    lines.append("╚════════════════════════════════════════════════════════════════════════════╝")
    return "\n".join(lines)


if __name__ == "__main__":
    d = calculate_progress(current_wave=6, target_chapters=200)
    print(render_terminal_dashboard(d))
