# Kiểm tra mẫu ngữ nghĩa Trung–Việt

Ngày kiểm tra: 2026-10-13. Chỉ đọc dữ liệu đã có trong thư mục; không gọi dịch vụ ngoài, không sửa bản gốc/bản dịch. Đây là audit mẫu, không phải chứng nhận toàn bộ 81 chương.

## Phạm vi và nguồn đối chiếu

- Đọc toàn bộ `chap1_raw.txt` và `output_dich/chuong_001_第1章 面试.txt`; đối chiếu các tình tiết chính và một số câu chính xác. Bản `chuong_1_dich_hoan_chinh.txt` cũng có các lỗi nêu dưới đây.
- Đọc bản dịch chương 32, đối chiếu các đoạn gốc trong `prepared_input/chap_032_第32章 法力和体育.txt`.
- Đọc mẫu đầu và trận đấu chương 70, đối chiếu gốc trong `prepared_input/chap_070_第70章 隐藏灵根.txt`.
- Kiểm tra thuật ngữ `法赛` qua chương 38, 51, 52 và `novel_lore.json`.
- Nguồn Trung của prepared_input cũng có nhiễu chữ/dấu câu, vì vậy các kết luận chỉ áp dụng cho bản nguồn cục bộ hiện có. Không đối chiếu trực tiếp website tác giả.

## Lỗi xác nhận bằng cặp câu

### S01 — Chương 70: sai thể thức trận đấu

Nguồn `prepared_input/chap_070_第70章 隐藏灵根.txt:22`: `其中有7个小组都有四名选手，要进行抽签后的两两对决，淘汰至最后一人。`

Đích `output_dich/chuong_070_第70章 隐藏灵根.txt:7`: “chia cặp đấu loại trực tiếp hai chọi hai”. Dòng 9 lặp lại “hai chọi hai”.

`两两对决` ở đây là từng cặp đấu với nhau, không phải hai người đấu hai người. Chính nguồn dòng 92 viết `一对一战斗`, và bản dịch dòng 91 viết “một chọi một”. Lỗi làm thay đổi luật cuộc thi và tạo mâu thuẫn trong cùng chương. Cách sửa: “bốc thăm chia từng cặp đấu một chọi một”.

### S02 — Chương 32: biến suy nghĩ nội tâm thành lời nói

Nguồn `prepared_input/chap_032_第32章 法力和体育.txt:262`: `“零分。”一旁的白真真心中幽幽道：“简直是高中的至高羞辱...”`

Đích `output_dich/chuong_032_第32章 法力和体育.txt:130`: “Bạch Chân Chân ngồi bên cạnh u ám cất lời”.

`心中` chỉ trong lòng. “Cất lời” làm thay đổi điều nhân vật khác có thể nghe. Cách sửa: “Bạch Chân Chân ngồi bên cạnh thầm nghĩ đầy u ám”.

### S03 — Chương 1: sai loại hộp thư điện thoại

Nguồn `chap1_raw.txt:365`: `张羽翻动着手机中的短信箱...密密麻麻的催款短信`.

Đích `output_dich/chuong_001_第1章 面试.txt:393`: “Trương Vũ mở hộp thư thoại ra xem... những tin nhắn đòi nợ”.

`短信箱` là hộp tin nhắn SMS; hộp thư thoại là voicemail. Cách sửa: “mở hộp tin nhắn trên điện thoại”.

### S04 — Chương 1: thêm hành động chưa có trong nguồn

Nguồn `chap1_raw.txt:197`: `她转了1000块钱给张羽，让张羽记得要谢谢同学和老师。`

Đích `output_dich/chuong_001_第1章 面试.txt:221`: “dặn cậu nhớ mua quà cảm ơn thầy cô và bạn bè”.

Nguồn chỉ yêu cầu nhớ cảm ơn, không yêu cầu mua quà. Chi tiết thêm khiến mục đích khoản chuyển tiền bị diễn giải mạnh hơn. Cách sửa: bỏ “mua quà”.

### S05 — Chương 70: thêm tính chất hợp đồng và khảo nghiệm

