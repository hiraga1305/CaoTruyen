"""Offline pipeline audit. Reads novels; writes only the requested evidence JSON.

Synthetic execution and the existing test suite use temporary directories.
No crawling, model calls, credentials, translation edits, or publishing.
Run from the repository root with .venv/Scripts/python.exe -X utf8.
"""
from __future__ import annotations

import ast
import contextlib
import io
import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
import zipfile
from collections import Counter
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from bs4 import BeautifulSoup
from semantic_gate import digest
from native_oauth.bns_prepass import UnifiedSemanticPreprocessor
from native_oauth.quality_gate import QualityGate4A
from native_oauth.autonomous.self_healing_engine import AutonomousSelfHealingEngine
from native_oauth.core.ast.semantic_parser import ASTNode, DiscourseType
import native_oauth.session_monitor as monitor


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def without_titles(paragraphs):
    result = list(paragraphs)
    while result and re.match(r"^(?:\d+\.\s*)?chương\s+\d+", result[0], re.I):
        result.pop(0)
    return result


def inventory():
    book = ROOT / "native_oauth/book_49736"
    result = {"books": {}, "totals": Counter(), "issues": {}, "missing_body_records": []}

    def issue(name, value):
        result["issues"].setdefault(name, []).append(value)

    for directory in sorted((ROOT / "native_oauth").glob("book_*")):
        if directory.is_dir():
            result["books"][directory.name] = {
                "sources": len(list((directory / "sources").glob("*.json"))),
                "txt": len(list((directory / "output_dich").glob("*.txt"))),
                "sidecars": len(list((directory / "output_dich").glob("*.dich.json"))),
            }
    for chapter in range(1, 326):
        sf = book / "sources" / f"source_chapter_{chapter:04d}.json"
        jf = book / "output_dich" / f"chuong_{chapter:04d}.dich.json"
        tf = book / "output_dich" / f"chuong_{chapter:04d}.txt"
        if not all(p.exists() for p in (sf, jf, tf)):
            issue("missing_files", chapter)
            continue
        source, target = read(sf), read(jf)
        text = tf.read_text(encoding="utf-8")
        segments, alignment = source["segments"], target["bilingual_alignment"]
        result["totals"].update(chapters=1, source_paragraphs=len(segments),
                                alignment_records=len(alignment), txt_whitespace_words=len(text.split()))
        if source["package_hash"] != digest({k: v for k, v in source.items() if k != "package_hash"}):
            issue("invalid_source_package_hash", chapter)
        if target.get("source_hash") != source["package_hash"]:
            issue("sidecar_source_hash_mismatch", chapter)
        raw = [s["source"] for s in segments]
        aligned_raw = [s["raw_zh"] for s in alignment]
        if len(alignment) != len(segments):
            extra_title = aligned_raw == raw[1:]
            issue("alignment_count_mismatch", {
                "chapter": chapter, "source": len(segments), "alignment": len(alignment),
                "declared_total": target["total_paragraphs"],
                "declared_translated": target["translated_paragraphs"],
                "explained_by_extra_source_title": extra_title,
            })
            if not extra_title:
                ids = {s["para_id"] for s in alignment}
                missing = [s for s in segments if s["id"] not in ids]
                result["missing_body_records"].append({
                    "chapter": chapter, "source": len(segments), "alignment": len(alignment),
                    "missing_count": len(missing), "missing_ids": [s["id"] for s in missing],
                    "first_missing_source": missing[0] if missing else None,
                    "last_alignment": alignment[-1],
                })
        if any(not s["translated_vi"].strip() for s in alignment):
            issue("empty_translations", chapter)
        src_by_id = {s["id"]: s["source"] for s in segments}
        bad_raw_ids = [s["para_id"] for s in alignment if src_by_id.get(s["para_id"]) != s["raw_zh"]]
        if bad_raw_ids:
            issue("raw_text_id_mismatch", {"chapter": chapter, "ids": bad_raw_ids})
        av = without_titles([s["translated_vi"].strip() for s in alignment])
        tv = without_titles([p.strip() for p in text.split("\n\n") if p.strip()])
        if av != tv:
            first = next(({"body_position": i, "json": a, "txt": b}
                          for i, (a, b) in enumerate(zip(av, tv), 1) if a != b), None)
            issue("txt_json_difference_after_title_normalization", {
                "chapter": chapter, "json_body_paras": len(av), "txt_body_paras": len(tv),
                "first_difference": first,
            })
        cjk = re.findall(r"[\u3400-\u9fff]", text)
        if cjk:
            issue("cjk_characters", {"chapter": chapter, "count": len(cjk), "sample": "".join(cjk[:20])})
    result["issue_counts"] = {k: len(v) for k, v in result["issues"].items()}
    result["missing_body_record_total"] = sum(x["missing_count"] for x in result["missing_body_records"])
    result["publication_evidence_files"] = len(list(book.rglob("*.evidence.json")))
    result["publication_manifest_files"] = len(list(book.rglob("*.publication.json")))
    result["raw_html_archives"] = len(list((ROOT / "source_archive/book_49736").glob("*.html")))
    runtimes = [read(p) for p in (book / "runs").glob("chapter_*/scene_*/runtime/runtime.json")]
    result["runtime_statuses"] = dict(Counter(r.get("status") for r in runtimes))
    result["epub_samples"] = []
    epub = book / "dist/Di_Tim_Vo_Gian_Dia_Nguc_Toan_Tap.epub"
    with zipfile.ZipFile(epub) as archive:
        for chapter in (239, 299, 318):
            name = f"EPUB/chap_{chapter:04d}.xhtml"
            paragraphs = [p.get_text().strip() for p in BeautifulSoup(archive.read(name), "html.parser").find_all("p")]
            result["epub_samples"].append({"chapter": chapter, "file": name, "paragraphs": len(paragraphs),
                                           "last_paragraph": paragraphs[-1]})
    return result


