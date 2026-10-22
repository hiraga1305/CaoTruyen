# Sửa tầng định danh, phân vai và xưng hô — 22/10/2026

Đã sửa code ở máy local, chưa commit/push GitHub. Không dịch lại hoặc sửa bản truyện cũ. Đây là sửa nguyên nhân sinh chỉ dẫn sai cho model, không phải chứng nhận chất lượng ngữ nghĩa toàn truyện.

## Những gì đã thay đổi

1. **Một người, một định danh.** `semantic_profiles.json` nối các tên giản thể/phồn thể bằng alias khai báo rõ. Hai runner 49736 dùng cùng hồ sơ và prompt. `萧羽`/`萧大师` là cùng định danh; cách gọi “Tiêu đại sư” được bảo toàn bằng `surface_vi`. Hai tên Việt giống nhau không tự động bị nhập thành một người. Alias trùng giữa hai người hoặc quy tắc xưng hô nhập thành cùng một người sẽ bị chặn.
2. **Phân vai có căn cứ hoặc UNKNOWN.** Không chọn người đầu danh sách hoặc người còn lại. Nhận dạng một số cấu trúc nói/hỏi trực tiếp trước/sau lời thoại, có trích đoạn làm căn cứ. Câu dẫn kết thúc bằng dấu hai chấm có thể nối sang đoạn kế tiếp. Không mặc định đổi lượt nói, không coi đối tượng đứng sau “đối với/nhìn về/theo…” là người nói. Lời chưa thực sự nói, phủ định, chủ thể là người thân của một người được nêu tên hoặc căn cứ xung đột phải để chưa xác định. Ngoặc kép lồng nhau được giữ thành một khối ngoài hoàn chỉnh.
3. **Bỏ suy đoán ép vai và ép thái độ.** Không còn `[Ø_SHIFT]` gán phản ứng cho người thứ hai, không phát sinh quy tắc `ta–ngươi` từ 找死/受死. Gợi ý ngắt câu vẫn giữ nguyên toàn bộ nội dung nguồn. `state:SOURCE_CONTEXT` yêu cầu đọc sắc thái thực trong nguyên tác.
4. **Xưng hô có chiều và phạm vi.** Thêm `scope`, khoảng chương, cảnh/đoạn và `known_by`/`evidence`, giữ tương thích constructor cũ. Quy tắc có nguồn chỉ được chuyển vào cảnh khi căn cứ có trong nguồn cảnh hoặc ngữ cảnh trước; không dùng nguồn sau để xác lập trạng thái hiện tại. Gợi ý theo đoạn chỉ xuất cho đúng chiều nói/nghe, đúng phạm vi và người biết. `paragraph_id` hiện là mã § cục bộ trong chunk. Các quy tắc cũ được ghi rõ là `editorial_default`, không phải quan hệ bất biến; bỏ ngữ khí/cảm xúc cố định khỏi các mặc định này.
5. **Bỏ dữ kiện cảnh bịa từ cấu hình cố định.** Không luôn đặt nhân vật ở Cửu Giang/tiệm phong thủy, trường thi hoặc luôn đang vận chuyển linh lực. Vị trí, tâm trạng, tác dụng đang diễn ra và người hành động cuối để `UNKNOWN` nếu chưa có dữ kiện. Không đưa tiểu sử/vai trò/cảm xúc không có phạm vi từ seed vào prompt. Gỡ khóa “ông/trưởng bối Khương gia” của Khương Ngọc Lâm; nguồn chương 3 nói đây là anh trai Khương Nhu Giáp.
6. **Prompt theo nguồn và ngữ vực.** Dùng chung `SOURCE_FIRST_V2`; bỏ lệnh cấm đại từ hiện đại và trợ từ cho mọi cảnh tu tiên, bỏ lệnh bắt mọi cuộc thoại dùng cặp Vân–Khương. Truyện 16014 dùng `XIANXIA_MODERN_SCHOOL`. Phân biệt ngôi kể và lời thoại, mẹ–con, học sinh–giáo viên, bạn bè, lời nhại/trích dẫn, ký ức và sự thật. Không thêm biểu cảm, cảm giác hoặc chi tiết cho “hay văn”. Chỉ xuất §1..§N, không yêu cầu delta ngoài schema đang kiểm.
7. **Ngữ cảnh không mất ở ranh giới chunk.** Trước mỗi lần gọi, kể cả khi chia nhỏ sau timeout, lấy lại tối đa bốn đoạn nguồn trước/1.600 ký tự và hai đoạn sau/1.000 ký tự, giữ nguyên từng đoạn. Nguồn trước ưu tiên chương hiện tại; chunk đầu dùng đuôi nguồn chương trước. Đây là ngữ cảnh chỉ đọc, không được dịch thêm hoặc đưa thông tin tương lai vào hiện tại. Khi còn ngân sách, tránh cắt giữa câu dẫn kết thúc hai chấm và lời thoại, hoặc giữa ngoặc thoại đang mở. Giới hạn 20 đoạn/3.200 ký tự vẫn được giữ; chưa phải bộ tách cảnh NLP hoàn chỉnh. Không xóa lời tác giả khỏi phần nguồn cần dịch.
8. **Kiểm tra không giả làm chứng nhận ngữ nghĩa.** Lưu phân vai/căn cứ vào `gate.json`; UNKNOWN và biến thể tên đã biết tạo cảnh báo cần duyệt. Không chặn “anh ta/cô ấy” chỉ dựa vào nhãn thể loại, không áp quy tắc thù địch cho toàn bộ lời thoại trong cảnh. Cảnh báo ngữ vực đô thị cần đối chiếu nguồn thay vì ép sửa. Tắt `SpotAuditor.apply_deterministic_repair()` vốn có thể đổi “không cho là đúng” thành “chẳng để tâm”. Bản nháp vẫn cần review độc lập qua cổng xuất bản hiện có.

