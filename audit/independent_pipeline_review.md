# Kiểm tra độc lập pipeline dịch truyện

Ngày kiểm tra: 13/10/2026. Phạm vi: mã nguồn tại workspace, kiểm tra tĩnh và các ca tái hiện offline. Không gọi API dịch, không tải chương mới, không thay đổi bản dịch hoặc mã sản xuất. Các số dòng dưới đây là số dòng ở phiên bản trước khi bản vá của điều phối viên được áp dụng.

## Kết luận

Pipeline hiện có đủ đường tải nguồn → gợi ý từ vựng → model biên tập → ghép chương, nhưng chưa có bước đối chiếu ngữ nghĩa độc lập. Tên gọi `Agentic QA`, `Critic`, `Chivi 3 AST` trong mã/tài liệu mạnh hơn chức năng thực tế: gợi ý đầu vào là thay chuỗi và regex; QA đầu ra là xóa dòng và thay từ. File lớn hơn 1 KB đang được coi là hoàn chỉnh dù chưa chứng minh độ đầy đủ hoặc trung thành.

Không thể xác nhận model trên Antigravity, chất lượng dịch toàn bộ truyện, hay năng lực từng model chỉ từ tên trong prompt/header. Việc kiểm tra này chứng minh lỗi luồng và dữ liệu có thể tái hiện, không phải benchmark model.

## Phát hiện ưu tiên

### P1 — Regex gợi ý cú pháp làm đổi ngữ nghĩa

- Vị trí: `prepare_for_agent.py:25-40`; `pipeline_api.py:30-45`; `agentic_batch_translator.py:39-61`.
- Ký tự `将` được nhận diện như cấu trúc xử lý tân ngữ kể cả trong `将来` (tương lai). Nhóm loại trừ chỉ có dấu câu ASCII, vì thế regex đi qua `。` hoặc `，`, ghép tân ngữ của câu trước với động từ câu sau. `\w{2,4}` nhận cả chữ Hán, không thể xác định ranh giới từ hoặc quan hệ định ngữ.
- Tái hiện bằng đúng hàm `pipeline_api.py` tách qua AST, không import module:

| Nguồn | Gợi ý thực tế |
|---|---|
| 他将来不会杀死任何人。 | 他杀死 来不会任何人。 |
| 他把刀收好。她杀死了敌人。 | 他杀死 刀收好。她了敌人。 |
| 他被击中，但没有被杀死。 | 他bị 击中，但没有被 杀死。 |
| 她的确不是他的朋友。 | 她的朋友 của 确不是他。 |

- Hậu quả: bản thô được quảng bá là cây cú pháp và model được yêu cầu khóa 100% theo nó; người/quan hệ/phủ định có thể sai ngay trước bước dịch.
- Khắc phục: RAW phải là nguồn quyết định. Loại bỏ đảo cú pháp regex; giữ bảng thuật ngữ được duyệt và gợi ý không có thẩm quyền. Khi dùng parser thật, lưu parser/version và kết quả phân tích có cấu trúc thay vì khẳng định AST từ regex.

### P1 — Bộ lấy RAW có thể mất nội dung hoặc trộn quảng cáo

- Vị trí: `prepare_for_agent.py:70-84`; `pipeline_api.py:68-82`; `agentic_batch_translator.py:98-112`.
- `soup.get_text()` đọc toàn bộ tài liệu thay vì `#content`. Xóa tất cả thẻ `<a>` bằng `decompose()` xóa luôn chữ bên trong, kể cả tên nhân vật thuộc thân truyện. Bất kỳ đoạn nào chứa `上一章`, `下一章`, `飘天文学`… bị bỏ cả đoạn, kể cả khi đó là câu chuyện thật. Tách bằng đúng bốn NBSP phụ thuộc HTML nguồn; `<br>` không được bảo toàn thành ranh giới đoạn rõ ràng.
- Fixture offline có `#content` chứa `张羽看着<a href="x">王海</a>说：这不是下一章的事。` và `他没有杀人。`, phía ngoài có `<aside>广告广告</aside>`.
- Kết quả thực tế: chỉ còn `他没有杀人。广告广告`. Câu đầu mất; quảng cáo ngoài thân bị ghép vào câu cuối.
- `pipeline_dich_truyen.py:49` cũng không xác nhận `#content` tồn tại: nếu thiếu marker, `split(...)[-1]` xử lý cả HTML như nội dung chương; dòng 59 loại nguyên dòng theo substring.
- GBK `errors='ignore'` (`prepare_for_agent.py:56`, `pipeline_api.py:59`, `get_toc.py:26`) có thể xóa byte lỗi mà không báo. Nguồn RAW và HTTP payload không được lưu kèm hash để truy nguyên.
- Khắc phục: chỉ lấy container đã xác nhận; giữ chữ của inline anchor; tách block/BR chuẩn; quảng cáo/navigation chỉ được xóa theo cấu trúc đã xác minh và phải có nhật ký đoạn bị loại. Lưu RAW bất biến, URL, thời điểm, encoding, hash, số đoạn. Thiếu container/giải mã lỗi/rỗng phải chặn dịch.

