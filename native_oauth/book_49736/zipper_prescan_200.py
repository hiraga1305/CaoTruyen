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

vault = GlobalEntityVault(VAULT_PATH)

chapters = []
for i in range(101, 201):
    src_file = SOURCES_DIR / f"source_chapter_{i:04d}.json"
    if src_file.exists():
        data = json.loads(src_file.read_text(encoding="utf-8"))
        full_text = "\n".join(s["source"] for s in data["segments"])
        chapters.append((i, full_text))

print(f"Loaded {len(chapters)} chapters (101-200) for pre-scan.")

coordinator = TwoPhaseZipperCoordinator(
    vault=vault,
    protagonist_zh="云千峰",
    protagonist_vi="Vân Thiên Phong",
    llm_micro_caller=None
)

candidates = coordinator.phase1_scan_batch_0_token(chapters)
print(f"\n[+] Total Discovered Entity Candidates (Freq >= 2): {len(candidates)}")
print("--- TOP 30 CANDIDATES IN CH 101-200 ---")
for c in candidates[:30]:
    snippets = " | ".join(c.context_snippets[:1])
    print(f"  [{c.inferred_cat}] {c.zh} (freq={c.frequency}, ch={c.first_chap}): {snippets[:60]}")

cands_data = [
    {"zh": c.zh, "cat": c.inferred_cat, "freq": c.frequency, "first_chap": c.first_chap, "snippets": c.context_snippets}
    for c in candidates
]
(BOOK_DIR / "prescan_candidates_200.json").write_text(json.dumps(cands_data, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\n[+] Saved candidates to {BOOK_DIR / 'prescan_candidates_200.json'}")