Tên chuẩn mới giữ **La Lâm Na** theo lore hiện hành cho 罗琳娜/羅琳娜; ghi nhận Lorina/Lorinna là biến thể cần duyệt, không thay hàng loạt bản cũ. Giữ **Fatina** theo TXT hiện có cho 法緹娜 và **Sophie Chung** cho 蘇菲.鍾. Đây là quy ước biên tập hiện hành, không khẳng định đã chứng minh cách viết Latin duy nhất của tác giả.

## Ví dụ trước/sau

| Nguồn | Hành vi cũ | Hành vi mới |
|---|---|---|
| 姜柔甲对秦疏影说：“你先坐。” | Khương Nhu Giáp → Vân Thiên Phong | Khương Nhu Giáp → Tần Sơ Ảnh |
| 秦疏影對雲千峰說：“我去接孩子。” | Vân Thiên Phong → một alias của chính mình hoặc Khương Nhu Giáp | Tần Sơ Ảnh → Vân Thiên Phong |
| 云千峰对姜柔甲说：“别找死，快回来！” | Tạo HOSTILE, đề xuất ta–ngươi | Giữ đúng hai người; không tự sinh đổi xưng hô |
| Chương 3 §68: lời Tần Sơ Ảnh trả lời về con trai | Router gán nam chính | Người nói Tần Sơ Ảnh từ câu dẫn §67, người nghe UNKNOWN |
| Chương 1 §62: người phụ nữ nói **với** Vân Thiên Phong | Bản regex đầu tiên của đợt sửa vẫn nhận tên người nghe thành người nói | Đã bổ sung hồi quy: người nói UNKNOWN, không gán nam chính |
| Chương 7 §59: Khương Nhu Giáp nhìn Vân Thiên Phong rồi nói | Tên sau “nhìn” dễ bị gán làm người nói | Đã bổ sung hồi quy: không gán Vân Thiên Phong; để model/reviewer đọc toàn mạch |
| Chương 126 §72: Tần Sơ Ảnh vừa **theo** Vân Thiên Phong chạy vừa hỏi | “Theo” có thể bị nhầm là “nói với” | Không coi đi theo là bằng chứng xác định người nghe |

