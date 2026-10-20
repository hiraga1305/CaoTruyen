# Kết quả crawl → dịch → GPT Codex audit, 13/10/2026

Đã thử thực tế Antigravity CLI với phiên OAuth đã đăng nhập, cào chương 1 Piaotia, chạy parser Trung thật, tạo bản dịch native và kiểm lại bằng GPT trong Codex. Hai GPT session độc lập đã kiểm toàn bộ 192 đoạn; sau sửa 19 đoạn, cả hai kiểm lại và PASS. Đây là kết quả một chương, không phải chứng nhận toàn bộ truyện hay độ chính xác 100%.

## Bản giao

- [Bản dịch chương 1 đã duyệt](approved_codex/chapter_0001_d469016d2ce9.txt): 192 đoạn; bản nháp Antigravity được giữ nguyên.
- [QA cuối](codex_audit/final_qa.json), [evidence](approved_codex/chapter_0001_d469016d2ce9.evidence.json), [publication manifest](approved_codex/chapter_0001_d469016d2ce9.publication.json).
- [19 sửa đổi có nguồn, trước/sau](codex_audit/edit_manifest.json).
- [GPT semantic review cuối](codex_audit/semantic_review.final.json) và [GPT literary review cuối](codex_audit/literary_review.final.json).
- [Audit mã nguồn](codex_audit/pipeline_audit.md), [kết luận tái kiểm và giới hạn](codex_audit/pipeline_audit.addendum.md).
- [Context cho chương 2](approved_codex/context_chapter_0002.json): đã tạo từ evidence và xác thực chuỗi continuity.
- [49 bài kiểm tra PASS](verification_tests.txt), gồm chặn thiếu kiểm văn phong, review cũ sau sửa, trùng session, thiếu chiều ngữ nghĩa và nguồn sai.

## Các lỗi GPT tìm thấy

Hai reviewer đọc độc lập nguyên văn Trung và bản nháp. Lỗi đáng chú ý: 两万 (20.000) bị đổi thành 20 triệu đồng; “ít nhất 900 g” thành “hơn 900 g”; quan hệ xã hội thành năng lực giao tiếp; 学杂费 thành phí tạp vụ; bỏ đối tượng sinh viên tốt nghiệp. Audit văn phong còn bắt câu convert, lời chào không tự nhiên, thêm vị trí túi áo hoặc tiếng thở dài không có trong nguồn. Tổng cộng 19 đoạn được sửa; 173 đoạn khác giữ nguyên. Không chỉ sửa số mà còn sửa tác nhân, đối tượng, quan hệ, phạm vi nghĩa và giọng văn.

Reviewer là `/root/gpt_semantics` và `/root/gpt_literary_audit`, chạy bằng GPT kế thừa trong Codex. Hai session cùng loại GPT được ghi trung thực `codex/gpt-inherited`; không có bằng chứng để gán tên phiên bản GPT cụ thể hoặc tuyên bố dùng hai họ model khác nhau. Review được khóa bằng source/package/candidate hash; sửa bản dịch làm review cũ mất hiệu lực. Attestation dựa trên phiên worker do điều phối viên thực sự chạy, không phải cơ chế chống giả mạo JSON.

## Antigravity, parser và thể loại

CLI đã dùng tài khoản OAuth lưu sẵn; subprocess bỏ biến API key và không đọc/copy token. Runtime coordinator và hai subagent crawl/research có trong [events](runs/research_claude/events.jsonl). Translator chương đầy đủ thực tế là `claude-sonnet-4-6`, conversation `d6d428fe-a468-4f88-a8c0-431bbd9d74ec`. Sau yêu cầu của người dùng, review cuối được chuyển sang Codex; native reviewer không làm căn cứ duyệt.

Đã kiểm chứng các repo chính chủ online, ghi commit/hash tại [repositories.json](research/repositories.json): [Chivi hanlp_mt](https://github.com/chi-vi/hanlp_mt), [Chivi ltp-dep-to-con](https://github.com/chi-vi/ltp-dep-to-con), [Chivi ltp-onnx](https://github.com/chi-vi/ltp-onnx), [HanLP](https://github.com/hankcs/HanLP), [LTP](https://github.com/HIT-SCIR/ltp). Lựa chọn đã chạy thực tế là LTP/small safetensors, revision `dea87bf0da3c5d054bbd426a78d7fa9efd347799`, kiểm hash trọng số.

[Phân tích 192 đoạn](research/chapter1_ltp_analysis.json) có CWS/POS/NER/SRL/DEP/SDP, không cắt ngầm đoạn. Cây DEP là kết quả dự đoán cú pháp; chưa chạy bộ chuyển CON của Chivi và không gọi DEP là cây ngữ nghĩa chuẩn hoặc CON. Nguyên văn luôn cao hơn parser. LTP module báo 4.2.13, distribution metadata 4.2.14; addendum ghi rõ chênh lệch này. Môi trường parser riêng dùng transformers tương thích, không đổi bộ thư viện global.

[Profile thể loại](genre_profiles.json) tách tiên hiệp, hiện đại và cyberpunk tu tiên. Hai fixture tự soạn, mỗi thể loại bốn đoạn, đã thực sự dịch bằng native Gemini và [GPT kiểm lại](codex_audit/genre_fixture_audit.final.json); cả tám đoạn cuối PASS ở phạm vi fixture. Đây không phải hai truyện cào hoàn chỉnh. Bản hiện đại đã sửa 件 thành sản phẩm, giữ ranh giới >=900 và diễn đạt trạng thái chưa nhận lời đúng bối cảnh.

Tiêu chí văn phong dựa trên hướng dẫn công khai của [Bạch Ngọc Sách](https://bachngocsach.cc/forum/threads/5069/) và [hướng dẫn dịch](https://bachngocsach.cc/forum/threads/32905/): đủ nghĩa, tiếng Việt tự nhiên, xưng hô đúng, thuật ngữ nhất quán, tránh convert. Một số trang diễn đàn trực tiếp yêu cầu đăng nhập; không tuyên bố xác minh toàn bộ quy định hiện hành hoặc được BNS chứng nhận.

## Những gì còn giới hạn

- 81 bản dịch cũ vẫn là tài liệu chưa duyệt; kết quả chương 1 mới không tự nâng chúng thành PASS.
- HTML chương tải thực tế khớp 192 đoạn prepared khi tách lại offline; không chứng minh nguồn web đầy đủ so với bản tác giả.
- Hai lượt GPT có thể cùng bỏ lọt lỗi. PASS phản ánh kiểm tra đã thực hiện và evidence, không phải bảo đảm tuyệt đối.
- Pilot native từng tiêu tốn nhiều context và gặp quota Opus. Gemini review bị dừng theo yêu cầu chuyển review sang Codex; NO_RESULT không tự chứng minh hết quota. Tra cây theo tối đa tám id mỗi lần đã thay cách dump toàn cây. Có timeout nhưng chưa có hard cumulative token watchdog cho native; không chạy hàng loạt không giới hạn.
- Chỉ xuất file local, chưa đăng lên BNS. Bản gốc, bản nháp, nguồn, sửa đổi và review đều được giữ để audit lại.
