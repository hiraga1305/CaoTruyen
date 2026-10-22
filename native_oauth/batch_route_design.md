# Luồng dịch hàng loạt: hợp đồng ngữ cảnh trước khi dịch

Mục tiêu là kiểm chứng Gemini 3.8 Flash low/medium với nhiều worker, rồi cải thiện **cách tạo đầu vào và điều phối** nếu thất bại. Đánh giá thử nghiệm là hoạt động ngoài luồng; pipeline vận hành độc lập trong Antigravity.

## Luồng đề xuất

1. Cào và khóa nguồn Trung văn, mã chương/đoạn, hash, bản HTML gốc. Không lấy bản Việt vừa sinh làm nguồn sự thật của chương tiếp theo.
2. Source prepass đọc các chương gốc và đánh chỉ mục nhân vật, khái niệm, sự kiện, quan hệ với **chapter + paragraph + exact Chinese quote**. Có thể dùng LTP/HanLP hoặc Chivi làm gợi ý phân tích; kết quả parser và phần tóm tắt do LLM suy luận đều phải được kiểm tra với câu gốc. Việc trích dẫn được một câu không chứng minh mọi suy luận về câu đó đúng.
3. Tách scene theo nguồn (người nói, chuyển cảnh, mốc thời gian); gán một owner cho mỗi đoạn. Nếu chưa có bộ tách scene được kiểm chứng, dùng chia đoạn cố định làm nhánh đối chứng, không gọi đó là bộ hiểu ngữ cảnh.
4. Đóng băng cùng một phiên bản story state cho các worker trong một block. Mỗi worker nhận nguồn mình sở hữu, các đoạn Trung văn lân cận chỉ để đọc, thuật ngữ phù hợp, style profile và một capsule có giới hạn. Không nhận bản Việt chưa duyệt của worker khác.
5. Chạy worker Flash low. Kiểm tra cơ học, thuật ngữ đã khóa, sai số/ngưỡng/phủ định theo ngữ cảnh, vai người nói, tính liền mạch giữa scene và văn phong. Flash medium có thể làm verifier, hoặc dịch nhánh khó; khả năng kiểm tra phải được đo trên bộ thử khóa, không suy từ tên model.
6. Nếu sai, phân loại **nguyên nhân hợp đồng**: thiếu bằng chứng xa, quan hệ thay đổi không có mốc, mất chủ ngữ qua ranh giới scene, thuật ngữ đa nghĩa, profile sai thể loại, hoặc low không giải được câu dù dữ liệu đầy đủ. Thay đổi retrieval/capsule/range/routing tương ứng và **sinh lại toàn scene/block bị phụ thuộc**, rồi kiểm tra lại. Không đưa câu dịch đúng của benchmark vào prompt; không sửa đoạn Việt bằng tay.
7. Chỉ commit theo thứ tự sau gate có bằng chứng thực. Nếu state/contract/source đổi, kết quả đang chạy trên phiên bản cũ bị hủy hiệu lực. Lưu mọi state version, nguồn, prompt, runtime, candidate, gate evidence để điều tra hồi quy.

Đây là kiến trúc và bộ kiểm tra tính toàn vẹn. Chưa có gate batch chứng minh đủ chất lượng để tự động xuất bản hàng chục nghìn chương. Vì vậy `commit_block` bị khóa nếu thiếu callback gate độc lập đã được triển khai và kiểm chứng.

## Module sử dụng được trong pilot

`native_oauth/batch_contract.py` không gọi model/API và không thay đổi file. Các hàm trả dữ liệu JSON tuần tự hóa được:

```python
state = build_story_state(
    source_packages, ledger_entries, glossary, style_profile,
    version=1, through_chapter=0,
)
plan = plan_parallel_block(
    state, consecutive_source_packages,
    max_owned_paragraphs=32, overlap=2,
    max_capsule_chars=12000, max_source_chars=20000,
    scene_end_ids=None,  # Hoặc danh sách source ids kết thúc scene, phủ toàn block.
)
scene = make_scene_contract(
    state, complete_source_packages, locked_excerpt_ids, overlap=3,
)  # experimental_partial_scene=True: không ngụ ý toàn chương đã được dịch/duyệt.
merged = validate_and_merge(plan, worker_candidates, current_state=state)
# merged.status == DRAFT_MERGED_UNREVIEWED; không phải PASS ngữ nghĩa.
next_state = commit_block(
    state, plan, merged, consecutive_source_packages,
    ledger_updates, gate_receipt, gate_verifier=trusted_gate_verifier,
)
```

Mỗi worker phải trả `job_id`, `state_hash`, `contract_hash`, `segments:[{id,text}]`, chính xác các `owned_segments` theo thứ tự. `neighbor_segments` không thuộc quyền xuất bản của worker. Ghép kết quả không phụ thuộc thứ tự worker hoàn thành.

Package Trung văn độc lập chỉ cần `chapter`, `segments:[{id,source}]`, `package_hash` đúng. Module kiểm tra hash, mã `cNNNNpNNNN`, thứ tự/độ phủ và nguồn gốc; không giả vờ có chuỗi bản Việt đã duyệt để chấp nhận chương 2 trở đi.

