# Pipeline kiểm dịch có nguồn — 2026-10-13

> **Phạm vi mới nhất 22/10/2026:** workflow cào–dịch–review–sửa–xuất bản thuộc Antigravity; Codex kiểm tra chéo và bổ sung hệ thống. [ANTIGRAVITY_WORKFLOW.md](native_oauth/ANTIGRAVITY_WORKFLOW.md) là hướng dẫn định hướng hiện hành. Các yêu cầu Codex duyệt từng chương và route API bên dưới là bối cảnh/pilot cũ, không phải phụ thuộc sản xuất hiện tại.

> Yêu cầu mới về hàng loạt: [BATCH_WORKFLOW](native_oauth/BATCH_WORKFLOW.md). GPT dùng để chấm route/mẫu, không phải vá câu sau mỗi chương. [Kết quả low/medium và các giới hạn](native_oauth/BATCH_RESULT_20261013.md) thay cho việc suy rộng từ chương 1 đã sửa.

> Cập nhật sau thử OAuth và yêu cầu review bằng GPT Codex: dùng [native_oauth/WORKFLOW.md](native_oauth/WORKFLOW.md). Chương 1 đã có bản duyệt sau hai GPT session độc lập, xem [kết quả hiện tại](native_oauth/AUDIT_RESULT_20261013.md). Các thử API/BLOCKED bên dưới là lịch sử; không thay thế kết quả mới. Chính sách API vẫn yêu cầu model khác nhau; luồng Codex dùng hai session GPT độc lập, không tự khai ba model khác nhau.

## Kết quả và giới hạn đã kiểm

- Audit mẫu xác nhận lỗi nghĩa ở chương 1, 32, 70 và lệch thuật ngữ liên chương. Xem `audit/semantic_sample_review.md`.
- Kiểm kê 81 TXT cũ: 50 chương có prepared source ghép đối chiếu, 57 chương có cờ triage (bao gồm thiếu nguồn). **Cờ không đồng nghĩa lỗi xác nhận; không chương cũ nào được tự coi là PASS.**
- Đã tải trực tiếp trang chương 1 Piaotia, lưu HTML và tách 192 đoạn / 6.032 ký tự Trung. Website hiện không có `#content`; parser đã được sửa theo biên `toplink`/`bottomlink`, giữ văn bản anchor, không xóa đoạn chỉ vì có từ khóa điều hướng. Không chứng nhận nguyên trang web là đầy đủ so với bản tác giả.
- 8 ca song ngữ khóa cố định: `audit/semantic_regression_cases.json`. Bản sửa chỉ là đoạn trích, không thay thế cả chương.
- Live model diagnostic: Gemini 3.8 Flash 16/16 phán định đúng; Gemini 3.6 Flash 14/16, bỏ lọt ranh giới >= và thể thức 1v1; Gemini 3.7 Flash HTTP 503, chưa kết luận chất lượng. Tổng token ở hai phản hồi thành công: 4.703. Đây là mẫu rất nhỏ, không phải độ chính xác của toàn truyện.
- Thử end-to-end đã tạo draft nhưng chưa hoàn tất hai review: Gemini 2.5 Pro trả 404; lần thử với Gemini 3.6 Flash trả 503 sau retry. `audit/pilot_runs/` giữ draft, usage, state BLOCKED. **Chưa có chương sản xuất được chứng nhận qua luồng live mới.**
- Danh sách model API trong `audit/model_discovery.json` chỉ chứng minh model được liệt kê. Khả năng sinh nội dung phải kiểm bằng cuộc gọi thực tế; model trong Antigravity IDE phải đọc từ phiên IDE, không suy ra từ API hay tài liệu cũ.

## Chuẩn ngữ nghĩa

Nguyên văn Trung là chuẩn cao nhất. Không ép truyện tuân theo bản thô regex hoặc một lời tóm tắt AI. Giữ người hành động, người nói, suy nghĩ nội tâm/lời nói, phủ định, khả năng/chắc chắn, số và đơn vị, ranh giới >=/>, thứ tự thời gian, nhân quả và quan hệ nhân vật. Văn phong được làm tự nhiên nhưng không thêm dữ kiện như “mua quà”, “bán mạng”, “đẫm máu”.

