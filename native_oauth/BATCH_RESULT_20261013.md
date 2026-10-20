# Thử route Gemini 3.8 Flash low/medium hàng loạt — 13/10/2026

**Đã thử generation nguyên bản, không sửa tay câu dịch.** 24 native OAuth worker sessions sinh 344 target paragraphs qua các route/diagnostic; đây là các bản lặp của 56 đoạn đích duy nhất, không phải 344 chương hoặc 344 đoạn unseen. GPT Codex chấm mù source/target, giữ lỗi và cả điểm chưa đủ căn cứ. Mạch chính trong mẫu được giữ, nhưng văn phong chưa đạt đều; **chưa đủ bằng chứng để thả 10.000 chương hoặc gọi là đạt chuẩn BNS**.

Route đã áp vào generator sau này: source-only SQLite memory, snapshot/contract bất biến, ownership+overlap, model low/medium từ runtime, prevention policy, optional approved style seed, resume có xác thực. Semantic/style auto-gate đủ tin cậy và typed coreference graph vẫn còn thiếu; output batch giữ DRAFT_UNREVIEWED.

## Mẫu và protocol

- Source thật: chương 1–4 cùng truyện Piaotia, 580 đoạn; chương 1 là development. Cào mới chương 2–4, đúng book/title, lưu HTML. Chấm 48 đoạn thật thuộc ba chương liên tiếp.
- Synthetic: ba scene, 12 đoạn tự soạn. Tám đoạn đầu làm source context; final bốn đoạn được sinh trong matrix. Sau đó bốn đoạn scene 102 được sinh lần đầu để kiểm tra dự phòng. Không gọi synthetic là truyện cào.
- Corpus khóa trước output: `3d8b75e3eb8ed2dcd0348e8c8f5ce93f14b34a17103488843767071737f5975e`. [Corpus](batch_benchmark/locked_cases.json), [thiết kế](batch_benchmark/benchmark_design.md).
- Native worker không được đọc gold hay target tham chiếu. Initial matrix giống owned source, glossary, style và parser hints; khác source memory/neighbor quotes. Candidate gốc không bị thay từ; nếu cần sửa JSON quotes chỉ sửa định dạng, giữ original.
- Model pin bằng `agy --model gemini-3.8-flash-low/medium`; từng init event khớp model yêu cầu. Topology là custom-agent CLI sessions độc lập được scheduler fan-out, không tuyên bố nested invoke_subagent.

## Matrix gốc — 52 đoạn mỗi route

Hai GPT reviewer độc lập đọc mù; table dưới là counts của gold reviewer. Style counts là nhận xét biên tập, không phải điểm hay chứng nhận BNS.

| Route | Lỗi nghĩa xác nhận /52 | Trong đó lỗi lớn | Đoạn có cờ văn phong /52 |
|---|---:|---:|---:|
| Flash low, local isolated | 3 | 1 | 6 |
| Flash low, shared source context | 2 | 0 | 8 |
| Flash medium, local isolated | 0 | 0 | 7 |
| Flash medium, shared source context | 0 | 0 | 7 |

Low lặp lại lỗi 小贷 thành loại vay tiêu dùng; isolated low còn biến tiếp cận/đảo khoản vay thành “quỵt nợ”. Source không xác nhận hành vi cố ý không trả. Shared source low không mắc lỗi lớn đó ở lần sinh này, nhưng **không suy ra quan hệ nhân quả từ một lần chạy**.

All routes giữ actor chính, khoản nợ 700.000, offer/refusal, reported violence, original/current identity, chị gái gọi điện, hai lần 500 và tổng hơn 1.000. Synthetic giữ 20.000 đã trả, 500 chưa trả, 2.000 tiền thuê còn ghi nợ. Nhiều câu nêu rõ actor và số tiền nên kết quả này chưa kiểm tra mạnh coreference phụ thuộc history.

`件 → kiện` ban đầu bị nghi là sai đơn vị, nhưng source không nói rõ bao gói. Hai review sau tách nó thành **bất định/thêm độ cụ thể chưa có căn cứ**, không tính là lỗi chắc chắn. Frozen gold được giữ; evaluator qualification minh bạch trong báo cáo. Đây là lý do gate không nên biến mọi cảnh báo regex/dictionary thành kết luận nghĩa.

[Gold review 208 targets](batch_benchmark/gpt_gold_evaluation_v1.md) · [blind literary/source review](batch_benchmark/gpt_blind_style_v1.md).

## Đổi route rồi sinh lại, không edit target

V2 thay cơ chế: indexed source retrieval giữ first anchor + recent quotes; generic classifier/unit/financial-action policy; context revision/hash. Flash low **sinh lại cả 52 đoạn**. Lỗi thêm “quỵt nợ” biến mất, còn một consumer-loan qualifier nhỏ; 上线/cấp trên được chấm là quan hệ diễn đạt chưa rõ, không đủ căn cứ khẳng định tự thêm quan hệ boss. Sáu đoạn có cờ văn phong, vẫn còn convert. Đây là diagnostic retest sau khi thấy lỗi, không phải unseen improvement proof.

