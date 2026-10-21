"""Crawl chapters for Book 49736 (寻找无间地狱 / 尋找無間地獄) with integrity checks.
Primary source: CZBooks (czbooks.net/n/s6p7bb)
Fallback/reference: 69shuba (69shuba.com/book/49736.htm)
"""
import argparse
import concurrent.futures
import hashlib
import json
import re
import sys
import threading
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from semantic_gate import digest, write_json

BOOK_ID = "49736"
BOOK_DIR = ROOT / "native_oauth" / f"book_{BOOK_ID}"
SOURCES_DIR = BOOK_DIR / "sources"
ARCHIVE_DIR = ROOT / "source_archive" / f"book_{BOOK_ID}"

SOURCES_DIR.mkdir(parents=True, exist_ok=True)
ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)

HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'zh-CN,zh-TW,zh;q=0.9,en;q=0.8',
}

PRINT_LOCK = threading.Lock()


def safe_print(*args, **kwargs):
    with PRINT_LOCK:
        print(*args, **kwargs, flush=True)


def extract_paragraphs(html: str) -> list[str]:
    soup = BeautifulSoup(html, 'html.parser')
    content_div = soup.select_one('.content')
    if not content_div:
        raise ValueError("Could not find .content container in chapter page")
    
    # Strip script and style
    for tag in content_div.select('script, style'):
        tag.decompose()
    for br in content_div.find_all('br'):
        br.replace_with('\n')
    for tag in content_div.find_all(['p', 'div']):
        tag.insert_before('\n')
        tag.insert_after('\n')
        
    paragraphs = [p.strip() for p in content_div.get_text().replace('\xa0', ' ').splitlines() if p.strip()]
    if not paragraphs or not any(re.search(r'[\u3400-\u9fff]', p) for p in paragraphs):
        raise ValueError("Empty or non-Chinese source extracted")
        
    # Remove trailing boilerplate like (本章完)
    if paragraphs and paragraphs[-1] in ["(本章完)", "（本章完）", "【本章完】"]:
        paragraphs = paragraphs[:-1]
        
    return paragraphs


def fetch_chapter_from_czbooks(href: str, max_retries: int = 5) -> tuple[list[str], bytes]:
    last_err = None
    for attempt in range(max_retries):
        try:
            req = urllib.request.Request(href, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=20) as resp:
                data = resp.read()
                html = data.decode('utf-8', errors='ignore')
            paras = extract_paragraphs(html)
            return paras, data
        except Exception as e:
            last_err = e
            time.sleep(1.0 * (attempt + 1))
    raise RuntimeError(f"Fetch failed after {max_retries} retries: {last_err}")


def crawl_one_chapter(chap_num: int, item: dict) -> tuple[int, bool, str]:
    href = item["href"]
    title = item["title"]
    out_path = SOURCES_DIR / f"source_chapter_{chap_num:04d}.json"
    
    if out_path.exists():
        return chap_num, True, "cached"

    try:
        paras, raw_bytes = fetch_chapter_from_czbooks(href)
        
        # Ensure title is paragraph 0
        if re.sub(r'\s+', '', paras[0]) != re.sub(r'\s+', '', title):
            paras = [title] + paras

        # Archive raw HTML
        stamp = hashlib.sha256(raw_bytes).hexdigest()
        raw_archive_name = f"chap_{chap_num:04d}_{stamp[:12]}.html"
        (ARCHIVE_DIR / raw_archive_name).write_bytes(raw_bytes)

        pkg = {
            "version": "bns-source-v1",
            "book_id": BOOK_ID,
            "chapter": chap_num,
            "title": title,
            "source_ref": href,
            "segments": [{"id": f"c{chap_num:04d}p{i:04d}", "source": p} for i, p in enumerate(paras, 1)],
            "paragraph_count": len(paras),
            "raw_sha256": stamp,
            "fetched_at_utc": datetime.now(timezone.utc).isoformat()
        }
        pkg["package_hash"] = digest(pkg)
        write_json(out_path, pkg)
        return chap_num, True, f"{title} ({len(paras)} paras)"
    except Exception as e:
        return chap_num, False, str(e)


def crawl_range(from_chap: int = 1, to_chap: int = 325, concurrency: int = 5):
    toc_file = BOOK_DIR / "toc.json"
    if not toc_file.exists():
        raise FileNotFoundError(f"Missing {toc_file}. Run fetch_full_toc first.")
    
    with open(toc_file, "r", encoding="utf-8") as f:
        chapters = json.load(f)

    actual_to_chap = min(to_chap, len(chapters))
    total_to_crawl = actual_to_chap - from_chap + 1
    safe_print(f"[*] Crawling chapters {from_chap} -> {actual_to_chap} (Total {total_to_crawl}) for Book {BOOK_ID} (寻找无间地狱) with concurrency={concurrency}...")

    tasks = []
    for chap_num in range(from_chap, actual_to_chap + 1):
        item = chapters[chap_num - 1]
        tasks.append((chap_num, item))

    success = 0
    failed = []
    start_time = time.time()

    with concurrent.futures.ThreadPoolExecutor(max_workers=concurrency) as executor:
        future_to_chap = {executor.submit(crawl_one_chapter, c, item): c for c, item in tasks}
        completed = 0
        for future in concurrent.futures.as_completed(future_to_chap):
            chap_num = future_to_chap[future]
            try:
                c_num, ok, msg = future.result()
                completed += 1
                if ok:
                    success += 1
                    if msg == "cached":
                        if completed % 20 == 0 or completed == total_to_crawl:
                            safe_print(f"  [Progress {completed}/{total_to_crawl}] Chapter {c_num:03d} (cached)")
                    else:
                        safe_print(f"  [✓] [{completed}/{total_to_crawl}] Chapter {c_num:03d}: {msg}")
                else:
                    safe_print(f"  [!] [{completed}/{total_to_crawl}] Failed Chapter {c_num:03d}: {msg}")
                    failed.append(c_num)
            except Exception as exc:
                completed += 1
                safe_print(f"  [!] [{completed}/{total_to_crawl}] Exception on Chapter {chap_num:03d}: {exc}")
                failed.append(chap_num)

    # Retry pass for failed chapters if any
    if failed:
        safe_print(f"\n[*] Retrying {len(failed)} failed chapters sequentially with delay...")
        retry_failed = []
        for chap_num in failed:
            item = chapters[chap_num - 1]
            time.sleep(1.0)
            c_num, ok, msg = crawl_one_chapter(chap_num, item)
            if ok:
                success += 1
                safe_print(f"  [✓] [Retry] Chapter {c_num:03d}: {msg}")
            else:
                retry_failed.append(c_num)
                safe_print(f"  [!] [Retry Failed] Chapter {c_num:03d}: {msg}")
        failed = retry_failed

    elapsed = time.time() - start_time
    safe_print(f"\n=======================================================")
    safe_print(f"[+] Crawl Completed: {success}/{total_to_crawl} chapters in {elapsed:.1f}s.")
    if failed:
        safe_print(f"[!] Remaining failed chapters: {failed}")
    else:
        safe_print(f"[✓] 100% of requested chapters successfully crawled and archived.")
    safe_print(f"=======================================================")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawl chapters for Book 49736")
    parser.add_argument("--from-chapter", type=int, default=1)
    parser.add_argument("--to-chapter", type=int, default=325)
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()
    crawl_range(args.from_chapter, args.to_chapter, args.concurrency)
