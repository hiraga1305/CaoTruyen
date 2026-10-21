"""Crawl chapters for Book 16014 (没钱修什么仙？) from Piaotia with integrity checks."""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from source_integrity import fetch_chapter_raw
from semantic_gate import digest, write_json

BOOK_ID = "16014"
BASE_URL = f"https://www.piaotia.com/html/16/{BOOK_ID}/"
BOOK_DIR = ROOT / "native_oauth" / f"book_{BOOK_ID}"
SOURCES_DIR = BOOK_DIR / "sources"
SOURCES_DIR.mkdir(parents=True, exist_ok=True)

def crawl_range(from_chap=1, to_chap=5):
    toc_file = BOOK_DIR / "toc.json"
    with open(toc_file, "r", encoding="utf-8") as f:
        chapters = json.load(f)

    print(f"[*] Crawling chapters {from_chap} -> {to_chap} from {BASE_URL}...")
    success = 0
    for chap_num in range(from_chap, to_chap + 1):
        if chap_num > len(chapters):
            break
        href, title = chapters[chap_num - 1]
        out_path = SOURCES_DIR / f"source_chapter_{chap_num:04d}.json"
        if out_path.exists():
            print(f"  [=] Chapter {chap_num:02d} already exists: {title}")
            success += 1
            continue

        try:
            paras = fetch_chapter_raw(href, base_url=BASE_URL, article_id=BOOK_ID)
            if re.sub(r'\s+', '', paras[0]) != re.sub(r'\s+', '', title):
                paras = [title] + paras

            pkg = {
                "version": "bns-source-v1",
                "book_id": BOOK_ID,
                "chapter": chap_num,
                "title": title,
                "source_ref": BASE_URL + href,
                "segments": [{"id": f"c{chap_num:04d}p{i:04d}", "source": p} for i, p in enumerate(paras, 1)],
                "paragraph_count": len(paras)
            }
            pkg["package_hash"] = digest(pkg)
            write_json(out_path, pkg)
            success += 1
            print(f"  [✓] Chapter {chap_num:02d}: {title} ({len(paras)} paras)")
        except Exception as e:
            print(f"  [!] Failed Chapter {chap_num:02d}: {e}")

    print(f"[+] Crawled {success}/{to_chap - from_chap + 1} chapters.")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--from-chapter", type=int, default=1)
    parser.add_argument("--to-chapter", type=int, default=5)
    args = parser.parse_args()
    crawl_range(args.from_chapter, args.to_chapter)
