# Vì sao pipeline mất đoạn và vẫn báo thành công?

## Nguyên nhân đã xác nhận

Cả sáu cảnh tương ứng với sáu chương thiếu đều có đúng diagnostic:

```text
[agy] print timeout after 2m30s with turn in progress; returning partial output
```

| Chương / scene | Số đoạn scene phải dịch | Dòng tagged thực trả | Thời gian wrapper |
|---|---:|---:|---:|
| 239 / 2 | 51 | 36 | 153,80 s |
| 248 / 1 | 54 | 41 | 154,81 s |
| 299 / 1 | 85 | 13 | 153,29 s |
| 306 / 1 | 98 | 49 | 154,80 s |
| 310 / 2 | 82 | 39 | 154,21 s |
| 318 / 2 | 124 | 49 | 154,30 s |

Nguồn chứng cứ: `native_oauth/book_49736/runs/chapter_NNNN/scene_N/runtime/{diagnostics.txt,events.jsonl,runtime.json}`. Bản runtime cũ ghi SUCCESS/exit 0 dù lượt sinh vẫn ACTIVE. Đây là timeout ở chế độ print của CLI, không có bằng chứng trong các diagnostic này để quy thành quota, model không biết dịch hay thiếu nguồn crawl.

Runner cũ chia mọi chương thành đúng hai nửa, không xét lượng chữ hoặc khối lượng output. Chương 318 có 247 đoạn nhưng vẫn chỉ chia hai request. Hạn 150 giây bao gồm cả xử lý lượt agent; ví dụ cảnh lỗi 239/2 báo 31.490 input token và 5.117 thinking token. Độ trễ/overhead có thể góp phần, nhưng chưa có phép đo live để phân rã thời gian hoặc quy toàn bộ nguyên nhân cho prompt/model. Bằng chứng chắc chắn là hết hạn trong lúc đang sinh.

## Chuỗi biến partial thành “hoàn tất”

1. **Transport đánh đồng SUCCESS với sinh xong.** `run_agy.py` cũ không đọc diagnostic timeout. Nó còn có đường thấy substring result trong log rồi terminate tiến trình và tự gán exit 0.
2. **Runner không dùng FAIL như một điều kiện chặn.** Kết quả thiếu đoạn qua QualityGate bị báo FAIL nhưng vòng chương vẫn tiếp tục lưu.
3. **Bộ sửa tạo đoạn rỗng cho các ID thiếu.** `identify_repair_targets` đưa MISSING_PARAGRAPH vào nhóm sửa; vòng sửa ghi lại `""` dưới các ID đó. Dictionary đủ khóa nên `len(chapter_paras)` bằng số nguồn. Bộ xuất bỏ chuỗi rỗng, thành ra JSON khai 170/170 nhưng chỉ chứa 98 bản ghi.
4. **Audit so hai số tự khai.** Nó không đọc source dù đã dựng đường dẫn, không đếm bản ghi thật, không kiểm từng ID.
5. **Cache và dashboard dùng dấu hiệu yếu.** Có TXT/JSON thì skip; số chương lớn nhất đã active bị dùng làm % hoàn thành. Lỗi đã lưu tiếp tục được coi là đã làm xong.
6. **Publisher chỉ đọc TXT.** Nó không đòi coverage hoặc review đã duyệt, nên câu cụt đi thẳng vào EPUB.

Vì vậy tăng timeout, đổi model hoặc dịch bù chỉ xử lý được một lần biểu hiện. Điều cần sửa là hợp đồng giữa các bước: complete transport, complete coverage, valid draft, reviewed candidate và published edition là các trạng thái khác nhau.

## Vì sao test xanh không bắt được?

Suite trước chủ yếu kiểm module và ví dụ chuẩn. Không có regression cho diagnostic partial + SUCCESS, runner nhận FAIL, lỗ trống được chèn chuỗi rỗng, hoặc export từ dữ liệu thiếu. Một test monitor còn kỳ vọng gọi hoàn tất riêng chương 25 thì đã làm xong 25/50 chương. Test self-healing kỳ vọng điểm heuristic >= 0.98 tự cho phép xuất bản. Hai kỳ vọng này đã được sửa và có các ca đối nghịch để giữ đúng nghĩa trạng thái.

Không thể lấy tỷ lệ test qua làm tỷ lệ dịch đúng. Heuristic số từ, từ phủ định và regex không chứng minh được ai giết ai: ca đảo Trương Tam/Lý Tứ vẫn có thể không bị heuristic phát hiện. Điểm đó hiện không còn được dùng để cấp quyền xuất bản.

## Đã sửa trong working tree

