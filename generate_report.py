import sys
import glob
import json
import os

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

output_dir = r'i:\Softs\Antigravity\CaoTruyen\output_dich'
data = []

for c in range(12, 32):
    json_path = os.path.join(output_dir, f'analytics_chap_{c:03d}.json')
    txt_pattern = os.path.join(output_dir, f'chuong_{c:03d}_*.txt')
    files = glob.glob(txt_pattern)
    fname = os.path.basename(files[0]) if files else 'N/A'
    
    if os.path.exists(json_path):
        with open(json_path, 'r', encoding='utf-8') as f:
            item = json.load(f)
            item['file'] = fname
            data.append(item)

print(f"Da thu thap du lieu: {len(data)}/20 chuong.")
print(f"{'Chuong':<8} | {'Thoi gian':<12} | {'Prompt Tok':<12} | {'Output Tok':<12} | {'Think Tok':<10} | {'Tong Tok':<10} | {'Toc do':<12}")
print("-" * 88)

total_elapsed = 0
total_prompt = 0
total_cand = 0
total_think = 0
total_tok = 0
total_chars = 0

for d in data:
    chap = d.get('chapter', 0)
    elapsed = d.get('elapsed_seconds', 0)
    prompt = d.get('prompt_tokens', 0)
    cand = d.get('candidate_tokens', 0)
    think = d.get('thinking_tokens', 0)
    tok = d.get('total_tokens', 0)
    speed = d.get('output_token_speed', 0)
    chars = d.get('characters_translated', 0)
    
    total_elapsed += elapsed
    total_prompt += prompt
    total_cand += cand
    total_think += think
    total_tok += tok
    total_chars += chars
    
    print(f"Chap {chap:<4} | {elapsed:<10.1f}s | {prompt:<12,} | {cand:<12,} | {think:<10,} | {tok:<10,} | {speed:<10.1f} tok/s")

print("=" * 88)
print("TONG HOP 20 CHUONG (CHUONG 12 -> 31):")
print(f"  - Tong so chuong: {len(data)} chuong")
print(f"  - Tong thoi gian xu ly gom cac worker: {total_elapsed:.1f}s ({total_elapsed/60:.2f} phut)")
print(f"  - Tong Prompt Tokens: {total_prompt:,} tokens")
print(f"  - Tong Output (Candidate) Tokens: {total_cand:,} tokens")
print(f"  - Tong Thinking Tokens: {total_think:,} tokens")
print(f"  - TONG TOKENS TIEU THU: {total_tok:,} tokens")
print(f"  - Tong ky tu tieng Viet: {total_chars:,} ky tu")
print(f"  - Trung binh moi chuong: {total_tok/len(data):,.0f} tokens / chuong")
print(f"  - Toc do trung binh dau ra: {total_cand/max(total_elapsed, 1):.1f} candidate tokens/giay")
