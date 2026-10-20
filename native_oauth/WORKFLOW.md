# Luồng vận hành: Antigravity draft, GPT Codex duyệt

> Luồng này là pilot chương đơn ban đầu. Theo yêu cầu dịch hàng loạt low/medium và cải tiến hệ thống, dùng [BATCH_WORKFLOW.md](BATCH_WORKFLOW.md). GPT trong route mới chấm mẫu và calibrate; không sửa từng chương để che lỗi generation.

Antigravity dùng OAuth để cào và dịch. GPT trong Codex chịu trách nhiệm review/audit cuối bằng hai subagent độc lập. Không dùng native reviewer thay cho hai GPT reviewer. Nguyên văn Trung là chuẩn, parser và tóm tắt chỉ hỗ trợ đọc.

## 1. Nguồn và continuity

Chạy từ `I:\Softs\Antigravity\CaoTruyen`. Với truyện hiện tại, lệnh có sẵn:

```powershell
python -X utf8 prepare_for_agent.py --chap 1
```

Nguồn đã thử: `native_oauth/pilot_workspace/prepared_input_v2/chap_001_第1章 面试_a4eef28c3f74.source.json`. Crawler lưu HTML nguyên byte và hash, kiểm title/book/chapter/encoding. Muốn truyện khác, dùng `python native_oauth/crawl_source.py --help`: bắt buộc base-url, article-id, href, title, chapter, genre và lore riêng cho truyện đó. Đọc mục lục để lấy đúng thông tin, không đoán URL. Chương sau phải đưa `--context` của chương trước đã duyệt.

Không lấy TXT cũ làm nguồn, không bỏ đoạn khó, không xem đoạn regex như cây cú pháp. Giữ id từng đoạn và khóa hash toàn package.

## 2. Parser thật và profile

Parser đã cài trong môi trường riêng, model/hash trong `models/LTP-small/verified_files.json`:

```powershell
native_oauth\.venv_parser\Scripts\python.exe -X utf8 native_oauth\parse_source.py --package SOURCE.json --out ANALYSIS.json
```

`SOURCE.json` và `ANALYSIS.json` là đường dẫn của chương cần làm. Parser từ chối đoạn vượt cửa sổ 512 token thay vì cắt ngầm; phải chia với offset có thể audit nếu cần. DEP/SRL/SDP là dự đoán; khi sai, ưu tiên câu Trung. Chưa chạy converter CON của Chivi.

Chọn `tien_hiep`, `hien_dai` hoặc `hybrid_cyberpunk_tu_tien`. Giữ tên/cảnh giới/công pháp bằng glossary có nguồn; đại từ theo vai vế/cảnh, không replace toàn truyện. Văn hiện đại dùng tiếng Việt tự nhiên, không ép ta-ngươi; tiên hiệp giữ cổ phong vừa phải mà tránh đảo cú pháp Hán.

## 3. Antigravity chỉ tạo draft

CLI đang dùng cached OAuth profile; `run_agy.py` bỏ biến API key khỏi môi trường và ghi model/conversation từ event init. Không đọc hoặc chép token.

```powershell
python -X utf8 native_oauth\pipeline_native.py --source SOURCE.json --analysis ANALYSIS.json --genre hien_dai --workspace native_oauth\JOB_WORKSPACE --translator-model claude-sonnet-4-6 --timeout 420
```

Thay genre đúng truyện, chọn workspace riêng cho từng job. Tên thư mục con hiện vẫn là `native_oauth/runs/chapter1` bên trong từng workspace; chapter thực được khóa trong package. CLI chạy job trong sandbox; đây không phải cách tạo quyền global. Kiểm runtime/model và kiểm cơ học rồi dừng tại `DRAFT_READY_FOR_CODEX`. `--resume-draft` chỉ nhận draft còn khớp source và runtime. Không dùng `--native-review-experiment` cho luồng được yêu cầu.

Đọc cây bằng `analysis_lookup.py --ids p0001 p0002`, tối đa tám id mỗi lần; không dump toàn JSON 1,5 MB vào context. Timeout giới hạn thời gian, chưa giới hạn hard tổng token native; giữ mỗi job một chương và xem quota trước mở rộng. Provider quota/cancel/JSON không hoàn chỉnh phải ghi BLOCKED, không xuất TXT.