Nguồn `prepared_input/chap_070_第70章 隐藏灵根.txt:128`: `在这里签下和‘父亲大人’的契约，成为他真正认可的儿子。`

Đích `output_dich/chuong_070_第70章 隐藏灵根.txt:123`: “ký kết bản khế ước bán mạng”. `契约` là khế ước/hợp đồng; câu này không nêu bán mạng.

Nguồn cùng tệp dòng 134: `通过层层考验` (vượt qua tầng tầng khảo nghiệm). Đích dòng 129 thêm “khảo nghiệm đẫm máu”. Đây là thêm thông tin về tính chất sự kiện, vượt khỏi sắc thái châm biếm có trong câu. Không nên dùng quyền biên tập văn phong để thêm các dữ kiện như vậy.

### S06 — Thuật ngữ liên chương: một sự kiện bị gọi bằng hai tên

`novel_lore.json:58` định nghĩa `法赛` → “Pháp Giải”.

- `output_dich/chuong_038_第38章 10级周天采气法.txt:16,18,19` dùng “Pháp Giải”.
- `prepared_input/chap_051_第51章 变化和加码.txt:56,296` và `prepared_input/chap_052_第52章 暗流涌动.txt:288,310` vẫn dùng cùng `法赛`.
- `output_dich/chuong_051_第51章 变化和加码.txt:38,160`, `output_dich/chuong_052_第52章 暗流涌动.txt:148,167` đổi thành “Pháp Tái”.

Hai cách gọi đều có thể hiểu là giải đấu, nhưng lỗi xác nhận là phá chuẩn tên sự kiện đã chọn, ảnh hưởng theo dõi xuyên chương. Cần một bản canonical được phê duyệt và QA phát hiện mọi alias chưa duyệt.

### S07 — Chương 1: mất ranh giới định lượng

Nguồn `chap1_raw.txt:103`: `900克以上` (ít nhất 900 g, có bao gồm 900). Đích `output_dich/chuong_001_第1章 面试.txt:125`: “hơn 900 gram”. Sai lệch nhỏ nhưng cho thấy kiểm số phải giữ cả quan hệ ≥, >, ≤, < chứ không chỉ chuỗi 900. Cùng đoạn `十倍以上` được dịch “gấp mười lần trở lên”, bảo toàn đúng ranh giới này.

## Rủi ro cần quyết định biên tập hoặc kiểm thêm

- `novel_lore.json:26,27` khóa `修仙贷`/`法力贷` thành “Tu Tiên Đới”/“Pháp Lực Đới”. Đó là sản phẩm vay; cách ghi “Đới” không biểu đạt nghĩa vay cho người đọc Việt. Nguồn chương 1 dòng 279 và đích dòng 303 xác nhận thuật ngữ này đi vào bản dịch. Cần chọn tên chuẩn như “khoản vay tu tiên” hoặc tên thương hiệu có chú thích; không tự sửa toàn bộ khi chưa chọn chuẩn.
- Chương 32 nguồn dòng 340 dùng `两百斤重、三百斤重...五百斤重`; đích dòng 213 dùng “hai ba trăm cân...năm trăm cân”. “Cân” có thể bị hiểu là kg trong tiếng Việt hiện đại. Cần quy định giữ đơn vị jin/cân Trung Quốc hay đổi đơn vị trước khi coi đây là lỗi chuyển đổi xác nhận.
- Chương 70 nguồn dòng 270 là ý nghĩ của Hổ Vân Đào ở mạch kể trước/sau, nhưng đích dòng 143 xưng “bà đây”; nguồn mô tả nam là con trai ở dòng 128/134. Đây là cờ sai giọng/ngôi giới tính cần duyệt; lối xưng hô trêu đùa vẫn có thể tồn tại nên không kết luận riêng chỉ dựa vào từ “bà”.
- Đại từ Trương Vũ biến từ “cậu/anh” ở chương 1 sang “hắn” ở chương 32. Việc đổi theo trước/sau xuyên không có thể chủ ý; đổi giữa chương cần quy định giọng kể. Không nên tự đánh lỗi mọi biến thể đại từ.
- `novel_lore.json:14` dùng khóa `周天翼`, trong khi nguồn chương 32 dòng 124 dùng `周天翊`. Đích đều là Chu Thiên Dực; hiện không thấy sai tên Việt tại mẫu này, nhưng khóa chữ Hán không khớp sẽ làm bảo vệ entity thất bại.
- Chương 70 nguồn có `百龙` ở đoạn nói về trường và `白龙` ở đoạn khác; đích đều Bạch Long. Nguồn cũng có nhiễu `来自2` ngắt sang `父亲大人` ở dòng 112–114. Cần audit nguồn/đối chiếu trước khi buộc bản dịch giữ các ký tự nhiễu ấy.

