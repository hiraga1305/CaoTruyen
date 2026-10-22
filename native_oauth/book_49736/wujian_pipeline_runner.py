# -*- coding: utf-8 -*-
"""CAOTRUYEN SOVEREIGN QUALITY TRANSLATION RUNNER FOR 《寻找无间地狱》 (Book 49736).
Integrates:
- Genre Cartridge: UrbanSuspenseCartridge (native_oauth/cartridges/urban_suspense.py)
- Prepass: UnifiedSemanticPreprocessor & SceneContract DSL (bns_prepass.py)
- Execution: Gemini 3.8 Flash Engine (agy CLI / multi_llm_client)
- Quality Gate 4A: 0-Token Linter, CJK check, Paragraph alignment (quality_gate.py)
- Spot-Auditor 4B: Surgical Micro-Repair (spot_auditor.py)
- Prosody & Cadence Engine: VietnameseProsodyEngine (prosody_engine.py)
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
from native_oauth.chapter_integrity import atomic_json
from native_oauth.scene_contract import EntityRecord, PronounRule, SceneContract
from native_oauth.bns_prepass import UnifiedSemanticPreprocessor
from native_oauth.quality_gate import QualityGate4A, GateViolation
from native_oauth.spot_auditor import SpotAuditor4B
from native_oauth.prosody_engine import VietnameseProsodyEngine
from native_oauth.cartridges.urban_suspense import UrbanSuspenseCartridge
from native_oauth.run_agy import run as run_agy_cli, require_complete_runtime

BOOK_ID = "49736"
BOOK_SLUG = "s6p7bb"
BOOK_DIR = ROOT / "native_oauth" / f"book_{BOOK_ID}"
SOURCES_DIR = BOOK_DIR / "sources"
OUTPUT_DIR = BOOK_DIR / "output_dich"
RUNS_DIR = BOOK_DIR / "runs"
LOGS_DIR = BOOK_DIR / "logs"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
RUNS_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# One source-first protocol for both entry points of the same book.
SYSTEM_PROMPT = (ROOT / "native_oauth/prompts/bns_system_cache_v1.md").read_text(encoding="utf-8")


def load_lore():
    lore_file = BOOK_DIR / "lore.json"
    if lore_file.exists():
        return json.loads(lore_file.read_text(encoding="utf-8"))
    return {}


def get_base_entities_and_pronouns():
    from native_oauth.book_49736.batch_pipeline_runner import get_semantic_profile
    entities, pronouns, _ = get_semantic_profile()
    return entities, pronouns


def invoke_llm(prompt_text: str, work_dir: Path, target_model: str = "gemini-3.8-flash-high", timeout: int = 150) -> str:
    """Native route only; partial/error output never falls back silently to API."""
    prompt_file = work_dir / "prompt.txt"
    prompt_file.write_text(prompt_text, encoding="utf-8")
    runtime = run_agy_cli(prompt_file=prompt_file, run_dir=work_dir / "runtime",
                          model=target_model, timeout=timeout, workspace=str(ROOT), approve_tools=False)
    return require_complete_runtime(runtime, target_model)


def translate_scene(
    preprocessor: UnifiedSemanticPreprocessor,
    gate: QualityGate4A,
    auditor: SpotAuditor4B,
    cartridge: UrbanSuspenseCartridge,
    chap_num: int,
    scene_idx: int,
    raw_paras: list[str],
    prev_vi_context: str,
    target_model: str = "gemini-3.8-flash-high",
    timeout: int = 150,
    prev_source_context: str = "",
    next_source_context: str = "",
    runtime_root: Path = None
) -> tuple[dict[int, str], str, bool]:
    scene_work_dir = (runtime_root or RUNS_DIR) / f"chapter_{chap_num:04d}" / f"scene_{scene_idx}"
    scene_work_dir.mkdir(parents=True, exist_ok=True)

    from native_oauth.book_49736.batch_pipeline_runner import get_semantic_profile
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
        genre='URBAN_SUSPENSE_MYSTERY'
    )

    pipe_dsl = contract.to_pipe_dsl()
    tagged_body = "\n".join(tagged_paras)

    prompt_text = (
        f"{system_prompt}\n\n"
        f"GIAO THỨC SCENE HIỆN TẠI:\n"
        f"{pipe_dsl}\n\n"
        f"NGUYÊN TÁC TRUNG VĂN CẦN BIÊN DỊCH (TỪ §1 ĐẾN §{len(raw_paras)}):\n"
        f"{tagged_body}\n\n"
        f"YÊU CẦU BẮT BUỘC:\n"
        f"1. Dịch toàn bộ {len(raw_paras)} đoạn văn trên đúng nghĩa nguồn và tự nhiên theo ngữ cảnh.\n"
        f"2. Bắt đầu mỗi đoạn bằng đúng mã §1..§{len(raw_paras)}. Tuyệt đối không gộp đoạn, không bỏ sót đoạn nào.\n"
    )

    resp = invoke_llm(prompt_text, scene_work_dir, target_model=target_model, timeout=timeout)

    # Quality Gate 4A
    gate_result = gate.verify_paragraphs(resp, expected_paragraph_count=len(raw_paras), contract=contract)

    # Persist mechanical checks and advisory cues; semantic approval is separate.
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
    cartridge: UrbanSuspenseCartridge,
    model: str = "gemini-3.8-flash-high",
    force: bool = False
) -> bool:
    generation_root = RUNS_DIR / ("generation_" + uuid.uuid4().hex)
    def scene(scene_idx, raw_paras, context):
        return translate_scene(preprocessor=preprocessor, gate=gate, auditor=auditor, cartridge=cartridge,
                               chap_num=chap_num, scene_idx=scene_idx, raw_paras=raw_paras,
                               prev_vi_context=context["prev_vi"], target_model=model,
                               prev_source_context=context["prev_zh"],
                               next_source_context=context["next_zh"], runtime_root=generation_root)
    toc_file = BOOK_DIR / "toc.json"
    total = len(json.loads(toc_file.read_text(encoding="utf-8"))) if toc_file.exists() else 325
    return run_chapter(chap_num, BOOK_ID, 'Đi Tìm Vô Gian Địa Ngục', 'URBAN_SUSPENSE_MYSTERY',
                       SOURCES_DIR, OUTPUT_DIR, scene, model, force, total_chapters=total, runtime_root=generation_root)


def run_pipeline(from_chap: int, to_chap: int, model: str = "gemini-3.8-flash-high", force: bool = False):
    preprocessor = UnifiedSemanticPreprocessor()
    gate = QualityGate4A()
    auditor = SpotAuditor4B()
    cartridge = UrbanSuspenseCartridge()

    print(f"[*] Starting Sovereign Quality Pipeline for 《寻找无间地狱》 (Chapters {from_chap} -> {to_chap})")
    for chap in range(from_chap, to_chap + 1):
        if not process_chapter(chap, preprocessor, gate, auditor, cartridge, model=model, force=force):
            raise SystemExit(2)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Pipeline Runner for 《寻找无间地狱》")
    parser.add_argument("--from-chapter", type=int, default=226, help="Start chapter")
    parser.add_argument("--to-chapter", type=int, default=230, help="End chapter")
    parser.add_argument("--model", type=str, default="gemini-3.8-flash-high", help="Target model")
    parser.add_argument("--force", action="store_true", help="Force re-translate")
    args = parser.parse_args()
    run_pipeline(args.from_chapter, args.to_chapter, model=args.model, force=args.force)
