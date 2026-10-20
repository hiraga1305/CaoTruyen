import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import re
import json
import time
import ssl
import urllib.request
import argparse
from bs4 import BeautifulSoup

from multi_llm_client import ask_ai, load_config
from get_toc import matches as toc_matches

LORE_FILE = "novel_lore.json"
OUTPUT_DIR = "output_dich"

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
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
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
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 + attempt * 2)
                continue
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

def critic_qa_linter(text):
    lines = text.split("\n")
    cleaned_lines = []
    skip_prefixes = [
        "dưới đây là", "đây là bản dịch", "hy vọng bản dịch",
        "chúc bạn đọc truyện", "bản dịch:", "lưu ý:", "dịch giả:",
        "here is the translation", "certainly"
    ]
    for line in lines:
        stripped = line.strip()
        if not stripped:
            cleaned_lines.append("")
            continue
        lower_line = stripped.lower()
        if any(lower_line.startswith(prefix) for prefix in skip_prefixes):
            continue
        # Chuẩn hóa đối thoại: “...” hoặc "..." ở đầu câu chuyển thành - "..."
        if (stripped.startswith('"') or stripped.startswith('“')) and not stripped.startswith('- '):
            stripped = '- ' + stripped
        cleaned_lines.append(stripped)

    result = "\n".join(cleaned_lines)
    result = result.replace("正 ", "đang ").replace("仙 đạo", "Tiên đạo").replace("thổ nát", "thổ nạp").replace("Thổ nát", "Thổ nạp")
    result = re.sub(r'\n{3,}', '\n\n', result).strip()
    return result

SYSTEM_PROMPT = """Bạn là Tổng Biên Tập viên dịch thuật tiểu thuyết mạng Trung - Việt xuất sắc nhất (Senior Web Novel Editor).
Nhiệm vụ: Bạn nhận được [BẢN RAW TIẾNG TRUNG] và [BẢN THÔ CÂY NGỮ PHÁP CHIVI 3] của từng phần trong chương truyện.

Quy tắc biên tập:
1. KHÓA CỨNG 100% các Danh từ riêng Hán Việt đã định danh trong bản Chivi 3:
   - Nhân vật: Trương Vũ, Chu Vĩ, Bạch Chân Chân, Hùng Lang Cẩu, Trương Phiên Phiên...
   - Địa danh / Trường học: Côn Khư, Tung Dương, Đông Dương, Bạch Long, Tử Vân, Hồng Tháp...
   - Thuật ngữ Tiên đạo: Vô Cực Vân Thủ, Bối Long Phiên Nhạc, Chu Thiên Thải Khí, Thiên Võ Luyện Tâm, Linh giới, Vũ Thư, Kiện Thể...
2. Nhuận sắc câu từ: Biến câu văn thô ráp thành bản dịch xuất sắc đạt 95% sức mạnh dịch giả người thật.
   - Giữ trọn văn phong hài hước châm biếm đen tối (dark comedy/cyberpunk tu tiên) độc nhất vô nhị của tác giả Hùng Lang Cẩu.
   - Nhịp điệu câu văn gãy gọn, dứt khoát, mượt mà tự nhiên, không vấp váp.
3. Chuẩn hóa đại từ xưng hô theo đúng quan hệ ngữ cảnh.
4. Định dạng:
   - Các câu thoại nhân vật bắt đầu bằng gạch đầu dòng: - "..."
   - Mỗi đoạn văn ngắt dòng thoáng mắt, dễ đọc.
   - Dịch đầy đủ 100% nội dung, TUYỆT ĐỐI KHÔNG tóm tắt hay cắt xén.
   - Xuất thẳng nội dung bản dịch, KHÔNG kèm các câu mở đầu/kết thúc chào hỏi.
"""