`novel_lore.json` đã sửa 修仙贷/法力贷 thành “khoản vay tu tiên”/“khoản vay pháp lực”; thêm khóa 周天翊 theo nguồn; bỏ lời chú thích “(Black Myth)” không có trong từ nguồn. Các bản dịch cũ giữ nguyên; việc đổi chuẩn cần audit lại các chương có thuật ngữ đó. Pháp Giải tiếp tục là canonical của 法赛. Không tự thống nhất đại từ chỉ bằng replace, và không tự coi “cân” Trung Quốc là kg.

## Luồng bắt buộc

1. Lưu source package với id cho từng đoạn, source URL, glossary và context; hash khóa toàn bộ nội dung. Crawler lưu HTML nguyên byte cùng encoding, URL, thời điểm tải và SHA-256 trong `source_archive/`.
2. Translator xuất JSON đúng mỗi id một đoạn, không gộp hoặc bỏ đoạn. Giữ source nguyên vẹn, không truyền bản “AST” giả làm chuẩn.
3. Kiểm cơ học: id/thứ tự/phủ đoạn, rỗng, chữ Hán sót, glossary. Số viết chữ, chuyển đổi đơn vị, đại từ và phủ định do reviewer đối chiếu, không tuyên bố regex kiểm được nghĩa.
4. Reviewer và auditor đọc nguồn + draft + context trong hai lượt độc lập; không xem nhận xét của nhau. Mỗi lượt có đủ đoạn, trích nguồn/đích, lý do và tám chiều kiểm tra.
5. FAIL/BLOCKED thì sửa, rồi cả hai reviewer kiểm lại draft mới. Hash review cũ không hợp lệ cho draft đã sửa. Mặc định một vòng sửa, tối đa hai; tối đa 9 lượt sinh thành công trong một run, không tính retry HTTP. Retry còn phụ thuộc `settings.max_retries` và số model/key cấu hình; nên đặt số model/key dự phòng nhỏ.
6. Chỉ PASS mới tạo TXT, evidence và publication manifest trong `approved_output/`. Bản cũ trong `output_dich/` không được dùng làm cache hoàn tất. TXT ghi atomic; `publication.json` xác nhận đã ghi đủ artifact.

PASS là hai model đã đồng ý và kiểm cơ học đạt; vẫn có rủi ro model cùng bỏ lọt lỗi. Người biên tập cần audit mẫu định kỳ, đặc biệt chương quan trọng và những trường hợp nguồn nhiễu/đơn vị/xưng hô chưa rõ.

## Context xuyên chương

Chương sau cần context của chương trước đã PASS. Context chứa sự kiện bằng đúng đoạn dịch đã duyệt, quote nguyên văn, id nguồn, hash evidence và hash bản chương trước; không nhận lời tóm tắt bịa chỉ vì nó kèm một quote có thật.

```powershell
python semantic_gate.py context --evidence approved_output/chapter_0001_HASH.evidence.json --out context_0002.json
python prepare_for_agent.py --chap 2 --context context_0002.json
```

Các fact trước đó được mang tiếp để giữ continuity. Đến khi package vượt 120.000 ký tự, API bị chặn trước sinh nội dung; không tự cắt hay tóm tắt. Điều phối viên có thể chọn giữ các fact quan trọng bằng cách bỏ nguyên row, vẫn giữ quote/statement đã duyệt và evidence tương ứng. Không sửa nội dung statement. Đây là lựa chọn editorial cần đối chiếu toàn chuỗi; tên, quan hệ, giọng kể, timeline và sự kiện đang mở phải được giữ. Sau khi chuyển máy cần cập nhật đường dẫn evidence và hash package; không thể tiếp tục bằng context thiếu artifact.

Chương 32–81 cũ chưa có chuỗi PASS: phải audit/backfill từ đầu hoặc cung cấp chuỗi evidence đã kiểm. Một chương có nguồn local không tự chứng minh continuity của 31 chương trước.

## Native Antigravity — hướng dẫn API/native ban đầu

Không giả định tên model chỉ từ prompt. Điều phối viên ghi đúng model/session đã chọn, tạo translator/reviewer/auditor độc lập; policy hiện yêu cầu ba identity model khác nhau. `identity_basis: native_attestation` là thông tin điều phối viên ghi, không phải bằng chứng từ API. JSON tự khai không chống giả mạo; vận hành phải kiểm quyền sở hữu/session của worker.