- **Transport:** phân loại PARTIAL_TIMEOUT/TIMEOUT từ diagnostic và deadline; giữ partial làm chứng cứ; kiểm status/exit/model thực; chờ tiến trình kết thúc, không tự tạo exit 0. Bỏ fallback API âm thầm ở runner 49736.
- **Coverage:** từ chối đoạn rỗng, ID trùng/sai thứ tự và output ngoài schema; giữ dòng tiếp của đoạn nhiều dòng. Bộ sửa không tạo đoạn thay thế rỗng và không giảm expected theo số đoạn còn sống.
- **Một bộ điều phối chương dùng chung:** cả bốn batch/wujian entrypoint dùng `chapter_runner.py`. Mỗi scene tối đa 20 đoạn và 3.200 ký tự nguồn; không cắt ngầm một đoạn quá dài. Timeout/thiếu coverage thì bỏ cả attempt đó và thử hai nửa nhỏ hơn, tối đa hai tầng, tối đa 32 lần gọi cho một chương. FAIL nội dung không được sửa bằng phép đệm. Hết giới hạn thì BLOCKED.
- **Đầu ra và cache:** chỉ ghi draft đầy đủ vào `book_*/drafts/`, TXT/JSON từ cùng alignment, atomic từng file và receipt ghi cuối. Receipt khóa source/candidate/text/pipeline/lore/model và hash runtime từng scene. Có claim chống hai worker cùng nhận một chương. Cache legacy không được dùng; nguồn/code/lore/runtime thay đổi thì dừng hoặc buộc một run mới. Revision/receipt cũ được giữ khi chạy lại.
- **Nguồn và context:** crawler kiểm UTF-8 strict, redirect, tên truyện/title và raw cache hash. Không thêm một tiêu đề để che trang sai; khác biệt dấu câu được chuẩn hóa khi đối chiếu title. Genre và glossary truyền tường minh. Ngữ cảnh qua chương dùng vài đoạn nguồn gốc đã khóa hash; không lấy TXT chưa duyệt làm sự kiện chuẩn. Đây chưa phải giải coreference hay memory toàn truyện.
- **Audit/publisher:** lấy expected từ source, actual từ alignment thật; kiểm raw/ID/hash/TXT. Export từ chối thiếu chương và yêu cầu bundle review nguồn–đích hợp lệ bằng cổng semantic chung, đúng bản cuối. Kiểm cấu trúc không được coi là duyệt nghĩa.
- **Các đường phụ:** import bản dịch chỉ tạo draft; polish tạo đề xuất mới trong `polished_drafts/`, cập nhật cả alignment và TXT, không sửa bản sản xuất. Wave báo lỗi khi chương BLOCKED. Status tracker đọc draft có receipt đã xác minh, không đếm TXT cũ.
- **Monitor:** % dựa vào tập chương thực đã qua kiểm cấu trúc; FAILED không cộng hoàn tất; ghi lặp cùng chương không cộng từ hai lần. State v2 có lock liên tiến trình và atomic write. Không suy conversation đang dùng từ mtime thư mục; đặt `ANTIGRAVITY_ARTIFACT_DIR` hoặc `ANTIGRAVITY_CONVERSATION_ID` để gắn đúng phiên. Không tự công nhận tổng đếm v1 cũ.
- **Self-healing:** chỉ là triage/repair heuristic. Không được tự đặt `publication_approved=True` từ điểm tự chấm; phải qua review nguồn–đích riêng.

## Cách xác minh và giới hạn

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests
.\.venv\Scripts\python.exe -X utf8 audit/reproduce_pipeline_review_20261021.py
```

Regression mới đọc lại sáu diagnostic thật, thử runner FAIL, cache có TXT lỗi, source đổi giữa lượt sinh, runtime bị sửa, ID trùng/rỗng, timeout rồi chia lại, audit metadata giả, publisher thiếu review, tiến độ và polish đồng bộ. Mọi model call đều mock hoặc dùng log đã có. Tests dùng temp; không tạo phiên dịch thật.

Kết quả xác minh working tree: **165/165 tests PASS** (23 ca mới so với 142 ca ban đầu), 24 module Python đã kiểm cú pháp. `pipeline_root_cause_20261021.evidence.json` lưu diagnostic/số đoạn/state ACTIVE của sáu cảnh và hash mã đã kiểm; `pipeline_review_current.evidence.json` lưu các phép tái hiện hiện tại. Dữ liệu nguồn, output và dist được kiểm bằng Git diff: không thay đổi.

`post_fix_structural_audit_20261021.json` đếm lại đúng 31.034 đoạn nguồn và 30.744 bản ghi thực, phát hiện 29 chương lệch count. Nó cũng chặn đồng bộ cho bản xuất legacy chưa khớp canonical TXT/hash. Không diễn giải số chương bị chặn thành số chương sai nghĩa: 23 count mismatch là title bổ sung, nhiều TXT chỉ khác bố trí header, và evidence review xuất bản vẫn chưa có. Không ghi đè báo cáo cũ để che sự khác nhau giữa hai cách kiểm.

Chưa gọi live để đo hiệu năng, quota, token hoặc chất lượng sau đổi scene size. Chưa phục hồi/chỉnh 325 chương hay sách cũ và chưa push GitHub. Bằng chứng trước sửa được giữ nguyên. Không thể dùng số test hoặc bản sửa này để cam kết 100% đúng nghĩa.

Phần còn cần đánh giá chất lượng: reviewer song ngữ độc lập cho chủ thể/đối tượng, phủ định, đơn vị, đại từ và thêm/bớt ý; critic tiếng Việt; kiểm biên và context đã duyệt; benchmark trên truyện/cảnh chưa dùng khi viết prompt. Có thể dùng AI cho các vai trò đó, không đẩy việc đọc chữ Hán sang người dùng. Runner mới dừng ở draft khi chưa có evidence; bước tạo/gắn evidence phải do điều phối viên đáng tin thực hiện theo `semantic_gate.py`/`codex_gate.py` hiện có, không tự điền PASS.

225 hash nguồn lệch và 23 trường hợp thêm title là vấn đề provenance/migration riêng. Chưa xác định được đầy đủ thao tác lịch sử tạo mọi mismatch, nên không quy chúng thành mất nội dung. Khi phục hồi phải đối chiếu snapshot/ID, không đổi hash cho khớp để bỏ qua kiểm tra.

Trước khi mở rộng: chạy pilot nhỏ có runtime/usage và review thật; đo tỷ lệ timeout/quarantine/lỗi còn lọt. Chỉ đóng lại sách sau khi nội dung phục hồi và bằng chứng khớp toàn bộ bản xuất.