## 4. Hai GPT Codex subagent độc lập

Điều phối viên trong Codex giao source.json, draft.json và codex.review.protocol.txt cho hai worker thực. Không dùng CLI Antigravity hay API để thay reviewer. Không để worker đọc kết quả của nhau trước kết luận ban đầu.

- Semantic reviewer: đọc đủ từng đoạn Trung/Việt, glossary/context; kiểm tác nhân/đối tượng, tên/thuật ngữ, người nói/suy nghĩ, phủ định/mức chắc chắn, số/đơn vị/ranh giới, thời gian, nhân quả/quan hệ, thêm/bớt nghĩa. Trích quote thật, ghi verdict và lỗi theo id; không phán từ điểm tự chấm.
- Literary reviewer: cũng đối chiếu toàn nguồn, đồng thời kiểm tiếng Việt tự nhiên, chính tả/ngữ pháp, giọng thể loại, xưng hô và dấu thoại. Không thêm tình tiết để câu hay hơn. Trả đúng năm `literary_checks`: `natural_vietnamese`, `spelling_grammar`, `genre_voice`, `address_consistency`, `dialogue_format`; true nghĩa đã kiểm, lỗi thật vẫn phải FAIL.

Mỗi review ghi package_hash, candidate_hash, model thực hoặc `codex/gpt-inherited`, `identity_basis: codex_subagent`, `agent_session` đúng task path. JSON schema đầy đủ lấy từ protocol do pipeline sinh. Cùng GPT được phép ở hai session tách biệt; không tự khai hai model khác nhau. Điều phối viên xác nhận đã chạy hai session; JSON khai identity không tự chống giả mạo.

FAIL: tạo bản sửa riêng, log source/trước/sau/lý do; giữ bản nháp gốc. Cả hai worker kiểm lại bản sửa bằng hash mới, đối chiếu phần sửa với nguồn và xác nhận phần còn lại giữ nguyên; lỗi mới cần audit lại phần liên quan. Chỉ PASS khi đủ đoạn/quote/hash/chiều kiểm/ngữ cảnh và không còn lỗi chặn.

## 5. Duyệt và xuất local

Lệnh đã xuất thành công chương thử:

```powershell
python -X utf8 native_oauth\codex_gate.py --package native_oauth\pilot_workspace\native_oauth\runs\chapter1\source.json --candidate native_oauth\codex_audit\draft.gpt_edited.json --semantic-review native_oauth\codex_audit\semantic_review.final.json --literary-review native_oauth\codex_audit\literary_review.final.json --semantic-session /root/gpt_semantics --literary-session /root/gpt_literary_audit --out native_oauth\codex_audit\final_qa.json --publish-dir native_oauth\approved_codex
```

Với chương mới thay toàn bộ artifact/session bằng job thực của chương đó; không tái dùng review chương 1. Shared gate cũng buộc năm flags văn phong, kể cả khi gọi publish trực tiếp. API policy mặc định vẫn giữ yêu cầu model khác nhau. Codex policy được lưu trong evidence và dùng lại khi xác thực continuity.

```powershell
python -X utf8 semantic_gate.py context --evidence native_oauth\approved_codex\chapter_0001_d469016d2ce9.evidence.json --out native_oauth\approved_codex\context_chapter_0002.json
python -X utf8 prepare_for_agent.py --chap 2 --context native_oauth\approved_codex\context_chapter_0002.json
```

Xuất TXT kèm QA/evidence/publication manifest; kiểm hash TXT. Context chứa fact/quote/id đã duyệt cùng chuỗi evidence, không tóm tắt bịa. Nếu context lớn, điều phối viên phải chọn giữ fact có chứng cứ về tên, quan hệ, timeline, sự kiện mở; không âm thầm cắt hoặc sửa statement. PASS không thay audit mẫu của biên tập viên. Tiêu chí BNS ở đây là rubric biên tập tham khảo công khai, không phải chứng nhận của diễn đàn.

Kết quả đã thực hiện và giới hạn: [AUDIT_RESULT_20261013.md](AUDIT_RESULT_20261013.md).
