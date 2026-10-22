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

## Sửa một bản dịch thử đã có

`revise_book.py` dành cho hậu kiểm/sửa bản legacy dựa trên nguồn đầy đủ. Đây là tác vụ thật có gọi model, chỉ chạy khi người dùng yêu cầu sửa sách. Runner tạo snapshot nguồn, bản dịch và các tệp xuất cũ ở cấp trực tiếp; không snapshot đệ quy mọi revision/runtime đã có. Không sửa đè bản cũ hoặc sửa hash cũ để coi là đạt.

```powershell
$job='native_oauth/book_49736/repair_jobs/revision_YYYYMMDD'
python -m native_oauth.revise_book --book-dir native_oauth/book_49736 --job $job --snapshot-only
python -m native_oauth.revise_book --book-dir native_oauth/book_49736 --job $job --through-chapter 325 --reviewer-model gemini-3.8-flash-high --auditor-model gemini-3.8-flash-high --max-repairs 2
python -m native_oauth.revision_status --book-dir native_oauth/book_49736 --job $job --out audit/revision_status.json
```

Mỗi chương được sinh bằng một phiên native có toàn bộ nguồn, bản cũ là dữ liệu đối chiếu chưa xác minh. Khi cần sửa, model nhận bản nháp gần nhất để giữ những chỗ đã sửa đúng. Hai reviewer chạy tuần tự trong các phiên riêng: một đọc đối chiếu nguồn, một đọc tiếng Việt trước rồi kiểm lại nguồn. Lượt review không chia sẻ báo cáo của nhau. Promote tuần tự, context chương sau chỉ lấy revision đã duyệt của chương trước. Đổi cấu hình reviewer hoặc package khi resume sẽ kiểm lại các chương có cấu hình cũ; đổi chương trước làm các entry sau mất hiệu lực nhưng giữ artifact lịch sử.

Lượt repair không lặp lại toàn bộ baseline/recovery cũ khi đã có candidate gần nhất; vẫn luôn gửi đủ nguồn và findings. Việc này giảm ngữ cảnh trùng và tránh model quay lại cách diễn đạt sai ban đầu. Nếu native trả `status:BLOCKED`, giữ response gốc và lý do rồi dừng, không coi nó là candidate hoặc lỗi JSON để hỏi lại tới khi đạt.

Lỗi quote/schema của một reviewer được thử lại tối đa một lần trên cùng draft đóng băng; một kết luận FAIL hợp lệ không được thử lại cho đến khi thành PASS. Lỗi nghĩa/cấu trúc dẫn đến một bản sửa mới và hai lượt review mới, theo giới hạn `--max-repairs`. Source/canon/baseline thay đổi, native timeout, thiếu bằng chứng hoặc hết số lượt đều dừng tại chương lỗi. Chạy lại đúng job để tiếp tục; không bỏ qua chương bị chặn. Nếu cần nâng cấp code giữa chiến dịch, đặt `restart_requested.json` trong job để runner dừng trước chương tiếp theo; lưu/xóa yêu cầu này sau khi đã xác nhận runner thoát rồi resume.

`recover_missing.py --book-dir ... --job ... --chapters 239 248 299 306 310 318` chỉ sinh nháp cho các ID thật sự thiếu. Nó đối chiếu từng `raw_zh`, hash baseline và nguồn hiện tại; trùng/lệch ID không được tự sửa. Các phần nhỏ có runtime riêng, tối đa một lần sửa lỗi cấu trúc. Đầu ra `RECOVERY_PROPOSAL_UNREVIEWED` chỉ là dữ liệu đối chiếu cho lượt sửa toàn chương; không được ghép vào bản xuất để thay thế review. Báo cáo `revision_status.py` kiểm lại nguồn/bản cũ/snapshot, provenance từng nháp và các approval trong manifest; đếm nháp phục hồi riêng với chương đã duyệt.

Có thể bổ sung phản hồi biên tập trong `JOB/diagnostics/chapter_NNNN.json`: `source_hash`, `comparison_file`, `comparison_sha256`, `findings:[{id,source_quote,target_quote,reason}]`. File đối chiếu phải thuộc archive approved của sách hoặc baseline bản cũ; hai quote phải khớp đúng cùng ID nguồn–đích. Phản hồi được đóng băng cùng package và chỉ là gợi ý cần kiểm lại trên nguồn, không phải approval hay sự thật mới. Thêm/sửa phản hồi làm package thay đổi nên phải dịch/review lại; một lỗi đã được sửa không cần sửa thêm. Đây là dữ liệu biên tập tùy chọn trong Antigravity, không cần ứng dụng duyệt ngoài.

