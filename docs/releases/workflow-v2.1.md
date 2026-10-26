# CaoTruyen workflow 2.1.0

Tối ưu điều phối và phục hồi, giữ policy nội dung/review v2 và các gate nguồn, coverage, runtime, hai reviewer, revision, prefix trước xuất bản.

## Hai thay đổi chính

- Hai reviewer chạy đồng thời từ cùng batch bất biến, mỗi role có key/session/workspace riêng. Không nhận kết luận của peer. Evidence vẫn sắp theo role cố định và chỉ duyệt khi cả hai hợp lệ. Reviewer lỗi kỹ thuật không xóa peer đã xong; resume dùng lại đúng proof. Tối đa hai request review và chịu giới hạn health; `--review-workers 1` là tùy chọn tuần tự.
- Response translator hoàn tất, có provenance và đúng ID nhưng lỗi cơ học có ID cụ thể: giữ response gốc, chọn ownership phần đúng, HIGH chỉ dịch lại các row lỗi. Kết quả được ghép từ các component native rồi kiểm toàn bộ và hai review như cũ. Không sửa text, xóa chữ, đổi ID hoặc gán PASS cho response lỗi. Journal giữ failure thật và proof của phần dùng lại; gián đoạn giữa repair và draft pointer không buộc sinh lại cả chương.

Partial, invalid JSON/ID, runtime/model mismatch, native safety/content block và integrity lỗi không được dùng đường tái sử dụng row. Repair vẫn hữu hạn; lỗi lặp/quota/auth có queue và next_actions, không bỏ chương hoặc ép hoàn tất.

Khóa tệp trạng thái và dashboard khởi tạo marker sau khi đã lấy OS lock, tránh worker khác ghi vào byte đang bị khóa khi nhiều luồng mở tệp lần đầu trên Windows. Kiểm thử dùng OS lock thật cho thứ tự khởi tạo và truy cập đồng thời.

## Cách đọc thời gian

Dashboard và chapter_metrics.csv tách:

- Tạo nháp: wall time đến nháp đầy đủ đầu tiên, gồm retry/repair cơ học và có thể có pause.
- Nháp → duyệt: wall time còn lại, gồm chờ phần khác, hai review và sửa ngữ nghĩa sau review.
- Đến khi duyệt: tổng hai giai đoạn khi đủ mốc; không cộng thời gian các chương chạy song song để tính wall time.

Mốc cũ thiếu timestamp để null/—, không suy đoán. Worker/model time vẫn tách trong metrics/native_calls.csv. Chỉ record đã commit native batch mang nhãn NATIVE_BATCH_PASS; bản structural cũ giữ nhãn cũ.

## Phạm vi kiểm chứng

Wave 41–45 trước tối ưu mất khoảng 451 giây cho cả năm chương: tạo nháp/phục hồi khoảng 247 giây, hai review tuần tự khoảng 113 và 81 giây. Đây là lý do chọn hai điểm tối ưu, không phải benchmark của bản 2.1. Nếu latency mỗi reviewer giữ nguyên, chạy song song có thể giảm phần review từ tổng về gần lượt chậm hơn; chưa cam kết wall time hoặc thời hạn toàn sách.

Kiểm thử offline gồm barrier xác nhận review overlap, không chia sẻ peer output, giữ nguyên byte text của row tốt, repair scope đúng một ID, resume không dịch lại toàn chương, chống sửa artifact và tính giai đoạn thời gian. Native benchmark mới phải chạy trong Antigravity theo phạm vi được giao, không chạy model chỉ để test code.

Đổi code/config cần job revision mới, giữ prefix approved cũ. Mặc định bốn worker dịch, tối đa năm chương/wave; chưa tăng tám worker hoặc dịch gối wave tiếp. Workflow không thêm audit ngoài/Codex dependency.
