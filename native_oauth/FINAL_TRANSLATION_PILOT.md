# Phép so sánh cuối LOW/MEDIUM/HIGH — 26/10/2026

Chạy độc lập trong Antigravity. Codex chỉ sửa và kiểm thử offline trong lượt này.
Không dùng `book_siwangyouxi/run_low_vs_medium_pilot.py` để chạy mới: runner cũ đã nghỉ, giữ lại để đọc bằng chứng lịch sử.

## Hai phần, không gộp số liệu

1. **Đường vận hành thật:** cùng chương 1–20, ba sách tạm tách biệt; mỗi wave 5 chương, hai worker dịch và một lane review có thứ tự. Hai reviewer MEDIUM dùng phiên riêng; wave auditor MEDIUM. A dịch LOW, B dịch MEDIUM, C dịch HIGH; sửa cùng model của arm, tối đa hai vòng. Chạy B rồi A rồi C, lần lượt, không chạy ba arm đồng thời. Giữ gate của `revise_book.run_campaign`, `semantic_gate` và `wave_review`; context chỉ kế thừa revision đã duyệt. Nháp song song vẫn có generation receipt riêng. Đo đến approval bản cuối và PASS đủ bốn wave, không xuất sách.
2. **Đoạn khó ở xa:** dịch, sửa thật và hai review cho chương 1622, 1975, 1978 ở cả A/B/C. Gửi đủ chương nguồn và nguyên văn hai chương trước, không dùng tóm tắt hardcode hoặc nguồn tương lai. Chỉ là `DIAGNOSTIC_PASS_NOT_APPROVAL`, không tạo approval/manifest và không thay thế tiền tố hơn nghìn chương đã duyệt. Thời gian và token báo riêng, không đưa vào throughput đường vận hành.

Chỉ chạy stress sau khi cả ba arm đã kết thúc COMPLETE hoặc BLOCKED; arm nào BLOCKED thì bỏ qua stress của arm đó và ghi rõ thiếu dữ liệu. Chọn cấu hình chỉ từ các arm hoàn thành đầy đủ điều kiện, không coi arm thiếu dữ liệu là thắng tốc độ.

Nguồn ở bộ này có tiêu đề tách khỏi thân bài. `metadata_title_source` kiểm lại `.name` CZBooks hoặc `h1.page-d-name` ixdzs8 trong HTML đã lưu; dịch thành `title_vi` và hai reviewer trả `metadata_title_review`. Không thêm đoạn vào nguồn hoặc đổi ID cũ. Gate xuất đối chiếu đúng title_vi đã được review. Những sách đã có heading trong segments giữ cách xử lý hiện hành.

## Lệnh

Chạy tại repository root với `.venv/Scripts/python.exe -X utf8 -m native_oauth.final_translation_pilot`.

```powershell
# Offline: tạo mới thư mục, sao chép nguyên byte nguồn, khóa code/canon/nguồn.
.venv/Scripts/python.exe -X utf8 -m native_oauth.final_translation_pilot prepare --out audit/pilot_siwangyouxi_low_medium_high_20261026 --chapters 20

# LIVE: chỉ chạy trong phiên Antigravity đã được người dùng yêu cầu pilot.
# Trước đó bind ANTIGRAVITY_ARTIFACT_DIR hoặc ANTIGRAVITY_CONVERSATION_ID
# theo phiên hiện tại thật; không dùng ID từ pilot cũ.
.venv/Scripts/python.exe -X utf8 -m native_oauth.final_translation_pilot run --out audit/pilot_siwangyouxi_low_medium_high_20261026 --arm B
.venv/Scripts/python.exe -X utf8 -m native_oauth.final_translation_pilot run --out audit/pilot_siwangyouxi_low_medium_high_20261026 --arm A
.venv/Scripts/python.exe -X utf8 -m native_oauth.final_translation_pilot run --out audit/pilot_siwangyouxi_low_medium_high_20261026 --arm C
.venv/Scripts/python.exe -X utf8 -m native_oauth.final_translation_pilot stress --out audit/pilot_siwangyouxi_low_medium_high_20261026 --arm B
.venv/Scripts/python.exe -X utf8 -m native_oauth.final_translation_pilot stress --out audit/pilot_siwangyouxi_low_medium_high_20261026 --arm A
.venv/Scripts/python.exe -X utf8 -m native_oauth.final_translation_pilot stress --out audit/pilot_siwangyouxi_low_medium_high_20261026 --arm C

# Offline: báo cáo cả các lượt lỗi; seal vẫn dùng được khi BLOCKED để bàn giao.
.venv/Scripts/python.exe -X utf8 -m native_oauth.final_translation_pilot report --out audit/pilot_siwangyouxi_low_medium_high_20261026
.venv/Scripts/python.exe -X utf8 -m native_oauth.final_translation_pilot seal --out audit/pilot_siwangyouxi_low_medium_high_20261026
```