Dữ liệu so sánh legacy chỉ giữ các row có cả ID và `raw_zh` khớp nguyên văn nguồn hiện tại. Chuẩn hóa/chèn tiêu đề có thể làm lệch cả dãy ID dù thân bài vẫn đủ; không ghép bản dịch cũ theo ID đó, không tự sửa hash hoặc renumber bản cũ. Model nhận đủ nguồn để dịch lại. Báo cáo thay đổi đánh dấu `NO_EXACT_SOURCE_MATCH` khi không có đối chiếu đáng tin ở cùng ID; trạng thái này không chứng minh mất thân bài.

Nếu nguồn v1 chứa cả tiêu đề metadata `.name` và tiêu đề thật đầu `.content` khác nhau, dùng snapshot đọc DOM chỉ của heading trong `JOB/source_heading_checks/chapter_NNNN.dom.json`. Snapshot ghi `method:read_only_browser_dom`, hai selector, `chapter`, URL, `metadata_title`, `article_heading`, `article_heading_html`, và thời điểm quan sát. Không gọi snapshot nhỏ này là raw HTML toàn trang. Hai heading phải khớp đúng hai ID đầu và cùng số chương; snapshot được hash và bind trước review. Cả hai reviewer phải trả `title_ownership_checked:true`. Mọi ID vẫn được dịch/kiểm đầy đủ; renderer dùng heading bài thật, giữ lời tác giả và ký hiệu như `^`, không in metadata bị cắt thêm vào thân bài. Sửa snapshot/selection sau review làm gate chặn. Giữ snapshot cùng runtime, không ghi đè hoặc xóa sau duyệt. Nguồn v2 đã tái dựng từ raw `.content` dùng heading bài tại ID đầu, không ép nó bằng metadata TOC có thể bị cắt.

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
- Neo nghĩa chỉ trích cue thật từ nguồn: thời lượng, quan hệ chưa thành, góc nhìn/mức chắc chắn, âm lượng, số lượng và một số ngữ cảnh chuyên môn. Không tự thay chữ. Khóa cứng chỉ dành cho tên nhân vật đã biên tập; từ điển nghĩa chung là gợi ý để tránh một cách dịch sai bị ép lặp suốt sách.

## Nguồn, context và dữ liệu đầu ra

- `sources/`: nguồn có ID/hash; schema v2 giữ raw HTML bất biến, raw hash và mapping từng đoạn. Nguồn/cache v2 phải tái dựng được từ raw; đổi parser tạo revision nguồn mới và giữ history. Nguồn v1 cũ được giữ để audit, không tự nâng cấp bằng sửa hash. Draft không được ghi ngược thành sự kiện nguồn.
- `drafts/`: TXT + alignment JSON + receipt đủ cấu trúc/runtime. Trạng thái này chưa có quyền xuất sách.
- `native_review_jobs/`: inputs đóng băng, workspace reviewer riêng, runtime, QA và evidence. Khi gate chặn, xem `state.json`/`qa.json`; không xóa dòng khó hoặc ghi PASS bằng tay.
- `approved/chuong_NNNN/REVISION/`: evidence/sidecar/TXT/receipt bất biến được promote sau gate. `approved/manifest.json` là commit point nguyên tử dưới OS lock; sửa revision chương trước vô hiệu các entry phía sau, không xóa artifact cũ. Chương sau cần evidence chương trước đã đạt. Context lấy tối đa 24 row / 6.000 ký tự nguồn+đích đã duyệt, ưu tiên giới thiệu đầu và đề cập gần; không tóm tắt AI thành sự thật. Bắt buộc giữ quote giới thiệu mà vượt ngân sách thì dừng để xử lý.
- `build_ebooks.py` của 49736 chỉ đọc manifest duyệt liên tục và xác minh evidence/hash trước render; xuất vào `dist/MANIFEST_HASH/EXPORT_ID/`. Đọc lại EPUB để đối chiếu title/thứ tự/mọi đoạn; PDF kiểm bookmark và token coverage, AZW3 cần Calibre chuyển ngược EPUB để kiểm. Chỉ cấp `publication.json` khi mọi định dạng đã chọn đạt và manifest vẫn khớp. Dùng `--formats pdf epub` nếu chưa có Calibre. PDF hiện yêu cầu font Times New Roman trên Windows; kiểm text không thay kiểm bố cục bằng render/xem trang. Bản cũ trong `output_dich/` hoặc `dist/` không tự được coi đã duyệt.

