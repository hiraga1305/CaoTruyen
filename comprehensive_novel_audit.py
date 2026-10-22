# -*- coding: utf-8 -*-
"""comprehensive_novel_audit.py - 5-Tier Full Novel Audit for Book 49736 (325 Chapters)
Generates full audit report across:
1. Structural Integrity & Lossless Coverage
2. CJK & DSL Leakage
3. Calque & Archaic Terminology
4. Entity Consistency
5. Prosody & Cadence Quality
"""
import json
import re
import sys
import time
from pathlib import Path
from collections import Counter

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "native_oauth" / "book_49736" / "output_dich"
SOURCES_DIR = ROOT / "native_oauth" / "book_49736" / "sources"

from native_oauth.prosody_engine import VietnameseProsodyEngine
from native_oauth.chapter_integrity import inspect_chapter

CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf\uf900-\ufaff]")
DSL_LEAK_PATTERN = re.compile(r"§\d+|\[\[PRON:[^\]]+\]\]")

CALQUE_TERMS = [
    "không cho là đúng",
    "hít một ngụm khí lạnh",
    "hít ngược một ngụm khí lạnh",
    "sắc mặt ngưng lại",
    "trong mắt hiện lên một tia",
    "trong mắt lóe lên một tia",
    "cười lạnh một tiếng",
    "sắc mặt kịch biến",
    "đem hắn cho giết",
    "đem nàng cho giết",
]

ARCHAIC_WUXIA_TERMS = [
    "tiểu tử",
    "tại hạ",
    "các hạ",
    "lão phu",
    "đạo hữu",
    "tiểu hữu",
    "chưởng quầy",
    "tiểu nhị",
]

STANDALONE_NGUOI = re.compile(r"\bngươi\b", re.IGNORECASE)

EXCLUDED_TA_PREFIXES = {"chúng", "cô", "cậu", "anh", "người", "bọn", "hắn", "ông", "bà", "nàng", "chú", "gã"}

def check_standalone_ta(text: str) -> list[str]:
    issues = []
    for m in re.finditer(r"\bta\b", text, re.IGNORECASE):
        start = m.start()
        prefix = text[:start].rstrip()
        last_word = prefix.split()[-1].lower() if prefix.split() else ""
        last_word = re.sub(r"[^\w]", "", last_word)
        if last_word in EXCLUDED_TA_PREFIXES:
            continue
        snippet = text[max(0, start - 15):min(len(text), start + 25)].replace("\n", " ")
        issues.append(snippet)
    return issues


