# Workflow chuẩn CaoTruyen — Resilient v2

Repository chuẩn: https://github.com/hiraga1305/CaoTruyen. Tác vụ dịch mới trong CaoTruyen dùng `translate.py` và policy v2; route cũ chỉ khi người dùng yêu cầu rõ. `workflow.json` khai báo phiên bản/default; test kiểm chúng khớp entry point thật.

Mọi live run dùng [quy trình khởi động bắt buộc](docs/WORKFLOW_LAUNCH.md): đối chiếu canonical GitHub main, `translate.py doctor`, rồi `translate.py launch`. `workflow_release.json` khóa code/hướng dẫn; process-local gate chặn job/code/policy cũ trước model và kiểm lại ở biên wave. Hướng dẫn lịch sử hoặc tên thư mục 2.x không chọn phiên bản. Route tương thích chỉ phục vụ đọc/replay; muốn vận hành dùng runner hiện hành, không gọi CLI ngoài gateway.

## Đầu vào và phiên Antigravity

Chạy từ root repo, Python 3.10+ với `requirements.txt`, native `agy` CLI và tài khoản OAuth hợp lệ. Nếu CLI không nằm ở vị trí `run_agy.find_cli()` nhận biết, khai `AGY_BIN` trỏ executable đã có. Không chuyển API key để né lỗi account/quota.

Book local có `sources/source_chapter_NNNN.json`, `toc.json`, `lore.json` cho tên/thuật ngữ và canon riêng tùy chọn `translation_canon.json`. Nguồn v2 giữ HTML tại `source_archive/book_BOOK_ID/`, hash và mapping từng đoạn. Crawler phải xác minh đúng truyện/chương; không lấy nháp làm nguồn hoặc sửa hash để hợp thức hóa dữ liệu lỗi. Code/canon/model policy được freeze trong job.

Mọi sách dùng [quy ước continuity chung](docs/CONTINUITY_CONVENTIONS.md) và schema `continuity_entries` trong canon local. Antigravity chuẩn bị bảng từ nguồn/approved đã xác minh của chính sách trước khi chạy; sách mới được bắt đầu với bảng rỗng. Không dùng danh xưng, quan hệ hoặc giới tính của một truyện làm mặc định cho truyện khác. [Prompt dịch tiếp dùng chung](docs/prompts/continue-translation.md) nhận phạm vi người dùng giao.

```powershell
# Offline: chỉ đọc/replay nguồn. Network chỉ khi thêm --repair-sources.
.venv/Scripts/python.exe -X utf8 translate.py preflight --book-dir BOOK_DIR --job JOB_DIR --through-chapter LAST_CHAPTER
```

Nguồn lỗi đi qua queue/refetch/import có lineage, giữ nguyên bản cũ. `--source-recovery-dir VERIFIED_DIR` kiểm book/chapter/hash chính xác, không chỉ tên file. Trước live run, Antigravity bind `ANTIGRAVITY_ARTIFACT_DIR` hoặc `ANTIGRAVITY_CONVERSATION_ID` vào phiên thật hiện tại; không dùng phiên cũ hoặc suy từ mtime. SessionMonitor ghi badge/dashboard HTML và Markdown, state riêng cho job.

## Dịch, review, sửa và phê duyệt

```powershell
.venv/Scripts/python.exe -X utf8 translate.py doctor
.venv/Scripts/python.exe -X utf8 translate.py launch --book-dir BOOK_DIR --job JOB_DIR --through-chapter LAST_CHAPTER --workers 4 --checkpoint-every 100
```

`LAST_CHAPTER` là phạm vi người dùng cho phép. Mặc định translator/reviewer MEDIUM, HIGH fallback; timeout đầu 300 s rồi retry có giới hạn. Runtime init phải xác nhận model thật; không tự khai identity. Account có thể chưa có model cấu hình, cần xử lý điều kiện hợp lệ thay vì đổi nhãn runtime.

