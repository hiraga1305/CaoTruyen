# Sửa bản thử 325 chương bằng Antigravity — 22–23/10/2026

**Chưa hoàn tất sửa và duyệt toàn bộ 325 chương.** Đây là báo cáo một chiến dịch sửa thật đang thực hiện, không phải kết quả benchmark hay chứng nhận bản sách đã sẵn sàng xuất bản. Trạng thái ở thời điểm kiểm tra nằm trong `live_native_repair_20261022.evidence.json`; trạng thái hiện hành nằm trong campaign/approved manifest local.

## Phạm vi và dữ liệu được giữ

Người dùng đã yêu cầu sửa bản thử *Tìm Kiếm Vô Gian Địa Ngục*, tìm nguyên nhân và cải thiện repo. Toàn bộ generation/review thực tế dùng Antigravity native CLI với cached account; không dùng API key, không thay quyền, không thêm ứng dụng duyệt ngoài vào workflow. Bridge MCP không trả được kết quả nên dùng adapter CLI local đã có.

Job local: `native_oauth/book_49736/repair_jobs/20261022T153633Z`. Snapshot ban đầu có **979 tệp, 33.410.091 byte**, gồm nguồn, output legacy và tệp dist ở cấp trực tiếp. Báo cáo status kiểm SHA-256 của cả snapshot và tệp gốc; không coi số tệp tồn tại là bằng chứng bảo toàn. Các revision, runtime và nháp mới được lưu riêng, không đẩy dữ liệu dang dở lên Git.

Đã sinh đủ **267 đoạn nháp phục hồi** bằng native sessions:

| Chương | Đoạn thiếu được phục hồi thành nháp |
|---|---:|
| 239 | 15 |
| 248 | 13 |
| 299 | 72 |
| 306 | 49 |
| 310 | 43 |
| 318 | 75 |

Từng phần có nguồn/ID/hash/runtime; `revision_status.py` so khớp văn bản tổng hợp với response native thật. Trạng thái vẫn là `RECOVERY_PROPOSAL_UNREVIEWED`. Phải sửa toàn chương và qua hai review trước khi có quyền xuất bản. Riêng đoạn cảm ơn chương 310 đã bị chặn vì giữ nguyên tài khoản chữ Hán; lượt native sau xử lý thành chữ Latin, không bỏ danh sách.

Các lượt đầu đã tạo revision được duyệt cho chương 1–4. Việc nâng cấu hình/phản hồi biên tập khiến chương trước được kiểm lại; manifest chỉ giữ chuỗi phụ thuộc hiện hành, archive cũ được giữ. Không cộng các approval lịch sử vào tiến độ hiện tại. Sự kiện native `SUCCESS` đơn lẻ không được dùng để công bố hoàn thành sách.

## Những lỗi nghĩa đã có bằng chứng cụ thể

Hai lượt chẩn đoán native độc lập đã đọc đủ 99 ID chương 3. Một lượt báo 9 findings, một lượt 8; 7 finding trùng nhau. Đây là một mẫu đã được dùng để cải thiện prompt, **không phải heldout** và không suy được tỷ lệ đúng của 325 chương.

- `c0003p0043`: thời lượng “đã nói suốt mấy năm” bị biến thành “mấy năm nữa”.
- `c0003p0055`: quan hệ chưa thành “chị dâu tương lai” và góc nhìn “trong ký ức” bị làm mờ.
- `c0003p0032`: thích ngửi bị chuyển thành quen ngửi.
- `c0003p0089`: nói nhỏ bị chuyển thành gắt gỏng.
- `c0003p0070`, `c0003p0086`: thêm hình dạng/động tác không có căn cứ rõ trong nguồn.

Revision native chương 3 ở lượt đầu đã sửa các trường hợp trên, nhưng một lượt Claude native chẩn đoán tiếp vẫn chỉ ra lỗi “vật lý tiền duyên” ở `c0003p0007`. Hai reviewer Gemini trước đó đã bỏ lọt nó. Vì vậy, đủ hai PASS không chứng minh không còn lỗi thuật ngữ hoặc câu Việt gượng.

Lượt Claude có 25 findings, nhưng chỉ 23 cặp quote neo được duy nhất vào cùng đoạn nguồn–đích; có finding chỉ nói câu đang đúng, hoặc đề xuất làm mất số lượng. Không áp dụng hàng loạt các đề xuất đó. `diagnostic_grounding.py` giữ nguyên báo cáo native và phân biệt grounding với approval. Lỗi chuyên ngành được ghi thành phản hồi có quote/hash để lượt sửa tiếp kiểm lại trên nguồn.

Ở chương 1, lượt hậu kiểm cũng phát hiện mức phỏng đoán bị nâng thành chắc chắn, và tên Pandora bị thay bằng vật thể gắn với tên đó trong câu giải thích tên gọi. Bản nháp native mới đã sửa hai điểm này; quyền xuất bản vẫn phụ thuộc review của đúng bản cuối.

## Vì sao có lỗi và phần đã thay đổi