### P1 — Kết quả chưa kiểm dịch đi thẳng vào bản cuối

- Vị trí: `pipeline_api.py:84-108,185-208`; `agentic_batch_translator.py:63-86,197-236`; `pipeline_dich_truyen.py:115-138`.
- `critic_qa_linter` không nhận nguồn Trung, không kiểm tra nghĩa, diễn biến, phủ định, chủ thể/tân ngữ, con số, đại từ hay đoạn thiếu. Việc thay vài chữ Hán không kiểm soát mọi chữ Hán còn sót. Không có reviewer/model độc lập sau bản dịch.
- Tái hiện offline ở `pipeline_api.py`: đầu vào `Lưu ý: nếu không quay lại, tôi sẽ chết.` bị xóa hoàn toàn. Bản `agentic_batch_translator.py` còn xóa mọi dòng bắt đầu `Hy vọng`, `Chúc bạn`, `***`, `---` mà không phân biệt lời truyện, lời thoại hoặc dấu chuyển cảnh.
- Mọi output sạch bề mặt đều được ghi thành bản hoàn tất. Các số liệu tokens/tốc độ không chứng minh độ đúng.
- Khắc phục: lưu draft nguyên trạng, không xóa nội dung theo prefix chung. Mỗi đoạn nguồn có ID ổn định; dịch trả đoạn tương ứng; reviewer đối chiếu trực tiếp RAW và draft, trả lỗi kèm ID và bằng chứng. Chỉ xuất bản sau gate đầy đủ và semantic reviewer độc lập; ca không chắc chắn phải `needs_review`.

### P1 — Cache và `--force` có thể giữ nguyên lỗi sau audit

- Vị trí: `pipeline_api.py:133-135,161-168,197-200`; `pipeline_dich_truyen.py:70-72,93-97`; `prepare_for_agent.py:97-99`; `agentic_batch_translator.py:137-139,169-180`.
- Kiểm tra file cuối dựa trên tồn tại/dung lượng. Cache phần chỉ kiểm tra file và metadata hoặc dung lượng. Không có hash RAW, danh mục, glossary, prompt, model/config, chunk boundaries, hoặc kết quả reviewer.
- `pipeline_api.py --force` chỉ bỏ skip bản cuối. Nó vẫn nạp nguyên cache phần ở 161-168. Vì vậy chạy “bắt buộc dịch lại” có thể không gọi model một lần nào.
- Cache chung giữa các pipeline dễ ghép phần dịch từ nguồn/prompt/model khác nhau. Đổi glossary không buộc cache prepared/draft cũ hết hạn.
- Khắc phục: manifest phiên bản, hash nguồn và target, nguồn chuẩn, chunk ID/hash, glossary/context/prompt/model fingerprint. Chỉ skip bản cuối khi bằng chứng approved khớp cả hash bản dịch. `--force` phải bỏ toàn bộ cache dịch; audit lại phải kiểm tra draft hiện hữu trước khi cân nhắc sửa.

### P1 — Client nhận đầu ra rỗng/cắt dở hoặc thinking block

- Vị trí: `gemini_helper.py:55-64`; `multi_llm_client.py:55-61,124-127`.
- Không kiểm tra `finishReason`/`finish_reason`; câu trả lời chạm giới hạn hoặc bị safety block vẫn được coi là thành công nếu có text. `gemini_helper` trả chuỗi rỗng khi thiếu candidates. Hai Gemini client lấy mọi part có `text` thay vì loại part được đánh dấu `thought`.
- OpenAI compatible client có thể trả rỗng khi không có choices và vẫn thành công. Lúc này pipeline vẫn ghép header/file rồi báo hoàn tất.
- Khắc phục: yêu cầu kết thúc hoàn chỉnh, non-empty, đúng schema đoạn, không reasoning text; báo lỗi trả về có kiểu; lưu finish status trong manifest. Timeout/retry không thay thế kiểm tra chất lượng.

