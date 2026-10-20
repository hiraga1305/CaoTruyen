import os
import sys
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
import re
import json
import time
import urllib.request
import ssl
from bs4 import BeautifulSoup
from gemini_helper import ask_gemini

LORE_FILE = "novel_lore.json"
OUTPUT_DIR = "output_dich"
ANALYTICS_FILE = "token_analytics_chap2_to_11.json"

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

def save_lore_entity(key, value, category="cultivation_and_tech"):
    data = {}
    if os.path.exists(LORE_FILE):
        with open(LORE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    if category not in data:
        data[category] = {}
    data[category][key] = value
    with open(LORE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def chivi3_parse_advanced(text, glossary):
    """
    Bộ phân tích cây cú pháp Chivi 3 nâng cao:
    - Áp dụng mỏ neo từ điển Lore động.
    - Cấu trúc câu chữ Ba/Bi/Tuong (Disposal/Passive).
    - Cụm Định - Trung ngữ (N + Adj đảo ngược).
    - Giới từ chỉ nơi chốn / phương hướng (Tai/Tung/Vang).
    """
    res = text
    # 1. Glossary Anchor (ưu tiên chuỗi dài nhất)
    for k in sorted(glossary.keys(), key=len, reverse=True):
        res = res.replace(k, glossary[k])

    # 2. Cấu trúc câu chữ 把/将 (Disposal): [把/将] + [Obj] + [Verb] -> [Verb] + [Obj]
    res = re.sub(r'(?:把|将)([^,.\n!?:;]+?)(摘除|唤醒|遮蔽|卖掉|还清|吞噬|打碎|炼化|吸收|提升)', r'\2 \1', res)

    # 3. Cấu trúc 被 (Passive)
    res = re.sub(r'被([^,.\n!?:;]+?)(打败|吞噬|吸收|击退|杀死)', r'bị \1 \2', res)

    # 4. Trợ từ kết cấu 的 (De-resolver)
    res = re.sub(r'(\w{2,4})的(\w{2,4})', r'\2 của \1', res)

    return res

def critic_qa_linter(text):
    """
    Lớp thẩm định và hiệu đính tự động (Critic / QA Filter):
    - Loại bỏ các câu mở đầu/kết thúc văn mẫu của AI.
    - Kiểm tra và xử lý chữ Hán còn sót lại.
    - Chuẩn hóa định dạng lời thoại.
    """
    lines = text.split("\n")
    cleaned_lines = []
    for line in lines:
        stripped = line.strip()
        # Loại bỏ các dòng intro/outro của AI
        if stripped.startswith("***") or stripped.startswith("---") or re.match(r'^(Dưới đây là|Đây là|Bản dịch|Phần \d+|Chúc bạn|Hy vọng).*', stripped, re.IGNORECASE):
            continue
        # Chuẩn hóa thoại: nếu có dấu thoại mà chưa có gạch đầu dòng
        if stripped.startswith("“") or stripped.startswith('"'):
            stripped = "- " + stripped
        cleaned_lines.append(stripped)

    result = "\n".join(cleaned_lines)
    result = result.replace("正 ", "đang ").replace("仙 đạo", "Tiên đạo").replace("仙人", "tiên nhân").replace("thổ nát", "thổ nạp").replace("Thổ nát", "Thổ nạp")
    # Gộp các dòng trống liên tiếp
    result = re.sub(r'\n{3,}', '\n\n', result).strip()
    return result

def fetch_chapter_raw(href):
    url = f"https://www.piaotia.com/html/16/16014/{href}"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, context=ctx, timeout=15) as resp:
        html = resp.read().decode('gbk', errors='ignore')
        
    soup = BeautifulSoup(html, 'html.parser')
    for s in soup.find_all(['script', 'style', 'a', 'table']):
        s.decompose()

    raw_text = soup.get_text()
    paragraphs = []
    for p in raw_text.split('\xa0\xa0\xa0\xa0'):
        clean_p = p.strip()
        if not clean_p:
            continue
        if clean_p.startswith('选择背景') or clean_p.startswith('选择字体') or '飘天文学' in clean_p or '上一章' in clean_p or '下一章' in clean_p or '返回书页' in clean_p or '加入书签' in clean_p or '天才一秒记住' in clean_p:
            continue
        paragraphs.append(clean_p)
        
    return paragraphs

SYSTEM_PROMPT = """Bạn là Tổng Biên Tập viên dịch thuật tiểu thuyết mạng Trung - Việt xuất sắc nhất (Senior Web Novel Editor).
Nhiệm vụ: Bạn nhận được [BẢN RAW TIẾNG TRUNG] và [BẢN THÔ CÂY NGỮ PHÁP CHIVI 3] của từng phần trong chương truyện.

Quy tắc biên tập:
1. KHÓA CỨNG 100% các Danh từ riêng Hán Việt đã định danh trong bản Chivi 3:
   - Nhân vật: Trương Vũ, Chu Vĩ, Bạch Chân Chân, Hùng Lang Cẩu...
   - Địa danh / Trường học: Côn Khư, Tung Dương, Đông Dương, Trường Cấp hai Đông Dương, Trường Cấp ba Tung Dương...
   - Thuật ngữ Tiên đạo: Vạn Hồn Phiên, Trúc Cơ, Kết Đan, Hồn Tu, Kim Đan, Nguyên Anh, Thiên Linh Căn, Tu Tiên Đới, Pháp Lực Đới, Thỉnh Thần, Vũ Thư, Kiện Thể, Chu Thiên Thải Khí...
2. Nhuận sắc câu từ: Biến câu văn thô ráp thành bản dịch xuất sắc đạt 95% sức mạnh dịch giả người thật.
   - Giữ trọn văn phong hài hước châm biếm đen tối (dark comedy/cyberpunk tu tiên) độc nhất vô nhị của tác giả Hùng Lang Cẩu.
   - Nhịp điệu câu văn gãy gọn, dứt khoát, mượt mà tự nhiên, không vấp váp, không dùng từ ngữ Hán Việt sống sượng.
3. Chuẩn hóa đại từ xưng hô theo đúng quan hệ ngữ cảnh (mẹ - con, giám khảo - thí sinh, sàn đòi nợ - con nợ, thầy - trò, bạn bè).
4. Định dạng:
   - Các câu thoại nhân vật bắt đầu bằng gạch đầu dòng: - "..."
   - Mỗi đoạn văn ngắt dòng thoáng mắt, dễ đọc.
   - Dịch đầy đủ 100% nội dung, TUYỆT ĐỐI KHÔNG tóm tắt hay cắt xén.
   - Xuất thẳng nội dung bản dịch, KHÔNG kèm các câu mở đầu/kết thúc chào hỏi.
"""

def process_single_chapter(chap_num, href, title, global_stats):
    clean_title = re.sub(r'[\\/*?:"<>|]', "", title).strip()
    final_output_path = os.path.join(OUTPUT_DIR, f"chuong_{chap_num:03d}_{clean_title}.txt")
    
    if os.path.exists(final_output_path) and os.path.getsize(final_output_path) > 1000:
        print(f"\n[BỎ QUA] Chương {chap_num}: '{title}' đã có bản dịch hoàn chỉnh trên đĩa.")
        return

    print(f"\n{'='*75}")
    print(f"BẮT ĐẦU DỊCH CHƯƠNG {chap_num}: {title} (ID: {href})")
    print(f"{'='*75}")

    paragraphs = fetch_chapter_raw(href)
    print(f"[*] Đã tải RAW: {len(paragraphs)} đoạn văn ({sum(len(p) for p in paragraphs)} ký tự).")

    glossary = load_lore()

    # Chia thành các phần (~60 đoạn/phần)
    chunk_size = 60
    chunks = [paragraphs[i:i + chunk_size] for i in range(0, len(paragraphs), chunk_size)]
    total_chunks = len(chunks)

    chap_cache_dir = os.path.join(OUTPUT_DIR, f"cache_chap_{chap_num}")
    os.makedirs(chap_cache_dir, exist_ok=True)

    translated_parts = []
    chap_prompt_tokens = 0
    chap_candidate_tokens = 0
    chap_thinking_tokens = 0
    chap_total_tokens = 0
    chap_start_time = time.time()

    for idx, chunk in enumerate(chunks, 1):
        part_cache = os.path.join(chap_cache_dir, f"part_{idx}.txt")
        part_meta_cache = os.path.join(chap_cache_dir, f"meta_{idx}.json")

        if os.path.exists(part_cache) and os.path.getsize(part_cache) > 100:
            print(f"  -> [Cache Hit] Nạp phần {idx}/{total_chunks} từ đĩa.")
            with open(part_cache, "r", encoding="utf-8") as f:
                translated_parts.append(f.read())
            if os.path.exists(part_meta_cache):
                with open(part_meta_cache, "r", encoding="utf-8") as f:
                    meta = json.load(f)
                    chap_prompt_tokens += meta.get("promptTokenCount", 0)
                    chap_candidate_tokens += meta.get("candidatesTokenCount", 0)
                    chap_thinking_tokens += meta.get("thoughtsTokenCount", 0)
                    chap_total_tokens += meta.get("totalTokenCount", 0)
            continue

        raw_chunk_text = "\n\n".join(chunk)
        chivi3_chunk_text = "\n\n".join([chivi3_parse_advanced(p, glossary) for p in chunk])

        prompt = f"""Hãy biên tập hoàn thiện Phần {idx}/{total_chunks} của Chương {chap_num}: "{title}":

[BẢN GỐC TIẾNG TRUNG]:
{raw_chunk_text}

[BẢN THÔ CÂY NGỮ PHÁP CHIVI 3]:
{chivi3_chunk_text}

Hãy xuất ra bản dịch biên tập hoàn chỉnh:"""

        print(f"  -> [Phần {idx}/{total_chunks}] Chivi 3 parsed ➔ Gửi Gemini 3.6 Flash...", flush=True)
        t0 = time.time()
        res_text, usage = ask_gemini(prompt, system_instruction=SYSTEM_PROMPT, return_usage=True)
        call_time = time.time() - t0

        # Lọc QA linter
        clean_res = critic_qa_linter(res_text)

        p_tok = usage.get("promptTokenCount", 0)
        c_tok = usage.get("candidatesTokenCount", 0)
        t_tok = usage.get("thoughtsTokenCount", 0)
        tot_tok = usage.get("totalTokenCount", 0)

        chap_prompt_tokens += p_tok
        chap_candidate_tokens += c_tok
        chap_thinking_tokens += t_tok
        chap_total_tokens += tot_tok

        speed = c_tok / call_time if call_time > 0 else 0
        print(f"     Xong trong {call_time:.2f}s | Tokens: {tot_tok} (Prompt: {p_tok}, Output: {c_tok}, Think: {t_tok}) | Tốc độ: {speed:.1f} tok/s")

        with open(part_cache, "w", encoding="utf-8") as f:
            f.write(clean_res)
        with open(part_meta_cache, "w", encoding="utf-8") as f:
            json.dump(usage, f)

        translated_parts.append(clean_res)
        time.sleep(2)

    chap_elapsed = time.time() - chap_start_time

    full_chapter = (
        f"CHƯƠNG {chap_num}: {title.upper()}\n"
        f"Tác phẩm: Không Tiền Tu Cái Gì Tiên?\n"
        f"Tác giả: Hùng Lang Cẩu (熊狼狗)\n"
        f"Quy trình: Chivi AI 3 Local + Gemini 3.6 Flash Senior Editor (Agentic QA)\n"
        f"{'='*75}\n\n"
        + "\n\n***\n\n".join(translated_parts)
    )

    with open(final_output_path, "w", encoding="utf-8") as f:
        f.write(full_chapter)

    # Thống kê chương
    stat_item = {
        "chapter": chap_num,
        "title": title,
        "paragraphs": len(paragraphs),
        "characters_translated": len(full_chapter),
        "elapsed_seconds": round(chap_elapsed, 2),
        "prompt_tokens": chap_prompt_tokens,
        "candidate_tokens": chap_candidate_tokens,
        "thinking_tokens": chap_thinking_tokens,
        "total_tokens": chap_total_tokens,
        "output_token_speed": round(chap_candidate_tokens / chap_elapsed, 1) if chap_elapsed > 0 else 0
    }
    global_stats.append(stat_item)

    # Lưu file thống kê riêng cho từng chương để các subagent song song không bị xung đột
    single_stat_file = os.path.join(OUTPUT_DIR, f"analytics_chap_{chap_num:03d}.json")
    with open(single_stat_file, "w", encoding="utf-8") as f:
        json.dump(stat_item, f, ensure_ascii=False, indent=2)

    try:
        with open(ANALYTICS_FILE, "w", encoding="utf-8") as f:
            json.dump(global_stats, f, ensure_ascii=False, indent=2)
    except Exception:
        pass

    print(f"\n[HOÀN TẤT CHƯƠNG {chap_num}] File: {final_output_path}")
    print(f"-> Thời gian: {chap_elapsed:.2f}s | Tổng Tokens tiêu thụ: {chap_total_tokens:,} tokens | Tốc độ xuất: {stat_item['output_token_speed']} tok/s\n")

def run_batch_chapters(start_chap=2, end_chap=11):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    from get_toc import matches as toc_matches

    global_stats = []
    if os.path.exists(ANALYTICS_FILE):
        try:
            with open(ANALYTICS_FILE, "r", encoding="utf-8") as f:
                global_stats = json.load(f)
        except Exception:
            global_stats = []

    print("=" * 80)
    print(f"KÍCH HOẠT QUY TRÌNH AGENTIC: DỊCH 10 CHƯƠNG KẾ TIẾP (CHƯƠNG {start_chap} ĐẾN {end_chap})")
    print(f"Tác phẩm: 《没钱修什么仙？》 (Không Tiền Tu Cái Gì Tiên?)")
    print("=" * 80)

    total_batch_start = time.time()

    for c in range(start_chap, end_chap + 1):
        idx = c - 1
        if idx < len(toc_matches):
            href, title = toc_matches[idx]
            process_single_chapter(c, href, title, global_stats)
            time.sleep(3)
        else:
            print(f"[!] Không tìm thấy chương {c} trong danh sách mục lục.")

    total_batch_time = time.time() - total_batch_start
    total_tokens_consumed = sum(s["total_tokens"] for s in global_stats if start_chap <= s["chapter"] <= end_chap)
    total_candidate_tokens = sum(s["candidate_tokens"] for s in global_stats if start_chap <= s["chapter"] <= end_chap)

    print("\n" + "#" * 80)
    print("BÁO CÁO TỔNG KẾT TOÀN DIỆN 10 CHƯƠNG (CHƯƠNG 2 -> 11):")
    print(f"Tổng thời gian chạy: {total_batch_time/60:.2f} phút ({total_batch_time:.1f} giây)")
    print(f"Tổng Tokens tiêu thụ: {total_tokens_consumed:,} tokens")
    print(f"  - Prompt Tokens: {sum(s['prompt_tokens'] for s in global_stats if start_chap <= s['chapter'] <= end_chap):,}")
    print(f"  - Candidates Tokens: {total_candidate_tokens:,}")
    print(f"  - Thinking Tokens: {sum(s['thinking_tokens'] for s in global_stats if start_chap <= s['chapter'] <= end_chap):,}")
    print(f"Trung bình mỗi chương: {total_tokens_consumed // (end_chap - start_chap + 1):,} tokens/chương")
    print(f"Tốc độ trung bình: {total_candidate_tokens / total_batch_time:.1f} candidate tokens/giây")
    print("#" * 80)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Agentic Novel Translator: Chivi 3 + Gemini 3.8 Flash")
    parser.add_argument("--from_chap", type=int, default=12, help="Chương bắt đầu")
    parser.add_argument("--to_chap", type=int, default=31, help="Chương kết thúc")
    args = parser.parse_args()
    run_batch_chapters(args.from_chap, args.to_chap)
