# -*- coding: utf-8 -*-
"""SOVEREIGN WAVE ORCHESTRATOR FOR BOOK 49736 (CHƯƠNG 226 -> 325)
Runs concurrent worker blocks with UrbanSuspenseCartridge & ASTOS Quality Gates.
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

from native_oauth.bns_prepass import UnifiedSemanticPreprocessor
from native_oauth.quality_gate import QualityGate4A
from native_oauth.spot_auditor import SpotAuditor4B
from native_oauth.cartridges.urban_suspense import UrbanSuspenseCartridge
from native_oauth.book_49736.status_tracker import calculate_progress, LIVE_STATUS_FILE
from native_oauth.book_49736.wujian_pipeline_runner import process_chapter, BOOK_ID, OUTPUT_DIR, SOURCES_DIR


class SovereignWaveRunner:
    def __init__(
        self,
        from_chapter: int = 227,
        to_chapter: int = 325,
        block_size: int = 5,
        max_workers: int = 2,
        stagger_delay: float = 3.0,
        model: str = "gemini-3.8-flash-high",
        force: bool = False
    ):
        self.from_chapter = from_chapter
        self.to_chapter = to_chapter
        self.block_size = block_size
        self.max_workers = max_workers
        self.stagger_delay = stagger_delay
        self.model = model
        self.force = force
        self.semaphore = asyncio.Semaphore(max_workers)

        self.preprocessor = UnifiedSemanticPreprocessor()
        self.gate = QualityGate4A()
        self.auditor = SpotAuditor4B()
        self.cartridge = UrbanSuspenseCartridge()

    def build_blocks(self) -> list[tuple[int, list[int]]]:
        chapters = list(range(self.from_chapter, self.to_chapter + 1))
        blocks = []
        for i in range(0, len(chapters), self.block_size):
            block_chaps = chapters[i : i + self.block_size]
            blocks.append((len(blocks) + 1, block_chaps))
        return blocks

    async def _process_block(self, block_id: int, chapters: list[int]):
        # Staggered ramp-up
        if block_id <= self.max_workers:
            delay = (block_id - 1) * self.stagger_delay
            if delay > 0:
                await asyncio.sleep(delay)

        async with self.semaphore:
            first_ch = chapters[0]
            last_ch = chapters[-1]
            print(f"\n[Wave Worker] >>> START BLOCK {block_id:02d} (Chương {first_ch:04d} -> {last_ch:04d})")
            t_block_start = time.time()

            for chap_num in chapters:
                loop = asyncio.get_running_loop()
                success = await loop.run_in_executor(
                    None,
                    process_chapter,
                    chap_num,
                    self.preprocessor,
                    self.gate,
                    self.auditor,
                    self.cartridge,
                    self.model,
                    self.force
                )
                if not success:
                    raise RuntimeError(f"Chapter {chap_num} BLOCKED; wave incomplete")
                else:
                    st = calculate_progress(active_chapter=chap_num, message=f"Block {block_id}: Xong Chương {chap_num:04d}", target_chapters=325)
                    print(f"  >>> [LIVE STATUS] [{st['progress_bar']}] {st['percent_complete']}% ({st['completed_chapters_count']}/325) | Vừa xong Chương {chap_num:04d}")

            t_block_elapsed = time.time() - t_block_start
            print(f"[Wave Worker] <<< FINISHED BLOCK {block_id:02d} (Chương {first_ch:04d} -> {last_ch:04d}) in {t_block_elapsed:.1f}s")

    async def run(self):
        blocks = self.build_blocks()
        total_blocks = len(blocks)
        total_chapters = self.to_chapter - self.from_chapter + 1
        print("=" * 66)
        print(" CAOTRUYEN SOVEREIGN WAVE ORCHESTRATOR — BOOK 49736")
        print(f" Phạm vi: Chương {self.from_chapter:04d} -> {self.to_chapter:04d} ({total_chapters} chương)")
        print(f" Cấu hình: {total_blocks} Blocks ({self.block_size} ch/block) | K={self.max_workers} Workers song song")
        print(f" Genre Cartridge: UrbanSuspenseCartridge | Model: {self.model}")
        print("=" * 66)

        t0 = time.time()
        tasks = [self._process_block(block_id, chaps) for block_id, chaps in blocks]
        await asyncio.gather(*tasks)
        print("\n" + "=" * 66)
        print(f"[✓] HOÀN TẤT TOÀN BỘ CÁC WAVE trong {time.time() - t0:.1f}s")
        print("=" * 66)


def main():
    parser = argparse.ArgumentParser(description="Wave Runner for Book 49736")
    parser.add_argument("--from-chapter", type=int, default=227)
    parser.add_argument("--to-chapter", type=int, default=325)
    parser.add_argument("--block-size", type=int, default=5)
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--stagger-delay", type=float, default=3.0)
    parser.add_argument("--model", default="gemini-3.8-flash-high")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    runner = SovereignWaveRunner(
        from_chapter=args.from_chapter,
        to_chapter=args.to_chapter,
        block_size=args.block_size,
        max_workers=args.max_workers,
        stagger_delay=args.stagger_delay,
        model=args.model,
        force=args.force
    )
    asyncio.run(runner.run())


if __name__ == "__main__":
    main()