### P1 — Chia chunk độc lập không có ngữ cảnh xuyên suốt

- Vị trí: `pipeline_dich_truyen.py:81-111`; `agentic_batch_translator.py:150-193`; `pipeline_api.py:145-181`; `prepare_for_agent.py:118-129`.
- Mỗi nhóm 60 đoạn chỉ có tên chương, RAW nhóm hiện tại và bản gợi ý. Không gửi đoạn lân cận, sự kiện đã xảy ra, người nói, quan hệ/xưng hô đang sử dụng, state/summary có bằng chứng, hoặc glossary version được khóa. Các chương do swarm dịch song song không có bước hội nhập context/continuity.
- Hậu quả: thuật ngữ toàn cục chưa đủ bảo toàn người nói, sự thay đổi quan hệ, thứ tự sự kiện, phủ định và giọng kể qua biên chunk/chương.
- Khắc phục: context có nguồn và ID, readonly cho translator; context hữu ích từ RAW chương trước được chốt trước khi dịch chương sau; reviewer continuity riêng đối chiếu biên và timeline. Không đưa bản dịch chưa duyệt làm nguồn sự thật cho chương sau. Worker đề xuất cập nhật lore, điều phối viên duyệt và commit phiên bản thống nhất.

## Phát hiện vận hành và tính kiểm chứng

### P2 — Tên model trong tài liệu/header không phải model thực dùng

- `gemini_helper.py:14-15` đặt default 3.7 và nhiều fallback, trong khi nhiều header và log ghi 3.6 (`pipeline_dich_truyen.py:113,129`, `agentic_batch_translator.py:195,230`). `agentic_batch_translator.py` có usage chứa model_used nhưng chưa đưa định danh thực tế vào header/analytics đầy đủ từng phần.
- `prepare_for_agent.py:111` chỉ yêu cầu Antigravity dùng Gemini 3.8; không có bằng chứng runtime thực hiện yêu cầu. `PIPELINE_GUIDE.md:14-17,26-39`, `DEPLOYMENT_GUIDE.md:33,54-55` nói model/tốc độ/quota/chất lượng mà chưa có bằng chứng đo tại lần chạy.
- `pipeline_api.py:155,161-168,204,217`: nếu dùng cache toàn bộ, `last_model` giữ `unknown`; nếu nhiều model thì header chỉ ghi model phần mới cuối cùng.
- Không kiểm tra model ID tồn tại trên provider trong audit này; tên chỉ được ghi nhận từ mã. Cần pin model đã kiểm chứng, ghi model runtime per-part/per-review và giữ benchmark ngữ nghĩa riêng với tốc độ/chi phí.

### P2 — Atomic cache và “chống trùng 100%” chưa đúng

- `pipeline_api.py:197-208`; `agentic_batch_translator.py:216-219,235-236` ghi trực tiếp `open(...,'w')`, không temp file + atomic replace, không lock nhận chương. Worker crash hoặc hai worker trùng chương có thể ghi partial/race.
- Tài liệu gọi là `Atomic Part Caching` (`DEPLOYMENT_GUIDE.md:328-329`), `Smart Skip chống dịch trùng 100%` (dòng 50) và “không bao giờ” ghi đè/token 2 lần (dòng 309), vượt khả năng hiện tại.
- Cần lock chapter/job, claim ownership, tmp+replace, manifest cuối cùng sau QA, draft/quarantine riêng. Không overwrite bản đã duyệt khi chưa có revision backup.

### P2 — Mục lục không có xác minh/refresh và import có tác dụng phụ

- `get_toc.py:13-30`: dùng cache vô hạn, không kiểm schema/thứ tự/duplicate/chapter số; nếu cache trống hoặc lỗi, import tự tải mạng và ghi cache. Regex trên toàn HTML có thể trộn link không thuộc TOC. Các pipeline dùng vị trí danh sách làm số chương.
- `pipeline_dich_truyen.py:34-40` lại lấy TOC trực tiếp mỗi lần mà không kiểm thứ tự, tạo hai cơ chế định danh khác nhau.
- Cần chức năng nạp rõ ràng, refresh explicit, kiểm định danh source/book/href/order/dedup và chốt TOC manifest. Số thứ tự chương kể cả các chương tác giả thông báo phải được giữ phân loại rõ.

