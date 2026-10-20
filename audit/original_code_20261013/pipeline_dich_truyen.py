import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import re
import time
import argparse
import urllib.request
from gemini_helper import ask_gemini
from run_production_chap1 import chivi3_parse

BASE_TOC_URL = "https://www.piaotia.com/html/16/16014/index.html"
BASE_CHAP_URL = "https://www.piaotia.com/html/16/16014/{chapter_id}"

SYSTEM_PROMPT = """Bạn là Tổng Biên Tập viên dịch thuật tiểu thuyết mạng Trung - Việt xuất sắc nhất (Senior Web Novel Editor).
Nhiệm vụ: Bạn nhận được [BẢN RAW TIẾNG TRUNG] và [BẢN THÔ CÂY NGỮ PHÁP CHIVI 3] của từng phần trong chương truyện.

Quy tắc biên tập:
1. KHÓA CỨNG 100% các Danh từ riêng Hán Việt đã định danh trong bản Chivi 3:
   - Nhân vật: Trương Vũ, Chu Vĩ, Bạch Chân Chân, Hùng Lang Cẩu...
   - Địa danh / Trường học: Côn Khư, Tung Dương, Đông Dương, Trường Cấp hai Đông Dương, Trường Cấp ba Tung Dương...
   - Thuật ngữ Tiên đạo: Vạn Hồn Phiên, Trúc Cơ, Kết Đan, Hồn Tu, Kim Đan, Nguyên Anh, Thiên Linh Căn, Tu Tiên Đới, Pháp Lực Đới, Thỉnh Thần, Vũ Thư...
2. Nhuận sắc câu từ: Biến câu văn thô ráp thành bản dịch xuất sắc đạt 95% sức mạnh dịch giả người thật.
   - Giữ trọn văn phong hài hước châm biếm đen tối (dark comedy/cyberpunk tu tiên) độc nhất vô nhị của tác giả Hùng Lang Cẩu.
   - Nhịp điệu câu văn gãy gọn, dứt khoát, mượt mà tự nhiên, không vấp váp, không dùng từ ngữ Hán Việt sống sượng.
3. Chuẩn hóa đại từ xưng hô theo đúng quan hệ ngữ cảnh (mẹ - con, giám khảo - thí sinh, sàn đòi nợ - con nợ, thầy - trò, bạn bè).
4. Định dạng:
   - Các câu thoại nhân vật bắt đầu bằng gạch đầu dòng: - "..."
   - Mỗi đoạn văn ngắt dòng thoáng mắt, dễ đọc.
   - Dịch đầy đủ 100% nội dung, TUYỆT ĐỐI KHÔNG tóm tắt hay cắt xén.
   - Chỉ xuất ra nội dung bản dịch, KHÔNG kèm các câu mở đầu/kết thúc như "Dưới đây là...", "Hy vọng bạn thích...".
"""

