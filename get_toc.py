import urllib.request
import re
import sys
import os
import json

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

CACHE_FILE = os.path.join(os.path.dirname(__file__), "toc_cache.json")
matches = []

if os.path.exists(CACHE_FILE):
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            matches = json.load(f)
    except Exception:
        matches = []

if not matches:
    url = "https://www.piaotia.com/html/16/16014/index.html"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read().decode('gbk', errors='ignore')
        matches = re.findall(r'<a href="(\d+\.html)">([^<]+)</a>', html)
        if matches:
            with open(CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(matches, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[!] Lỗi tải danh mục mục lục: {e}")

if __name__ == "__main__":
    print(f"Tổng số chương tìm thấy: {len(matches)}")
    print("\n--- 5 chương đầu ---")
    for href, title in matches[:5]:
        print(f"ID: {href} -> {title}")
    print("\n--- 5 chương mới nhất ---")
    for href, title in matches[-5:]:
        print(f"ID: {href} -> {title}")