1. Bốn worker tạo nháp, tối đa năm chương/wave. Context là nguồn trước đúng thời điểm và canon có phạm vi; nháp chưa duyệt không thành sự thật.
2. Hai reviewer chạy đồng thời ở session/workspace độc lập, đọc đủ nguồn–đích, nghĩa/văn học/thực thể/phủ định/số lượng/luật chơi/continuity. Không xem kết luận của nhau, không thêm wave audit thứ ba. Tối đa hai phiên review, chịu giới hạn health; `--review-workers 1` chọn tuần tự.
3. ID/hash, coverage, text rỗng, partial và chữ Hán chưa dịch là lỗi cứng. Tên→đại từ/alias hợp context phải được cả hai reviewer kiểm; không chặn chỉ vì thiếu chuỗi tên. Optional style suggestions riêng, lỗi nghĩa hoặc canon bắt buộc vẫn FAIL.
   Policy `scoped-continuity-1` yêu cầu cả hai reviewer khai `continuity_checks` cho tên/nhãn, alias/góc nhìn và người nói–người nghe; mỗi mục canon đang áp dụng có quyết định theo `(slot,key)`. Thiếu cách viết chuẩn cần giải thích `valid_variation`, hoặc issue thật. `violation`/`needs_context` không được chuyển thành suggestion. Tên mới chưa có canon vẫn phải kiểm nhất quán trên wave và prefix được cung cấp; đây là đánh giá native, không phải host tự nhận diện tất cả thực thể.
4. Lỗi thật tạo revision native và review lại đủ hai lượt. Response đã hoàn tất, có provenance và đủ ID đúng thứ tự chỉ lỗi vài row: HIGH sửa đúng các row đó; phần đúng lấy nguyên text native, journal giữ response lỗi và proof. Partial/sai ID không dùng đường giữ row. Host không tự dịch, xóa chữ, đổi ID/verdict hoặc hỏi lại cùng bản FAIL để tìm PASS.
5. Commit batch nguyên tử sau hai review PASS; prefix phải liên tục, còn khớp nguồn/revision. Diagnostics không có quyền approval/xuất bản.

Wave tự co nếu prompt vượt ngân sách, không cắt nguồn. Bản 2.1 cho hai reviewer chạy đồng thời; không tăng bốn translator và không dịch gối wave tiếp trong lúc review. Reviewer lỗi kỹ thuật không xóa kết quả peer đã xong; resume vẫn cần đủ hai review. Hiệu năng phải đo native riêng, không suy tăng tốc tuyến tính.

Checkpoint `JOB_DIR/checkpoints/chapter_NNNN.json` ghi tại mỗi 100 chương và cuối phạm vi. Đây là mốc đã commit, không gọi model thêm, không chờ Codex và không tự dừng xin duyệt lại. Antigravity đọc throughput/queue/suggestions để xử lý. Chỉ mở toàn sách khi đã được giao phạm vi đó.

Khi cần thêm/sửa quy ước, Antigravity đối chiếu ID/quote nguồn và bản approved, không tự lấy mọi suggestion làm canon. Giữ nguyên file canon đã được evidence cũ bind; lưu bản mới trong `BOOK_DIR/canon_revisions/` rồi dùng `launch --canon-file NEW_CANON` để chọn job revision mới và tái sử dụng prefix hợp lệ. Chỉ tạo job mới không cho phép ghi đè input cũ. Không sửa canon giữa run hoặc sửa approved bằng tìm–thay thế. Không thêm reviewer thứ ba hoặc HIGH toàn bộ chỉ để xây bảng tên.

## Phục hồi và resume

| Lỗi | Hành động |
|---|---|
| Timeout/partial/format | Journal, session mới, retry/fallback hữu hạn, chia output theo ID; không dùng partial |
| Sai nghĩa/thực thể | Native sửa đúng phạm vi, candidate mới và hai review mới |
| Thiếu context | Query nguyên văn trong slot hoặc nguồn trước; không bịa tên/tóm tắt thành canon |
| Quota/network | Backoff/circuit breaker, giảm concurrency, giữ nháp |
| Auth/quyền | Khôi phục account/quyền thật rồi retry-ready có lý do; không bật tool hoặc né bảo vệ |
| Native chặn nội dung | Giữ lý do/runtime; không đổi thành timeout để lách |
| Source/integrity thay đổi | Khôi phục input freeze hoặc job revision mới, không sửa hash |
| Tiến trình chết | Replay artifact native hoàn chỉnh nếu có; phần thiếu retry hữu hạn |