```powershell
python prepare_for_agent.py --chap 1
# Hoặc dùng source package đã tải và lưu trong audit/live_source_chapter1.source.json
python semantic_gate.py review-prompt --package SOURCE.json --candidate draft.json --out review_prompt.txt
python semantic_gate.py validate --package SOURCE.json --candidate draft.json --review reviewer.json --review auditor.json --out qa.json --publish-dir approved_output
```

Prompt điều phối có thể sao chép:

> Đọc QUALITY_WORKFLOW.md. Dùng source package được chỉ định. Giao translator đọc file `.translator.txt` và xuất `draft.json`, đủ mỗi id một đoạn. Điều phối viên ghi identity model đã chọn vào `model`, ghi `identity_basis: native_attestation`. Chạy kiểm cơ học bằng `review-prompt`; nếu lỗi phải sửa trước. Giao reviewer và auditor khác model, phiên context độc lập, cùng đọc `review_prompt.txt`, không xem nhận xét của nhau; xuất `reviewer.json` và `auditor.json`, ghi identity model thực tế đã chọn. Chạy `validate`. FAIL thì giao translator sửa theo nguồn và lỗi, tạo prompt review mới, kiểm lại cả hai lượt. Tối đa 2 vòng sửa; hết ngân sách/lỗi nguồn/model/session không rõ thì BLOCKED, lưu state, không viết vào output_dich. Chỉ dùng publish-dir khi validate PASS. Trả đường dẫn artifact, model, token/giờ nếu có, phạm vi đã kiểm và điểm chưa rõ. Không gọi nguồn mới hoặc tự đổi glossary để làm review PASS.

Chưa điều khiển hoặc khởi chạy phiên Antigravity IDE trong lượt audit này. Các subagent dùng ở đây là subagent của Codex để rà code, đối chiếu nghĩa và sửa client.

## API đa model

`api_config.json` đang giữ thông tin provider cũ. Cấu hình `quality_roles` riêng, tên model tường minh, pool không giao nhau. `quality_roles.example.json` là mẫu, chưa phải cấu hình chất lượng đã phê duyệt. Không dùng Gemini 3.6 Flash làm reviewer duy nhất vì pilot đã chứng minh bỏ lọt lỗi. Reviewer chính nên qua regression suite; auditor thứ hai kiểm độc lập. Alias `latest` có thể đổi; client ghi version API thực tế và chặn khi API không báo model.

Role có thể thêm `temperature: 0` và `thinking_budget: null` để dùng thiết lập reasoning mặc định của model. Một model lỗi sẽ chặn role; không fallback sang vai trò hoặc model ngoài pool.

```powershell
python quality_pipeline.py --package SOURCE.json --preflight
python pipeline_api.py --package SOURCE.json --max-repairs 1
```

`--preflight` không gọi API và không chứng nhận model đã sinh thành công. Các entrypoint `agentic_batch_translator.py`, `pipeline_dich_truyen.py`, `run_production_chap1.py` chuyển vào cổng mới. Lệnh batch/provider chung cũ bị từ chối: chạy tuần tự với context đã duyệt cho từng chương. Muốn song song thì chỉ các worker của cùng chương chạy đồng thời; không duyệt chương sau trước context chương trước.

Các file benchmark lịch sử `pipeline_test_chap1.py` vẫn là thí nghiệm, không chứng nhận hoặc publish qua cổng mới. PDF/ZIP cũ chưa qua kiểm dịch; không dùng chúng để khẳng định cả truyện đã đạt.

## Chạy audit lại

```powershell
python -X utf8 -m unittest discover -s tests -v
python -X utf8 audit_existing.py
# Hai lệnh dưới gọi API thật, có usage; chỉ chạy khi cần đánh giá model mới:
python -X utf8 audit/model_pilot.py
python -X utf8 audit/end_to_end_pilot.py
```

Regression pilot khóa câu nguồn và đáp án. Không sửa đáp án để làm model tăng điểm. Thay prompt/model thì giữ kết quả cũ ở run riêng và so cả false accept/false reject. 16 phán định không thay thế test độc lập trên cả chương. Bản gốc code trước vá ở `audit/original_code_20261013/`; chưa tạo lại ZIP/PDF sản xuất.

Quy tắc finish reason/loại thought dựa trên tài liệu API chính thức: https://ai.google.dev/api/generate-content . `STOP` tự nó không chứng minh dịch đầy đủ; còn cần kiểm dịch có nguồn.
