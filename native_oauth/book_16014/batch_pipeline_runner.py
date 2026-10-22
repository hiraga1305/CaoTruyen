"""CAOTRUYEN BNS BATCH TRANSLATION RUNNER FOR BOOK 16014 (没钱修什么仙？).
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
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from native_oauth.chapter_runner import run_chapter
from native_oauth.semantic_context import normalize_profile
from native_oauth.chapter_integrity import atomic_json
from native_oauth.scene_contract import EntityRecord, PronounRule, SceneContract
from native_oauth.bns_prepass import UnifiedSemanticPreprocessor
from native_oauth.quality_gate import QualityGate4A, GateViolation
from native_oauth.spot_auditor import SpotAuditor4B
from native_oauth.run_agy import run, require_complete_runtime

BOOK_ID = "16014"
BOOK_DIR = ROOT / "native_oauth" / f"book_{BOOK_ID}"
SOURCES_DIR = BOOK_DIR / "sources"
OUTPUT_DIR = BOOK_DIR / "output_dich"
LOGS_DIR = BOOK_DIR / "logs"
RUNS_DIR = BOOK_DIR / "runs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = (ROOT / "native_oauth" / "prompts" / "bns_system_cache_v1.md").read_text(encoding="utf-8")

# Base character profiles for 《没钱修什么仙？》
BASE_ENTITIES = [
    EntityRecord("张羽", "Trương Vũ", "M", "hắn", "Học sinh nghèo Đông Dương / Nhân vật chính", "Điềm tĩnh, cơ trí, kiên định, thực dụng"),
    EntityRecord("周伟", "Chu Vĩ", "M", "hắn", "Bạn thân Trương Vũ / Học sinh", "Nhiệt tình, hào sảng"),
    EntityRecord("白真真", "Bạch Chân Chân", "F", "nàng", "Học sinh / Bạn cùng lớp", "Xinh đẹp, thanh tú"),
    EntityRecord("赵天行", "Triệu Thiên Hành", "M", "ông", "Giám khảo Tung Dương Cao Trung", "Nghiêm nghị, quan sát"),
    EntityRecord("苏海峰", "Tô Hải Phong", "M", "ông", "Giám khảo", "Khắt khe"),
    EntityRecord("王海", "Vương Hải", "M", "thầy", "Giáo viên chủ nhiệm Đông Dương", "Nhiệt tình"),
    EntityRecord("魏馨", "Ngụy Hinh", "F", "cô", "Cán bộ tuyển sinh", "Ôn hòa"),
]

BASE_PRONOUNS = [
    PronounRule("张羽", "赵天行", "COURTEOUS", "em", "thầy", "kính cẩn, điềm tĩnh"),
    PronounRule("赵天行", "张羽", "SUPERIOR", "thầy", "em", "nghiêm khắc"),
    PronounRule("张羽", "周伟", "INTIMATE", "tôi", "ông", "bạn bè thân thiết"),
    PronounRule("周伟", "张羽", "INTIMATE", "tôi", "ông", "bạn bè thân thiết"),
    PronounRule("张羽", "白真真", "COURTEOUS", "tôi", "bạn", "bình thường"),
]


def load_lore():
    lore_file = BOOK_DIR / "lore.json"
    if lore_file.exists():
        return json.loads(lore_file.read_text(encoding="utf-8"))
    return {}


_ENTITY_SEEDS, _PRONOUN_SEEDS = BASE_ENTITIES, BASE_PRONOUNS


def get_semantic_profile():
    return normalize_profile(BOOK_ID, _ENTITY_SEEDS, _PRONOUN_SEEDS, load_lore())


BASE_ENTITIES, BASE_PRONOUNS, BASE_GLOSSARY = get_semantic_profile()


def translate_scene(
    preprocessor: UnifiedSemanticPreprocessor,
    gate: QualityGate4A,
    auditor: SpotAuditor4B,
    chap_num: int,
    scene_idx: int,
    raw_paras: list[str],
    prev_vi_context: str,
    target_model: str,
    timeout: int = 150,
    prev_source_context: str = "",
    next_source_context: str = "",
    runtime_root: Path = None
) -> tuple[dict[int, str], str, bool]:
    scene_work_dir = (runtime_root or RUNS_DIR) / f"chapter_{chap_num:04d}" / f"scene_{scene_idx}"
    scene_work_dir.mkdir(parents=True, exist_ok=True)
    
    entities, pronouns, glossary = get_semantic_profile()
    system_prompt = (ROOT / "native_oauth/prompts/bns_system_cache_v1.md").read_text(encoding="utf-8")
    contract, tagged_paras = preprocessor.build_scene_contract(
        chap_id=chap_num,
        scene_id=scene_idx,
        raw_paragraphs=raw_paras,
        entities=entities,
        pronouns=pronouns,
        prev_vi=prev_vi_context[-800:] if prev_vi_context else "",
        glossary=glossary,
        source_before=prev_source_context, source_after=next_source_context,
        genre='XIANXIA_MODERN_SCHOOL'
    )
    
    pipe_dsl = contract.to_pipe_dsl()
    tagged_body = "\n".join(tagged_paras)
    
    prompt_text = (
        f"{system_prompt}\n\n"
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
    
    resp = require_complete_runtime(runtime, target_model)

    gate_result = gate.verify_paragraphs(resp, expected_paragraph_count=len(raw_paras), contract=contract)
    
    atomic_json(scene_work_dir / "gate.json", {
        "status": "STRUCTURAL_PASS" if gate_result.is_pass else "BLOCKED",
        "expected": len(raw_paras), "actual": len(gate_result.sanitized_paragraphs),
        "violations": [vars(v) for v in gate_result.violations],
        "semantic_context": contract.semantic_context,
    })

    last_text = gate_result.sanitized_paragraphs.get(len(raw_paras), "")
    return gate_result.sanitized_paragraphs, last_text, gate_result.is_pass


def process_chapter(
    chap_num: int,
    preprocessor: UnifiedSemanticPreprocessor,
    gate: QualityGate4A,
    auditor: SpotAuditor4B,
    model: str = "gemini-3.8-flash-high",
    force: bool = False,
    initial_context: str = ""
) -> bool:
    generation_root = RUNS_DIR / ("generation_" + uuid.uuid4().hex)
    def scene(scene_idx, raw_paras, context):
        return translate_scene(preprocessor=preprocessor, gate=gate, auditor=auditor,
                               chap_num=chap_num, scene_idx=scene_idx, raw_paras=raw_paras,
                               prev_vi_context=context["prev_vi"], target_model=model,
                               prev_source_context=context["prev_zh"],
                               next_source_context=context["next_zh"], runtime_root=generation_root)
    toc_file = BOOK_DIR / "toc.json"
    total = len(json.loads(toc_file.read_text(encoding="utf-8"))) if toc_file.exists() else 325
    return run_chapter(chap_num, BOOK_ID, 'Không tiền tu tiên cái gì', 'XIANXIA_MODERN_SCHOOL',
                       SOURCES_DIR, OUTPUT_DIR, scene, model, force, total_chapters=total, runtime_root=generation_root)


def main():
    parser = argparse.ArgumentParser(description="CaoTruyen BNS Batch Translator for Book 16014")
    parser.add_argument("--from-chapter", type=int, default=1)
    parser.add_argument("--to-chapter", type=int, default=5)
    parser.add_argument("--model", default="gemini-3.8-flash-high")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    
    preprocessor = UnifiedSemanticPreprocessor()
    gate = QualityGate4A()
    auditor = SpotAuditor4B(gate=gate)
    
    print(f"================================================================")
    print(f" CAOTRUYEN BNS BATCH PIPELINE: CHAPTERS {args.from_chapter} -> {args.to_chapter}")
    print(f" Target Novel: Book 16014 (没钱修什么仙？)")
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
    print(f"    Draft directory (unreviewed): {OUTPUT_DIR.parent / 'drafts'}")
    print(f"================================================================")

    if success != total:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
