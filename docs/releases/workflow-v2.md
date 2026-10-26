# CaoTruyen workflow 2.0.0 — 26/10/2026

Chốt Resilient v2 làm mặc định tại `hiraga1305/CaoTruyen`: entry point `translate.py`, hợp đồng `workflow.json`, hướng dẫn `WORKFLOW.md`. API cũng mặc định resilient; wave/sequential chỉ tương thích khi chỉ định rõ.

Bốn translator MEDIUM, tối đa năm chương/wave tự co, hai reviewer MEDIUM độc lập, HIGH fallback/sửa tập trung. Có journal, timeout hữu hạn, source recovery/resume và checkpoint approved mỗi 100 chương không thêm audit ngoài.

## Pilot đã đo

Local đã hoàn tất 1–20 bằng v1, 21–40 bằng v2 và ba diagnostic 1622/1975/1978 không có quyền approval. 40 chương có native evidence hợp lệ. Hai job khác nội dung nên không phải A/B cùng chương:

| Chỉ số | V1 1–20 | V2 21–40 |
|---|---:|---:|
| Wall time | 24 phút 14 giây | 23 phút 34 giây |
| Native calls | 44 | 36 |
| HIGH calls | 12 | 3 |
| Worker seconds | 3.310,58 | 2.273,23 |
| Approved source chars/hour | 106.767 | 108.226 |

V2 không gặp glossary false block, timeout/quota trong run này. Có bốn lần sai ID được fallback/chia scope xử lý; HIGH cũng có một lần sai ID, không tuyên bố thành công 100%. Hai style suggestions không gây tái sinh bản đúng. Entity obligations không phát sinh trong run mới; 192 trường hợp là replay offline, không phải 192 review native mới.

Worker time giảm rõ nhưng wall chỉ giảm khoảng 2,7%. Ngoại suy 5,25 triệu ký tự ra khoảng 48,5 giờ liên tục chưa gồm quota/pause/độ khó về sau, không cam kết hai ngày lịch. Không lấy số test/PASS làm tỷ lệ dịch đúng.

## Bảo vệ và giới hạn

Thiếu chuỗi tên được cả hai reviewer kiểm chủ thể; sai người/ý vẫn FAIL. NFC/NFD/case/whitespace chỉ chuẩn hóa khi so sánh, không sửa output hoặc bỏ dấu. Optional style suggestions và source-script quotes có source-bound duty; không whitelist chữ Hán. needs_context phải có query nguồn trước; schema sai được phục hồi như lỗi protocol.

Report chỉ tính công suất phần mới; dashboard nhận prefix có proof mà không gán latency giả. Seal giữ dependency prefix và raw/lineage của cả replacement chưa dùng.

Reviewer có thể bỏ sót sạn. Pilot `c0030p0043` dùng “ăn thịt người” cho 殺過人 (“giết người”), cần native sửa/review trước xuất bản. Release code không chỉnh approved hoặc giả tạo review để xóa finding này.

Code/canon/config mới cần job revision; approval/bundle cũ giữ nguyên, policy v1 không nới hồi tố. Dataset/runtime/report chi tiết/ZIP ở local. Workflow không cần một phiên Codex hoặc audit ngoài để vận hành.
