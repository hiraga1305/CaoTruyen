"""Test BNS translation pipeline on Chapter 1 of Book 14713."""
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from native_oauth.scene_contract import EntityRecord, PronounRule, SceneContract, parse_worker_output
from native_oauth.bns_prepass import UnifiedSemanticPreprocessor
from native_oauth.quality_gate import QualityGate4A
from native_oauth.spot_auditor import SpotAuditor4B
from native_oauth.run_agy import run

BOOK_DIR = ROOT / "native_oauth" / "book_14713"
source_file = BOOK_DIR / "sources" / "source_chapter_0001.json"
source = json.loads(source_file.read_text(encoding="utf-8"))

paragraphs = [s["source"] for s in source["segments"]]
print(f"Total source paragraphs: {len(paragraphs)}")

# System prompt
system_prompt = (ROOT / "native_oauth" / "prompts" / "bns_system_cache_v1.md").read_text(encoding="utf-8")

# Entities for this chapter
entities = [
    EntityRecord("萧羽", "Tiêu Vũ", "M", "hắn", "Luyện Khí tầng 1", "Bình tĩnh / thần bí"),
    EntityRecord("美女", "cô gái", "F", "nàng", "Người phàm", "Hoài nghi"),
]
pronouns = [
    PronounRule("萧羽", "美女", "COURTEOUS", "tôi", "cô", "điềm đạm"),
    PronounRule("美女", "萧羽", "COURTEOUS", "tôi", "anh", "nghi ngờ"),
]

preprocessor = UnifiedSemanticPreprocessor()

# To ensure maximum quality and avoid any token clipping, we can process in 2 scenes:
# Scene 1: paras 1 to 45
# Scene 2: paras 46 to 91
CHUNK_SIZE = 45
scene_chunks = []
for i in range(0, len(paragraphs), CHUNK_SIZE):
    scene_chunks.append((i, paragraphs[i:i+CHUNK_SIZE]))

print(f"Divided into {len(scene_chunks)} scenes.")

gate = QualityGate4A()
auditor = SpotAuditor4B(gate=gate)

work_dir = BOOK_DIR / "runs" / "chapter_0001"
work_dir.mkdir(parents=True, exist_ok=True)

translated_paragraphs = {}

for s_idx, (start_idx, chunk_paras) in enumerate(scene_chunks, start=1):
    print(f"\n--- Processing Scene {s_idx} (paras {start_idx+1} to {start_idx+len(chunk_paras)}) ---")
    
    contract, tagged_paras = preprocessor.build_scene_contract(
        chap_id=1,
        scene_id=s_idx,
        raw_paragraphs=chunk_paras,
        entities=entities,
        pronouns=pronouns,
        location_vi="Phòng trọ của Tiêu Vũ / Phòng livestream",
        mood="hồi hộp, bất ngờ",
        active_effect="vận chuyển thần thức nhìn thấu thiên cơ"
    )
    
    pipe_dsl = contract.to_pipe_dsl()
    tagged_body = "\n".join(tagged_paras)
    
    prompt_text = (
        f"{system_prompt}\n\n"
        f"GIAO THỨC SCENE HIỆN TẠI:\n"
        f"{pipe_dsl}\n\n"
        f"NGUYÊN TÁC TRUNG VĂN CẦN BIÊN DỊCH (TỪ §1 ĐẾN §{len(chunk_paras)}):\n"
        f"{tagged_body}\n\n"
        f"YÊU CẦU: Hãy dịch toàn bộ {len(chunk_paras)} đoạn văn trên theo chuẩn văn học Bạch Ngọc Sách. "
        f"Bắt đầu mỗi đoạn bằng đúng mã §1..§{len(chunk_paras)}. Tuyệt đối không để sót đoạn nào."
    )
    
    scene_run_dir = work_dir / f"scene_{s_idx}"
    scene_run_dir.mkdir(parents=True, exist_ok=True)
    prompt_file = scene_run_dir / "prompt.txt"
    prompt_file.write_text(prompt_text, encoding="utf-8")
    
    model = "gemini-3.8-flash-low" if contract.route_tier == "LOW" else "gemini-3.8-flash-medium"
    print(f"  Tier: {contract.route_tier} -> Model: {model}")
    
    # Run agy
    start_t = time.time()
    runtime = run(
        prompt_file=prompt_file,
        run_dir=scene_run_dir / "runtime",
        model=model,
        timeout=180,
        workspace=str(ROOT),
        approve_tools=False
    )
    elapsed = time.time() - start_t
    print(f"  Executed in {elapsed:.1f}s, status: {runtime.get('status')}")
    
    # Read response
    resp = runtime.get("result", {}).get("response", "")
    if not resp:
        # Check events
        events_file = scene_run_dir / "runtime" / "events.jsonl"
        if events_file.exists():
            for line in reversed(events_file.read_text(encoding="utf-8").splitlines()):
                try:
                    ev = json.loads(line)
                    if ev.get("event") == "result":
                        resp = ev.get("result", {}).get("response", "")
                        break
                except Exception:
                    pass
    
    print(f"  Response length: {len(resp)} chars")
    
    # Verify with Quality Gate 4A
    gate_result = gate.verify_paragraphs(resp, expected_paragraph_count=len(chunk_paras), contract=contract)
    print(f"  Gate 4A Result: PASS={gate_result.is_pass}, Violations={len(gate_result.violations)}")
    for v in gate_result.violations:
        print(f"    [{v.severity}] §{v.paragraph_idx}: {v.error_code} - {v.message}")
        
    for p_id, p_text in gate_result.sanitized_paragraphs.items():
        global_idx = start_idx + p_id
        translated_paragraphs[global_idx] = p_text

# Assemble final chapter text
print(f"\n[+] Total assembled paragraphs: {len(translated_paragraphs)}/{len(paragraphs)}")
final_text = "\n\n".join(translated_paragraphs[i] for i in sorted(translated_paragraphs.keys()))
out_txt = BOOK_DIR / "runs" / "chapter_0001" / "chuong_0001_dich.txt"
out_txt.write_text(final_text, encoding="utf-8")
print(f"[+] Written output to {out_txt}")
print("\n=== SAMPLE FIRST 5 PARAGRAPHS ===")
for i in range(1, 6):
    print(f"§{i}: {translated_paragraphs.get(i, '')}")