Ledger entry ví dụ:

```json
{
  "ledger_id": "event-c0002p0053",
  "kind": "event",
  "keys": ["张羽"],
  "references": [
    {"source_id": "c0002p0053", "source_quote": "Trích nguyên văn tiếng Trung có 张羽"}
  ],
  "required": true
}
```

Ví dụ chỉ mô tả schema; quote giả trên sẽ bị từ chối. Mỗi key phải có trong quote gốc. `kind` gồm `entity`, `relation`, `event`, `concept`. `valid_from` mặc định vị trí evidence đầu tiên và không được sớm hơn evidence. `interpretation` nếu lưu chỉ là gợi ý chưa xác minh và bị loại khỏi capsule worker. Module không nhận trường tùy ý chứa khẳng định không có bằng chứng.

## Tránh mất mạch khi song song

- **Temporal lens:** ledger trong prepass có thể biết chương sau, nhưng capsule worker không nhận event/quote xác nhận sau cuối range sở hữu. Alias chỉ có trong quote tương lai cũng bị loại. Nguồn overlap phía sau được đánh dấu chỉ để đọc; người dịch vẫn phải giữ thời điểm tiết lộ và góc nhìn của từng câu.
- **Nhân vật trở lại xa:** key nhân vật truy hồi quote cũ, tên chuẩn và quan hệ có mốc. Để kiểm tra trường hợp tên không được lặp mà chỉ có “hắn/nàng”, source prepass phải gắn coreference cùng bằng chứng; tìm chuỗi tên đơn thuần trong module là baseline, chưa đủ giải coreference. Không được bỏ qua hạn chế này bằng một tóm tắt trôi nổi.
- **Quan hệ thay đổi:** dùng event id riêng theo thời điểm thay vì ghi đè một câu “A là sư phụ của B” rồi áp cho toàn truyện. Version cũ phải được lưu. Khi sửa cùng một ledger id, commit bắt buộc `previous_entry_hash` trùng entry trước; các kết quả phụ thuộc snapshot cũ phải sinh lại.
- **Xưng hô:** khóa tên/thuật ngữ khác với lựa chọn đại từ. Profile tiên hiệp có thể dùng ta/ngươi, hiện đại có thể dùng tôi/anh, nhưng quyết định từng lượt phải dựa người nói/người nghe và quan hệ tại đúng mốc; không thay tên thành đại từ theo regex.
- **Ngân sách:** capsule truy hồi bắt buộc không vừa giới hạn thì dừng và thu nhỏ range/retrieval có lý do. Không cắt đuôi quote/source, không lặng lẽ bỏ bằng chứng bắt buộc. `max_source_chars` chặn nguyên job quá lớn; capsule giới hạn theo ký tự là kiểm soát kích thước, không phải số token/quota chính xác.

`source_anchor_candidates` trích các số và từ ngưỡng/phủ định kèm vị trí, quote và ngữ cảnh. Đây là ứng viên cần kiểm tra: chữ “一” có thể thuộc thành ngữ, “两万” cần đúng đơn vị và phạm vi; không được xem phép tìm chuỗi là kiểm chứng nghĩa. Parser chỉ giúp tìm chỗ cần đọc kỹ, không được làm đáp án vàng.

## Kiểm chứng cải thiện trước khi áp rộng

Đóng băng source, spans và tiêu chí trước khi gọi model. So sánh low solo không memory, low song song không capsule, low song song có capsule + overlap, medium cùng hợp đồng. Mỗi nhánh có cùng nguồn và tiêu chí, artifact riêng, không dùng câu dịch đúng làm đầu vào. Thêm thử tên trở lại sau nhiều chương, chủ ngữ bị lược, đổi quan hệ, cảnh hội thoại, số tiền/ngưỡng, sự kiện phủ định và thoại nội tâm ở cả tiên hiệp/hiện đại.

Nếu capsule không cải thiện hoặc medium cũng thất bại, sửa thiết kế trên bộ development rồi chạy lại **heldout khác** để tránh thuộc đề. Đo lỗi nghiêm trọng trên chương/scene, lỗi tên/xưng hô xuyên chương, độ tự nhiên theo thể loại, retry/escalation rate, thời gian và quota. Không gọi vài scene/chương là bằng chứng cho 10.000 chương. Chạy canary dài có mốc dừng, audit ngẫu nhiên và audit khi có dấu hiệu drift trước khi tăng batch.

Tiêu chí biên tập hướng Bạch Ngọc Sách là policy thực dụng về tiếng Việt, thể loại và tính nhất quán; không phải chứng nhận của diễn đàn. Cần bộ mẫu văn phong và rubric rõ ràng để tách lỗi ngữ nghĩa bắt buộc chặn khỏi lựa chọn văn chương hợp lệ.

## Kiểm tra đã thực hiện

`python -X utf8 -m unittest tests.test_batch_contract -v`: **13/13 PASS**. Tests kiểm tra quote/hash, ownership/overlap, thứ tự ghép, temporal filtering, budget không cắt nguồn, stale invalidation, barrier commit, cập nhật ledger, scene partial, và từ chối PASS tự khai khi chưa có external verifier. Những tests này không đo chất lượng dịch.

