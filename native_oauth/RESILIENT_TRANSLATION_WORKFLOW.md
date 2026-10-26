# Luồng dịch có phục hồi — 26/10/2026

Luồng vận hành độc lập trong Antigravity, dùng native OAuth/CLI. Không có dependency vào một phiên Codex hoặc dịch vụ audit ngoài. Codex đã kiểm thử code offline; chất lượng/tốc độ thật của giao thức mới cần đo ở pilot trước khi mở rộng toàn sách.

## Cấu hình mặc định

- Translator MEDIUM; tối đa bốn worker dịch, cửa sổ tối đa năm chương.
- Hai reviewer MEDIUM trong hai session độc lập, chạy đồng thời từ bản 2.1, tối đa hai request review và chịu giới hạn health. Cả hai đọc đủ nguồn–đích cả wave; reviewer văn học kiêm kiểm continuity. `--review-workers 1` chọn tuần tự. Không có wave-auditor thứ ba mặc định.
- HIGH là fallback thật khi lỗi phản hồi/timeout và là model sửa tập trung. Runtime lưu model thực tế; không tự khai identity hoặc ghi LOW/MEDIUM cho một lượt thực chất dùng HIGH.
- Timeout đầu 300 giây, lần tiếp theo tối đa 450 giây; mọi runtime vẫn chịu giới hạn hữu hạn. Không đặt timeout vô hạn.
- Wave quá ngân sách prompt sẽ tự thu nhỏ; không cắt nguồn. Khi lỗi nguồn/prefix, chỉ tạo tối đa ba cửa sổ nháp phía trước rồi chờ phục hồi, tránh dịch mù cả phần còn lại.
- Nguồn, canon, model/policy và code có snapshot; đổi cấu hình/code/canon phải dùng revision job mới, giữ job cũ. `translate.py`, API `run_campaign()` và CLI `revise_book.py` đều mặc định resilient; route cũ chỉ dùng khi chỉ định rõ.

## Gate batch mới

### Policy v2 — tránh chặn sai do tên riêng, Unicode và góp ý văn phong

Runner mới dùng `resilient-content-2` và `resilient-review-2`. Nguồn/ID/hash, coverage, bản dịch rỗng, ký tự lỗi và chữ Hán chưa dịch vẫn là lỗi cứng. Việc thiếu chuỗi tên Việt ở một đoạn trở thành `review_obligations` có nguồn–đích: cả hai reviewer phải trả `semantic_obligations_checked` đủ slot được giao. Đại từ/bí danh đúng chủ thể được chấp nhận; sai người, sai tên hoặc mất danh tính vẫn phải FAIL và sửa native. Không tự duyệt chỉ vì có từ “hắn”. Unicode NFC/NFD, chữ hoa và khoảng trắng được chuẩn hóa để **so sánh**, không sửa output native hoặc bỏ dấu tiếng Việt.

Góp ý văn phong không bắt buộc nằm trong `suggestions`, được giữ trong evidence/report và không gây tái sinh bản đúng. Sai nghĩa, phủ định, số lượng, luật chơi hoặc canon bắt buộc có phạm vi vẫn ở `issues` và chặn approval. `needs_context` phải có truy vấn nguyên văn trong slot lỗi hoặc nguồn trước đã cung cấp; không lấy tên từ tương lai hoặc tự tạo tên.

Trường hợp nguyên tác cố ý nói về một chữ/chuỗi chữ Hán: translator có thể khai `source_script_quotes:[{id,quote,reason}]`, quote 1–32 ký tự phải có nguyên văn ở cả nguồn và đích, gắn đúng ID. Mọi chữ Hán không thuộc quote khai báo vẫn bị chặn. Quote khai báo trở thành nghĩa vụ cho cả hai reviewer; không phải whitelist hoặc PASS tự động. Host chỉ ghép annotation native theo ownership, không xóa chữ Hán. Ký hiệu quẻ Dịch không bị coi nhầm là từ Hán.

Canon mặc định mới của Siwangyouxi là `siwangyouxi_translation_canon_v2.json`: làm rõ tên Lâm Ngự so với đại từ hắn, thống nhất tên đạo cụ Máy phát hiện nói dối và xưng trẫm chỉ cho lời Hoàng Đế trong đúng phạm vi. Canon v1 giữ nguyên để evidence cũ không bị mất hiệu lực. Các batch v1 vẫn được kiểm bằng policy v1; không nới hồi tố gate cũ.

