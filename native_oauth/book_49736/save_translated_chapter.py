# -*- coding: utf-8 -*-
"""Helper utility to save and validate translated chapters for Book 49736."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOK_DIR = ROOT / "native_oauth" / "book_49736"
SOURCES_DIR = BOOK_DIR / "sources"
OUTPUT_DIR = BOOK_DIR / "output_dich"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def save_chapter(chap_num: int, title_vi: str, translated_paragraphs: list[str], model: str = "gemini-3.8-flash-high") -> bool:
    src_file = SOURCES_DIR / f"source_chapter_{chap_num:04d}.json"
    if not src_file.exists():
        print(f"[!] Source missing: {src_file}")
        return False

    with open(src_file, "r", encoding="utf-8") as f:
        src_data = json.load(f)

    raw_segments = src_data.get("segments", [])
    expected_count = len(raw_segments)
    actual_count = len(translated_paragraphs)

    # Save TXT
    txt_file = OUTPUT_DIR / f"chuong_{chap_num:04d}.txt"
    lines = [f"CHƯƠNG {chap_num}: {title_vi.upper()}", ""]
    for p in translated_paragraphs:
        cleaned = p.strip()
        if cleaned:
            lines.append(cleaned)
            lines.append("")
    txt_file.write_text("\n".join(lines).strip() + "\n", encoding="utf-8")

    # Build bilingual alignment
    bilingual_records = []
    for i, p in enumerate(translated_paragraphs, 1):
        raw_zh = raw_segments[i - 1]["source"] if i - 1 < len(raw_segments) else ""
        bilingual_records.append({
            "para_id": f"c{chap_num:04d}p{i:04d}",
            "index": i,
            "raw_zh": raw_zh,
            "translated_vi": p.strip()
        })

    json_file = OUTPUT_DIR / f"chuong_{chap_num:04d}.dich.json"
    pkg_out = {
        "book_slug": "s6p7bb",
        "book_title": "寻找无间地狱",
        "book_title_vi": "Tìm Kiếm Vô Gian Địa Ngục",
        "chapter_num": chap_num,
        "title": title_vi,
        "total_paragraphs": expected_count,
        "translated_paragraphs": actual_count,
        "source_hash": src_data.get("package_hash", ""),
        "model_used": model,
        "bilingual_alignment": bilingual_records
    }
    json_file.write_text(json.dumps(pkg_out, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"[OK] Saved Chapter {chap_num:04d}: {actual_count}/{expected_count} paras -> {txt_file.name}")
    return True


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python save_translated_chapter.py <chap_num> <json_paras_file>")
        sys.exit(1)
    c_num = int(sys.argv[1])
    p_file = Path(sys.argv[2])
    data = json.loads(p_file.read_text(encoding="utf-8"))
    title = data.get("title_vi", f"Chương {c_num}")
    paras = data.get("paragraphs", [])
    save_chapter(c_num, title, paras)