Nếu thư mục đã được chuẩn bị, không gọi prepare lần nữa. Nếu sửa code/canon/nguồn sau freeze, tạo experiment mới; không cập nhật hash để hợp thức hóa kết quả cũ. Không pull/reset/checkout đè workspace đang có thay đổi. Không thay `max_workers`, model hoặc gate giữa ba arm.

`run` không gọi model lại với arm đã COMPLETE. Resume giữ job và tính tổng thời gian mọi invocation, ghi khoảng dừng qua timestamp; process chết trước khi ghi thời gian cuối phải được chẩn đoán, không đoán số. Stress không tự lặp lại một lần chạy đã có kết quả. Native timeout/quota/permission không trở thành danh sách lỗi rỗng hoặc PASS. Semantic FAIL chỉ sửa qua candidate mới; không hỏi lại cùng bản để lấy PASS. Hai vòng sửa hết mà còn lỗi thì giữ BLOCKED. Gate wave FAIL cũng giữ BLOCKED và source-bound diagnostics, không được chạy lại tùy ý để đổi verdict.

## Bằng chứng và tiêu chí đọc

- `experiment.json`, `experiment.sha256`, `workflow_snapshot/`, `input_archives/`: điều kiện đóng băng. Chuẩn bị snapshot không thuộc thời gian native; giống nhau giữa ba arm.
- `A|B|C/invocations.json`, `measurement.json`, `job/`: wall time, mọi native attempt, prompt, events, runtime, candidate/revision, review, wave review và approved manifest của sách tạm.
- `A|B|C/stress_job/`, `stress_result.json`: chẩn đoán ở xa; không phải approval.
- `metrics.json`, `chapter_metrics.csv`, `native_calls.csv`: tốc độ bản cuối được duyệt; tổng worker time có nhãn riêng. Token thiếu là null; không cộng thinking thêm lần nữa vào total đã do runtime cung cấp.
- `blinded_final/`: cùng nguồn và ba bản cuối X/Y/Z, không ghi model. `comparison_key.json` chỉ mở sau khi chốt đánh giá; không gửi key hoặc review trước cho người đánh giá mù.
- `final_quality_comparison.md/json`: người điều phối ghi kết quả đọc bản cuối và bảng lỗi còn sót có quote đúng ID, phân biệt lỗi nghĩa với lựa chọn văn phong; không tự sinh điểm chất lượng từ số findings.
- `manifest.json` và ZIP nằm cạnh thư mục experiment. Seal sau khi đã thêm báo cáo chất lượng. Không sửa bản ZIP đã niêm phong.

Chỉ chọn cấu hình khi: đủ 20/20 approval và bốn wave PASS; ba stress case đều có bản cuối qua hai review; đối chiếu cuối không còn lỗi nghĩa major/critical đã xác nhận. Hai native PASS vẫn không chứng minh hết lỗi; có lỗi mới thì kết luận chưa đạt, không sửa điểm hoặc giảm gate. Không tự duyệt toàn bộ 2.115 chương bằng kết quả 20 chương đầu. Không lấy tỷ lệ đếm raw findings làm tỷ lệ cải thiện chất lượng.

Quyết định theo ba trục: chất lượng nghĩa/văn phong của bản cuối, approved source chars/hour và tài nguyên/tỷ lệ sửa thực tế. So cả bản nháp ban đầu với bản cuối để thấy HIGH có giảm công sửa đủ bù thời gian suy luận hay không; không chọn chỉ theo số lỗi reviewer tìm được. Chỉ so tốc độ khi hoàn thành cùng khối lượng. Cấu hình bị trội cả về chất lượng lẫn thời gian/tài nguyên được đánh dấu ít lợi thế. Chênh lệch tốc độ dưới 20% trong một lượt chạy chỉ là lợi thế nhỏ, không phải kết luận thống kê. HIGH đáng dùng đại trà khi có cải thiện chất lượng có dẫn chứng hoặc giảm đủ sửa/retry để tổng luồng cạnh tranh; nếu lợi ích chỉ ở cảnh khó, có thể đề xuất HIGH cho cảnh đó, nhưng phải ghi cấu hình kết hợp chưa được đo trong pilot này. Khi chất lượng cuối ngang nhau, ưu tiên throughput và tài nguyên toàn luồng tốt hơn. Có thể kết luận INCONCLUSIVE, không mặc định mức nào thắng.

Token chỉ là tài nguyên sử dụng, không tự suy thành tiền nếu không có billing hoặc đơn giá đúng model. Một lượt B → A → C còn ảnh hưởng thứ tự/cache/quota; nêu rõ giới hạn đó. Chưa có dữ liệu giai đoạn muộn để cam kết số giờ cho toàn sách, và không mở rộng lên nhiều worker từ kết quả ba slot này. Experiment hai mức trước được giữ nguyên; không ghép log cũ với HIGH mới rồi gọi là phép so sánh có kiểm soát.
