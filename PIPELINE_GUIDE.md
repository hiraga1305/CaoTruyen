# Pipeline dịch truyện đã bổ sung kiểm dịch — 2026-10-13

Route hàng loạt hiện tại: [native_oauth/BATCH_WORKFLOW.md](native_oauth/BATCH_WORKFLOW.md), kết quả thử low/medium: [native_oauth/BATCH_RESULT_20261013.md](native_oauth/BATCH_RESULT_20261013.md). Đây là source-first generation và calibration, không phải sửa tay từng chương.

Tài liệu vận hành hiện tại theo yêu cầu GPT Codex: [native_oauth/WORKFLOW.md](native_oauth/WORKFLOW.md). Kết quả chương 1: [native_oauth/AUDIT_RESULT_20261013.md](native_oauth/AUDIT_RESULT_20261013.md). Phần dưới giữ bối cảnh kiểm dịch ban đầu; các thử API đang BLOCKED không phải trạng thái của bản chương 1 mới.

Luồng: nguồn nguyên vẹn + id đoạn + glossary/context có chứng cứ → translator → reviewer độc lập → auditor độc lập → sửa và kiểm lại → approved_output khi PASS.

Bản dịch cũ trong output_dich chưa được coi là đã kiểm dịch. Không dùng dung lượng file để skip, không dùng regex làm cây cú pháp, không dùng tài liệu cũ để suy ra model thực tế.

Xem audit/semantic_sample_review.md cho lỗi nghĩa đã xác nhận, audit/legacy_inventory.json cho kiểm kê 81 chương, audit/model_pilot_report.json cho thử model thực tế, và audit/pilot_runs cho các lượt end-to-end đang BLOCKED bởi provider.

Lệnh chạy test:

```powershell
python -X utf8 -m unittest discover -s tests -v
python -X utf8 audit_existing.py
```

Các lệnh batch, cách ghi trực tiếp output_dich, nhận định 95% chất lượng hoặc 0% lỗi 429 của tài liệu cũ không được dùng làm bảo đảm vận hành. Bản tài liệu/code trước vá được giữ trong audit/original_code_20261013.