```powershell
# Resume selected_job do launch trả; job không khớp sẽ được tách revision mới.
.venv/Scripts/python.exe -X utf8 translate.py launch --book-dir BOOK_DIR --job SELECTED_JOB --through-chapter LAST_CHAPTER

# Chỉ sau hành động khôi phục điều kiện kỹ thuật thật.
.venv/Scripts/python.exe -X utf8 translate.py retry-ready --book-dir BOOK_DIR --job JOB_DIR --through-chapter LAST_CHAPTER --reason "Việc khôi phục đã thực hiện"
```

`run/watch` exit 2 khi còn việc chờ, không báo hoàn tất giả. Watch hữu hạn; Antigravity xử lý next_actions và tiếp tục, không bỏ chương. Code/canon/phạm vi đổi dùng job revision mới; prefix được kiểm và tái sử dụng. API `run_campaign()` cũng mặc định resilient. Approval legacy cần kế hoạch revision cách ly; không trộn manifest hoặc chỉnh file approved trực tiếp.

## Report, seal và xuất

```powershell
.venv/Scripts/python.exe -X utf8 translate.py report --book-dir BOOK_DIR --job JOB_DIR --through-chapter LAST_CHAPTER
.venv/Scripts/python.exe -X utf8 translate.py seal --book-dir BOOK_DIR --job JOB_DIR --through-chapter LAST_CHAPTER --out NEW_BUNDLE.zip

# Chỉ khi đủ toàn TOC và người dùng yêu cầu xuất.
.venv/Scripts/python.exe -X utf8 translate.py export --book-dir BOOK_DIR --job JOB_DIR --through-chapter BOOK_TOTAL --out approved_book.json
```

Report tách approved của book và approved trong job; throughput không cộng prefix. Worker time không phải wall; thinking không cộng lại vào total, usage thiếu để null. Hai native PASS không chứng minh không còn sạn: finding có ID/quote thật cần native sửa có revision trước xuất bản.

Dashboard/CSV tách `draft_elapsed_seconds` (đến nháp đầy đủ đầu tiên), `post_draft_elapsed_seconds` (nháp → duyệt, gồm review và sửa sau review), `elapsed_until_approval_seconds` (tổng). Đây là thời gian thực có thể gồm chờ/pause, không phải model latency. Bản cũ thiếu mốc để null/—. Record qua batch native đã commit mới mang nhãn NATIVE_BATCH_PASS; không đổi nhãn STRUCTURAL_PASS cũ thành native approval.

Seal giữ attempts/prompt/events, candidate/review, source/canon/code snapshot, proof prefix, raw archive và lineage của cả replacement chưa dùng trong pilot. Không ghi đè ZIP cũ. Manifest có đường dẫn gốc/hash; chuyển máy cần khôi phục mapping có kiểm chứng, không tự sửa proof/hash. Export mặc định tạo JSON approved; builder EPUB/PDF/AZW3 tương thích vẫn phải đọc gate. Hoàn tất pilot prefix không cấp quyền xuất toàn sách/phát hành.

## Git và kiểm thử

Chỉ commit code/test/docs. Không push truyện, OAuth account, runtime/bundle hoặc database. `.gitignore` giữ dữ liệu mới local; dữ liệu cũ đã tracked vẫn phải chọn file commit rõ, không `git add .`.

```powershell
.venv/Scripts/python.exe -X utf8 -m unittest discover -s tests -v
```

CI kiểm Windows/Linux và exporter khi có dependency. Test dùng fixture/mock, không gọi model thật. Runtime/benchmark local không phải dependency vận hành, không thêm Codex hoặc audit ngoài định kỳ.
