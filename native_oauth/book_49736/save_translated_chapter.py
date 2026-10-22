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
    """Import a complete draft; never label manually supplied text as approved."""
    sys.path.insert(0, str(ROOT))
    from native_oauth.chapter_runner import run_chapter
    from native_oauth.chapter_integrity import validate_source
    source_file = SOURCES_DIR / f"source_chapter_{chap_num:04d}.json"
    source = json.loads(source_file.read_text(encoding="utf-8"))
    segments = validate_source(source)
    if len(translated_paragraphs) != len(segments) or any(not isinstance(p, str) or not p.strip() for p in translated_paragraphs):
        raise ValueError("Import blocked: missing/extra/empty source-aligned paragraphs")
    cursor = 0
    def scene(scene_idx, paragraphs, context):
        nonlocal cursor
        if json.loads(source_file.read_text(encoding="utf-8")) != source:
            raise ValueError("Source changed during draft import")
        texts = translated_paragraphs[cursor:cursor + len(paragraphs)]
        cursor += len(paragraphs)
        return dict(enumerate(texts, 1)), texts[-1], True
    return run_chapter(chap_num, "49736", "Đi Tìm Vô Gian Địa Ngục", "URBAN_SUSPENSE_MYSTERY",
                       SOURCES_DIR, OUTPUT_DIR, scene, "manual/unverified-" + model, total_chapters=325)


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
