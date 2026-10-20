"""Prepare continuity context capsules for parallel Arc subagents."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BOOK_DIR = ROOT / "native_oauth" / "book_14713"
SOURCES_DIR = BOOK_DIR / "sources"
OUTPUT_DIR = BOOK_DIR / "output_dich"
ARCS_DIR = BOOK_DIR / "arcs"
ARCS_DIR.mkdir(parents=True, exist_ok=True)

# Load lore
lore_file = BOOK_DIR / "lore.json"
lore = json.loads(lore_file.read_text(encoding="utf-8"))

# Define the 5 Arcs covering remaining chapters 16 to 50
ARCS = [
    {"arc_id": 1, "from_chap": 16, "to_chap": 22, "name": "Bắt Kẻ Đào Tẩu & Chế Tạo Bùa Chú", "pred_chap": 15},
    {"arc_id": 2, "from_chap": 23, "to_chap": 29, "name": "Bán Bùa Trừ Tà & Streamer Khiêu Chiến", "pred_chap": 22},
    {"arc_id": 3, "from_chap": 30, "to_chap": 36, "name": "Bắt Gian Tại Trận & Tìm Trẻ Lạc", "pred_chap": 29},
    {"arc_id": 4, "from_chap": 37, "to_chap": 43, "name": "Kỳ Tích Toàn Mạng & Trúng Thưởng Triệu Bạc", "pred_chap": 36},
    {"arc_id": 5, "from_chap": 44, "to_chap": 50, "name": "Vạch Trần Lừa Đảo & Đả Giả Tự Bạo", "pred_chap": 43},
]

for arc in ARCS:
    pred_chap = arc["pred_chap"]
    pred_src = SOURCES_DIR / f"source_chapter_{pred_chap:04d}.json"
    pred_out = OUTPUT_DIR / f"chuong_{pred_chap:04d}.txt"
    
    # Get predecessor context
    pred_text_summary = ""
    if pred_out.exists():
        txt = pred_out.read_text(encoding="utf-8")
        paras = [p for p in txt.split("\n\n") if p.strip()]
        # Last 5 paragraphs provide immediate handoff context
        pred_text_summary = "\n".join(paras[-5:])
    elif pred_src.exists():
        src_data = json.loads(pred_src.read_text(encoding="utf-8"))
        paras = [s["source"] for s in src_data["segments"]]
        pred_text_summary = "\n".join(paras[-5:])
        
    capsule = {
        "arc_id": arc["arc_id"],
        "name": arc["name"],
        "from_chap": arc["from_chap"],
        "to_chap": arc["to_chap"],
        "pred_chap": pred_chap,
        "pred_context_anchor": pred_text_summary[:1000],
        "shared_lore": lore,
        "instructions": (
            f"Dịch liên tục từ Chương {arc['from_chap']} đến Chương {arc['to_chap']}. "
            f"Kế thừa bối cảnh kết thúc của Chương {pred_chap} làm mỏ neo ngữ cảnh liền mạch. "
            f"Áp dụng triệt để BNS Literary Engine: bns_prepass -> SceneContract -> Gemini 3.8 Flash -> QualityGate 4A."
        )
    }
    
    capsule_file = ARCS_DIR / f"arc_{arc['arc_id']}_capsule.json"
    capsule_file.write_text(json.dumps(capsule, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[+] Prepared Arc {arc['arc_id']} ({arc['name']}): Ch.{arc['from_chap']}->{arc['to_chap']} with pred Ch.{pred_chap}")

print(f"\n[+] All {len(ARCS)} Arc Capsules prepared in {ARCS_DIR}")
