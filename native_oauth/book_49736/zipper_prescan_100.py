import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from native_oauth.global_vault import GlobalEntityVault
from native_oauth.zipper_coordinator import TwoPhaseZipperCoordinator

BOOK_DIR = ROOT / "native_oauth" / "book_49736"
SOURCES_DIR = BOOK_DIR / "sources"
VAULT_PATH = BOOK_DIR / "vault.sqlite"

# 1. Initialize Vault
vault = GlobalEntityVault(VAULT_PATH)

# Seed base entities
base_entities = [
    ("云千峰", "Vân Thiên Phong", "PERSON", "M", "hắn", "Chủ tiệm phong thủy Tam Tiền Tế Thế / Nhân vật chính"),
    ("姜柔甲", "Khương Nhu Giáp", "PERSON", "F", "nàng", "Nữ chính / Khách hàng đầu tiên"),
    ("秦疏影", "Tần Sơ Ảnh", "PERSON", "F", "nàng", "Nữ chính / Bạn đồng hành"),
    ("罗琳娜", "La Lâm Na", "PERSON", "F", "nàng", "Nhà thám hiểm lai / Bạn đồng hành"),
    ("小神经", "Tiểu Thần Kinh", "PERSON", "F", "cô ấy", "Đồng hành thám hiểm"),
]
for zh, vi, cat, gender, narr, bio in base_entities:
    vault.upsert_locked_entity(
        canonical_zh=zh,
        canonical_vi=vi,
        category=cat,
        gender=gender,
        narr_lock=narr,
        persona_tag=f"{cat} ({narr})",
        bio_capsule=bio,
        chap_id=1,
        is_locked=1
    )

# 2. Load first 100 chapters
chapters = []
for i in range(1, 101):
    src_file = SOURCES_DIR / f"source_chapter_{i:04d}.json"
    if src_file.exists():
        data = json.loads(src_file.read_text(encoding="utf-8"))
        full_text = "\n".join(s["source"] for s in data["segments"])
        chapters.append((i, full_text))

print(f"Loaded {len(chapters)} chapters for pre-scan.")

# 3. TwoPhaseZipperCoordinator 0-Token AST Pre-scan
coordinator = TwoPhaseZipperCoordinator(
    vault=vault,
    protagonist_zh="云千峰",
    protagonist_vi="Vân Thiên Phong",
    llm_micro_caller=None
)

candidates = coordinator.phase1_scan_batch_0_token(chapters)
print(f"\n[+] Total Discovered Entity Candidates (Freq >= 2): {len(candidates)}")
print("--- TOP 35 CANDIDATES ---")
for c in candidates[:35]:
    snippets = " | ".join(c.context_snippets[:1])
    print(f"  [{c.inferred_cat}] {c.zh} (freq={c.frequency}, ch={c.first_chap}): {snippets}")

# Save candidates to json for review/micro-lock
cands_data = [
    {"zh": c.zh, "cat": c.inferred_cat, "freq": c.frequency, "first_chap": c.first_chap, "snippets": c.context_snippets}
    for c in candidates
]
(BOOK_DIR / "prescan_candidates_100.json").write_text(json.dumps(cands_data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n[+] Saved candidates to {BOOK_DIR / 'prescan_candidates_100.json'}")