### P2 — Lỗi tải/source không được fail-closed nhất quán

- `prepare_for_agent.py:58-63`: khi hết mọi lần retry HTTP 429/5xx, vòng lặp có thể kết thúc với `html=''` và trả 0 đoạn thay vì raise. Các hàm khác cũng không kiểm `paragraphs` rỗng trước tạo chunks/header.
- `pipeline_api.py:248-255` nuốt lỗi chương rồi tiếp tục; cuối chương trình không có tổng kết thất bại hay nonzero exit. Pipeline dài có thể nhìn như chạy xong dù bỏ nhiều chương.
- Cần manifest trạng thái từng chương, chặn nguồn rỗng, lỗi cuối cùng có nonzero exit và báo chapter IDs cần retry.

### P2 — Khóa API hiện diện trực tiếp trong mã/tài liệu

- Vị trí: `gemini_helper.py:13`; `PIPELINE_GUIDE.md:61`.
- Có giá trị credential hard-coded; báo cáo này không sao chép giá trị. Không thể xác nhận còn hiệu lực. Đóng gói/đẩy repo có thể mang theo giá trị đó.
- Đọc credential từ môi trường/secret riêng và dùng placeholder trong tài liệu; nếu là khóa thật cần thay khóa sau khi gỡ khỏi phiên bản chia sẻ. Không thực hiện thao tác credential trong audit này.

### P2 — Config và fallback gây khó lặp lại benchmark

- `pipeline_api.py:145` hard-code 60, bỏ qua `settings.chunk_size_paragraphs`; request delay config không được dùng trong vòng dịch.
- `multi_llm_client.py:156` thiếu ngoặc quanh nhóm `(api_key or api_keys)`, nên provider đang active có api_keys có thể bị thêm lặp vào fallback.
- Fallback tự chuyển model/provider nhưng chưa bắt buộc reviewer hoặc đánh dấu chất lượng chưa xác định. Khi so sánh model phải pin version và cùng bộ test, giữ output/model thực tế, từ chối silent downgrade.

## Luồng đề nghị

1. Fetch và xác minh nguồn; lưu RAW/HTML manifest bất biến và đoạn nguồn có ID.
2. Chốt glossary + context có nguồn, phiên bản; chỉ sinh gợi ý từ vựng an toàn.
3. Translator tạo draft theo ID; lưu model runtime, prompt/context fingerprint và finish status.
4. Gate cấu trúc kiểm thiếu/thừa/trùng ID, output rỗng, chữ Hán còn sót, con số/tên cần kiểm, status cắt dở. Đây là kiểm cơ học, chưa phải xác nhận nghĩa.
5. Reviewer độc lập đối chiếu từng đoạn RAW–dịch, kiểm người nói/chủ thể/tân ngữ, phủ định, thời gian, số lượng/đơn vị, tên/công pháp, sắc thái và thêm/bớt tình tiết. Báo bằng chứng ID và đề nghị sửa.
6. Repair giới hạn ở ID bị lỗi; giữ lịch sử; reviewer lại cả sửa và biên lân cận. Giới hạn số vòng; chưa giải quyết chuyển `needs_review`.
7. Reviewer continuity đối chiếu state có nguồn xuyên chunk/chương; chốt glossary/context updates. Chỉ publish approved với hash khớp bản cuối; bản cũ chưa có bằng chứng không tự nhận đạt.

## Kiểm tra đã làm và giới hạn

- Đọc mã nguồn/tài liệu được liệt kê, thêm `multi_llm_client.py` và `run_production_chap1.py` để lần đúng call path.
- Tái hiện offline bằng function AST extraction và BeautifulSoup fixture, không import module có fetch side effect.
- Không dùng credential, không gọi API, không kích hoạt swarm Antigravity, không đánh giá model từ tên, không sửa/chấm đạt toàn bộ chương.
- Các lỗi tái hiện chứng minh nguồn/gợi ý/cleaner có thể mất hoặc đổi nội dung. Chất lượng bản dịch thực tế phải được kiểm trên RAW đầy đủ và reviewer được ghi nhận; không suy ra tỷ lệ đúng từ một vài ca hoặc từ file lớn/không có chữ Hán.
