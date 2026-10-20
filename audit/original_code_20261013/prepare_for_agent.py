import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import re
import json
import urllib.request
from bs4 import BeautifulSoup
from get_toc import matches as toc_matches

LORE_FILE = "novel_lore.json"
PREPARED_DIR = "prepared_input"

def load_lore():
    if os.path.exists(LORE_FILE):
        with open(LORE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            flat = {}
            for category in data.values():
                if isinstance(category, dict):
                    flat.update(category)
            return flat
    return {}

def chivi3_parse_advanced(text, glossary):
    res = text
    # 1. Glossary Anchor (từ dài trước)
    for k in sorted(glossary.keys(), key=len, reverse=True):
        res = res.replace(k, glossary[k])

    # 2. Cấu trúc câu chữ 把/将 (Disposal): [把/将] + [Obj] + [Verb] -> [Verb] + [Obj]
    res = re.sub(r'(?:把|将)([^,.\n!?:;]+?)(推倒|扔掉|打破|斩断|炼化|吞噬|吸收|击碎|杀死|消灭)', r'\2 \1', res)

    # 3. Cấu trúc 被 (Passive)
    res = re.sub(r'被([^,.\n!?:;]+?)(击中|吞噬|杀死|重创|打断)', r'bị \1 \2', res)

    # 4. Trợ từ kết cấu 的 (De-resolver)
    res = re.sub(r'(\w{2,4})的(\w{2,4})', r'\2 của \1', res)

    return res

def fetch_chapter_raw(href, max_retries=5):
    url = f"https://www.piaotia.com/html/16/16014/{href}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"}
    import ssl
    import time
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=headers)
    
    html = ""
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
                html = resp.read().decode('gbk', errors='ignore')
            break
        except urllib.error.HTTPError as e:
            if e.code == 429 or e.code >= 500:
                print(f"[*] Piaotia web throttle (HTTP {e.code}), chờ {attempt*2 + 2}s rồi thử lại...")
                time.sleep(attempt * 2 + 2)
                continue
            raise e
        except Exception as e:
            time.sleep(2)
            if attempt == max_retries - 1:
                raise e
    time.sleep(0.3)

    soup = BeautifulSoup(html, 'html.parser')
    for s in soup.find_all(['script', 'style', 'a', 'table']):
        s.decompose()

    raw_text = soup.get_text()
    paragraphs = []
    for p in raw_text.split('\xa0\xa0\xa0\xa0'):
        clean_p = p.strip()
        if not clean_p:
            continue
        if any(marker in clean_p for marker in ['选择背景', '选择字体', '飘天文学', '上一章', '下一章', '返回书页', '加入书签', '天才一秒记住', '最新章节', 'PT文学', 'www.piaotia.com']):
            continue
        paragraphs.append(clean_p)

    return paragraphs

def prepare_chapter(chap_num):
    os.makedirs(PREPARED_DIR, exist_ok=True)
    idx = chap_num - 1
    if idx < 0 or idx >= len(toc_matches):
        print(f"Chương {chap_num} không tồn tại trong danh mục!")
        return None

    href, title = toc_matches[idx]
    clean_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
    out_file = os.path.join(PREPARED_DIR, f"chap_{chap_num:03d}_{clean_title}.txt")

    if os.path.exists(out_file) and os.path.getsize(out_file) > 1000:
        print(f"[*] Chương {chap_num} đã có sẵn nguyên liệu: {out_file}")
        return out_file

    paragraphs = fetch_chapter_raw(href)
    glossary = load_lore()

    lines_out = []
    lines_out.append(f"CHƯƠNG CẦN DỊCH: Chương {chap_num} - {title}")
    lines_out.append(f"TÁC GIẢ: Hùng Lang Cẩu (熊狼狗)")
    lines_out.append(f"TÁC PHẨM: Không Tiền Tu Cái Gì Tiên? (没钱修什么仙？)")
    lines_out.append("=" * 80)
    lines_out.append("YÊU CẦU BIÊN TẬP (SENIOR EDITOR GUIDELINES):")
    lines_out.append("1. Bạn là Trưởng Ban Biên Tập (Senior Editor) văn học mạng tu tiên.")
    lines_out.append("2. Sử dụng 100% năng lực suy luận sâu (Thinking) của Gemini 3.8 Flash trên Antigravity để:")
    lines_out.append("   - Giữ trọn văn phong hài hước châm biếm đen tối (dark comedy/cyberpunk tu tiên).")
    lines_out.append("   - Đối thoại nhân vật bắt buộc định dạng gạch đầu dòng: - \"...\"")
    lines_out.append("   - Đại từ xưng hô linh hoạt, tự nhiên theo phân tầng xã hội học đường và sàn nợ.")
    lines_out.append("   - Dịch đủ 100% nội dung, không cắt xén, không văn mẫu chào hỏi thừa thãi.")
    lines_out.append("=" * 80)

    # Chia chunks
    chunk_size = 60
    chunks = [paragraphs[i:i + chunk_size] for i in range(0, len(paragraphs), chunk_size)]
    for c_idx, chunk in enumerate(chunks, 1):
        raw_text = "\n\n".join(chunk)
        chivi_text = "\n\n".join([chivi3_parse_advanced(p, glossary) for p in chunk])
        lines_out.append(f"\n--- [PHẦN {c_idx}/{len(chunks)}] ---")
        lines_out.append("[BẢN GỐC TIẾNG TRUNG]:")
        lines_out.append(raw_text)
        lines_out.append("\n[BẢN THÔ CÂY NGỮ PHÁP CHIVI 3 LOCAL]:")
        lines_out.append(chivi_text)
        lines_out.append("-" * 60)

    content = "\n".join(lines_out)
    with open(out_file, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"[*] Đã chuẩn bị xong nguyên liệu cho Chương {chap_num}: {out_file} ({len(paragraphs)} đoạn, {len(content)} ký tự)")
    return out_file

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--chap", type=int, default=32)
    parser.add_argument("--from_chap", type=int)
    parser.add_argument("--to_chap", type=int)
    args = parser.parse_args()

    if args.from_chap and args.to_chap:
        for c in range(args.from_chap, args.to_chap + 1):
            prepare_chapter(c)
    else:
        prepare_chapter(args.chap)