Sau cập nhật code/canon, tạo **job revision mới**. Có thể tiếp tục trên book đã có prefix 20 chương được duyệt: runner xác minh prefix rồi bắt đầu từ 21; không cần dịch lại 20 chương hoặc đổi nhãn runtime cũ thành v2. Nếu tăng `through-chapter`, cũng dùng job mới theo configuration freeze. ZIP mới chứa cả dependency native của prefix thuộc job trước và file nguồn gốc trong recovery lineage. Không ghi đè ZIP đã seal.

Report mới tách `job_approved_chapters`, `job_approved_source_characters` và `approved_in_this_job` khỏi tổng approved của book. Công suất chỉ lấy ký tự được duyệt trong job này chia wall time của job, không cộng prefix để làm tốc độ cao giả; diagnostic có scope riêng và không được tính là chương approved mới.

`resilient_gate.py` và `resilient_publication.py` dùng schema riêng. Reviewer nhận catalog đầy đủ theo thứ tự gồm slot số nguyên, chapter, ID nguồn gốc, nguyên văn Trung và Việt. Mỗi row trả `[slot,"PASS"|"FAIL"]`; slot tham chiếu nguyên đoạn nguồn–đích, không phải quote do model chép lại. Issue FAIL phải có slot, `source_ref:0`, `target_ref:0`, kind và reason. Gate chặn thiếu/trùng/lệch coverage, PASS mâu thuẫn issues, model/session không hợp lệ và thay nguồn/revision/context.

Hai reviewer vẫn phải kiểm đủ tám chiều ngữ nghĩa, các chiều văn học, metadata tiêu đề, nguồn trước theo thời điểm và context Việt đã duyệt của predecessor. Cues phủ định/quan hệ/số lượng là gợi ý nguyên văn, không thay việc đọc cả đoạn. Chấp nhận cách diễn đạt Việt tương đương; không biến sở thích từ ngữ thành lỗi chặn. Canon ngôi kể chỉ áp dụng đúng người và ngôi kể, không regex thay toàn bộ đại từ hoặc ép lời thoại ta–ngươi.

Approval là **hai review native thật của batch**, không sao chép PASS thành nhiều review chương giả. Mọi component dịch phải replay đúng JSON native ban đầu. Khi chia nhỏ/sửa, host chỉ ghép các row native được khai ownership, không tự dịch hoặc xóa ký tự. Cùng ID ở nguồn revision khác được phân biệt bằng source/package hash; không ghép bản cũ chỉ theo ID.

Nguồn hiện hành và snapshot nguyên byte được giữ riêng; từng nguồn phục hồi có lineage tới hash nguồn cũ. `approved/resilient_manifest.json` chỉ được commit một lần sau khi cả wave cuối PASS, giữ ancestry theo thứ tự và context của predecessor thật. Export yêu cầu đủ range liên tục từ 1 và validate mọi batch. Không trộn manifest mới với approval legacy đã có; dùng sách/job cách ly khi kiểm thử.

## Đường xử lý lỗi

