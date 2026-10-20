"""Test Chapter 2 with gemini-3.8-flash-low to measure speed and Gate 4A compliance."""
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from native_oauth.scene_contract import EntityRecord, PronounRule
from native_oauth.bns_prepass import UnifiedSemanticPreprocessor
from native_oauth.quality_gate import QualityGate4A
from native_oauth.run_agy import run

BOOK_DIR = ROOT / "native_oauth" / "book_14713"
source_file = BOOK_DIR / "sources" / "source_chapter_0002.json"
source = json.loads(source_file.read_text(encoding="utf-8"))
paragraphs = [s["source"] for s in source["segments"]]
print(f"Total source paragraphs: {len(paragraphs)}")

system_prompt = (ROOT / "native_oauth" / "prompts" / "bns_system_cache_v1.md").read_text(encoding="utf-8")
entities = [
    EntityRecord("萧羽", "Tiêu Vũ", "M", "hắn", "Luyện Khí tầng 1", "Bình tĩnh"),
    EntityRecord("美女", "cô gái", "F", "nàng", "Người phàm", "Kinh hãi"),
    EntityRecord("唐小妹", "Đường Tiểu Tiểu", "F", "nàng", "Người phàm", "Thảng thốt"),
]
pronouns = [
    PronounRule("萧羽", "唐小妹", "COURTEOUS", "tôi", "cô", "điềm tĩnh"),
]

preprocessor = UnifiedSemanticPreprocessor()
half = len(paragraphs) // 2
scene_chunks = [(0, paragraphs[:half]), (half, paragraphs[half:])]

gate = QualityGate4A()
work_dir = BOOK_DIR / "runs" / "chapter_0002_test"
work_dir.mkdir(parents=True, exist_ok=True)

translated_paragraphs = {}

start_total = time.time()
for s_idx, (start_idx, chunk_paras) in enumerate(scene_chunks, start=1):
    contract, tagged_paras = preprocessor.build_scene_contract(
        chap_id=2,
        scene_id=s_idx,
        raw_paragraphs=chunk_paras,
        entities=entities,
        pronouns=pronouns,
        location_vi="Phòng livestream của Tiêu Vũ / Bên ngoài đường phố",
        mood="kinh hoàng, sống sót sau tai nạn",
        active_effect="thiên cơ hiển hóa"
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
    
    # Run agy with gemini-3.8-flash-low
    t0 = time.time()
    runtime = run(
        prompt_file=prompt_file,
        run_dir=scene_run_dir / "runtime",
        model="gemini-3.8-flash-low",
        timeout=120,
        workspace=str(ROOT),
        approve_tools=False
    )
    t1 = time.time()
    resp = runtime.get("result", {}).get("response", "")
    print(f"Scene {s_idx}: {t1-t0:.1f}s, response {len(resp)} chars")
    
    gate_result = gate.verify_paragraphs(resp, expected_paragraph_count=len(chunk_paras), contract=contract)
    print(f"  Gate PASS={gate_result.is_pass}, Violations={len(gate_result.violations)}")
    for p_id, p_text in gate_result.sanitized_paragraphs.items():
        translated_paragraphs[start_idx + p_id] = p_text

print(f"\nTotal elapsed: {time.time()-start_total:.1f}s")
print(f"Assembled: {len(translated_paragraphs)}/{len(paragraphs)}")