def synthetic_reproductions():
    prepass = UnifiedSemanticPreprocessor()
    contract, _ = prepass.build_scene_contract(1, 1, ["他走了。"], [], [])
    result = {"default_contract_genre": contract.genre, "gate": {}}
    for label, text in {
        "empty": "§1 ", "duplicate": "§1 Bản thứ nhất.\n§1 Bản thứ hai.",
        "multiline": "§1 Dòng đầu.\nCâu thứ hai vẫn thuộc đoạn một.",
    }.items():
        gate = QualityGate4A().verify_paragraphs(text, 1, contract)
        result["gate"][label] = {"pass": gate.is_pass, "output": gate.sanitized_paragraphs,
                                   "violations": [v.error_code for v in gate.violations]}
    node = ASTNode(node_id="x", discourse_type=DiscourseType.NARRATION,
                   source_text="张三昨天晚上杀了李四。", normalized_text="张三昨天晚上杀了李四。")
    healed, ledger = AutonomousSelfHealingEngine().audit_and_heal_chapter(
        "synthetic", [node], {"x": "Lý Tứ đã giết Trương Tam vào tối hôm qua."})
    result["wrong_subject"] = {"source": node.source_text, "translation": healed["x"],
                               "approved": ledger.publication_approved, "confidence": ledger.final_confidence}
    with tempfile.TemporaryDirectory(prefix="caotruyen_review_") as temporary:
        temp = Path(temporary)
        (temp / "sources").mkdir()
        (temp / "out").mkdir()
        source = {"book_id": "synthetic", "chapter": 1, "title": "Synthetic",
                  "segments": [{"id": f"c0001p{i:04d}", "source": char} for i, char in enumerate("甲乙丙丁", 1)]}
        source["package_hash"] = digest(source)
        (temp / "sources/source_chapter_0001.json").write_text(json.dumps(source), encoding="utf-8")
        from native_oauth.chapter_runner import run_chapter
        def callback(scene, paragraphs, context):
            return {1: "Bản thử."}, "Bản thử.", False
        with patch.object(monitor, "ROOT", temp), patch.object(monitor, "get_active_artifact_dir", return_value=temp / "artifacts"), patch.object(monitor.SessionMonitor, "_instance", None), contextlib.redirect_stdout(io.StringIO()):
            ok = run_chapter(1, "synthetic", "Synthetic", "URBAN_MODERN", temp / "sources", temp / "out", callback, "fixture")
        result["process_chapter_gate_failure"] = {
            "returned_success": ok, "expected_paragraphs": 4,
            "production_files_written": len(list((temp / "out").glob("*.txt"))),
            "complete_drafts_written": len(list((temp / "drafts").glob("*.txt"))),
        }
        with patch.object(monitor, "ROOT", temp), patch.object(monitor, "get_active_artifact_dir", return_value=temp / "artifacts"):
            mon = monitor.SessionMonitor("synthetic", "Synthetic", 325)
            mon.record_worker_active("w", 325, 65)
            result["monitor_no_completions"] = {"completed_records": len(mon.history),
                                                "badge_shows_100_percent": "100.0%" in mon.render_markdown_badge()}
            for _ in range(2):
                mon.record_chapter_done(325, "Synthetic", 65, "w", 3, 10, 1, False)
            result["monitor_duplicate_failed"] = {"status": mon.history[-1].status,
                                                    "counted_words": mon.total_words_accumulated}
    return result


def existing_tests():
    with tempfile.TemporaryDirectory(prefix="caotruyen_review_tests_") as temporary:
        temp = Path(temporary)
        stream = io.StringIO()
        with patch.object(monitor, "ROOT", temp), patch.object(monitor, "get_active_artifact_dir", return_value=temp / "artifacts"), contextlib.redirect_stdout(stream):
            suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"))
            result = unittest.TextTestRunner(stream=stream).run(suite)
        return {"run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
                "skipped": len(result.skipped), "success": result.wasSuccessful(),
                "isolation": "SessionMonitor state and artifacts redirected to temporary directory"}


def main():
    result = {"review_date_local": "2026-10-21", "timezone": "Asia/Saigon",
              "commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
              "scope": "Current working tree audit; baseline evidence from the first review is preserved separately",
              "inventory": inventory(), "reproductions": synthetic_reproductions(), "tests": existing_tests()}
    output = ROOT / "audit/pipeline_review_current.evidence.json"
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"evidence": str(output), "tests": result["tests"],
                      "issue_counts": result["inventory"]["issue_counts"],
                      "missing_body_records": result["inventory"]["missing_body_record_total"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