1. **Mất đoạn do nhận nhầm completion.** Lịch sử sáu chương cho thấy print-timeout có thể trả `SUCCESS` với agent response còn `ACTIVE`. Runner cũ bù rỗng rồi formatter bỏ đoạn khiến tệp vẫn tồn tại và được xuất. Các guard partial/owned-ID/export của release trước được giữ; không sửa hash legacy để hợp thức hóa.
2. **Ràng buộc hình thức chưa kiểm được nghĩa.** ID/hash/quote đúng chỉ chứng minh đối chiếu đúng văn bản. Dịch giả và reviewer vẫn có thể cùng bỏ qua thời lượng, mức chắc chắn, thuật ngữ hoặc điểm nhìn. Thêm neo trích đúng cue nguồn; reviewer văn học đọc Việt trước rồi kiểm lại Trung. Hai session phải độc lập, nhưng cùng họ model vẫn có điểm mù chung.
3. **Gợi ý từ điển có thể thành áp lực dịch sai.** Gate nay chỉ khóa tên nhân vật đã biên tập; nghĩa chung/chữ riêng lẻ là gợi ý theo ngữ cảnh. Nguồn quyết định quan hệ, sắc thái và lĩnh vực, không lấy biography hay thuật ngữ gợi ý làm sự kiện.
4. **Sửa lại từ bản cũ gây hồi quy.** Lượt repair nay nhận candidate gần nhất cùng findings cần kiểm lại. Giữ câu đã sửa đúng; mọi bản sửa vẫn phải được hai phiên mới review, không dùng evidence cũ cho chữ mới.
5. **Sai evidence không đồng nghĩa sai bản dịch.** Quote bị thêm dấu mở ngoặc của đoạn trước từng làm cả chương bị sinh lại. Quote/schema lỗi được thử lại tối đa một lần ở riêng reviewer, trên candidate đóng băng. FAIL nội dung hợp lệ không được retry cho tới PASS. JSON sai được giữ nguyên, không vá thành một báo cáo duyệt.
6. **Transport/tool không phù hợp gây gián đoạn.** Lượt đầu mất thời gian vào đường dẫn tương đối sai và Python bị chính sách native từ chối. Route JSON mới gửi đủ dữ liệu qua stdin, không gọi tools/shell, không sửa quyền. CLI vẫn có lượt phát result rồi không thoát dù đổi sang stdin hữu hạn và review tuần tự; chưa xác định nguyên nhân bên trong CLI. Runner mới phân biệt model đã hoàn tất với client chưa thoát: chỉ đóng sau ít nhất 10 giây khi đã kiểm một init/result cùng session/model, response `DONE`, JSON hợp lệ, không tool/denied/partial/truncation. `COMPLETED_CLI_CLEANUP` giữ exit code thật và hash events/response/stdin; provenance kiểm lại proof, không đổi runtime TIMEOUT cũ thành đạt. Mọi ID và hai review vẫn phải qua gate. Thử nghiệm stdout `SUCCESS` hoặc một substring đơn lẻ không đủ điều kiện này.
7. **Tiến độ cần gắn đúng phiên.** Dashboard dùng conversation id quan sát từ init thật, giữ tối đa sáu session gần nhất; không lấy thư mục sửa gần nhất làm phiên đang chạy. Hoàn tất worker/kiểm cấu trúc không được tính là duyệt nghĩa toàn sách.

`revise_book.py` lưu baseline, candidate, attempt, review và approval theo revision; resume kiểm cả cấu hình reviewer lẫn package hiện hành. Phản hồi biên tập tùy chọn phải có quote nguồn–đích đúng cùng ID, hash của bản đối chiếu và nguồn không đổi. Phản hồi là dữ liệu cần kiểm lại, không tự biến thành kết luận PASS. `revision_status.py` kiểm lại cả provenance và nội dung các nháp phục hồi; trạng thái campaign không tự thay thế manifest.

## Kiểm chứng và phần còn lại

Suite offline hiện có **251 tests đạt**. Tests mock model; kiểm native completion, provenance, EOF/command-line Windows, schema-only retry, FAIL không bị thử lại để lấy PASS, quote/hash/canon, snapshot và việc không nhầm nháp thành approval. Trường hợp client cần đóng sau DONE phải giữ actual exit, hash và stdin; ACTIVE, JSON hỏng, tool, finish reason bị cắt, sai session, proof thay đổi và timeout cũ không được nâng thành completion. Số test không đo chất lượng dịch.

Chiến dịch vẫn cần hoàn tất các chương theo thứ tự và kiểm lại revision cuối. Chưa tạo ebook mới hoặc cập nhật bản xuất cũ để giả lập hoàn thành. Cần đủ chuỗi 1–325 approved rồi mới chạy gate/render/export; bản cũ vẫn chỉ là bản thử.

Bộ điều phối local hiện được khởi chạy bằng tiến trình Windows riêng, có log/checkpoint trong job; không cần một session kiểm tra chéo tiếp tục gọi model. Wrapper local chỉ gọi bộ sửa của repo và native CLI; sau đủ 325 approval nó kiểm `revision_status`/`book_progress --verify` rồi mới gọi builder PDF/EPUB. Nếu có lỗi/quota/gate bị chặn, wrapper ghi `controller_result.json` và không xuất sách thiếu duyệt. Lượt chạy mới đã duyệt lại chương 1 với hai runtime thoát tự nhiên mã 0 (138,01 và 134,5 giây), rồi chuyển sang chương 2. Chưa có kết quả hoàn tất toàn sách tại thời điểm ghi báo cáo.

Hướng phát triển nội dung tiếp theo là tập đánh giá có nguồn và kỳ vọng nghĩa được biên tập, gồm xưng hô nhiều người, lời nhại/độc thoại, quan hệ thay đổi, độ chắc chắn, số lượng, thuật ngữ chuyên ngành và thành ngữ. Giữ tập chưa dùng để sửa prompt riêng với các mẫu đã dùng ở đây; ghi nhận false positive của reviewer và lỗi do repair tạo mới. Các bước đó có thể chạy trong Antigravity, không cần ràng buộc một công cụ kiểm tra chéo bên ngoài.