| Trường hợp | Phục hồi tự động | Trạng thái khi còn điều kiện ngoài cần xử lý |
|---|---|---|
| Timeout/partial/phản hồi rỗng | Giữ log, session mới, timeout có giới hạn, HIGH fallback; chia output dịch thành tối đa 35 đoạn rồi chia nhỏ tiếp với ID/neighbor context gốc | Journal ghi retry/action; không dùng partial làm bản dịch |
| JSON/coverage/ID review sai | Review compact bằng slot/ref; session mới; giảm coverage output xuống 60 rồi nhỏ hơn khi cần, vẫn gửi toàn wave nguồn–đích | Giữ yêu cầu, lỗi schema và artifact gốc, không sửa ID/verdict để lấy PASS |
| Lỗi cơ học có ID trong response đầy đủ | Giữ response/provenance gốc, giữ ownership phần đúng, HIGH chỉ sửa row lỗi; ghép xong vẫn kiểm đủ coverage và hai review | Không giữ partial hoặc response sai ID; không sửa text bằng host |
| Lỗi nghĩa từ reviewer | Native sửa đúng row, candidate revision mới và hai review mới; timeout sửa cũng chia nhỏ | Không hỏi lại cùng bản FAIL để lấy PASS; sửa không đổi text thì cần xử lý context/canon |
| Thiếu context | Reviewer có thể nêu `needs_context` + `context_query` nguyên văn; tìm nguồn trước chương hiện tại qua SQLite, xác minh ID/quote/hash, dịch/review revision mới | Cần bổ sung truy vấn hoặc nguồn có bằng chứng nếu tìm chưa đủ; không đoán sự thật |
| Transport lỗi liên tiếp | Circuit breaker sau ba lỗi, giảm concurrency, cooldown; tăng lại từ từ sau thành công | Chờ thời điểm retry, giữ nháp đã xong |
| Quota | Không spam model khác hoặc yêu cầu mới; giữ queue và backoff mặc định 10 phút | Sau các epoch hữu hạn, kiểm reset/quota rồi resume/retry-ready |
| Native auth/quyền truy cập | Ghi rõ loại lỗi, dừng các request liên quan, giữ nháp và approval trước | Khôi phục native account/quyền hợp lệ, ghi lý do `retry-ready`, không tự cấp quyền tool |
| Native báo chặn nội dung | Giữ nguyên lý do và runtime, phân biệt với timeout | Kiểm lý do/provider; không sửa nội dung để lách chặn |
| Nguồn/HTML/mapping lỗi | Lấy lại từ TOC đã biết hoặc alternate book identity đã xác minh; kiểm chapter/canonical/encoding/archive; lưu `effective_sources` mới | Nguồn cũ giữ nguyên; có file chờ replacement và hành động refetch/import rõ ràng |
| Tiến trình bị ngắt | Journal ghi trước mỗi call; replay artifact native hoàn chỉnh nếu đã có, còn lại retry fresh có giới hạn | Không đoán output partial hay thời gian đã mất |

Repair ngữ nghĩa giới hạn theo pass và có budget tích lũy; retry transport có epoch hữu hạn. Không có vòng hỏi lại vô hạn. Mỗi chương luôn có trạng thái QUEUED/DRAFT_READY/WAITING_SOURCE/RECOVERY_PENDING/APPROVED và hành động tiếp theo trong campaign. Điều kiện bên ngoài chưa khôi phục không thể được hứa là đã dịch; queue tiếp tục lưu việc cần làm, không bỏ chương hoặc báo hoàn tất giả.

## Nguồn đã phục hồi trong kiểm thử

Đã kiểm 2.115 nguồn offline. Ba nguồn 350/1608/1609 cũ không replay được và có dữ liệu obfuscation; đã lấy lại thành công từ alternate book `/read/644367/`, kiểm heading/chapter và archive, giữ nguyên nguồn cũ. Site yêu cầu một chuyển hướng trình duyệt có token do server cấp; adapter chỉ theo mẫu cùng origin có giới hạn, không chạy JavaScript tùy ý, không tự tạo token hoặc giải CAPTCHA/login.

Replacement hiện ở `audit/resilient_upgrade_20261026/source_preflight/effective_sources/`. Đây là artifact kiểm thử có thể import; workflow vẫn tự phục hồi được nguồn mà không cần thư mục Codex này.

Kiểm tra cả metadata tiêu đề đạt 2.115/2.115. Tám chương 1429, 1456–1461 và 1575 có số in trên trang lệch thứ tự TOC. Gate chỉ chấp nhận khi archive khớp tiêu đề, `toc_index`, URL `chapterNumber` và canonical cùng xác minh mapping; không sửa ID, nguồn hoặc số trong thân truyện. Packet và catalog review ghi riêng số in nguồn và số thứ tự xuất bản để reviewer kiểm đúng ngoại lệ.

```powershell
# OFFLINE — full-source preflight, tùy chọn dùng các replacement đã xác minh.
.venv/Scripts/python.exe -X utf8 -m native_oauth.resilient_translation preflight --book-dir native_oauth/book_siwangyouxi --job audit/resilient_source_check --through-chapter 2115 --source-recovery-dir audit/resilient_upgrade_20261026/source_preflight/effective_sources

# Cho phép network refetch khi cần: thêm --repair-sources vào preflight.
```