def get_chapter_list():
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    req = urllib.request.Request(BASE_TOC_URL, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('gbk', errors='ignore')
    matches = re.findall(r'<a href="(\d+\.html)">([^<]+)</a>', html)
    return matches

def fetch_chapter_content(href):
    url = f"https://www.piaotia.com/html/16/16014/{href}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        html = resp.read().decode('gbk', errors='ignore')
        
    text_content = html.split('<div id="content">')[-1].split('</div>')[0]
    text_content = text_content.replace("&nbsp;&nbsp;&nbsp;&nbsp;", "\n")
    text_content = text_content.replace("<br />", "\n").replace("<br/>", "\n").replace("<br>", "\n")
    text_content = re.sub(r'<!--.*?-->', '', text_content, flags=re.DOTALL)
    
    paragraphs = []
    for line in text_content.splitlines():
        line = line.strip()
        if not line:
            continue
        if "飘天文学" in line or "piaotia" in line.lower() or "天才一秒记住" in line or "书友群" in line:
            continue
        paragraphs.append(line)
        
    return paragraphs

def translate_chapter(chap_idx, href, title, output_dir="output_dich"):
    os.makedirs(output_dir, exist_ok=True)
    clean_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
    final_output_path = os.path.join(output_dir, f"chuong_{chap_idx:03d}_{clean_title}.txt")
    
    if os.path.exists(final_output_path) and os.path.getsize(final_output_path) > 1000:
        print(f"[*] Chương {chap_idx} ({title}) đã có bản dịch hoàn chỉnh: {final_output_path}. Bỏ qua.")
        return final_output_path

    print(f"\n{'='*70}")
    print(f"TIẾN HÀNH DỊCH CHƯƠNG {chap_idx}: {title} (ID: {href})")
    print(f"{'='*70}")

    paragraphs = fetch_chapter_content(href)
    print(f"[1] Đã tải RAW: {len(paragraphs)} đoạn văn.")

    # Chia đoạn thành các phần nhỏ (chunk size ~60 đoạn)
    chunk_size = 60
    chunks = [paragraphs[i:i + chunk_size] for i in range(0, len(paragraphs), chunk_size)]
    total_chunks = len(chunks)
    print(f"[2] Đã chia thành {total_chunks} phần xử lý.")

    translated_parts = []
    chap_cache_dir = os.path.join(output_dir, f"cache_chap_{chap_idx}")
    os.makedirs(chap_cache_dir, exist_ok=True)

    for idx, chunk in enumerate(chunks, 1):
        part_cache = os.path.join(chap_cache_dir, f"part_{idx}.txt")
        if os.path.exists(part_cache) and os.path.getsize(part_cache) > 100:
            print(f"  -> [Cache] Nạp phần {idx}/{total_chunks} từ đĩa.")
            with open(part_cache, "r", encoding="utf-8") as f:
                translated_parts.append(f.read())
            continue

        print(f"  -> [Chivi 3 Local] Phân tích cây ngữ pháp phần {idx}/{total_chunks} ({len(chunk)} đoạn)...", flush=True)
        raw_chunk_text = "\n\n".join(chunk)
        chivi3_chunk_text = "\n\n".join([chivi3_parse(p) for p in chunk])

        prompt = f"""Hãy biên tập hoàn thiện Phần {idx}/{total_chunks} của Chương: "{title}":

[BẢN GỐC TIẾNG TRUNG]:
{raw_chunk_text}

[BẢN THÔ CÂY NGỮ PHÁP CHIVI 3]:
{chivi3_chunk_text}

Hãy xuất ra bản dịch biên tập hoàn chỉnh:"""

        print(f"  -> [Gemini 3.6 Flash] Biên tập cao cấp phần {idx}/{total_chunks}...", flush=True)
        t0 = time.time()
        res = ask_gemini(prompt, system_instruction=SYSTEM_PROMPT)
        # Làm sạch các lời mở đầu thừa
        res = re.sub(r'^(Dưới đây là|Đây là|Bản dịch|Phần \d+).*?\n\n', '', res.strip(), flags=re.IGNORECASE)
        print(f"  -> Hoàn thành phần {idx}/{total_chunks} trong {time.time()-t0:.1f}s.")

        with open(part_cache, "w", encoding="utf-8") as f:
            f.write(res)
        translated_parts.append(res)
        time.sleep(2)

    full_text = (
        f"CHƯƠNG {chap_idx}: {title.upper()}\n"
        f"Tác phẩm: Không Tiền Tu Cái Gì Tiên?\n"
        f"Tác giả: Hùng Lang Cẩu (熊狼狗)\n"
        f"Quy trình: Chivi AI 3 Local + Gemini 3.6 Flash Senior Editor\n"
        f"{'='*70}\n\n"
        + "\n\n***\n\n".join(translated_parts)
    )

    with open(final_output_path, "w", encoding="utf-8") as f:
        f.write(full_text)

    print(f"\n[THÀNH CÔNG] Đã lưu bản dịch: {final_output_path} ({len(full_text)} ký tự)\n")
    return final_output_path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline Dịch Truyện: Chivi AI 3 Local + Gemini 3.6 Flash")
    parser.add_argument("--chap", type=int, help="Số thứ tự chương cần dịch (ví dụ: --chap 2)")
    parser.add_argument("--from_chap", type=int, help="Dịch từ chương số (ví dụ: --from_chap 2)")
    parser.add_argument("--to_chap", type=int, help="Đến chương số (ví dụ: --to_chap 5)")
    args = parser.parse_args()

    chap_list = get_chapter_list()
    print(f"Nạp danh sách chương từ Piaotia: tổng cộng {len(chap_list)} chương.")

    if args.chap:
        idx = args.chap - 1
        if 0 <= idx < len(chap_list):
            href, title = chap_list[idx]
            translate_chapter(args.chap, href, title)
        else:
            print(f"Chương {args.chap} vượt quá giới hạn (1 - {len(chap_list)})")
    elif args.from_chap and args.to_chap:
        for c in range(args.from_chap, args.to_chap + 1):
            idx = c - 1
            if 0 <= idx < len(chap_list):
                href, title = chap_list[idx]
                translate_chapter(c, href, title)
    else:
        print("Vui lòng cung cấp tham số: --chap <số_chương> hoặc --from_chap <từ> --to_chap <đến>")
