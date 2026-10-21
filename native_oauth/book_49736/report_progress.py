"""Dashboard report for Book 49736 (寻找无间地狱) translation pipeline."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOK_DIR = ROOT / "native_oauth" / "book_49736"
SOURCES_DIR = BOOK_DIR / "sources"
OUTPUT_DIR = BOOK_DIR / "output_dich"

src_files = sorted(SOURCES_DIR.glob("source_chapter_*.json"))
out_files = sorted(OUTPUT_DIR.glob("chuong_*.txt"))

print(f"==================================================")
print(f" BOOK 49736 (寻找无间地狱) - BNS PIPELINE DASHBOARD")
print(f"==================================================")
print(f"Total Crawled Sources: {len(src_files)} chapters")
print(f"Total Translated Outputs: {len(out_files)} chapters")
print(f"--------------------------------------------------")

total_words = 0
total_paras = 0

for out in out_files:
    text = out.read_text(encoding="utf-8")
    words = len(text.split())
    paras = len([p for p in text.split("\n\n") if p.strip()])
    total_words += words
    total_paras += paras
    first_line = text.splitlines()[0] if text.splitlines() else ""
    print(f"  {out.name}: {first_line[:45]} | {paras} paras | {words} words | {out.stat().st_size} bytes")

print(f"--------------------------------------------------")
print(f"Total Translated Words: {total_words:,} words")
print(f"Total Translated Paragraphs: {total_paras:,} paras")
print(f"==================================================")
