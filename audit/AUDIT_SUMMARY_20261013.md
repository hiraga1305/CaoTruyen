# Kết quả audit và bản vá — 2026-10-13

## Kết luận

Pipeline cũ không có kiểm dịch ngữ nghĩa thực sự. Đã vá luồng để giữ nguyên source, khóa id từng đoạn/glossary/context, yêu cầu hai lượt kiểm dịch độc lập có chứng cứ và kiểm lại sau sửa. Đầu ra cũ và PDF/ZIP giữ nguyên; chưa gắn nhãn đạt chất lượng cho 81 chương.

Ba subagent thực hiện: audit mẫu song ngữ; audit code độc lập trước/sau vá; sửa và kiểm thử AI client. Điều phối viên tích hợp gate/crawler/native/API, tải thử nguồn và thử model thật. Không khởi chạy Antigravity IDE; các worker ở đây thuộc Codex.

## Lỗi nghĩa đã chứng minh

- 短信箱 → hộp thư thoại, thay vì hộp SMS.
- 两两对决 → hai chọi hai, thay vì từng cặp 1 chọi 1.
- 心中幽幽道 → cất lời, thay vì thầm nghĩ.
- 900克以上 → hơn 900 g, làm mất trường hợp đúng 900 g.
- Thêm “mua quà”, “bán mạng”, “đẫm máu” ngoài nguồn.
- 法赛 gọi Pháp Giải/Pháp Tái giữa các chương.
- Regex “Chivi AST” phá tên Trương Vũ/số 1000 và có thể đảo sai câu phủ định.

Chi tiết cặp câu và vị trí: `semantic_sample_review.md`. Đoạn sửa đã kiểm: `excerpt_corrections.txt`; khóa regression: `semantic_regression_cases.json` (8 ca).

## Kiểm tra đã hoàn thành

- **42/42 test offline đạt**: `verification_tests.txt`. Test dùng mock kiểm cơ chế, không phải 42 bản dịch được chứng nhận.
- Nguồn thực chương 1: HTTP thành công; 192 đoạn / 6.032 ký tự. HTML trong `live_source_chapter1.html`; raw HTML nguyên byte + encoding/URL/time/hash trong `../source_archive/`. Tiêu đề/chapter/book/final URL được kiểm. Không có bản nguồn tác giả độc lập để chứng minh đầy đủ.
- `prepare_for_agent.py --chap 1` chạy thành công, tạo source package + prompt trong `../prepared_input_v2/`.
- Kiểm kê `legacy_inventory.json`: 81 chương; 50 có prepared source; 57 có cờ (kể cả thiếu nguồn). Cờ không tự chứng minh lỗi, tất cả giữ trạng thái UNREVIEWED_LEGACY.
- Live model pilot: Gemini 3.8 Flash **16/16**, Gemini 3.6 Flash **14/16**, hai false accept; Gemini 3.7 Flash **503** nên chưa đánh giá được. Hai lượt thành công dùng 4.703 token. Có modelVersion và STOP thật trong usage. Bộ mẫu nhỏ, có đoạn trích thay vì nguyên chương, không dùng tỷ lệ này làm độ chính xác production.
- Live end-to-end: lần 1 tạo draft bởi 3.8 nhưng reviewer 2.5 Pro **404**; lần 2 translator 3.6 **503** sau retry. Cả hai state BLOCKED, không có bản xuất PASS. Danh sách model được API liệt kê không chứng minh generateContent khả dụng. Xem `pilot_runs/`.
- API production preflight đang BLOCKED vì chưa có `quality_roles` tường minh trong `api_config.json`. Không tự chọn một auditor production chưa qua đánh giá để làm gate có vẻ hoạt động.

## Thay đổi chính

- `source_integrity.py`: parser đúng template live, không xóa văn bản anchor/đoạn có từ điều hướng; strict decode/TLS; xác minh danh tính trang và lưu snapshot.
- `semantic_gate.py`: contract nguồn/draft/review, hash và quote, tám chiều ngữ nghĩa, hai reviewer khác identity, chặn context bịa; TXT atomic và publication manifest.
- `quality_pipeline.py`: whole-chapter context, vai trò model tường minh, không fallback ngoài role, sửa có giới hạn, kiểm input budget trước mọi lượt gọi, lưu draft/review/usage/state.
- `multi_llm_client.py`/`gemini_helper.py`: chặn rỗng/cắt dở/refusal/thought; ghi actual model/finish reason; tránh log key; bỏ key viết cứng trong helper.
- `prepare_for_agent.py`/`pipeline_api.py` và ba entrypoint cũ đi qua luồng mới, không reuse cache dung lượng; các lệnh batch cũ cần chuyển sang chạy tuần tự với context PASS.
- Glossary sửa hai sản phẩm vay, thêm khóa 周天翊, bỏ chú thích Black Myth tự thêm. Các TXT cũ không bị sửa hàng loạt bằng replace.

## Điều kiện còn thiếu để chạy sản xuất

Chọn ba vai trò model đã kiểm khả năng chạy; reviewer chính phải vượt regression và kiểm mẫu nguyên chương. Điền quality_roles theo `../quality_roles.example.json`, chạy preflight, rồi chạy một chương qua đủ hai review thật. Chuỗi chương cũ cần audit/backfill nguồn/context; không thể coi file lớn là hoàn tất. Context phải giữ fact có nguồn, giới hạn 120.000 ký tự mỗi prompt; khi cần rút gọn chỉ bỏ/chọn fact đã duyệt, không tự tóm tắt thêm nghĩa.

Quy trình/copyable native prompt và lệnh audit lại: `../QUALITY_WORKFLOW.md`.
