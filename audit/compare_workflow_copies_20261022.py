"""Read-only comparison of workflow code; deliberately excludes novels/credentials/runs."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OTHER = Path(r"G:\Other computers\My Computer\Antigravity\CaoTruyen")
SKIP = {".git", ".venv", ".venv_parser", "__pycache__", "models", "runs", "logs",
        "output_dich", "sources", "source_archive", "dist", "drafts", "approved",
        "batch_jobs", "batch_benchmark", "native_jobs", "native_review_jobs",
        "approved_codex", "codex_audit", "research", "chivi_repos", "PhaoHoiNamXung"}

def inventory(root):
    import os
    result = {}
    for directory, children, files in os.walk(root):
        relative = Path(directory).relative_to(root)
        children[:] = [name for name in children if name not in SKIP and not name.startswith(('pilot_', 'prepared_')) and (
            relative.parts or name in {"native_oauth", "tests", "docs", ".github", ".agents"})]
        for name in files:
            path = Path(directory) / name
            if path.suffix not in {".py", ".md", ".yml", ".yaml"} and name not in {
                ".gitignore", "requirements.txt", "requirements-publishing.txt", "semantic_profiles.json"}:
                continue
            raw = path.read_bytes().replace(b"\r\n", b"\n")
            result[path.relative_to(root).as_posix()] = hashlib.sha256(raw).hexdigest()
    return result

def main():
    left, right = inventory(ROOT), inventory(OTHER)
    rows = []
    for name in sorted(set(left) | set(right)):
        if left.get(name) == right.get(name):
            continue
        base = subprocess.run(["git", "show", "HEAD:" + name], cwd=ROOT, capture_output=True)
        base_hash = hashlib.sha256(base.stdout.replace(b"\r\n", b"\n")).hexdigest() if base.returncode == 0 else None
        rows.append({"file": name, "D": left.get(name), "G": right.get(name), "base": base_hash,
                     "D_changed": left.get(name) != base_hash, "G_changed": right.get(name) != base_hash})
    report = {"D": str(ROOT), "G": str(OTHER), "base": subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "counts": {"D_files": len(left), "G_files": len(right), "differences": len(rows)}, "differences": rows}
    output = ROOT / "audit/copy_comparison_20261022.evidence.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["counts"]))
    for row in rows:
        if row["G_changed"]:
            print(("BOTH" if row["D_changed"] else "G_ONLY") + " " + row["file"])

if __name__ == "__main__":
    main()