Hai lỗi phát hiện thêm trên nguồn thật được đưa vào kiểm thử và script tái hiện. Không coi việc giải được ví dụ tổng hợp ngắn là đủ chứng minh xử lý đúng truyện thật.

## Kiểm chứng

- Suite: **206/206 test qua**, gồm 41 test mới cho ngữ nghĩa/ngữ cảnh, các kiểm thử an toàn trước đó và mock cả bốn hàm dựng scene thật. Không gọi model/API.
- Sửa các kỳ vọng test cũ từng buộc chuyển chủ ngữ không có căn cứ, sinh `ta–ngươi` từ từ khóa hoặc cấm đại từ theo nhãn thể loại. Các kiểm thử không được dùng để đo tỷ lệ bản dịch đúng nghĩa.
- Replay **325 chương, 31.034 đoạn nguồn, 1.728 chunk**. Không có đoạn vượt ngân sách và không mất/lặp đoạn thuộc chunk trong replay.
- Nhận dạng **7.504 khối ngoặc kép ngoài hoàn chỉnh trong từng đoạn**; không đồng nghĩa với tổng số lượt thoại thực trong truyện. Cấu trúc trực tiếp trong phạm vi nhận dạng cho **468 gợi ý người nói**, chỉ **3 gợi ý đủ cả hai người**; **7.501 khối còn thiếu ít nhất một vai**. Đây là độ phủ của heuristic, **không phải tỷ lệ dịch sai**, cũng không phải điểm chính xác. Không có cặp hai tên thực chất là cùng định danh được khẳng định.
- 16 đoạn song ngữ cũ vẫn khớp nguyên văn nguồn hiện tại. Replay các đoạn này chỉ đánh giá chỉ dẫn phân vai, không sinh một bản dịch mới.
- Hash của **1.087 file** trong `sources/`, `output_dich/`, `dist/` của ba sách giữ nguyên trước/sau replay; `git diff` không có thay đổi dữ liệu truyện trong các thư mục đó.
- Cổng xuất bản vẫn từ chối bản chưa được review nguồn–đích. Đủ ID/cấu trúc không tự trở thành semantic PASS.

Lệnh tái hiện:

```powershell
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -q
.\.venv\Scripts\python.exe -X utf8 audit/replay_semantic_context_20261022.py
git diff --check
```

Chi tiết máy đọc được: [semantic_context_fix_20261022.evidence.json](semantic_context_fix_20261022.evidence.json).

## Giới hạn còn lại

Regex bảo thủ chưa giải được phần lớn người nói/nghe từ đại từ, lời gọi tắt, vai mẹ–con hoặc đối đáp dài. Model dịch và reviewer phải đối chiếu nguồn lân cận, không tuân một nhãn UNKNOWN như kết luận cuối. Các gợi ý nhận dạng được cũng vẫn có thể sai ở câu phức; chúng không có quyền ghi quan hệ vào kho sự thật hoặc duyệt xuất bản.

Chưa xây một đồ thị tri thức có phiên bản đầy đủ cho 325 chương; hiện bỏ tiểu sử không có phạm vi khỏi prompt và hỗ trợ gợi ý xưng hô cục bộ có căn cứ. Không tự suy ra sự thật từ ký ức/lời nhân vật, không tự ghi chuyển quan hệ lâu dài. Chưa có bản dịch mới sau sửa để đo mức cải thiện của model. Các lỗi La Lâm Na/Lorina, ngôi xưng và đoạn thiếu trong bản cũ vẫn cần một lượt xử lý riêng có review; bản sửa này không làm chúng tự biến mất.