Bốn synthetic dự phòng sinh lần đầu giữ số, người vay/cho vay, tối thiểu 900g và phạm vi từ chối tối đó; vẫn có bất định bao gói. Một worker medium sinh cùng 48 đoạn thật giữ nghĩa, còn năm cờ văn phong. Control nhận union source context rộng hơn ba worker, nên chưa cô lập được tác động concurrency.

[Phase 2 gold/source review](batch_benchmark/gpt_gold_evaluation_phase2.md) · [independent literary review](batch_benchmark/gpt_blind_style_phase2.md).

V3 là lượt cuối có giới hạn: low và medium cùng sinh lại nguyên 16 đoạn scene chương 3 với generic Vietnamese literary decoder, bốn cặp Trung–Việt development đã duyệt làm seed và POS idiom candidates từ LTP thật. Cả hai giữ 7/7 nghĩa vụ ngữ nghĩa, nhưng mỗi bản vẫn có ba cờ văn phong. Clause “không/chẳng cho là đúng” và “ánh mắt ... ngưng lại” còn tồn tại. **Few-shot và thêm cây NLP chưa giải được văn phong toàn mệnh đề.** Lượt này có một GPT blind review hoàn tất; reviewer thứ hai gặp model capacity, nên không gắn nhãn hai-review cho V3.

[V3 bounded review](batch_benchmark/gpt_gold_evaluation_style_v3.md). Không có đoạn target nào được vá để nâng các kết quả trên.

## Kết luận về nhiều worker và Chivi

Đã chứng minh integrity của fan-out trong mẫu: tất cả job có đúng source/state/model identity, đủ owned paragraphs, không output overlap hay trùng owner; cache resume giữ phiên gốc. Chưa phát hiện drift actor/amount/debtstate trong các span đã chọn. **Không chứng minh mọi worker giữ được mạch hàng nghìn chương**, đặc biệt alias, lược chủ ngữ, role change và reveal xa chưa được thử đủ.

Đã kiểm online và local các repo Chivi [hanlp_mt](https://github.com/chi-vi/hanlp_mt), [ltp-dep-to-con](https://github.com/chi-vi/ltp-dep-to-con), [LTP](https://github.com/HIT-SCIR/ltp), [HanLP](https://github.com/hankcs/HanLP). Chưa xác nhận một release “Chivi v3” đã chạy. LTP thực tế cung cấp predicted syntax/roles, không phải semantic truth hay crosschapter coreference. Trong một câu thật nó gộp `不以为然道` thành idiom token; raw Chinese phải cao hơn parse. Chivi HanLP repo mô tả phrase matching/CON và dependency sense selection; converter/CON engine chưa thực thi trong pilot này.

Nghiên cứu document translation hỗ trợ kiểm tra source-primed segments và long memory nhưng không chứng minh Gemini 3.8 trên truyện này. Xem [research primary sources + code review](batch_benchmark/context_repo_research.md).

## Cải tiến tiếp ở cấp hệ thống

1. Tách source semantic plan và decoder Việt: plan giữ speaker/addressee, attitude đối với câu nào, typed relation, số/đơn vị, phủ định/thời gian và source quotes. Kiểm plan trước khi dùng; không nâng summary/model prediction thành chuẩn.
2. Entity ID + alias, relation valid_from/valid_to, domain-scoped lexicon và active plot state. Quote index hiện có là tầng evidence, chưa thay thế graph đó.
3. Fixed narrator/address/genre canon theo truyện; style seed đã duyệt một lần. Decode whole clause/scene, không chạy replace chuỗi hay dictionary từng từ.
4. Low cho scene nhẹ đã qua calibration; medium cho polysemy/domain/idiom/risk, scene phụ thuộc chạy tuần tự. Model cao hơn trong cùng họ vẫn có cùng bias convert, nên gate văn phong phải độc lập với lời tự chấm của translator.
5. Automatic source/boundary/style checker được kiểm bằng unseen context-dependent corpus; GPT chấm mẫu/calibrate định kỳ. Fail làm đổi contract/segmentation/model, invalidate cache và sinh lại toàn scene phụ thuộc; không publish phần còn lỗi. Sau hai lượt phục hồi vẫn không đạt thì quarantine.

## Artifact và kiểm tra

- [Hướng dẫn chạy và phần còn thiếu](BATCH_WORKFLOW.md).
- [batch_contract.py](batch_contract.py), [story_store.py](story_store.py), [batch_policy.py](batch_policy.py), [prepare_batch_route.py](prepare_batch_route.py), [batch_run.py](batch_run.py).
- [95 tests PASS](batch_benchmark/verification_tests.txt): source/quotes/future visibility, stale/ownership, model attestation, cache provenance, glossary conflicts, source lock, policy rerun/quarantine, native default/explicit API và SQLite persistence/revision. Tests integrity không thay thế semantic/literary measurements.
- [Runtime/candidate hashes và số token](batch_benchmark/final_runtime_verification.json). Usage được ghi từ provider, có CLI/system/cache overhead; không suy chi phí hay rate 10.000 chương từ pilot.

24 jobs hoàn tất; không còn native worker của pilot đang chạy. Bản gốc, chương 1 đã duyệt trước và toàn candidate sai được giữ. Các draft mới không tự đưa vào approved_codex hay đăng BNS.
