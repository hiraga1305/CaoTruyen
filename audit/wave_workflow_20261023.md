# Điều phối nhóm 5 chương — 23/10/2026

Đổi runner `native_oauth.revise_book` sang mặc định `--mode wave --max-workers 3`: tối đa 5 chương/nhóm, hai worker sinh nháp và một luồng review theo thứ tự. Phê duyệt không chạy vượt chương trước; review chương đầu có thể bắt đầu trong khi các worker còn sinh nháp các chương sau. `--max-workers 6` cho phép năm worker dịch cùng một luồng review. `--mode sequential` giữ đường chạy tuần tự.

## Bảo toàn nghĩa và bằng chứng

- Nháp có schema/receipt sinh riêng, giữ nguyên package hash và response native; không sửa hash để giả đã dùng context cuối.
- Gate đối chiếu lại nguồn, canon, heading và phản hồi biên tập trước khi dùng nháp với context đã duyệt. Cả hai review phải xác nhận `generation_context_checked:true`.
- Hai reviewer vẫn có runtime/workspace độc lập. Có bảng lựa chọn trích dẫn nguyên văn để giảm lỗi chép quote; việc chọn mã quote không thay verdict, lý do hoặc các chiều kiểm nghĩa. Quote/ref mâu thuẫn bị chặn.
- Sau mỗi nhóm, native wave-auditor kiểm liên kết trên đủ nguồn–đích cả nhóm và prefix có nguồn. `wave_gates` gắn với đúng revision, chặn xuất sách khi chưa PASS hoặc evidence thay đổi.
- FAIL chương loại nháp khỏi cache tái sử dụng. FAIL nhóm lưu findings đúng ID/quote/hash vào `wave_diagnostics`, dừng và yêu cầu sửa/review lại phần bị ảnh hưởng khi resume; không hỏi lại cùng bản thất bại đến khi có PASS.
- Cache nháp, checkpoint và artifact lịch sử được giữ. Approval cũ còn hợp lệ được tái sử dụng. Có thể dùng cùng pipeline cho sách nguồn mới chưa có legacy output.
- Binding dashboard vào session native được khóa cùng tiến độ khi các worker khởi tạo đồng thời.

## Kiểm thử thực hiện

Baseline trước sửa: **259 tests đạt**. Sau sửa: **276 tests đạt**, gồm **17 ca mới** trong `tests/test_wave_revision.py`. Models/transport được giả lập, không gọi model thật. Kiểm syntax 13 file Python và `git diff --check` đạt. CLI `--help` hiển thị mode và giới hạn worker mới.

Các ca mới kiểm thực thi đồng thời hai worker, review xen kẽ, thứ tự predecessor, gate nhóm, không mất legacy, resume không gọi model thêm khi đã hoàn tất, resume sau lỗi schema không sinh lại nháp, nháp semantic FAIL không được dùng lại, nguồn đổi giữa generation bị chặn, generation/package không được hoán đổi, bắt buộc review context cuối, wave receipt bị sửa chặn export, dừng tại checkpoint, prefix của nhóm tiếp theo, nhóm cuối ngắn hơn 5 chương, sách chưa có legacy và quote references không bỏ các cổng nghĩa/provenance.

Kiểm read-only dữ liệu thực tế: approval **1–5** của `book_49736` vẫn hợp lệ, không có invalid approval. Cả năm được hàm nhận diện resume chấp nhận với cấu hình reviewer hiện tại. Không chạy lại bản dịch, không sửa nguồn hoặc approval thật và không khởi chạy chương tiếp theo trong lượt chỉnh code này.

## Giới hạn của kết quả

Các test chỉ xác nhận hành vi điều phối và các guard đã kiểm; chưa chứng minh chất lượng bản dịch tương đương hoặc tốc độ cải thiện trên native model thật. Kiểm liên kết nhóm là một lượt gọi model bổ sung, có chi phí token/thời gian. Quota, lỗi CLI hoặc toàn bộ prompt vượt ngân sách vẫn dừng job. Chạy thật cần đo thời gian cả job, token gồm mọi attempt, lỗi nghĩa và lỗi liên kết trên cùng nguồn để so với tuần tự.

## Chạy tiếp nhóm 6–10 khi vận hành

```powershell
python -m native_oauth.revise_book --book-dir native_oauth/book_49736 --job native_oauth/book_49736/repair_jobs/revision_20261023 --through-chapter 10 --mode wave --max-workers 3
```

Lệnh gọi model thật. Năm approval trước được kiểm lại và bỏ qua nếu vẫn hợp lệ; không tự đẩy mã nguồn hoặc dữ liệu lên GitHub.
