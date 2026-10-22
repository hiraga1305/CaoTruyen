# Pipeline cào–dịch–xuất bản trong Antigravity

Dùng [workflow hiện hành](native_oauth/ANTIGRAVITY_WORKFLOW.md).

Cào và xác minh nguồn → draft có ID/hash → gate cấu trúc/runtime → hai native review độc lập → sửa/sinh lại có giới hạn → approved → xuất sách. Không có bước chuyển sang nền tảng duyệt ngoài Antigravity.

Các CLI theo sách tạo draft; chạy `python -m native_oauth.review_book_chapter --help` để review/promote. Route package chương đơn dùng `python -m native_oauth.pipeline_native --help`.

Các hướng dẫn API và pilot cũ là lịch sử; không dùng cache TXT cũ hoặc số test qua làm chứng nhận chất lượng truyện.
