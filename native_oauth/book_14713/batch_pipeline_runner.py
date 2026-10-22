"""CAOTRUYEN BNS BATCH TRANSLATION RUNNER FOR BOOK 14713 (我在直播间窥探天机).
Integrates:
- Module 1: BNS Literary Prompt (prompts/bns_system_cache_v1.md) & SceneContract DSL
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

BOOK_ID = "14713"
BOOK_DIR = ROOT / "native_oauth" / f"book_{BOOK_ID}"
SOURCES_DIR = BOOK_DIR / "sources"
OUTPUT_DIR = BOOK_DIR / "output_dich"
LOGS_DIR = BOOK_DIR / "logs"
RUNS_DIR = BOOK_DIR / "runs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = (ROOT / "native_oauth" / "prompts" / "bns_system_cache_v1.md").read_text(encoding="utf-8")

# Base character profiles for the novel
BASE_ENTITIES = [
    EntityRecord("萧羽", "Tiêu Vũ", "M", "hắn", "Chưởng môn Thiên Cơ môn / Tu tiên giả", "Bình tĩnh, cơ trí, thần bí"),
    EntityRecord("萧大师", "Tiêu đại sư", "M", "ngài", "Đại sư xem bói", "Tôn kính"),
    EntityRecord("江夏", "Giang Hạ", "M", "hắn", "Streamer", "Nhiệt tình"),
    EntityRecord("徐菲", "Từ Phỉ", "F", "nàng", "Người phàm", "Kinh hãi, cảm kích"),
    EntityRecord("林美婷", "Lâm Mỹ Đình", "F", "nàng", "Phú bà bảng nhất", "Hào sảng, sùng bái"),
    EntityRecord("柳凡", "Liễu Phàm", "M", "hắn", "Cảnh sát / Thủy hữu", "Nghiêm túc, chính trực"),
    EntityRecord("胡菲菲", "Hồ Phỉ Phỉ", "F", "nàng", "Streamer", "Xinh đẹp"),
    EntityRecord("唐小妹", "Đường Tiểu Tiểu", "F", "nàng", "Người phàm / Nữ sinh", "Bướng bỉnh, hoài nghi"),
]

BASE_PRONOUNS = [
    PronounRule("萧羽", "徐菲", "COURTEOUS", "tôi", "cô", "điềm đạm"),
    PronounRule("徐菲", "萧羽", "COURTEOUS", "tôi", "anh", "run rẩy, kính phục"),
    PronounRule("萧羽", "唐小妹", "COURTEOUS", "tôi", "cô", "điềm tĩnh"),
    PronounRule("唐小妹", "萧羽", "COURTEOUS", "tôi", "anh", "nghi ngờ"),
    PronounRule("萧羽", "林美婷", "COURTEOUS", "tôi", "cô", "ôn hòa"),
    PronounRule("林美婷", "萧羽", "COURTEOUS", "em", "Tiêu đại sư", "sùng bái, tôn kính"),
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
    """Translates a single scene chunk, runs Quality Gate 4A, and Spot Auditor 4B if needed."""
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
        genre='URBAN_MODERN'
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
    
    # Run agy
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
    
    # Persist mechanical results and advisory semantic triage; no regex rewriting.
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
    model: str = "gemini-3.8-flash-low",
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
    return run_chapter(chap_num, BOOK_ID, 'Tôi soi thiên cơ trong phòng livestream', 'URBAN_MODERN',
                       SOURCES_DIR, OUTPUT_DIR, scene, model, force, total_chapters=total, runtime_root=generation_root)


def main():
    parser = argparse.ArgumentParser(description="CaoTruyen BNS Batch Translator")
    parser.add_argument("--from-chapter", type=int, default=1)
    parser.add_argument("--to-chapter", type=int, default=50)
    parser.add_argument("--model", default="gemini-3.8-flash-low", choices=["gemini-3.8-flash-low", "gemini-3.8-flash-medium", "gemini-3.8-flash-high"])
    parser.add_argument("--arc-capsule", type=str, default="", help="Path to arc capsule json for predecessor context")
    parser.add_argument("--force", action="store_true", help="Overwrite existing translated chapters")
    args = parser.parse_args()
    
    preprocessor = UnifiedSemanticPreprocessor()
    gate = QualityGate4A()
    auditor = SpotAuditor4B(gate=gate)

    capsule_context = ""
    if args.arc_capsule and Path(args.arc_capsule).exists():
        try:
            c_data = json.loads(Path(args.arc_capsule).read_text(encoding="utf-8"))
            capsule_context = c_data.get("pred_context_anchor", "")
            print(f"[+] Loaded continuity anchor from {args.arc_capsule}")
        except Exception as e:
            print(f"[!] Warning reading capsule {args.arc_capsule}: {e}")
    
    print(f"================================================================")
    print(f" CAOTRUYEN BNS BATCH PIPELINE: CHAPTERS {args.from_chapter} -> {args.to_chapter}")
    print(f" Target Novel: Book 14713 (我在直播间窥探天机)")
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
                force=args.force,
                initial_context=capsule_context
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