def run_full_audit(max_chapters=325, report_file=None):
    print("=" * 70)
    print(" BẮT ĐẦU KIỂM ĐỊNH TOÀN DIỆN 5 TẦNG CHO BỘ TRUYỆN 325 CHƯƠNG")
    print(" Bộ truyện: 《Tìm Kiếm Vô Gian Địa Ngục》 (Book 49736)")
    print("=" * 70)

    t0 = time.time()
    stats = {
        "total_chapters": max_chapters,
        "verified_chapters": 0,
        "scanned_chapters": 0,
        "scope": "structural audit and heuristic triage; not semantic/literary approval",
        "integrity_findings": [],
        "total_words": 0,
        "total_paras": 0,
        "raw_segments_total": 0,
        "missing_files": [],
        "small_files": [],
        "para_mismatches": [],
        "cjk_leaks": [],
        "dsl_leaks": [],
        "calque_hits": Counter(),
        "archaic_wuxia_hits": Counter(),
        "standalone_nguoi_count": 0,
        "standalone_ta_count": 0,
        "prosody_run_ons": 0,
        "prosody_clunky": 0,
        "key_entities": {
            "Vân Thiên Phong": 0,
            "Khương Nhu Giáp": 0,
            "Tần Sơ Ảnh": 0,
            "La Lâm Na": 0,
            "Fatina": 0,
            "Pháp Đề Na": 0,
            "Tam Tiền Tế Thế": 0,
            "Chúc Do thuật": 0,
        }
    }

    for ch in range(1, max_chapters + 1):
        txt_file = OUTPUT_DIR / f"chuong_{ch:04d}.txt"
        json_file = OUTPUT_DIR / f"chuong_{ch:04d}.dich.json"
        src_file = SOURCES_DIR / f"source_chapter_{ch:04d}.json"

        if not txt_file.exists() or not json_file.exists() or not src_file.exists():
            stats["missing_files"].append(ch)
            continue

        size = txt_file.stat().st_size
        if size < 1000:
            stats["small_files"].append((ch, size))

        txt = txt_file.read_text(encoding="utf-8")
        words = len(txt.split())
        stats["total_words"] += words

        # 1. Structural check
        integrity_errors = []
        try:
            jd = json.loads(json_file.read_text(encoding="utf-8"))
            source = json.loads(src_file.read_text(encoding="utf-8"))
            exp_p = len(source.get("segments", []))
            act_p = len(jd.get("bilingual_alignment", []))
            integrity_errors = inspect_chapter(source, jd, txt)
            stats["total_paras"] += act_p
            stats["raw_segments_total"] += exp_p
            if exp_p > 0 and exp_p != act_p:
                stats["para_mismatches"].append((ch, exp_p, act_p))
        except Exception as e:
            stats["para_mismatches"].append((ch, "JSON_ERROR", str(e)))
            integrity_errors = ["INVALID_ARTIFACT: " + str(e)]
        if integrity_errors:
            stats["integrity_findings"].append({"chapter": ch, "errors": integrity_errors})

        # 2. CJK & DSL leaks
        cjk_found = CJK_PATTERN.findall(txt)
        # Filter out legitimate CJK if title or quotes (e.g. chữ 'Phan' 潘)
        real_cjk = [c for c in cjk_found if c not in "第章潘"]
        if real_cjk:
            stats["cjk_leaks"].append((ch, len(real_cjk), "".join(real_cjk[:5])))

        dsl_found = DSL_LEAK_PATTERN.findall(txt)
        if dsl_found:
            stats["dsl_leaks"].append((ch, len(dsl_found)))

        # 3. Calques & Archaic
        txt_lower = txt.lower()
        for c in CALQUE_TERMS:
            cnt = txt_lower.count(c)
            if cnt > 0:
                stats["calque_hits"][c] += cnt

        for w in ARCHAIC_WUXIA_TERMS:
            cnt = len(re.findall(r"\b" + re.escape(w) + r"\b", txt_lower))
            if cnt > 0:
                stats["archaic_wuxia_hits"][w] += cnt

        nguoi_matches = STANDALONE_NGUOI.findall(txt)
        stats["standalone_nguoi_count"] += len(nguoi_matches)

        ta_issues = check_standalone_ta(txt)
        stats["standalone_ta_count"] += len(ta_issues)

        # 4. Entities
        for ent in stats["key_entities"].keys():
            stats["key_entities"][ent] += len(re.findall(r"\b" + re.escape(ent) + r"\b", txt, re.IGNORECASE))

        # 5. Prosody
        p_anomalies = VietnameseProsodyEngine.audit_cadence_and_rhythm(txt)
        for a in p_anomalies:
            if a.error_code == "RUN_ON_CLAUSE_TOO_LONG":
                stats["prosody_run_ons"] += 1
            else:
                stats["prosody_clunky"] += 1

        stats["scanned_chapters"] += 1
        if not integrity_errors:
            stats["verified_chapters"] += 1

    elapsed = time.time() - t0
    print("\n" + "=" * 70)
    print(f" KẾT QUẢ KIỂM ĐỊNH TOÀN DIỆN ({elapsed:.2f}s)")
    print("=" * 70)
    print(f"1. TỔNG QUAN:")
    print(f"   - Đã quét: {stats['scanned_chapters']}/{stats['total_chapters']}; đúng cấu trúc/đồng bộ: {stats['verified_chapters']}")
    print("   - Kiểm cấu trúc không thay thế review nghĩa/văn học hoặc quyền xuất bản.")
    print(f"   - Tổng số từ tiếng Việt: {stats['total_words']:,} từ")
    print(f"   - Tổng số đoạn văn: {stats['total_paras']:,} đoạn (Nguyên tác: {stats['raw_segments_total']:,} đoạn)")
    print(f"   - Tệp thiếu / Tệp hỏng (<1KB): {len(stats['missing_files'])} / {len(stats['small_files'])}")
    print(f"   - Lệch đoạn (Segment Mismatch): {len(stats['para_mismatches'])} chương")

    print(f"\n2. AN TOÀN KÝ TỰ & RÒ RỈ:")
    print(f"   - Lọt chữ Hán thô (CJK Leaks): {len(stats['cjk_leaks'])} chương")
    print(f"   - Lọt thẻ DSL (§, [[PRON...]]): {len(stats['dsl_leaks'])} chương")

    print(f"\n3. KHỬ HÁN HÓA & KHẨU KHÍ ĐÔ THỊ:")
    print(f"   - Sáo ngữ convert thô: {sum(stats['calque_hits'].values())} lần")
    for k, v in stats['calque_hits'].items():
        print(f"     + '{k}': {v}")
    print(f"   - Từ xưng hô kiếm hiệp cổ trang: {sum(stats['archaic_wuxia_hits'].values())} lần")
    for k, v in stats['archaic_wuxia_hits'].items():
        print(f"     + '{k}': {v}")
    print(f"   - Xưng hô 'ngươi' độc lập: {stats['standalone_nguoi_count']} lần")
    print(f"   - Xưng hô 'ta' cổ đại độc lập: {stats['standalone_ta_count']} lần")

    print(f"\n4. NHẤT QUÁN THỰC THỂ:")
    for ent, count in stats['key_entities'].items():
        print(f"   - {ent:<22}: {count:>5} lần")

    print(f"\n5. ÂM VẬN & NHỊP ĐIỆU (PROSODY):")
    print(f"   - Phân câu quá dài không ngắt (Run-on): {stats['prosody_run_ons']} lần")
    print(f"   - Liên từ hành chính / Tây hóa (Clunky): {stats['prosody_clunky']} lần")
    print("=" * 70)

    # Save detailed audit report
    report_file = Path(report_file) if report_file else ROOT / "audit" / "full_novel_325_audit_report.json"
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[✓] Đã xuất báo cáo chi tiết ra: {report_file}")
    return stats

if __name__ == "__main__":
    run_full_audit(325)
