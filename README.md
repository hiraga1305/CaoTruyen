# CaoTruyen — workflow Antigravity

Cào nguồn truyện Trung, dịch sang tiếng Việt, review độc lập và xuất sách trong **Antigravity**. Workflow chạy độc lập; không cần Codex hoặc dịch vụ duyệt ngoài Antigravity.

Luồng: **khóa nguồn → dịch draft → kiểm cấu trúc/runtime → hai native review độc lập → approved → đóng sách**. Một lần kiểm thử ngoài luồng không phải bước vận hành định kỳ.

## Bắt đầu

Đọc [workflow và lệnh vận hành](native_oauth/ANTIGRAVITY_WORKFLOW.md). Bốn runner theo sách dùng chung [chapter_runner.py](native_oauth/chapter_runner.py); các wave tạo draft, review được thực hiện tiếp bằng [review_book_chapter.py](native_oauth/review_book_chapter.py) trong Antigravity.

```powershell
# Kiểm thử ngoại tuyến, không gọi model
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -q

# Xem CLI trước khi chạy: review thật sẽ gọi model qua OAuth native
python -m native_oauth.review_book_chapter --help
python -m native_oauth.pipeline_native --help
```

## Những bảo vệ đang có

- Nguồn/ID/hash bất biến; không đệm đoạn mất bằng chuỗi rỗng hoặc xóa chữ chưa dịch.
- Runtime timeout/partial/model mismatch và cache cũ không hợp lệ bị chặn.
- Identity/alias nhân vật dùng chung; phân vai thiếu căn cứ để UNKNOWN; không tự đổi xưng hô theo từ khóa.
- Reviewer đọc nguồn–đích trong hai workspace riêng, có runtime/model/session thực và kiểm tra hash. Cùng model được phép ở các session độc lập; không tự chấm rồi tự approve.
- Context lấy các đoạn đã duyệt có nguồn, ưu tiên giới thiệu đầu và đề cập gần; không tự tóm tắt thành sự thật.
- Chỉ promote sau hai review đạt trên bản cuối. Chương sau cần evidence chương trước. Đóng sách 49736 đọc `approved/`, không đọc bản TXT cũ làm bản đã duyệt.
- SessionMonitor hiển thị công việc và từng giai đoạn ngay trong session Antigravity.

## Phạm vi kiểm chứng

Các test/mock và replay chỉ chứng minh các ca hồi quy đã kiểm, không chứng nhận cả bản dịch. Chưa chạy một lượt dịch/review live mới sau các sửa 22/10/2026. Các chương cũ thiếu đoạn hoặc lệch tên chưa được tự sửa; xuất sách mới sẽ bị chặn cho tới khi có đủ bản approved.

Mẫu ngữ nghĩa đã dùng để sửa hệ thống không được coi là heldout. Đo thêm trên nguồn mới trước khi tăng quy mô; không dùng điểm heuristic hoặc số test qua làm tỷ lệ chính xác dịch.

## Tài liệu

- [Workflow hiện hành](native_oauth/ANTIGRAVITY_WORKFLOW.md).
- [Tổng kết bản hoàn thiện 22/10/2026](audit/antigravity_release_20261022.md).
- [Nguyên nhân mất đoạn và bản sửa](audit/pipeline_root_cause_and_fix_20261021.md).
- [Rà ngữ nghĩa và xưng hô](audit/semantic_context_fix_20261022.md).
- [Kết quả audit workflow trước sửa](audit/workflow_review_and_improvement_20261022.md).
- [Thiết kế batch source-frozen](native_oauth/BATCH_WORKFLOW.md).

Các tài liệu/audit pilot cũ được giữ dưới `audit/` và các thư mục benchmark; không phải phụ thuộc của workflow hiện hành. API experiments cũ không được gọi bởi đường chạy native chính.