Dữ liệu approval hiện gắn với các file nguồn/canon/runtime local. Giữ các workspace bằng chứng khi sao lưu; chỉ copy TXT hoặc riêng sidecar không đủ để validate. Repository chứa code và kiểm thử; các workspace sinh mới không tự đưa vào Git. Chuyển máy cần kế hoạch di chuyển bằng chứng và kiểm chứng đường dẫn, không tự đổi identity/hash để hợp thức hóa.

## Điều phối, hiển thị và hồi phục

SessionMonitor hiển thị tên/genre/chương/range/wave, số từ/đoạn, worker và trạng thái các giai đoạn trong session Antigravity. Hoàn tất công việc của worker không đồng nghĩa approved. Các wave dịch tạo draft; bước nghỉ quota không phải calibration nội dung.

Các stage JSON truyền nguồn/context qua stdin stream-json của native CLI, tránh giới hạn command line Windows. Stdin là tệp NDJSON hữu hạn có EOF rõ ràng; không giữ pipe ghi giữa các worker. Chúng yêu cầu response JSON đầy đủ và không gọi công cụ/shell; không thay cấu hình quyền Antigravity. Host lưu nguyên response, đối chiếu nó với events/runtime và mới thêm provenance. Không vá JSON sai hoặc gán exit code thành công cho tiến trình bị dừng. Dashboard gắn với conversation id quan sát từ init thật; đồng bộ tối đa sáu session gần nhất, không đoán session từ thời gian sửa thư mục. Workspace repair/approved và tiến độ sinh mới ở local, cần sao lưu cùng runtime; không tự đẩy dữ liệu chưa hoàn tất lên Git.

Một số lượt đã kết thúc model nhưng CLI không thoát. Riêng route JSON không-tools, runner có thể đóng tiến trình sau ít nhất 10 giây nếu thấy đúng một init/result cùng model/session, response cuối `DONE`, result `SUCCESS`, JSON object đầy đủ và không có tool, denied action, marker partial hay finish reason bị cắt. Trạng thái `COMPLETED_CLI_CLEANUP` giữ **mã thoát thật**, hash events/response/stdin và thời gian chờ; provenance kiểm lại toàn bộ chúng cùng tệp `input.jsonl`. Đây chỉ xác nhận generation đã kết thúc, không duyệt nội dung: đủ ID, quote, hai reviewer và manifest vẫn bắt buộc. Nonzero không có proof này vẫn ERROR; runtime TIMEOUT cũ không được sửa trạng thái để dùng lại. Phải giữ stdin cùng workspace khi sao lưu.

Route batch manifest tổng quát trong `BATCH_WORKFLOW.md` vẫn là đường thử nghiệm source-frozen, không tự publish. Đường theo sách đã có review/promote riêng như trên. Nếu review phát hiện lỗi, sửa cơ chế nguồn/context/canon hoặc chạy lại scene/chương bằng runner; không để công cụ regex tự sửa nghĩa. `pipeline_native.py` có vòng sinh lại bounded; review command theo sách dừng khi lỗi để Antigravity xử lý/rerun và kiểm lại.

UrbanAuditor là triage chỉ đọc. Polisher chỉ tạo bản nháp đề xuất mới; mọi sửa chữ phải được review lại trước approved. Runtime partial/timeout hoặc owned IDs thiếu/rỗng bị chặn trên cả generation và resume. Candidate phải trùng kết quả cleanup định dạng của response generation; init/result/model/session được kiểm từ events.jsonl. Mỗi lượt generation có runtime riêng để giữ nguyên bằng chứng revision cũ. OS lock tự nhả khi tiến trình chết; không cần xóa claim để chạy lại.

## Kiểm chứng trước sử dụng

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -X utf8 audit/replay_semantic_context_20261022.py
```

Test sử dụng fixture/mock không gọi model. Lượt sửa native thực tế ngày 22/10/2026 đã chỉ ra thêm lỗi nghĩa và điểm mù reviewer; tình trạng chiến dịch 325 chương xem `audit/live_native_repair_20261022.md` và manifest local hiện hành. Không suy tỷ lệ dịch đúng từ số test hoặc số đoạn PASS, không dùng mẫu đã tác động prompt làm heldout. Kết quả pilot lịch sử nằm trong audit/benchmark, không là phụ thuộc của workflow.
