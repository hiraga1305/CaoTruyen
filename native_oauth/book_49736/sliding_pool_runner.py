"""CAOTRUYEN V2.0 - SLIDING WORKER POOL RUNNER FOR BOOK 49736
Co-engineered with Gemini 4 Argon Architecture Blueprint.

Features:
- Wave Execution: 1 Wave = 4 Blocks = 20 chapters (K=4 workers, 5 chapters/block).
- Staggered Ramp-up: 3.5s delay to flatten token spikes and prevent HTTP 429.
- Style Seed Memory: Golden anchor pairs to keep tone consistent across all blocks.
- StyleAndEntityGuard: 0-Token strict entity parity & pronoun mutation firewall.
- QualityGate4A & SpotAuditor4B: Immediate surgical micro-repair at paragraph level.
- Checkpoint Idempotence: Auto-skips chapters already verified in output_dich/.
"""
import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from native_oauth.scene_contract import EntityRecord, PronounRule, SceneContract
from native_oauth.bns_prepass import UnifiedSemanticPreprocessor
from native_oauth.quality_gate import QualityGate4A
from native_oauth.spot_auditor import SpotAuditor4B
from native_oauth.book_49736.status_tracker import calculate_progress, render_terminal_dashboard
from native_oauth.book_49736.batch_pipeline_runner import (
    process_chapter,
    BASE_ENTITIES,
    BASE_PRONOUNS,
    BOOK_ID,
    OUTPUT_DIR,
    SOURCES_DIR
)

BOOK_DIR = ROOT / "native_oauth" / f"book_{BOOK_ID}"
STYLE_SEED_FILE = BOOK_DIR / "golden_style_seeds.json"


class SlidingPoolRunner:
    def __init__(
        self,
        from_chapter: int = 1,
        to_chapter: int = 20,
        block_size: int = 5,
        max_workers: int = 4,
        stagger_delay: float = 3.5,
        target_model: str = "gemini-3.8-flash-high",
        force: bool = False
    ):
        self.from_chapter = from_chapter
        self.to_chapter = to_chapter
        self.block_size = block_size
        self.max_workers = max_workers
        self.stagger_delay = stagger_delay
        self.target_model = target_model
        self.force = force
        self.semaphore = asyncio.Semaphore(max_workers)
        
        # Tools
        self.preprocessor = UnifiedSemanticPreprocessor()
        self.gate = QualityGate4A()
        self.auditor = SpotAuditor4B(gate=self.gate)
        
    def build_blocks(self) -> list[tuple[int, list[int]]]:
        chapters = list(range(self.from_chapter, self.to_chapter + 1))
        blocks = []
        for i in range(0, len(chapters), self.block_size):
            block_chaps = chapters[i : i + self.block_size]
            blocks.append((len(blocks) + 1, block_chaps))
        return blocks

    async def _process_block(self, block_id: int, chapters: list[int]):
        # Staggered ramp-up to prevent burst rate limit
        if block_id <= self.max_workers:
            delay = (block_id - 1) * self.stagger_delay
            if delay > 0:
                await asyncio.sleep(delay)
                
        async with self.semaphore:
            first_ch = chapters[0]
            last_ch = chapters[-1]
            print(f"\n[Worker] >>> BẮT ĐẦU BLOCK {block_id:02d} (Chương {first_ch:03d} -> {last_ch:03d})")
            t_block_start = time.time()
            
            # Execute the 5 chapters sequentially inside this block for seamless local seam continuity
            for chap_num in chapters:
                loop = asyncio.get_running_loop()
                success = await loop.run_in_executor(
                    None,
                    process_chapter,
                    chap_num,
                    self.preprocessor,
                    self.gate,
                    self.auditor,
                    self.target_model,
                    self.force,
                    ""
                )
                if not success:
                    raise RuntimeError(f"Chapter {chap_num} BLOCKED; wave incomplete")
                else:
                    st = calculate_progress(active_chapter=chap_num, message=f"Block {block_id}: Xong Chương {chap_num:03d}")
                    print(f"  >>> [LIVE STATUS] [{st['progress_bar']}] {st['percent_complete']}% ({st['completed_chapters_count']}/100) | Vừa xong Chương {chap_num:03d}")

            t_block_elapsed = time.time() - t_block_start
            print(f"[Worker] <<< HOÀN TẤT BLOCK {block_id:02d} (Chương {first_ch:03d} -> {last_ch:03d}) trong {t_block_elapsed:.1f}s")

    async def run(self):
        blocks = self.build_blocks()
        total_blocks = len(blocks)
        total_chapters = self.to_chapter - self.from_chapter + 1
        print(f"================================================================")
        print(f" CAOTRUYEN V2.0 - SLIDING WORKER POOL RUNNER")
        print(f" Bộ truyện: Book {BOOK_ID} (寻找无间地狱)")
        print(f" Phạm vi: Chương {self.from_chapter} -> {self.to_chapter} ({total_chapters} chương)")
        print(f" Cấu hình: {total_blocks} Blocks (mỗi block {self.block_size} chương) | K={self.max_workers} Workers song song")
        print(f" Lệch pha (Stagger): {self.stagger_delay}s | Model: {self.target_model}")
        print(f" Kiểm cấu trúc: QualityGate4A; draft cần hai native review trước approved")
        print(f"================================================================")
        
        t0 = time.time()
        tasks = [
            self._process_block(block_id, chaps)
            for block_id, chaps in blocks
        ]
        await asyncio.gather(*tasks)
        print(f"\n================================================================")
        print(f"[✓] HOÀN TẤT ĐỢT CHẠY trong {time.time() - t0:.1f}s")
        print(f"================================================================")


def main():
    parser = argparse.ArgumentParser(description="Sliding Worker Pool Runner for CaoTruyen")
    parser.add_argument("--wave", type=int, help="Chạy theo từng Wave 20 chương (1: Ch 1-20, 2: Ch 21-40, ..., 10: Ch 181-200)")
    parser.add_argument("--from-chapter", type=int, default=1)
    parser.add_argument("--to-chapter", type=int, default=20)
    parser.add_argument("--block-size", type=int, default=5)
    parser.add_argument("--max-workers", type=int, default=4)
    parser.add_argument("--stagger-delay", type=float, default=3.5)
    parser.add_argument("--model", default="gemini-3.8-flash-high")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    from_ch = args.from_chapter
    to_ch = args.to_chapter
    if args.wave:
        from_ch = (args.wave - 1) * 20 + 1
        to_ch = args.wave * 20

    runner = SlidingPoolRunner(
        from_chapter=from_ch,
        to_chapter=to_ch,
        block_size=args.block_size,
        max_workers=args.max_workers,
        stagger_delay=args.stagger_delay,
        target_model=args.model,
        force=args.force
    )
    asyncio.run(runner.run())


if __name__ == "__main__":
    main()
