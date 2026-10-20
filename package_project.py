import os
import sys
import zipfile
import argparse

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

ESSENTIAL_FILES = [
    "quality_pipeline.py",
    "semantic_gate.py",
    "source_integrity.py",
    "QUALITY_WORKFLOW.md",
    "quality_roles.example.json",
    "multi_llm_client.py",
    "pipeline_api.py",
    "prepare_for_agent.py",
    "get_toc.py",
    "toc_cache.json",
    "novel_lore.json",
    "api_config.json",
    "requirements.txt",
    "PIPELINE_GUIDE.md",
    "DEPLOYMENT_GUIDE.md"
]

def create_bundle(include_output=False, zip_name="CaoTruyen_Deployment.zip"):
    base_dir = os.path.dirname(os.path.abspath(__file__))
    zip_path = os.path.join(base_dir, zip_name)

    print(f"[*] Bắt đầu đóng gói dự án vào: {zip_path}")
    count = 0

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for fname in ESSENTIAL_FILES:
            fpath = os.path.join(base_dir, fname)
            if os.path.exists(fpath):
                zf.write(fpath, arcname=fname)
                print(f"  + Đã thêm: {fname} ({os.path.getsize(fpath):,} bytes)")
                count += 1
            else:
                print(f"  - Bỏ qua (không tìm thấy): {fname}")

        if include_output:
            out_dir = os.path.join(base_dir, "output_dich")
            if os.path.exists(out_dir):
                print("[*] Đang đóng gói thư mục output_dich/ (các chương đã dịch)...")
                for root, _, files in os.walk(out_dir):
                    for f in files:
                        if f.startswith("chuong_") and f.endswith(".txt"):
                            full_path = os.path.join(root, f)
                            rel_path = os.path.relpath(full_path, base_dir)
                            zf.write(full_path, arcname=rel_path)
                            count += 1

    size_mb = os.path.getsize(zip_path) / (1024 * 1024)
    print(f"\n[THÀNH CÔNG] Đã tạo gói đóng gói: {zip_name} ({size_mb:.2f} MB, {count} files).")
    print(f"Bạn có thể sao chép file {zip_name} này sang máy tính mới hoặc VPS để chạy ngay!")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Đóng gói mã nguồn dịch truyện để mang sang máy khác/VPS.")
    parser.add_argument("--include-output", action="store_true", help="Kèm theo cả thư mục output_dich (các chương đã dịch 1..81)")
    parser.add_argument("--out", type=str, default="CaoTruyen_Deployment.zip", help="Tên file zip đầu ra")
    args = parser.parse_args()

    create_bundle(include_output=args.include_output, zip_name=args.out)
