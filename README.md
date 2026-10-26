# CaoTruyen — workflow dịch trong Antigravity

Repository chuẩn của thư mục CaoTruyen: **[hiraga1305/CaoTruyen](https://github.com/hiraga1305/CaoTruyen)**. Workflow hiện hành: **Resilient v2**, khai báo ở [workflow.json](workflow.json), hướng dẫn ở [WORKFLOW.md](WORKFLOW.md).

Luồng: **khóa nguồn → bốn worker MEDIUM tạo nháp → hai reviewer MEDIUM độc lập đọc toàn wave → sửa native → approved manifest → checkpoint → đóng gói/xuất**. Wave tối đa năm chương, tự co theo ngân sách. HIGH dự phòng và sửa tập trung. Vận hành độc lập trong Antigravity, không cần Codex hoặc audit ngoài định kỳ.

## Bắt đầu

```powershell
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements.txt
.venv/Scripts/python.exe -X utf8 translate.py --help

# Offline: không gọi model/network.
.venv/Scripts/python.exe -X utf8 translate.py preflight --book-dir BOOK_DIR --job JOB_DIR --through-chapter 100

# Live: phiên Antigravity thật đã bind dashboard và có native OAuth.
.venv/Scripts/python.exe -X utf8 translate.py watch --book-dir BOOK_DIR --job JOB_DIR --through-chapter 100
```

BOOK_DIR/JOB_DIR là đường dẫn local được chọn. Phạm vi phải được người dùng cho phép; không tự mở toàn sách. Đổi code/canon/phạm vi dùng job revision mới, cùng cấu hình dùng đúng job để resume. Checkpoint mỗi 100 chương không thêm native audit hoặc dừng chờ xác nhận ngoài.

## Bảo vệ

- Giữ source/ID/hash/native response; không duyệt thiếu đoạn, partial hoặc model/runtime không khớp.
- Đại từ/alias đúng người do hai reviewer kiểm, không chặn chỉ vì thiếu chuỗi tên. Style suggestions tùy chọn được lưu riêng.
- Timeout/format có journal, retry hữu hạn, HIGH fallback và chia output. Quota/network có backoff/circuit breaker/resume.
- Approval sau hai review native độc lập trên bản cuối, prefix liên tục; diagnostics không có quyền xuất bản.
- Dashboard/badge hiển thị trực tiếp, tính prefix đã xác minh mà không gán model time giả.
- Bundle giữ proof prefix, raw archive và lineage của cả nguồn phục hồi chưa dùng trong pilot.

## Kiểm thử và dữ liệu

```powershell
.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -v
```

Test/mock không gọi model. CI kiểm Windows/Linux và exporter tùy dependency. Pilot đã hoàn tất 1–40 và ba diagnostic; [release notes](docs/releases/workflow-v2.md) ghi đúng phạm vi, hiệu năng và giới hạn. Native PASS không chứng nhận bản dịch không còn sạn.

Nguồn truyện, output, OAuth account, evidence và ZIP giữ local, không thuộc payload release. Route wave/sequential và benchmark cũ chỉ tương thích hoặc đọc lịch sử, không phải mặc định.

## Tài liệu

- [Workflow chuẩn](WORKFLOW.md).
- [Giao thức, gate và phục hồi](native_oauth/RESILIENT_TRANSLATION_WORKFLOW.md).
- [Native OAuth và route tương thích](native_oauth/ANTIGRAVITY_WORKFLOW.md).
- [Quy tắc agent](AGENTS.md).
