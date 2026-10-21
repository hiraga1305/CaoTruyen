"""CAOTRUYEN BNS BATCH TRANSLATION RUNNER FOR BOOK 49736 (寻找无间地狱 / 尋找無間地獄).
Integrates:
- Module 1: BNS Literary Prompt & SceneContract DSL
- Module 2: Tier 1 NLP Pre-processor (bns_prepass.py)
- Execution: Native agy OAuth runner (run_agy.py)
- Module 3.1: Quality Gate 4A Linter & Verification (quality_gate.py)
- Module 3.2: Spot-Audit 4B Surgical Micro-Repair (spot_auditor.py)
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from native_oauth.scene_contract import EntityRecord, PronounRule, SceneContract
from native_oauth.bns_prepass import UnifiedSemanticPreprocessor
from native_oauth.quality_gate import QualityGate4A, GateViolation
from native_oauth.spot_auditor import SpotAuditor4B
from native_oauth.run_agy import run

BOOK_ID = "49736"
BOOK_DIR = ROOT / "native_oauth" / f"book_{BOOK_ID}"
SOURCES_DIR = BOOK_DIR / "sources"
OUTPUT_DIR = BOOK_DIR / "output_dich"
LOGS_DIR = BOOK_DIR / "logs"
RUNS_DIR = BOOK_DIR / "runs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = (ROOT / "native_oauth" / "prompts" / "bns_system_cache_v1.md").read_text(encoding="utf-8")

# Base character profiles for 《寻找无间地狱》 (supporting both Simplified & Traditional forms)
BASE_ENTITIES = [
    EntityRecord("云千峰", "Vân Thiên Phong", "M", "hắn", "Chủ tiệm phong thủy Tam Tiền Tế Thế / Nhân vật chính", "Trầm tĩnh, cơ trí, quan sát tỉ mỉ, mỉa mai sắc sảo"),
    EntityRecord("雲千峰", "Vân Thiên Phong", "M", "hắn", "Chủ tiệm phong thủy Tam Tiền Tế Thế / Nhân vật chính", "Trầm tĩnh, cơ trí, quan sát tỉ mỉ, mỉa mai sắc sảo"),
    EntityRecord("姜柔甲", "Khương Nhu Giáp", "F", "nàng", "Khách hàng đầu tiên / Nữ chính", "Thanh tú, ngập tràn u uất và nghi hoặc, giàu có"),
    EntityRecord("薑柔甲", "Khương Nhu Giáp", "F", "nàng", "Khách hàng đầu tiên / Nữ chính", "Thanh tú, ngập tràn u uất và nghi hoặc, giàu có"),
    EntityRecord("秦疏影", "Tần Sơ Ảnh", "F", "nàng", "Nữ chính / Bạn đồng hành", "Thông tuệ, quyết đoán"),
    EntityRecord("罗琳娜", "La Lâm Na", "F", "nàng", "Nhà thám hiểm lai / Bạn đồng hành", "Phóng khoáng, dũng cảm"),
    EntityRecord("羅琳娜", "La Lâm Na", "F", "nàng", "Nhà thám hiểm lai / Bạn đồng hành", "Phóng khoáng, dũng cảm"),
    EntityRecord("姜玉林", "Khương Ngọc Lâm", "M", "ông", "Trưởng bối Khương gia", "Nghiêm nghị, từng trải"),
    EntityRecord("薑玉林", "Khương Ngọc Lâm", "M", "ông", "Trưởng bối Khương gia", "Nghiêm nghị, từng trải"),
    EntityRecord("满都拉图", "Mãn Đô Lạp Đồ", "M", "hắn", "Người thám hiểm Mông Cổ", "Thẳng thắn, can trường"),
    EntityRecord("滿都拉圖", "Mãn Đô Lạp Đồ", "M", "hắn", "Người thám hiểm Mông Cổ", "Thẳng thắn, can trường"),
    EntityRecord("维多利亚", "Victoria", "F", "cô", "Nhân vật người nước ngoài", "Phương Tây"),
    EntityRecord("維多利亞", "Victoria", "F", "cô", "Nhân vật người nước ngoài", "Phương Tây"),
    EntityRecord("小神经", "Tiểu Thần Kinh", "F", "cô ấy", "Đồng hành thám hiểm", "Kỳ quặc, tinh quái"),
    EntityRecord("安德", "An Đức", "M", "hắn", "Nhân vật thám hiểm / Thuyền viên", "Thực dụng, cơ trí"),
]

BASE_PRONOUNS = [
    PronounRule("云千峰", "姜柔甲", "COURTEOUS", "tôi", "cô", "điềm tĩnh, lịch thiệp, thăm dò"),
    PronounRule("姜柔甲", "云千峰", "COURTEOUS", "tôi", "anh", "lo âu, khẩn thiết, tôn kính"),
    PronounRule("雲千峰", "薑柔甲", "COURTEOUS", "tôi", "cô", "điềm tĩnh, lịch thiệp, thăm dò"),
    PronounRule("薑柔甲", "雲千峰", "COURTEOUS", "tôi", "anh", "lo âu, khẩn thiết, tôn kính"),
    PronounRule("云千峰", "秦疏影", "COURTEOUS", "tôi", "cô", "bình thản, thăm dò"),
    PronounRule("秦疏影", "云千峰", "COURTEOUS", "tôi", "anh", "sắc sảo"),
    PronounRule("雲千峰", "秦疏影", "COURTEOUS", "tôi", "cô", "bình thản, thăm dò"),
    PronounRule("秦疏影", "雲千峰", "COURTEOUS", "tôi", "anh", "sắc sảo"),
    PronounRule("云千峰", "罗琳娜", "COURTEOUS", "tôi", "cô", "thẳng thắn, đối đáp nhanh"),
    PronounRule("罗琳娜", "云千峰", "COURTEOUS", "tôi", "anh", "phóng khoáng, khiêu khích"),
    PronounRule("雲千峰", "羅琳娜", "COURTEOUS", "tôi", "cô", "thẳng thắn, đối đáp nhanh"),
    PronounRule("羅琳娜", "雲千峰", "COURTEOUS", "tôi", "anh", "phóng khoáng, khiêu khích"),
]


def load_lore():
    lore_file = BOOK_DIR / "lore.json"
    if lore_file.exists():
        return json.loads(lore_file.read_text(encoding="utf-8"))
    return {}


def translate_scene(
    preprocessor: UnifiedSemanticPreprocessor,
    gate: QualityGate4A,
    auditor: SpotAuditor4B,
    chap_num: int,
    scene_idx: int,
    raw_paras: list[str],
    prev_vi_context: str,
    target_model: str,
    timeout: int = 180
) -> tuple[dict[int, str], str, bool]:
    scene_work_dir = RUNS_DIR / f"chapter_{chap_num:04d}" / f"scene_{scene_idx}"
    scene_work_dir.mkdir(parents=True, exist_ok=True)
    
    contract, tagged_paras = preprocessor.build_scene_contract(
        chap_id=chap_num,
        scene_id=scene_idx,
        raw_paragraphs=raw_paras,
        entities=BASE_ENTITIES,
        pronouns=BASE_PRONOUNS,
        location_vi="Cửu Giang Thành / Tiệm Tam Tiền Tế Thế / Hành trình thám hiểm",
        mood="kỳ bí, u ám, hồi hộp, trinh thám",
        active_effect="đoán quẻ bói toán, chúc do thuật, tầm tìm dấu vết",
        prev_vi=prev_vi_context[:200] if prev_vi_context else ""
    )
    
    pipe_dsl = contract.to_pipe_dsl()
    tagged_body = "\n".join(tagged_paras)
    
    prompt_text = (
        f"{SYSTEM_PROMPT}\n\n"
        f"GIAO THỨC SCENE HIỆN TẠI:\n"
        f"{pipe_dsl}\n\n"
        f"NGUYÊN TÁC TRUNG VĂN CẦN BIÊN DỊCH (TỪ §1 ĐẾN §{len(raw_paras)}):\n"
        f"{tagged_body}\n\n"
        f"YÊU CẦU: Hãy dịch toàn bộ {len(raw_paras)} đoạn văn trên theo chuẩn văn học Bạch Ngọc Sách. "
        f"Bắt đầu mỗi đoạn bằng đúng mã §1..§{len(raw_paras)}. Tuyệt đối không để sót đoạn nào."
    )
    
    prompt_file = scene_work_dir / "prompt.txt"
    prompt_file.write_text(prompt_text, encoding="utf-8")
    
    runtime = run(
        prompt_file=prompt_file,
        run_dir=scene_work_dir / "runtime",
        model=target_model,
        timeout=timeout,
        workspace=str(ROOT),
        approve_tools=False
    )
    
    resp = runtime.get("result", {}).get("response", "")
    if not resp:
        events_file = scene_work_dir / "runtime" / "events.jsonl"
        if events_file.exists():
            for line in reversed(events_file.read_text(encoding="utf-8").splitlines()):
                try:
                    ev = json.loads(line)
                    if ev.get("event") == "result":
                        resp = ev.get("result", {}).get("response", "")
                        break
                except Exception:
                    pass
                    
    gate_result = gate.verify_paragraphs(resp, expected_paragraph_count=len(raw_paras), contract=contract)
    
    if not gate_result.is_pass and any(v.severity == "ERROR" for v in gate_result.violations):
        print(f"    [!] Gate 4A flagged {len(gate_result.violations)} violations. Applying Spot-Audit 4B...")
        repair_tasks = auditor.identify_repair_targets(gate_result, raw_paras, contract)
        for task in repair_tasks:
            fixed_text = task.current_flawed_translation
            for v in task.violations:
                if v.error_code == "CALQUE_KHONG_CHO_LA_DUNG":
                    fixed_text = re.sub(r"\bkhông cho là đúng\b", "chẳng mảy may bận tâm", fixed_text)
                elif v.error_code == "CALQUE_SAC_MAT_NGUNG_LAI":
                    fixed_text = re.sub(r"\bsắc mặt\s+(?:một\s+)?ngưng lại\b", "sắc mặt chợt đanh lại", fixed_text)
                elif v.error_code == "CALQUE_HIT_NGUOC_KHI_LANH":
                    fixed_text = re.sub(r"\bhít ngược một ngụm khí lạnh\b", "lạnh toát cả sống lưng", fixed_text)
                elif v.error_code == "CALQUE_DEM_TAN_NGU_DONG_TU":
                    fixed_text = re.sub(r"\bđem\s+([^,.]+?)\s+ném ra\b", r"ném \1 ra", fixed_text)
            gate_result.sanitized_paragraphs[task.paragraph_idx] = fixed_text
            
    last_text = gate_result.sanitized_paragraphs.get(len(raw_paras), "")
    return gate_result.sanitized_paragraphs, last_text, gate_result.is_pass


def get_predecessor_context(chap_num: int, capsule_context: str = "") -> str:
    if chap_num > 1:
        prev_file = OUTPUT_DIR / f"chuong_{chap_num - 1:04d}.txt"
        if prev_file.exists():
            try:
                txt = prev_file.read_text(encoding="utf-8")
                paras = [p.strip() for p in txt.split("\n\n") if p.strip()]
                if paras:
                    return "\n".join(paras[-3:])[:300]
            except Exception:
                pass
    return capsule_context[:300] if capsule_context else ""


def process_chapter(
    chap_num: int,
    preprocessor: UnifiedSemanticPreprocessor,
    gate: QualityGate4A,
    auditor: SpotAuditor4B,
    model: str = "gemini-3.8-flash-high",
    force: bool = False,
    initial_context: str = ""
) -> bool:
    out_file = OUTPUT_DIR / f"chuong_{chap_num:04d}.txt"
    if out_file.exists() and not force:
        print(f"[=] Chapter {chap_num:02d} already exists. Skipping.")
        return True
        
    src_file = SOURCES_DIR / f"source_chapter_{chap_num:04d}.json"
    if not src_file.exists():
        print(f"[!] Source for Chapter {chap_num:02d} missing at {src_file}")
        return False
        
    src_data = json.loads(src_file.read_text(encoding="utf-8"))
    title = src_data.get("title", f"Chương {chap_num}")
    paragraphs = [s["source"] for s in src_data["segments"]]
    total_paras = len(paragraphs)
    
    print(f"\n=======================================================")
    print(f"[*] TRANSLATING CHAPTER {chap_num:02d}: {title} ({total_paras} paras)")
    print(f"=======================================================")
    
    chunk_size = 50
    chunks = []
    for i in range(0, total_paras, chunk_size):
        chunks.append((len(chunks) + 1, i, paragraphs[i:i + chunk_size]))
    
    chapter_paras: dict[int, str] = {}
    prev_context = get_predecessor_context(chap_num, initial_context)
    start_time = time.time()
    
    for s_idx, offset, chunk in chunks:
        print(f"  [>] Processing Scene {s_idx}/{len(chunks)} ({len(chunk)} paras, offset +{offset})...")
        t0 = time.time()
        scene_dict, last_para_text, is_pass = translate_scene(
            preprocessor=preprocessor,
            gate=gate,
            auditor=auditor,
            chap_num=chap_num,
            scene_idx=s_idx,
            raw_paras=chunk,
            prev_vi_context=prev_context,
            target_model=model
        )
        prev_context = last_para_text
        for local_id, text in scene_dict.items():
            chapter_paras[offset + local_id] = text
        print(f"      Completed in {time.time()-t0:.1f}s (Gate PASS={is_pass})")
        
    if len(chapter_paras) < total_paras:
        print(f"  [!] Missing paragraphs: got {len(chapter_paras)}/{total_paras}")
        
    clean_lines = []
    for i in sorted(chapter_paras.keys()):
        p_text = chapter_paras[i].strip()
        if p_text:
            clean_lines.append(p_text)
            clean_lines.append("")
            
    full_text = "\n".join(clean_lines).strip() + "\n"
    out_file.write_text(full_text, encoding="utf-8")
    
    total_time = time.time() - start_time
    print(f"  [✓] Chapter {chap_num:02d} saved to {out_file.name} ({len(chapter_paras)}/{total_paras} paras, {total_time:.1f}s)")
    return True


def main():
    parser = argparse.ArgumentParser(description="CaoTruyen BNS Batch Translator for Book 49736")
    parser.add_argument("--from-chapter", type=int, default=1)
    parser.add_argument("--to-chapter", type=int, default=1)
    parser.add_argument("--model", default="gemini-3.8-flash-high")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    
    preprocessor = UnifiedSemanticPreprocessor()
    gate = QualityGate4A()
    auditor = SpotAuditor4B(gate=gate)
    
    print(f"================================================================")
    print(f" CAOTRUYEN BNS BATCH PIPELINE: CHAPTERS {args.from_chapter} -> {args.to_chapter}")
    print(f" Target Novel: Book 49736 (寻找无间地狱 / 尋找無間地獄)")
    print(f" Architecture: NLP Pre-pass -> SceneContract DSL -> Flash ({args.model}) -> QualityGate4A")
    print(f"================================================================")
    
    success = 0
    total = args.to_chapter - args.from_chapter + 1
    start_all = time.time()
    
    for chap in range(args.from_chapter, args.to_chapter + 1):
        try:
            ok = process_chapter(
                chap_num=chap,
                preprocessor=preprocessor,
                gate=gate,
                auditor=auditor,
                model=args.model,
                force=args.force
            )
            if ok:
                success += 1
        except Exception as e:
            print(f"[!] Error on Chapter {chap}: {e}")
            import traceback
            traceback.print_exc()
            
    print(f"\n================================================================")
    print(f"[+] BATCH COMPLETE: {success}/{total} chapters translated in {time.time()-start_all:.1f}s")
    print(f"    Output directory: {OUTPUT_DIR}")
    print(f"================================================================")


if __name__ == "__main__":
    main()