def process_single_chapter(chap_num, href, title, provider=None, force=False):
    clean_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
    final_output_path = os.path.join(OUTPUT_DIR, f"chuong_{chap_num:03d}_{clean_title}.txt")

    if not force and os.path.exists(final_output_path) and os.path.getsize(final_output_path) > 1000:
        print(f"[*] [BỎ QUA] Chương {chap_num}: '{title}' đã có bản dịch hoàn chỉnh trên đĩa.", flush=True)
        return True

    print(f"\n{'='*75}", flush=True)
    print(f"BẮT ĐẦU DỊCH CHƯƠNG {chap_num}: {title} (Provider: {provider or 'Auto'})", flush=True)
    print(f"{'='*75}", flush=True)

    paragraphs = fetch_chapter_raw(href)
    print(f"[*] Đã tải RAW: {len(paragraphs)} đoạn văn.", flush=True)

    glossary = load_lore()
    chunk_size = 60
    chunks = [paragraphs[i:i + chunk_size] for i in range(0, len(paragraphs), chunk_size)]
    total_chunks = len(chunks)

    chap_cache_dir = os.path.join(OUTPUT_DIR, f"cache_chap_{chap_num}")
    os.makedirs(chap_cache_dir, exist_ok=True)

    translated_parts = []
    chap_start_time = time.time()
    total_tokens = 0
    last_model = "unknown"

    for idx, chunk in enumerate(chunks, 1):
        part_file = os.path.join(chap_cache_dir, f"part_{idx}.txt")
        meta_file = os.path.join(chap_cache_dir, f"meta_{idx}.json")

        if os.path.exists(part_file) and os.path.exists(meta_file):
            print(f"  -> [Cache Hit] Nạp phần {idx}/{total_chunks} từ đĩa.", flush=True)
            with open(part_file, "r", encoding="utf-8") as f:
                translated_parts.append(f.read())
            with open(meta_file, "r", encoding="utf-8") as f:
                meta = json.load(f)
                total_tokens += meta.get("total_tokens", 0)
            continue

        raw_chunk_text = "\n\n".join(chunk)
        chivi3_chunk_text = "\n\n".join([chivi3_parse_advanced(p, glossary) for p in chunk])

        prompt = f"""Hãy biên tập hoàn thiện Phần {idx}/{total_chunks} của Chương {chap_num}: "{title}":

[BẢN GỐC TIẾNG TRUNG]:
{raw_chunk_text}

[BẢN THÔ CÂY NGỮ PHÁP CHIVI 3]:
{chivi3_chunk_text}

Hãy xuất ra bản dịch biên tập hoàn chỉnh:"""

        print(f"  -> [Phần {idx}/{total_chunks}] Chivi 3 AST -> Gửi AI Model...", flush=True)
        t0 = time.time()
        res_text, usage, model_used = ask_ai(prompt, system_instruction=SYSTEM_PROMPT, preferred_provider=provider)
        elapsed = time.time() - t0
        last_model = model_used

        clean_res = critic_qa_linter(res_text)
        translated_parts.append(clean_res)

        p_tokens = usage.get("prompt_tokens", usage.get("promptTokenCount", 0))
        c_tokens = usage.get("completion_tokens", usage.get("candidatesTokenCount", 0))
        part_tok = usage.get("total_tokens", usage.get("totalTokenCount", p_tokens + c_tokens))
        total_tokens += part_tok

        with open(part_file, "w", encoding="utf-8") as f:
            f.write(clean_res)
        with open(meta_file, "w", encoding="utf-8") as f:
            json.dump({"part": idx, "model": model_used, "total_tokens": part_tok, "elapsed": round(elapsed, 2)}, f, indent=2)

        print(f"     Xong trong {elapsed:.2f}s | Model: {model_used} | Tokens: {part_tok}", flush=True)

    header = f"CHƯƠNG {chap_num}: {title}\nTác phẩm: Không Tiền Tu Cái Gì Tiên?\nTác giả: Hùng Lang Cẩu (熊狼狗)\nQuy trình: Pipeline 2 Multi-Provider API ({last_model})\n{'='*75}\n\n"
    full_chapter = header + "\n\n".join(translated_parts)

    with open(final_output_path, "w", encoding="utf-8") as f:
        f.write(full_chapter)

    total_elapsed = round(time.time() - chap_start_time, 2)
    analytics_file = os.path.join(OUTPUT_DIR, f"analytics_chap_{chap_num:03d}.json")
    with open(analytics_file, "w", encoding="utf-8") as f:
        json.dump({
            "chapter": chap_num,
            "title": title,
            "provider": provider or "auto",
            "model": last_model,
            "characters": len(full_chapter),
            "elapsed_seconds": total_elapsed,
            "total_tokens": total_tokens
        }, f, ensure_ascii=False, indent=2)

    print(f"\n[HOÀN TẤT CHƯƠNG {chap_num}] File: {final_output_path} ({len(full_chapter):,} ký tự, {total_elapsed}s)\n", flush=True)
    return True

def main():
    parser = argparse.ArgumentParser(description="Pipeline 2: Dịch truyện tự động đa nguồn AI API (Portable / Headless)")
    parser.add_argument("--chap", type=int, help="Chạy một chương cụ thể (vd: --chap 82)")
    parser.add_argument("--from_chap", type=int, default=1, help="Chương bắt đầu")
    parser.add_argument("--to_chap", type=int, default=len(toc_matches), help="Chương kết thúc")
    parser.add_argument("--provider", type=str, choices=["gemini", "deepseek", "openrouter", "custom_openai"], help="Chỉ định nhà cung cấp AI")
    parser.add_argument("--force", action="store_true", help="Bắt buộc dịch lại kể cả khi chương đã có sẵn trên đĩa")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if args.chap:
        idx = args.chap - 1
        if 0 <= idx < len(toc_matches):
            href, title = toc_matches[idx]
            process_single_chapter(args.chap, href, title, provider=args.provider, force=args.force)
        return

    start_c = max(1, args.from_chap)
    end_c = min(len(toc_matches), args.to_chap)
    print(f"[*] Kích hoạt Pipeline 2 từ Chương {start_c} đến Chương {end_c} (Tổng {end_c - start_c + 1} chương)", flush=True)

    for c in range(start_c, end_c + 1):
        idx = c - 1
        href, title = toc_matches[idx]
        try:
            process_single_chapter(c, href, title, provider=args.provider, force=args.force)
        except Exception as e:
            print(f"[!] Lỗi khi xử lý Chương {c}: {e}. Đang tạm dừng 5s trước khi tiếp tục...", flush=True)
            time.sleep(5)

if __name__ == "__main__":
    main()
