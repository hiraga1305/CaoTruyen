# Hợp nhất workflow D và G — 22/10/2026

Đã chọn ghép phần quản lý nguồn/revision/xuất bản từ bản G với phần chống partial và xử lý ngữ nghĩa từ bản D. Bản vận hành chỉ dùng Antigravity: cào → dịch nháp → hai native review độc lập → sửa/sinh lại → duyệt → xuất bản. Kiểm tra chéo trong phiên này là một lần sửa/kiểm thử; không thêm phụ thuộc Codex hoặc dịch vụ duyệt ngoài.

## Đối chiếu và lựa chọn

Hai checkout cùng HEAD `a81dd75e1693d772ed76e0ecb51704de817239d1` lúc đối chiếu. Thay đổi mới nằm trong working tree. Đã đọc/so nội dung và hash thay vì dựa riêng vào ngày sửa hay trạng thái Git của ổ đồng bộ G. Không chỉnh bản G và không sao chép toàn bộ thư mục, môi trường, credential, tác phẩm, ZIP/PDF hoặc các script sửa riêng từng chương.

| Phần | Lựa chọn | Lý do và cách ghép |
|---|---|---|
| Nguồn cào | Lấy adapter CZBooks và schema v2 từ G, bổ sung kiểm danh tính từ D | Host/book/chapter/redirect/canonical/title, UTF-8 strict; giữ anchor text, raw HTML/hash và mapping mọi đoạn. Nguồn v2 phải tái dựng được từ raw. Không tự sửa nguồn cũ. |
| Dịch theo cảnh | Giữ `chapter_runner.py` và bốn runner D | ID đầy đủ, không padding, giữ continuation, chống partial timeout/ACTIVE; chia có ngân sách và source overlap, retry chia nhỏ có giới hạn. G dùng chunk lớn và parser lấy một dòng/ID có thể bỏ continuation. |
| Tên/xưng hô | Giữ semantic profiles/context/prepass và prompt D | Alias được khai báo rõ, không gộp người theo tên Việt; không lấy thứ tự entity làm người nói/nghe hoặc suy ta–ngươi từ từ khóa. UNKNOWN khi thiếu căn cứ. |
| Bằng chứng generation | Kết hợp kiểm response của G với runtime/events của D | Draft phải trùng response đã hoàn tất sau cleanup định dạng. Xác minh init/result/model/session; mỗi lượt generation có thư mục riêng, không làm hỏng evidence của revision cũ. |
| Review | Giữ hai native reviewer trong workspace riêng của D | Đọc đủ nguồn/đích, quote theo ID, kiểm nghĩa và văn học/continuity. Không mang nhánh `codex_gpt_sessions` hoặc attestation tự khai từ G vào workflow. |
| Revision/manifest | Lấy thiết kế G, tích hợp vào `book_publication.py` | Revision bất biến; manifest thay nguyên tử dưới OS lock là commit point. Đổi bản duyệt chương trước vô hiệu các entry phía sau; không xóa revision cũ. Một schema duyệt cho route theo sách. |
| Context | Giữ retrieval D, đọc các revision trong manifest | Tối đa 24 row / 6.000 ký tự nguồn+đích; ưu tiên giới thiệu đầu và đề cập gần. Không lấy draft chưa duyệt làm fact. |
| Atomic I/O/lock | Lấy `workflow_io.py` từ G | Ghi LF, replace nguyên tử có retry Windows; OS lock nhả khi tiến trình chết. |
| Xuất bản | Lấy exporter và `export_integrity.py` từ G, nối manifest mới | Kiểm toàn bộ chương trước render; đọc lại EPUB, kiểm PDF text/bookmark, AZW3 qua Calibre round-trip. Chỉ ghi publication receipt khi mọi định dạng đã chọn đạt. Mỗi lần xuất có EXPORT_ID riêng, giữ lần xuất trước. |
| Tiến độ/CI | Giữ live SessionMonitor D, lấy cách phân biệt approved/draft và CI từ G | `book_progress` báo riêng approved, draft, legacy và approval hỏng. CI kiểm code ngoại tuyến, không gọi model, không tham gia luồng duyệt nội dung. |
| Regex tự sửa / script theo chương | Không nhập vào route vận hành | Heuristic chỉ cảnh báo; UrbanAuditor chỉ đọc. Không xóa Hán tự hay đổi ngôi xưng/từ đa nghĩa để làm PASS. Sửa text cần generation/review mới. |

