# Cào–dịch–review–xuất bản trong Antigravity

Workflow vận hành độc lập trong Antigravity qua OAuth/native CLI. Không có dịch vụ duyệt ngoài, bước chờ nền tảng khác hoặc yêu cầu phải mở công cụ kiểm thử bên ngoài để chạy từng chương.

## Luồng theo sách

Chạy từ thư mục gốc repository. Ví dụ với book 49736; lệnh crawl/dịch/review bên dưới thực sự sử dụng mạng/model khi chạy.

```powershell
# 1. Cào một block nhỏ và kiểm danh tính/HTML/encoding/hash nguồn
python -m native_oauth.book_49736.crawl_chapters --from-chapter 1 --to-chapter 3

# 2. Tạo draft theo scene; không dùng TXT cũ làm cache hoàn tất
python -m native_oauth.book_49736.batch_pipeline_runner --from-chapter 1 --to-chapter 3 --model gemini-3.8-flash-high

# 3. Hai native reviewer trong các workspace riêng; promote tuần tự khi đạt
python -m native_oauth.review_book_chapter --book-dir native_oauth/book_49736 --from-chapter 1 --to-chapter 3 --reviewer-model gemini-3.8-flash-high --auditor-model gemini-3.8-flash-medium

# 4. Chỉ sau khi đủ 325 chương approved: xuất sách, có gate trước render
python -m native_oauth.book_progress --book-dir native_oauth/book_49736 --chapters 325 --verify
python -m native_oauth.book_49736.build_ebooks --formats pdf epub
```

Model trong ví dụ là cấu hình sẵn có của project, không phải cam kết tài khoản luôn có model đó. Chọn model được cấu hình trong Antigravity và kiểm init runtime; model khác yêu cầu hoặc thiếu provenance sẽ bị chặn.

`book_14713/batch_pipeline_runner.py`, `book_16014/batch_pipeline_runner.py` và hai runner 49736 dùng chung `chapter_runner.py`. `review_book_chapter.py` nhận `--chapter N` hoặc một range tối đa 20 chương. Khi một chương review thất bại, range dừng với exit khác 0; không tiếp tục promote các chương phụ thuộc.

## Luồng source package + parser

Khi đã có source package chuẩn của `semantic_gate.py` và parser analysis khớp nguồn:

```powershell
python -m native_oauth.pipeline_native --source SOURCE.json --analysis ANALYSIS.json --genre hien_dai --workspace native_oauth/native_jobs/my_run --translator-model gemini-3.8-flash-low --reviewer-model gemini-3.8-flash-high --auditor-model gemini-3.8-flash-medium --max-repairs 1
```

Mặc định chạy translator → hai native reviewer → gate → publication evidence. `--draft-only` dừng ở `DRAFT_READY_FOR_NATIVE_REVIEW`; `--resume-draft` chỉ dùng lại draft có source/runtime đúng. Hồi phục có giới hạn 0–2 vòng; mỗi vòng sinh lại từ nguồn, không sửa dữ kiện để làm gate đạt. Workspace attempt/reviewer riêng giữ lịch sử và tránh reviewer xem kết luận của nhau. BLOCKED trả exit code khác 0.

Parser LTP chỉ hỗ trợ đọc, không tự quyết nghĩa. `parse_source.py` cần môi trường/model parser đã cài và đã kiểm hash; route theo sách không yêu cầu cài parser này để chạy. Khi cần phân tích đoạn vượt cửa sổ model, phải chia theo offset có thể kiểm, không cắt ngầm.

## Review và cổng duyệt

- Reviewer 1 đối chiếu đủ từng đoạn Trung–Việt: chủ thể, lời nói/suy nghĩ, tên/quan hệ, số/đơn vị/ngưỡng, phủ định, thời gian/nhân quả và thêm/bớt nghĩa.
- Reviewer 2 cũng đọc nguồn; kiểm xưng hô theo đúng người nói/nghe và chiều gọi, vai vế, người thứ ba, ký ức/điều nhân vật biết, biên chunk/chương và tiếng Việt tự nhiên.
- Mỗi reviewer chạy một phiên native độc lập. Gate xác minh file runtime, events init/result, hash, actual model, conversation id, status/exit/partial và artifact nội dung sau lượt chạy. Đây là bằng chứng transport local, không là chữ ký hay chứng minh danh tính backend nhà cung cấp. Hai reviewer không dùng lại phiên translator hoặc cùng một phiên với nhau. Cùng loại model ở hai phiên độc lập được phép; sự đồng ý của hai phiên không bảo đảm không còn lỗi.
- Review phải khớp package/candidate hash, có đủ ID và quote nguồn/đích thật, tám chiều ngữ nghĩa và flags văn học. Không tự duyệt bằng điểm confidence.
- UNKNOWN của heuristic không tự chứng minh lỗi dịch. Thiếu context thì nêu finding needs_context và dừng; sự mơ hồ cố ý được bảo toàn đúng có thể đạt.
- Source/alias/canon thay đổi hoặc draft sửa chữ làm bằng chứng cũ không còn dùng được. Review lại bản cuối; giữ candidate thất bại và revision trước.

