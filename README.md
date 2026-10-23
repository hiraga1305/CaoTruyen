# CaoTruyen — workflow Antigravity

Cào nguồn truyện Trung, dịch sang tiếng Việt, review độc lập và xuất sách trong **Antigravity**. Workflow chạy độc lập; không cần Codex hoặc dịch vụ duyệt ngoài Antigravity.

Luồng: **khóa nguồn → tạo nháp song song theo nhóm 5 chương → hai native review từng chương theo thứ tự → kiểm liên kết cả nhóm → đóng sách**. Một lần kiểm thử ngoài luồng không phải bước vận hành định kỳ.

## Bắt đầu

Đọc [workflow và lệnh vận hành](native_oauth/ANTIGRAVITY_WORKFLOW.md). Runner ưu tiên [revise_book.py](native_oauth/revise_book.py) dùng `--mode wave --max-workers 3`: hai worker dịch và một luồng review xen kẽ; tối đa 5 chương/nhóm. Dùng được cho nguồn mới và bản legacy. Các runner tạo draft từng chương và `review_book_chapter.py` vẫn được giữ để tương thích.

```powershell
# Kiểm thử ngoại tuyến, không gọi model
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -q

# Xem CLI trước khi chạy: review thật sẽ gọi model qua OAuth native
python -m native_oauth.revise_book --help
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
- Nháp song song giữ nguyên hash/response và lưu ngữ cảnh sinh nháp riêng. Review cuối kiểm lại context đã duyệt; gate nhóm chưa PASS hoặc sai revision sẽ chặn xuất bản. Có thể chọn mã trích dẫn nguồn–đích chính xác để giảm lỗi chép quote.
- SessionMonitor hiển thị công việc và từng giai đoạn ngay trong session Antigravity.

## Phạm vi kiểm chứng

Các test/mock và replay chỉ chứng minh các ca hồi quy đã kiểm, không chứng nhận cả bản dịch. Điều phối nhóm 5 chương có kiểm thử offline; vận hành thực tế vẫn cần kiểm nghĩa trực tiếp, chưa có phép đo chất lượng/tốc độ A/B bằng native model thật. Trạng thái truyện thực tế đọc từ manifest local; xuất sách mới bị chặn cho tới khi đủ approval và các gate nhóm hiện hành đạt.

Mẫu ngữ nghĩa đã dùng để sửa hệ thống không được coi là heldout. Đo thêm trên nguồn mới trước khi tăng quy mô; không dùng điểm heuristic hoặc số test qua làm tỷ lệ chính xác dịch.

## Tài liệu

- [Workflow hiện hành](native_oauth/ANTIGRAVITY_WORKFLOW.md).
- [Tổng kết bản hoàn thiện 22/10/2026](audit/antigravity_release_20261022.md).
- [Nguyên nhân mất đoạn và bản sửa](audit/pipeline_root_cause_and_fix_20261021.md).
- [Rà ngữ nghĩa và xưng hô](audit/semantic_context_fix_20261022.md).
- [Kết quả audit workflow trước sửa](audit/workflow_review_and_improvement_20261022.md).
- [Thiết kế batch source-frozen](native_oauth/BATCH_WORKFLOW.md).

Các tài liệu/audit pilot cũ được giữ dưới `audit/` và các thư mục benchmark; không phải phụ thuộc của workflow hiện hành. API experiments cũ không được gọi bởi đường chạy native chính.
