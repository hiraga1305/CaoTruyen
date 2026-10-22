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

from semantic_gate import digest, write_json, read_json
from native_oauth.chapter_integrity import validate_source, source_content_hash
from native_oauth.source_adapters import (fetch_czbooks, normalize_paragraphs, extract_paragraphs as strict_extract,
    clean_title as normalized_title, PARSER_VERSION)
from native_oauth.workflow_io import atomic_json, atomic_text, file_lock

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


def extract_paragraphs(html):
    return strict_extract(html)


def validate_page_identity(html, expected_title):
    soup = BeautifulSoup(html, 'html.parser')
    headings = [n.get_text(strip=True) for n in soup.select('h1,.chapter-title,.name')]
    declared = [name for heading in headings for name in re.findall(r'《([^》]+)》',heading)]
    if any(name not in ('尋找無間地獄','寻找无间地狱') for name in declared):
        raise ValueError('Book title mismatch')
    if not any(normalized_title(text) == normalized_title(expected_title) for text in headings):
        raise ValueError('Chapter title mismatch')


def fetch_chapter_from_czbooks(href, max_retries=5, expected_title=None):
    last_err=None
    for attempt in range(max_retries):
        try:
            return fetch_czbooks(href, book_slug="s6p7bb", expected_title=expected_title, headers=HEADERS,
                                 expected_book_titles=('尋找無間地獄','寻找无间地狱'))
        except (ValueError, UnicodeError):
            raise
        except (OSError, TimeoutError) as error:
            last_err=error
            if attempt+1<max_retries:
                time.sleep(min(10,attempt+1))
    raise RuntimeError("Source fetch failed") from last_err


def crawl_one_chapter(chap_num, item):
    href,title=item["href"],item["title"]
    out_path=SOURCES_DIR/f"source_chapter_{chap_num:04d}.json"
    try:
        with file_lock(out_path.with_suffix(".lock")):
            if out_path.exists():
                previous=validate_source(read_json(out_path))
                archive=ARCHIVE_DIR/previous.get("raw_archive","")
                if (previous["version"]=="bns-source-v2" and previous["source_ref"]==href
                        and previous['normalization']['parser_version']==PARSER_VERSION
                        and Path(previous['raw_archive']).name==previous['raw_archive']
                        and previous["title"]==title and archive.is_file()
                        and hashlib.sha256(archive.read_bytes()).hexdigest()==previous["raw_sha256"]):
                    return chap_num,True,"cached"
            paras,raw=fetch_chapter_from_czbooks(href,expected_title=title)
            stamp=hashlib.sha256(raw).hexdigest()
            archive_name=f"chap_{chap_num:04d}_{stamp}.html"
            ARCHIVE_DIR.mkdir(parents=True,exist_ok=True)
            archive=ARCHIVE_DIR/archive_name
            if archive.exists() and archive.read_bytes()!=raw:
                raise ValueError("Raw archive collision")
            atomic_text(archive, raw.decode('utf-8', errors='strict'))
            segments,mapping=normalize_paragraphs(paras,chap_num)
            pkg={"version":"bns-source-v2","book_id":BOOK_ID,"chapter":chap_num,
                 "toc_index":chap_num,"chapter_key":href.split("?")[0].rstrip("/").split("/")[-1],
                 "title":title,"source_ref":href,"segments":segments,"paragraph_count":len(segments),
                 "raw_sha256":stamp,"raw_archive":archive_name,"normalization":mapping,
                 "fetched_at_utc":datetime.now(timezone.utc).isoformat()}
            pkg["content_hash"]=source_content_hash(pkg)
            pkg["package_hash"]=digest(pkg)
            validate_source(pkg)
            if out_path.exists():
                previous=read_json(out_path)
                atomic_json(SOURCES_DIR/"history"/(previous["package_hash"]+".json"),previous)
            atomic_json(out_path,pkg)
            return chap_num,True,f"{title} ({len(segments)} paragraphs; original raw preserved)"
    except Exception as error:
        return chap_num,False,str(error)


def crawl_range(from_chap: int = 1, to_chap: int = 325, concurrency: int = 5):
    if not 1 <= from_chap <= to_chap or not 1 <= concurrency <= 20:
        raise ValueError("Invalid chapter range or concurrency")
    toc_file = BOOK_DIR / "toc.json"
    if not toc_file.exists():
        raise FileNotFoundError(f"Missing {toc_file}. Run fetch_full_toc first.")
    
    with open(toc_file, "r", encoding="utf-8") as f:
        chapters = json.load(f)
    if to_chap > len(chapters):
        raise ValueError("Requested range exceeds the frozen TOC")

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
    return {"status":"COMPLETE" if not failed else "BLOCKED", "success":success,
            "requested":total_to_crawl, "failed":failed}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Crawl chapters for Book 49736")
    parser.add_argument("--from-chapter", type=int, default=1)
    parser.add_argument("--to-chapter", type=int, default=325)
    parser.add_argument("--concurrency", type=int, default=5)
    args = parser.parse_args()
    result = crawl_range(args.from_chapter, args.to_chapter, args.concurrency)
    raise SystemExit(0 if result["status"] == "COMPLETE" else 2)