## Nguồn, context và dữ liệu đầu ra

- `sources/`: nguồn có ID/hash; schema v2 giữ raw HTML bất biến, raw hash và mapping từng đoạn. Nguồn/cache v2 phải tái dựng được từ raw; đổi parser tạo revision nguồn mới và giữ history. Nguồn v1 cũ được giữ để audit, không tự nâng cấp bằng sửa hash. Draft không được ghi ngược thành sự kiện nguồn.
- `drafts/`: TXT + alignment JSON + receipt đủ cấu trúc/runtime. Trạng thái này chưa có quyền xuất sách.
- `native_review_jobs/`: inputs đóng băng, workspace reviewer riêng, runtime, QA và evidence. Khi gate chặn, xem `state.json`/`qa.json`; không xóa dòng khó hoặc ghi PASS bằng tay.
- `approved/chuong_NNNN/REVISION/`: evidence/sidecar/TXT/receipt bất biến được promote sau gate. `approved/manifest.json` là commit point nguyên tử dưới OS lock; sửa revision chương trước vô hiệu các entry phía sau, không xóa artifact cũ. Chương sau cần evidence chương trước đã đạt. Context lấy tối đa 24 row / 6.000 ký tự nguồn+đích đã duyệt, ưu tiên giới thiệu đầu và đề cập gần; không tóm tắt AI thành sự thật. Bắt buộc giữ quote giới thiệu mà vượt ngân sách thì dừng để xử lý.
- `build_ebooks.py` của 49736 chỉ đọc manifest duyệt liên tục và xác minh evidence/hash trước render; xuất vào `dist/MANIFEST_HASH/EXPORT_ID/`. Đọc lại EPUB để đối chiếu title/thứ tự/mọi đoạn; PDF kiểm bookmark và token coverage, AZW3 cần Calibre chuyển ngược EPUB để kiểm. Chỉ cấp `publication.json` khi mọi định dạng đã chọn đạt và manifest vẫn khớp. Dùng `--formats pdf epub` nếu chưa có Calibre. PDF hiện yêu cầu font Times New Roman trên Windows; kiểm text không thay kiểm bố cục bằng render/xem trang. Bản cũ trong `output_dich/` hoặc `dist/` không tự được coi đã duyệt.

Dữ liệu approval hiện gắn với các file nguồn/canon/runtime local. Giữ các workspace bằng chứng khi sao lưu; chỉ copy TXT hoặc riêng sidecar không đủ để validate. Repository chứa code và kiểm thử; các workspace sinh mới không tự đưa vào Git. Chuyển máy cần kế hoạch di chuyển bằng chứng và kiểm chứng đường dẫn, không tự đổi identity/hash để hợp thức hóa.

## Điều phối, hiển thị và hồi phục

SessionMonitor hiển thị tên/genre/chương/range/wave, số từ/đoạn, worker và trạng thái các giai đoạn trong session Antigravity. Hoàn tất công việc của worker không đồng nghĩa approved. Các wave dịch tạo draft; bước nghỉ quota không phải calibration nội dung.

Route batch manifest tổng quát trong `BATCH_WORKFLOW.md` vẫn là đường thử nghiệm source-frozen, không tự publish. Đường theo sách đã có review/promote riêng như trên. Nếu review phát hiện lỗi, sửa cơ chế nguồn/context/canon hoặc chạy lại scene/chương bằng runner; không để công cụ regex tự sửa nghĩa. `pipeline_native.py` có vòng sinh lại bounded; review command theo sách dừng khi lỗi để Antigravity xử lý/rerun và kiểm lại.

UrbanAuditor là triage chỉ đọc. Polisher chỉ tạo bản nháp đề xuất mới; mọi sửa chữ phải được review lại trước approved. Runtime partial/timeout hoặc owned IDs thiếu/rỗng bị chặn trên cả generation và resume. Candidate phải trùng kết quả cleanup định dạng của response generation; init/result/model/session được kiểm từ events.jsonl. Mỗi lượt generation có runtime riêng để giữ nguyên bằng chứng revision cũ. OS lock tự nhả khi tiến trình chết; không cần xóa claim để chạy lại.

## Kiểm chứng trước sử dụng

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -X utf8 audit/replay_semantic_context_20261022.py
```

Test sử dụng fixture/mock không gọi model. Chưa có bản dịch/review live mới sau các sửa này; cần một pilot native nhỏ trước mở rộng. Không suy tỷ lệ dịch đúng từ số test, không dùng mẫu đã tác động prompt làm heldout. Kết quả pilot lịch sử nằm trong audit/benchmark, không là phụ thuộc của workflow.