`source-recovery-dir` kiểm book/chapter và hash nguồn cũ chính xác, không chỉ tin tên file. Nguồn đã approved không bị thay tại chỗ. Import hoặc refetch nguồn mới chỉ thêm revision/HTML archive; không sửa bản truyện gốc.

## Chạy, phục hồi và bàn giao

Phải bind `ANTIGRAVITY_ARTIFACT_DIR` hoặc `ANTIGRAVITY_CONVERSATION_ID` theo phiên Antigravity hiện tại. SessionMonitor state nằm trong job riêng để không nhận nhầm tiến độ pilot cũ; badge/dashboard hiển thị đầu/cuối stage/chương/wave và lúc chờ retry. Bản dịch chỉ được đếm done sau approval batch.

```powershell
# LIVE — chạy pilot trên BOOK_DIR cách ly và job mới.
.venv/Scripts/python.exe -X utf8 -m native_oauth.resilient_translation watch --book-dir BOOK_DIR --job JOB_DIR --through-chapter 20 --workers 4 --watch-rounds 3

# Resume giữ nguyên BOOK_DIR/JOB_DIR và tham số. Không xóa job để chạy lại.
# Quota/auth đã được sửa thật: chỉ release request kỹ thuật, không xóa FAIL ngữ nghĩa.
.venv/Scripts/python.exe -X utf8 -m native_oauth.resilient_translation retry-ready --book-dir BOOK_DIR --job JOB_DIR --through-chapter 20 --reason "Mô tả việc khôi phục native account/quota đã thực hiện"

# Diagnostic nguồn ở xa; không tạo approval giả tiền tố 1.600+ chương.
.venv/Scripts/python.exe -X utf8 -m native_oauth.resilient_translation diagnose --book-dir BOOK_DIR --job DIAGNOSTIC_JOB --through-chapter 2115 --chapters 1622 1975 1978 --workers 4

# Bàn giao cả kết quả thành công lẫn queue cần xử lý.
.venv/Scripts/python.exe -X utf8 -m native_oauth.resilient_translation report --book-dir BOOK_DIR --job JOB_DIR --through-chapter 20
.venv/Scripts/python.exe -X utf8 -m native_oauth.resilient_translation seal --book-dir BOOK_DIR --job JOB_DIR --through-chapter 20 --out BUNDLE.zip

# Chỉ sau khi người dùng cho phép chạy toàn bộ và đủ approval:
.venv/Scripts/python.exe -X utf8 -m native_oauth.resilient_translation export --book-dir BOOK_DIR --job JOB_DIR --through-chapter 2115 --out approved_book.json
```

`run/watch` trả exit 2 khi còn việc chờ, không giả exit 0. `retry-ready` yêu cầu lý do và chỉ mở lại lỗi kỹ thuật sau hành động vận hành; không bỏ gate nguồn/integrity hoặc duyệt một bản FAIL. Khi code/canon đổi dùng job revision mới và giữ snapshot/evidence cũ.

Report phân biệt logical attempts, runtime records, lỗi giao thức, wall time của các invocation và tổng worker time. Usage thiếu là null, có tổng token biết được như cận dưới. Thinking không cộng thêm lần nữa vào total. Thời gian từng chương trên dashboard là elapsed tới approval gồm queue/pause, không gọi đó là latency model. ZIP lưu mọi attempt, source/context snapshot, candidate/component ownership, hai review, manifest, code snapshot, dashboard và hash; không ghi đè ZIP đã seal.

Mục tiêu hai ngày cho 5,25 triệu ký tự nguồn cần khoảng 109.300 ký tự **đã duyệt** mỗi giờ. Cấu trúc cơ sở giảm từ 16 xuống 7 native call/wave năm chương không lỗi, nhưng chưa có phép đo tốc độ thật mới để cam kết hai ngày. Hoàn tất pilot 20 chương và diagnostic trước; tiếp theo dùng checkpoint 100 chương trong chiến dịch, không tự mở cả 2.115 chương chỉ vì kiểm thử offline PASS.