## Chất lượng tiếng Việt và bản thô

Chương 1 đích có “trời chưa háng sáng” (195), “mày chùy nhíu chặt” (225), “âm sầm” (351). Đó là lỗi chữ rõ cần proofreading. Các lỗi này có trong cả bản output lẫn `chuong_1_dich_hoan_chinh.txt`.

`prepared_input/chap_032_第32章 法力和体育.txt:143` có bản thô `Trương 疼痛等级 của Vũ`, dòng 169 có `10价格改成 của 00块钱了1万`, dòng 199 có `Trươ của 而现在ng Vũ`. Đây không phải câu dịch Việt hoàn chỉnh, làm vỡ tên người/số. Nguồn Trung phải là căn cứ tối cao; bản thô này chỉ nên là trợ giúp có thể loại bỏ, không được dùng như evidence của bản dịch đúng.

## Những gì mẫu kiểm đã giữ được

- Chương 1: số thí sinh 989, 5/2/3 giờ, 9 năm/gần một vạn giờ, 36 tầng trên/18 tầng dưới, quá hạn 30 ngày và 3 ngày, nợ hơn bảy mươi vạn, tiền còn hơn 50, ký hiệu một phần mười đều giữ được ở các đoạn đã đọc.
- Chương 32: cấp đau 37, 60 phút, đạo tâm gần cấp 2; giá 1000 → 1万 thành 1.000 → 10.000; tiến độ `(3/160) → (6/160)`; phủ định kép tác dụng phụ và không muốn tiếp tục dùng thuốc được giữ trong mẫu đối chiếu.
- Chương 70: 33 tuyển thủ, 8 bảng, 7 bảng bốn người và 1 bảng năm người, điểm 266, tiền viện phí 60万 được giữ số ở mẫu đối chiếu.

Không có thống kê tỷ lệ chính xác: mẫu do người kiểm chọn theo rủi ro, không ngẫu nhiên, và chưa align từng đoạn toàn bộ 81 chương. Việc giữ số không chứng minh ngữ nghĩa đúng toàn câu; S01 cho thấy số có thể còn nguyên trong khi quan hệ đổi.

## Đề xuất tiêu chí nhận bản dịch

1. Lưu nguồn bất biến và ID đoạn; mỗi đoạn nguồn phải có đoạn đích hoặc lý do loại metadata rõ ràng. Gate độ phủ phải kiểm mapping, không chỉ tỷ lệ độ dài.
2. Khóa entity, thuật ngữ, đơn vị và các con số cùng quan hệ định lượng; bảo vệ tên trước khi phân tích cú pháp bản thô.
3. Audit độc lập phải đọc cặp Trung–Việt và trạng thái lore trước/sau chương. Tách lời nói/thầm nghĩ, chủ thể, phủ định, giả định/chắc chắn, sự kiện thêm/bớt.
4. Mỗi finding phải chứa source span, target span, độ nghiêm trọng, rationale, đề xuất sửa; validator kiểm span thật có trong tệp. Đầu ra thiếu/sai schema hoặc model từ chối không được coi là pass.
5. Khi sửa, giữ bản cũ, lưu patch và audit lại đoạn sửa cùng ngữ cảnh lân cận. Chưa có semantic reviewer thì trạng thái là chưa kiểm, không xuất bản với nhãn đã đạt.
6. Đưa S01–S07 vào regression fixtures; giữ thêm fixture đúng (số chương 32, phủ định kép, tiến độ) để chống cờ giả. Fixtures chỉ chứng minh gate bắt được mẫu cụ thể, không chứng nhận cả kho.