Danh mục so sánh nằm ở [copy_comparison_20261022.evidence.json](copy_comparison_20261022.evidence.json); đây là snapshot code khi hợp nhất, không là inventory dữ liệu truyện. Các runner và schema riêng `book_runner.py`/`book_workflow.py` của G không được nhập nguyên khối để tránh hai cơ chế duyệt song song. Các kiểm thử tương ứng đã được chuyển sang schema hợp nhất.

## Những lỗ hổng được khép khi nối hai bản

- Chống việc sửa draft/receipt rồi vẫn trỏ runtime của một response khác; kiểm lại nội dung response thật, ownership và runtime events.
- Tách runtime theo generation để chạy lại không ghi đè bằng chứng đang được bản approved tham chiếu.
- Manifest duyệt nguyên tử, giữ revision cũ; publisher chặn thiếu/thừa chương hoặc predecessor/canon/source/runtime đã đổi.
- Khóa cả trạng thái chưa có file canon: thêm lore sau duyệt cũng khiến approval cũ cần kiểm lại.
- Bỏ claim có thể mắc lại khi process chết, dùng OS lock cho generation/review/manifest/export.
- Calque/genre/xưng hô heuristic là cảnh báo cho reviewer, không là phép sửa nghĩa. Profile reviewer phân biệt thiếu context với nguyên tác cố ý mơ hồ.
- Không ghi đè lần xuất trước khi một lần xuất mới thất bại; receipt xuất bản ghi sau kiểm định định dạng và manifest cuối.

## Xác minh và giới hạn

Kiểm thử trên fixture/mock ngoại tuyến, không chạy model, crawl hoặc sửa truyện thật. Suite và các phép replay được ghi trong [merged_release_20261022.evidence.json](merged_release_20261022.evidence.json). Bao gồm đường draft → hai review → revision → manifest → tạo PDF/EPUB thật trong thư mục tạm → đọc lại nội dung và kiểm publication receipt. Kiểm AZW3 thiếu Calibre phải bị chặn; chưa tạo/round-trip AZW3 thật trong đợt này. CI được cấu hình Windows/Linux, kết quả từ xa cần xem riêng sau push.

Replay trên 325 chương, 31.034 đoạn nguồn không đổi dữ liệu được bảo vệ. Nó đo hành vi heuristic và độ phủ, không đo độ chính xác dịch. Bản dịch legacy còn 267 bản ghi thân bị thiếu trong sáu chương và các mismatch provenance đã báo trước; không tự phục hồi/chỉnh lại trong lần hợp nhất này. Publisher mới phải chặn chúng cho tới khi có đủ bản duyệt hợp lệ.

Chưa chạy native pilot mới sau sửa; chưa chứng nhận ngữ nghĩa toàn bộ truyện. Hai reviewer độc lập vẫn có thể cùng sai. Trước vận hành quy mô lớn, chạy pilot nhỏ trong Antigravity với nguồn chưa dùng để sửa prompt. Runtime/events/artifact là provenance transport local, không phải chữ ký nhà cung cấp. Evidence có đường dẫn local: phải sao lưu cả nguồn, canon và runtime; chuyển máy cần xử lý/kiểm chứng đường dẫn, không tự bịa hash hoặc identity.

Lệnh và giới hạn hiện hành: [ANTIGRAVITY_WORKFLOW.md](../native_oauth/ANTIGRAVITY_WORKFLOW.md). Các báo cáo audit/pilot trước sửa được giữ làm lịch sử; chỉ hướng dẫn hiện hành xác định luồng vận hành.
