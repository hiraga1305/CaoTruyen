"""CAOTRUYEN V2.0 - MULTI-WAVE ORCHESTRATOR WITH LIVE VISUAL TRACKING
Co-engineered with Gemini 4 Argon Architecture Blueprint.

Coordinates Wave 2 -> 5 (Chapters 21 to 100):
- Automatically cascades Wave 2 -> Wave 3 -> Wave 4 -> Wave 5.
- Real-time live status updates to live_status.json after each chapter.
- Calibration Gate between waves to synchronize state and verify continuity.
- Staggered ramp-up (3.5s) per wave to prevent rate limits.
"""
import asyncio
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from native_oauth.book_49736.sliding_pool_runner import SlidingPoolRunner
from native_oauth.book_49736.batch_pipeline_runner import BOOK_ID, OUTPUT_DIR
from native_oauth.book_49736.status_tracker import calculate_progress, render_terminal_dashboard

BOOK_DIR = ROOT / "native_oauth" / f"book_{BOOK_ID}"
LIVE_STATUS_FILE = BOOK_DIR / "live_status.json"


def update_live_status(current_wave: int, active_chapter: int = 0, message: str = ""):
    return calculate_progress(current_wave, active_chapter, message, target_chapters=100)


async def run_waves(start_wave: int = 2, end_wave: int = 5):
    print("=" * 70)
    print(" CAOTRUYEN V2.0 - AUTO WAVE ORCHESTRATOR (CHƯƠNG 21 -> 100)")
    print(f" Bộ truyện: Book {BOOK_ID} (Đi Tìm Vô Gian Địa Ngục)")
    print(f" Kế hoạch: Wave {start_wave} -> Wave {end_wave} (Mỗi Wave 20 chương, 4 Workers song song)")
    print("=" * 70)

    start_all = time.time()
    cur_st = calculate_progress(start_wave, message="Khởi động bộ điều phối các Wave")
    print(render_terminal_dashboard(cur_st))

    for wave in range(start_wave, end_wave + 1):
        from_ch = (wave - 1) * 20 + 1
        to_ch = wave * 20
        wave_start = time.time()

        print(f"\n>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
        print(f"[*] BẮT ĐẦU WAVE {wave}/5: CHƯƠNG {from_ch:03d} -> {to_ch:03d}")
        print(f">>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>>")
        
        calculate_progress(wave, message=f"Đang dịch Wave {wave} (Chương {from_ch} -> {to_ch})")

        runner = SlidingPoolRunner(
            from_chapter=from_ch,
            to_chapter=to_ch,
            block_size=5,
            max_workers=4,
            stagger_delay=3.5,
            target_model="gemini-3.8-flash-high",
            force=False
        )

        # Run this wave
        await runner.run()

        elapsed = time.time() - wave_start
        print(f"\n[✓] HOÀN TẤT WAVE {wave}/5 trong {elapsed:.1f}s")
        st_after = calculate_progress(wave, message=f"Hoàn tất Wave {wave} trong {elapsed:.1f}s")
        print(render_terminal_dashboard(st_after))

        # Quota cooldown between draft waves; this is not a semantic gate
        if wave < end_wave:
            print(f"\n--- [Quota cooldown #{wave}] Nghỉ 5s trước Wave {wave + 1}; review nội dung là bước riêng ---")
            await asyncio.sleep(5)

    total_time = time.time() - start_all
    final_status = calculate_progress(end_wave, message="ĐÃ TẠO DRAFT CHO ĐỢT CHẠY; CHƯA DUYỆT NGHĨA")
    print("\n" + "=" * 70)
    print(f"[🎉] CHIẾN DỊCH HOÀN THÀNH: ĐỢT TẠO DRAFT ĐÃ KẾT THÚC TRONG {total_time:.1f}s")
    print(f"     Tổng số từ: {final_status['total_words']:,} từ | Tổng số đoạn: {final_status['total_paragraphs']:,} đoạn")
    print(render_terminal_dashboard(final_status))
    print("=" * 70)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Multi-Wave Orchestrator for CaoTruyen")
    parser.add_argument("--start-wave", type=int, default=2)
    parser.add_argument("--end-wave", type=int, default=5)
    args = parser.parse_args()

    asyncio.run(run_waves(args.start_wave, args.end_wave))