## Review bổ sung cho runner pilot và source prepass

`tests/test_batch_experiment.py`: **12/12 kiểm tra ngoại tuyến PASS**; mọi lệnh native trong tests đều mock. Đã kiểm tra phép chiếu protocol giữ nguyên toàn bộ đoạn Trung văn sở hữu và overlap, chỉ giữ NER/SRL compact được yêu cầu, không chuyển obligations/đáp án Việt của reviewer cho worker, từ chối workspace có candidate/runtime cũ, chặn model init khác model đã yêu cầu, chặn wave kế tiếp nếu thiếu usage, chặn glossary xung đột, yêu cầu đủ parser coverage/hash, và giữ quote gốc thay vì suy luận coreference. Đã thêm hồi quy chặn source mới + parser mới dùng lại corpus lock cũ; runner chuẩn bị hiện kiểm tra bản nguồn thực so với khóa đánh giá.

`batch_source_prepass.extract_ledger` hiện dùng tên trong glossary, NER dự đoán và từ chỉ quan hệ để **đánh chỉ mục quote gốc**. Nó chưa tự hiểu ai là chủ ngữ của “hắn”, chưa chứng minh quan hệ giữa hai người, chưa xử lý trạng thái thay đổi bằng phép suy luận. `parse_raw_packages` mới là đường chạy parser LTP thực trên toàn nguồn với coverage và cửa sổ không bị cắt; test mock không thay thế bằng chứng runtime này.

`batch_experiment` hiện là runner có đối chứng: exact Flash low/medium, tối đa hai worker đồng thời, tách workspace, hash hợp đồng, kiểm tra id/độ phủ và ngưỡng usage giữa các wave. Thành công ở runner chỉ là `DRAFT_COMPLETE_UNREVIEWED`/`DRAFTS_COMPLETE_UNREVIEWED`; không có xuất bản tự động. Ngưỡng token giữa wave không chặn được một lời gọi đang chạy vượt ngân sách. Không suy chất lượng dịch từ số worker thành công hoặc từ tests cơ học.

## Policy production cần kiểm chứng riêng

Policy này là thiết kế để triển khai sau pilot, không phải tính năng đã được runner thực hiện:

1. **Phân luồng bằng rủi ro nguồn:** scene có tên/thuật ngữ mới, đổi quan hệ, chủ ngữ bị lược, hội thoại cắt qua ranh giới, nhiều mốc thời gian, số tiền/đơn vị/ngưỡng/phủ định hoặc retrieved evidence vượt ngân sách phải nhận context đầy đủ hơn và kiểm tra tăng cường. Các dấu hiệu là lý do kiểm tra, không tự chứng minh bản dịch sai.
2. **Kiểm tra tự động:** kiểm tra cơ học/hash/ownership trước; verifier medium đọc cả nguồn và draft theo rubric nghĩa + phong cách, trả trích dẫn xác định sai hoặc còn bất định, đồng thời kiểm tra seam giữa scene. Model verifier phải được đo với bộ sai/đúng khóa và heldout; self-score hay câu “đã kiểm tra” không đủ làm gate. Một nét mơ hồ có chủ ý trong nguồn được giữ nguyên không phải lỗi cần cưỡng ép giải nghĩa.
3. **Retry toàn scene:** khi lỗi đến từ thiếu nguồn xa hoặc ranh giới không đúng, cập nhật contract từ quote Trung văn, mở retrieval/overlap hoặc ghép scene; sinh lại toàn scene với low. Khi dữ liệu đã đủ mà low vẫn sai, đổi sang medium và dịch scene đó theo thứ tự cùng hàng xóm đã chấp nhận. Khi lỗi là bất đồng terminology/quan hệ, tăng version state và vô hiệu mọi job phụ thuộc snapshot cũ. Không đưa câu Việt đúng của reviewer vào prompt, không patch đoạn lỗi.
4. **Dừng có giới hạn:** đặt số retry/escalation hữu hạn; failure lặp lại, gate chưa hiệu chỉnh hoặc quota không rõ thì quarantine scene/block, không xuất bản. Giữ nguyên candidates thất bại để so sánh design, không xóa lịch sử rồi chỉ báo bản cuối.
5. **Kiểm định route trước mở rộng:** đánh giá thiết kế trên tập khóa, đối chứng và canary. Hoạt động kiểm thử ngoài luồng không tạo phụ thuộc vận hành vào nền tảng khác. Đối với sản xuất, vẫn cần gate source-bound đáng tin cậy; lấy mẫu chỉ ước lượng chất lượng và không đảm bảo mọi chương đều sạch.

Các dấu hiệu improvement phải đo được trên **bản sinh lại nguyên scene** ở heldout mới và chuỗi canary dài. Nếu shared capsule không thắng isolated, tiếp tục sửa cách lựa chọn quote/scene/coreference hoặc định tuyến model; không kết luận nhiều subagent giữ mạch chỉ vì dùng chung state hash.
