"""Fetch first 50 chapters of Book 14713 (我在直播间窥探天机) from Piaotia with integrity checks."""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from source_integrity import fetch_chapter_raw
from semantic_gate import digest, write_json

BOOK_ID = "14713"
BASE_URL = f"https://www.piaotia.com/html/14/{BOOK_ID}/"
BOOK_DIR = ROOT / "native_oauth" / f"book_{BOOK_ID}"
SOURCES_DIR = BOOK_DIR / "sources"
SOURCES_DIR.mkdir(parents=True, exist_ok=True)

# 1. Load or fetch TOC
toc_file = BOOK_DIR / "toc.json"
if not toc_file.exists():
    import urllib.request
    req = urllib.request.Request(f"{BASE_URL}index.html", headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode("gbk", errors="ignore")
    chapters = re.findall(r'<a href="(\d+\.html)">([^<]+)</a>', html)
    write_json(toc_file, chapters)
    print(f"[+] Saved TOC with {len(chapters)} chapters to {toc_file}")
else:
    with open(toc_file, "r", encoding="utf-8") as f:
        chapters = json.load(f)

# 2. Lore / Glossary for Book 14713
lore_file = BOOK_DIR / "lore.json"
if not lore_file.exists():
    lore = {
        "book_title": "我在直播间窥探天机",
        "book_title_vi": "Tôi Ở Phòng Livestream Dòm Ngó Thiên Cơ",
        "author": "只余豁达",
        "author_vi": "Chỉ Dư Khoát Đạt",
        "genre": "URBAN_XIANXIA",
        "characters": {
            "萧羽": "Tiêu Vũ",
            "萧大师": "Tiêu đại sư",
            "江夏": "Giang Hạ",
            "徐菲": "Từ Phỉ",
            "林美婷": "Lâm Mỹ Đình",
            "柳凡": "Liễu Phàm",
            "胡菲菲": "Hồ Phỉ Phỉ"
        },
        "terms": {
            "水友": "thủy hữu / người xem",
            "直播间": "phòng livestream / phòng phát sóng",
            "窥探天机": "dòm ngó thiên cơ / nhìn thấu thiên cơ",
            "算命": "bói toán / xem mệnh",
            "修仙": "tu tiên",
            "功德": "công đức",
            "大难临头": "tai họa ngập đầu / đại họa lâm đầu",
            "房管": "quản trị viên phòng",
            "榜一": "top 1 bảng vàng / bảng nhất",
            "超火": "Siêu Hỏa Tiễn",
            "火箭": "Hỏa Tiễn",
            "嘉年华": "Gia Niên Hoa"
        }
    }
    write_json(lore_file, lore)
    print(f"[+] Saved lore to {lore_file}")

# 3. Fetch first 50 chapters
print(f"[*] Crawling first 50 chapters from {BASE_URL}...")
success_count = 0

for chap_num in range(1, 51):
    href, title = chapters[chap_num - 1]
    out_path = SOURCES_DIR / f"source_chapter_{chap_num:04d}.json"
    if out_path.exists():
        success_count += 1
        continue
    
    try:
        paras = fetch_chapter_raw(href, base_url=BASE_URL, article_id=BOOK_ID)
        # Ensure title is paragraph 0 if author did not include it in text body
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
        success_count += 1
        print(f"  [✓] Chapter {chap_num:02d}: {title} ({len(paras)} paras)")
    except Exception as e:
        print(f"  [✗] Chapter {chap_num:02d} ({href}): {e}")
        time.sleep(1)

print(f"\n[+] Completed crawling: {success_count}/50 chapters ready.")
