import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from semantic_gate import digest, CHECKS, validate_review, validate_package

RUN = ROOT / 'native_oauth/pilot_workspace/native_oauth/runs/chapter1'
source = json.loads((RUN / 'source.json').read_text(encoding='utf-8'))
draft = json.loads((RUN / 'draft.json').read_text(encoding='utf-8'))
OUT = Path(__file__).resolve().parent

# Các nhận xét được viết sau khi đối chiếu riêng toàn bộ 192 cặp, không dùng peer reviews.
issue_specs = [
    (5, 'low', 'Thêm vị trí cất điện thoại “vào túi”; nguồn chỉ nói cất điện thoại, không xác định túi.', 'Nhìn tin nhắn mẹ gửi trên màn hình, Trương Vũ lặng lẽ cất điện thoại, hít một hơi thật sâu, nhắm mắt lại, yên lặng chờ đợi.'),
    (9, 'medium', '“Ba thầy cô chào” đảo lời chào sai cú pháp tiếng Việt; người được chào bị đặt thành chủ thể chào.', 'Cậu nhìn ba giám khảo, nở nụ cười lịch sự đã luyện tập từ lâu: "Em chào ba thầy cô, em là Trương Vũ đến từ Trường cấp hai Đông Dương."'),
    (11, 'medium', '贵校 là cách kính xưng trường của bên được nói tới; “Trường ta” đổi thành trường của phía người nói đang chưa nhập học.', 'Trương Vũ: "Quý trường có lịch sử lâu đời, nền tảng vững chắc, nguồn lực giảng dạy phong phú, từ trước đến nay đã đào tạo nhiều nhân tài xuất sắc cho xã hội…"'),
    (14, 'medium', '全科 chỉ tất cả các môn học; “toàn khoa” chỉ khoa/đơn vị học thuật, sai đối tượng điểm tối đa.', 'Giám khảo khẽ mỉm cười, nhìn hồ sơ trên tay rồi nói: "Ừ, đạt điểm tối đa ở tất cả các môn, đứng nhất toàn trường? Bảo sao được giới thiệu đến đây."'),
    (37, 'high', '纸篓 là sọt đựng giấy bỏ/thùng rác giấy; “thùng giấy” thành vật chứa bằng giấy, làm mất hành vi vứt hồ sơ vào rác và cú châm biếm “dự phòng”.', 'Nói xong, ông ta ném hồ sơ của Trương Vũ vào sọt rác giấy bên cạnh, chen cùng mấy trăm bộ hồ sơ dự phòng khác.'),
    (43, 'medium', '促智剂 là chất tăng cường khả năng nhận thức/trí não; “chất xúc tác trí tuệ” gán khái niệm xúc tác không có trong nguồn.', 'Để tôi giới thiệu các phúc lợi ở đây nhé. Chúng tôi thêm chất tăng cường trí não vào nước uống, đảm bảo học sinh luôn duy trì trạng thái tập trung cấp năm.'),
    (44, 'high', '900克以上 bao gồm mốc 900 gram, khác “hơn 900”; 十倍以上 là hiệu quả bằng ít nhất mười lần ban đầu, cần tránh “cao hơn trước mười lần” dễ thành tăng thêm mười lần.', 'Mỗi ngày, giáo viên chủ nhiệm sẽ phát cho các bạn từ 900 gram thực phẩm bổ sung chuyên dụng cho ngưu yêu trở lên, đảm bảo hiệu quả tu luyện của các bạn đạt ít nhất gấp mười lần ban đầu.'),
    (65, 'medium', '“Năm nghìn quỹ dự phòng” đặt lượng tiền trước tên khoản tiền thành năm nghìn quỹ; phải thể hiện đây là một khoản tiền trị giá 5.000, không thêm đơn vị chưa được nguồn nêu.', 'Tiếp đó, cậu nhận được một tin nhắn từ bên kia: Khoản tiền dự phòng 5.000 của bạn đã sẵn sàng, chỉ cần mười giây là có thể chuyển vào tài khoản…'),
    (66, 'medium', '小贷 phân loại theo khoản vay nhỏ; “vay tiêu dùng” phân loại theo mục đích chi tiêu, không được nguồn xác định.', '"Quảng cáo cho vay nhỏ lẻ à?"'),
    (90, 'medium', '好人缘 là được mọi người quý mến/có quan hệ tốt; “khả năng giao tiếp tốt” chuyển kết quả quan hệ thành một kỹ năng chưa được nêu.', 'Người mẹ vui vì con chăm chỉ, càng vui hơn khi thấy cậu được mọi người quý mến và thể hiện xuất sắc ở lớp luyện thi.'),
    (103, 'critical', '两万块钱 là 20.000 đơn vị tiền, không phải 20.000.000; sai một nghìn lần và phá tương quan khoản tiền với các con số còn lại.', 'Từ hai ba nghìn đến bảy tám nghìn… lần cuối cùng cậu còn bảo bà chuyển thẳng hai vạn đồng, Trương Vũ nói đó là phí thuê Thiên Linh Căn.'),
    (105, 'medium', '学杂费 là các khoản phụ thu/tạp phí học đường; “phí tạp vụ” thành tiền cho công việc tạp vụ, sai loại chi phí.', 'Người mẹ vô cùng mừng rỡ, tự hào về sự nỗ lực và tài năng của con. Những khoản học phí, phụ phí học tập, phí thuốc cùng các khoản khác mà Trương Vũ nói tiếp đó, bà đều nhận lời ngay.'),
    (111, 'medium', '“Những khoản chi tiêu ... được trân trọng” sai kết hợp chủ thể-vị ngữ; 赏识 nói việc cậu được đánh giá cao nên được hỗ trợ, không phải khoản chi được trân trọng.', 'Hơn một năm qua, mọi khoản chi trong quá trình học tập đều chẳng có chuyện miễn phí, được ưu ái hay được tặng như cậu vẫn nói… Toàn bộ tiền đều đến từ những khoản cậu vay trên các nền tảng lớn.'),
    (120, 'medium', '前功尽弃 là mọi công sức trước đó đổ sông đổ biển; “trắng tay từ đầu” chuyển sang mất của cải và gây hiểu sai về kết quả tu luyện.', '"Mẹ ơi, thuốc này không thể ngừng được. Ngừng thuốc thì đạo tâm sẽ thụt lùi, mọi công sức trước đây của con sẽ đổ sông đổ biển…"'),
    (122, 'medium', 'Nguồn phân biệt lớp luyện thi với 学校老师, thầy ở trường chính khóa; draft bỏ “ở trường” khiến nơi dạy công pháp không còn rõ trong cảnh đang nói lớp luyện thi.', '"Thẻ VIP của lớp luyện thi này phải nạp tiền rồi, không thì con không hiểu được công pháp thầy ở trường giảng trên lớp…"'),
    (149, 'medium', 'Dấu phẩy trong “Bây giờ ta, đã trở thành…” tách chủ ngữ khỏi vị ngữ do bê dấu ngắt nguồn sang tiếng Việt. Đổi “ta” thành “mình” trong câu sửa là đề xuất thống nhất giọng, không phải riêng đại từ “ta” đã làm sai nghĩa.', '"Giờ mình đã trở thành Trương Vũ của một thế giới khác rồi."'),
    (162, 'low', 'Nguồn chỉ tả bất lực ngồi xuống giường; draft thêm hành động “thở dài” không có chứng cứ.', 'Trương Vũ bất lực ngồi phịch xuống giường.'),
    (177, 'medium', '“Mua thuốc học thêm” không tách hai hành động 吃药 và 补课, dễ đọc thành loại thuốc học thêm; “lấy vay nuôi vay” còn nguyên cấu trúc Hán, cần diễn đạt vòng vay mới trả khoản vay cũ.', '"Thằng này đã bắt đầu vay tiền học thêm từ trước khi vào cấp ba. Sau khi vào Trường cấp ba Tung Dương, để theo kịp thành tích của mọi người, hắn lại nảy ra một sáng kiến: vay khoản mới trả khoản cũ để nâng cao thành tích, vay tiền khắp nơi để dùng thuốc và học thêm, ép tiềm năng bộc phát. Kết quả, không những tiền vay ngày càng nhiều mà tiềm năng cũng dần bị vắt cạn."'),
]

pass_notes_text = '''
1|Tiêu đề chương và sự kiện phỏng vấn được giữ đúng.
2|Câu hỏi mẹ gửi ngắn gọn; dấu ngoặc được nguồn dùng, p0005 xác nhận là SMS.
3|Giữ lời trấn an, thành tích tốt và sự chắc chắn của mẹ.
4|Đủ việc làm thêm mới, tiền phẫu thuật và lời bảo con yên tâm phỏng vấn.
6|Giữ việc chờ rồi nghe gọi số; thời lượng được diễn đạt khái quát, không đảo thứ tự.
7|Tên Trương Vũ và số thí sinh 989 đúng.
8|Giữ hành động đứng dậy, bước vào nơi phỏng vấn; “phòng” là cách diễn đạt gọn chấp nhận được.
10|Giám khảo giữa hỏi lý do ứng tuyển; thầy/em đúng cảnh, câu hỏi hơi sát cấu trúc Hán nhưng rõ nghĩa.
12|Giữ nhíu mày, ngắt lời và từ chối lời sáo rỗng.
13|Giữ mục tiêu đại học danh tiếng và so sánh tỷ lệ tuyển sinh trong các trường có thể ứng tuyển.
15|Giữ quan hệ điểm nội bộ tốt nhưng chưa đủ nhập học, không xóa phủ định.
16|Giữ suy nghĩ rồi hỏi về thời gian ngủ; cách nói “tùy tiện” có thể nhuận sắc nhưng không đổi nghĩa chính.
17|Thí sinh trả lời năm tiếng, đúng người nói và con số.
18|Giữ sự ngạc nhiên của giám khảo và lặp lại năm tiếng.
19|Đúng mốc từ tiểu học, trung bình không quá hai giờ; giữ mức khái quát “về cơ bản” của nhóm xuất sắc.
20|Giữ năm giờ, thiếu ba giờ/ngày, chín năm và gần một vạn giờ; không tự sửa phép tính tác giả.
21|Giữ ngỡ mình cố gắng và nhận ra khoảng cách cố gắng với người khác.
22|Giữ lời hứa cố gắng bắt kịp, xưng em hợp cảnh phỏng vấn.
23|Đúng giám khảo trái hỏi phần chương trình cấp ba đã học.
24|Giữ bình tĩnh lại, tự tin và tự học xong lớp mười.
25|Giữ vẻ không hài lòng và tiền đề học hết cấp ba trước khi vào học.
26|Giữ thông tin chưa biết và lợi thế lập tức thành bất lợi.
27|Đúng thời điểm bối rối, giám khảo giữa tiếp tục đặt câu hỏi.
28|Đủ mục tiêu, toàn bộ học sinh, trước nhập học, cắt cơ quan và triệt sản; không làm nhẹ tình tiết.
29|Giữ câu hỏi xác nhận biết yêu cầu trước đó.
30|Giữ gia đình đang chuẩn bị, lời chắc chắn mổ trước nhập học và mức hormone tối ưu.
31|Giữ gật đầu không rõ thái độ, kết thúc phỏng vấn và bảo thí sinh ra ngoài.
32|Giữ lo lắng và cảm giác “có vẻ” thời gian phỏng vấn ngắn hơn.
33|Giữ lời phán xét chưa triệt sản ở cấp hai và tâm hướng đạo; giọng đạo đức giả vẫn còn.
34|Đủ thiếu báo cáo/điểm ngoại khóa, chất lượng giảm và điều kiện hỗ trợ; không đổi người nói.
35|Giữ thiên kiến người nghèo phải cố gắng hơn và khả năng kỳ vọng quá cao.
36|Giữ nhãn “dự phòng” tạm thời; cần đọc cùng hành động ở p0037.
38|Giữ nhận định chưa chắc thất bại, thiếu thời gian suy nghĩ và chuỗi phỏng vấn trường khác.
39|Giữ hoàn cảnh có lẽ không đủ học phí, ưu đãi vay và điều kiện thế chấp cơ quan.
40|Đủ nữ sinh/nam giới, phẫu thuật chuyển giới, học sinh nòng cốt và Nguyên Âm Luyện Khí Chi Thuật.
41|Đủ thiếu chuẩn chút ít, chính sách năng khiếu, bỏ nhục thân và học trong Vạn Hồn Phiên.
42|Giữ lời chào hàng cho thiên tài bình dân; mở một lượt thoại kéo dài đến p0047 như nguồn.
45|Giữ chất kích thích trong hệ thống không khí, không cần ngủ và lời quảng cáo miễn phí.
46|Đúng điều kiện cải tạo tại bệnh viện chỉ định để chịu được thuốc; nhịp quảng cáo đi tới bẫy phí.
47|Đủ cấy pháp khí nhỏ, tăng chuyển hóa và đưa bảng giá; kết thúc lượt thoại kéo dài.
48|Giữ nhịp lặp các cuộc phỏng vấn và câu hỏi.
49|Giữ lựa chọn rào cản quá cao khiến mất hy vọng.
50|Giữ lựa chọn hợp đồng nhiều bẫy, hình ảnh bị nuốt chửng không được tô thêm.
51|Giữ cảm giác bị đè đến ngạt thở trước toàn bộ trải nghiệm.
52|Đủ nhất trường cấp hai ngoại ô và khoảng cách trời vực đã tồn tại với học sinh trung tâm.
53|Giữ mới thấy một phần nhỏ khoảng cách; hình ảnh phần nổi tảng băng phù hợp.
54|Giữ tính nhận định “xem chừng” của công sức thành trò cười.
55|Giữ đối chiếu bạn học không chăm học và cùng không vào cấp ba; cách diễn đạt gọn chấp nhận được.
56|Giữ về nhà và ngồi lặng như tượng.
57|Giữ điện thoại trên bàn rung liên tục.
58|Nhãn Mẹ xác định tin nhắn, hỏi kết quả phỏng vấn đúng.
59|Tin mẹ làm thêm giờ, con tự hâm cơm; “cơm” dùng nghĩa bữa ăn hợp tiếng Việt.
60|Giữ một lúc sau điện thoại rung thêm một lần.
61|SMS giữ cả hai lựa chọn triệt sản/chuyển giới và mẹ chắc chắn gom tiền.
62|Giữ không nhìn điện thoại, nhìn trần và không thể suy nghĩ tương lai.
63|Giữ điện thoại lại rung mạnh vào đúng lúc đó.
64|Đủ không muốn nghe, hơn một phút, cầm lên và phía kia đã ngắt máy.
67|Tiếng hừ ngắn đúng nguồn; không gán thành hành động khác.
68|Nguồn ghi nghĩ thầm; draft giữ nghĩ thầm và khả năng hồ sơ bị bán, không đổi thành sự thật xác nhận.
69|Đủ đặt xuống rồi cầm lại, mở lại tin nhắn sau ít lâu.
70|Dấu lược chuyển cảnh được giữ.
71|Đúng đêm mẹ tăng ca về, vẻ phục hồi chưa chắc chắn và ngồi đọc sách.
72|Con trấn an mẹ, không dễ bị đánh gục; xưng mẹ/con đúng.
73|Giữ năm nay thất bại thì thi lại năm sau, quyết tâm tu tiên.
74|Giữ ngày mai tìm lớp và bổ sung từng phần thiếu; có thể làm câu gọn hơn nhưng không thiếu nghĩa.
75|Giữ sáng sớm hôm sau đi, tối cùng ngày vui vẻ về.
76|Giữ lớp tiên đạo, giáo viên từ trường trọng điểm và lời đảm bảo đỗ cấp ba.
77|Đủ miễn tạm, điều kiện đỗ Tung Dương năm sau, không hoàn lại và quảng cáo; lời nhân vật không thành sự thật narrator.
78|Giữ niềm tin công ty lớn không lừa, là lời con nói.
79|Đúng lịch đi trước bình minh, về đêm và học đến hai ba giờ.
80|Đúng lớp 11/12, các môn, một năm, trừ tiên đạo và sự hài lòng của mẹ.
81|Giữ nghi ngờ nhẹ khi mẹ nhìn hộp thuốc.
82|Giữ ít hơn một vạn giờ, từ nhỏ đến lớn và nguy cơ bị bỏ xa.
83|Giữ khả năng chỉ ngủ nửa tiếng, hiệu suất tăng và không tiếp tục nới khoảng cách.
84|Giữ lời cam đoan thuốc không tốn tiền, chưa xác nhận lời đó là thật.
85|Giữ hiệu trưởng lớp đánh giá cao và lời nói được tặng thuốc.
86|Giữ mẹ vui vì con được đánh giá cao; “trân trọng” hơi lệch sắc thái nhưng không sai sự kiện.
87|Giữ sau đó sớm mang thêm nhiều thứ về.
88|Đủ giáo trình, kích thích thần kinh, viên nang hormone, bổ sung yêu thú và bột không bao bì.
89|Giữ nhiều cách giải thích tiền làm thêm, bạn tặng, lớp thưởng, không bỏ một nguồn lời nói nào.
91|Giữ số 1.000, chuyển tiền và dặn cảm ơn, không tự thêm việc mua quà.
92|Giữ mẹ dần thấy tâm trạng lạ, vui buổi sáng nhưng tối im lặng đi ngủ.
93|Giữ đang ăn vui, nhận điện thoại, nhíu mày và không ăn thêm.
94|Giữ suy đoán chắc chắn thuộc góc nhìn mẹ về áp lực tu tiên.
95|Đủ mua đồ ăn thích, dành học phí, mong giảm áp lực.
96|Đủ bám điện thoại, cấm chạm và đóng cửa nhà vệ sinh khi nghe gọi.
97|Giữ mẹ sạc điện thoại hết pin rồi bị con giận mắng.
98|Đúng mẹ vì cho rằng con áp lực mà không dám chạm máy, sợ ảnh hưởng tu tiên.
99|Giữ xin học phí bổ sung, đàn anh thi đỗ đại học hàng đầu và tiền thù lao cho người đó.
100|Đúng khoản phí giới thiệu trả giáo viên tuyển sinh cấp ba.
101|Đúng khoản phí xét nghiệm linh căn ở bệnh viện.
102|Giữ mua chung bạn lớp luyện thi, cấp dân dụng và phi kiếm trẻ em.
104|Đúng tin đỗ Trường cấp ba Tung Dương.
106|Giữ sau nhập học xin tiền tăng và thu không đủ chi.
107|Giữ một buổi chiều, tiếng qua điện thoại làm mẹ hoảng.
108|Đúng lời hỏi mẹ Trương Vũ qua điện thoại, không đổi thành SMS.
109|Giữ con vay và quá hạn 30 ngày, đúng đối tượng người nghe là mẹ.
110|Đúng tối cùng ngày con thú nhận mọi chuyện.
112|Giữ con xin lỗi mẹ.
113|Giữ lời nhấn mạnh thực sự muốn tu tiên.
114|Giữ nhượng bộ mắc nợ không trả được cả đời vẫn muốn tu tiên.
115|Đủ bán tất cả đồ đáng tiền, vay thêm một phần rồi trả nợ con.
116|Giữ kỳ vọng của mẹ con được an tâm, không đổi thành kết quả đã xảy ra.
117|Giữ sớm phát hiện khoản vay quá hạn mới.
118|Chu kỳ trả/vay lặp đúng thứ tự và nhịp châm biếm.
119|Giữ mẹ hết chịu nổi và khuyên giảm chi tiêu.
121|Giữ thuê Thiên Linh Căn bắt buộc và thiếu căn thì pháp lực không theo kịp.
123|Đủ người không linh căn vẫn tu được, đổi lại học/bảo dưỡng định kỳ tốn nhất để tiếp tục.
124|Đúng ba tháng sau khai giảng, nợ tăng, thiếu tiền thuê/điện/nước và mẹ hết chịu nổi.
125|Giữ quan hệ thế là một ngày tan học về không còn thấy mẹ; không tự xác định chết hay bị bắt.
126|Giữ đọc lời nhắn, ngồi ngẩn lâu rồi lặng lẽ lên sân thượng.
127|Dấu lược chuyển cảnh được giữ.
128|Đúng mái/sân thượng nơi thuê ở, mở cảnh kế tiếp.
129|Nguồn chuyển sang người đàn ông tỉnh ý thức; “anh ta” đúng giai đoạn chưa nhận rõ thân phận.
130|Giữ mở mắt, đường gần trước mặt, đông người và nước thải.
131|Đủ biển neon màu sắc và dãy nhà tối chen chúc như che trời.
132|Đủ chung cư cũ, chiếu lên gạch đỏ, tiên quảng cáo khoản vay tu tiên và 30 ngày miễn lãi người mới.
133|Giữ câu tự hỏi đang chơi Hắc Ma Hầu, khóa tên đúng, giọng gamer hiện đại phù hợp.
134|Giữ tự hỏi đang ở đâu, không thêm thông tin.
135|Đúng đang tự hỏi, quay đầu thấy sân thượng đầy nến.
136|Đủ hàng nến đỏ bao quanh người và búp bê cũ.
137|Đủ búp bê vải ố/phai, chỉ khâu lệch và khả năng rách bất cứ lúc nào.
138|Giữ “dường như” cảnh kích thích ký ức vỡ vụn; không biến tác động suy đoán thành chắc chắn.
139|Đúng không còn Trung Quốc và nghi vấn bị đưa sang thế giới khác; giọng hiện đại còn giữ.
140|Giữ khó chấp nhận xuyên việt, không thêm phản ứng kịch tính.
141|Đúng ký ức tiên đạo tác động, đồng thời hòa vào nguyên thân và nhận ra thế giới khác.
142|Đúng Côn Khư, hình gần kim tự tháp, 36 tầng nổi và 18 tầng ngầm.
143|Đúng tầng một lớn nhất như lục địa, mỗi tầng là một cõi khác.
144|Giữ không có đáp án về thế giới bên ngoài; không bịa kiến thức ngoài Côn Khư.
145|Giữ thế giới đặt đại tông môn tiên đạo ở địa vị được tôn trọng cao nhất.
146|Đủ ngành độc quyền gần hết, chính phủ/quân đội so với đội chấp pháp như bảo vệ cổng.
147|Giữ phần lớn phúc lợi không dành người thường và đời sống mưu sinh.
148|Đủ tầng một, học sinh Trương Vũ đỗ Tung Dương và gần đây mê nghi lễ; “cậu” hợp khi đã nhận thân phận học sinh.
150|Giữ đúng lúc đau nhói lòng tay cắt dòng ký ức.
151|Đúng dấu trong suốt lòng bàn tay và chuyển đen cực chậm, chưa nói chuyển hết.
152|Giữ câu hỏi nhận diện dấu; sắc thái “lại” có thể bổ sung nhưng không đổi nghĩa sự kiện.
153|Giữ gió đêm và ánh nến đỏ dao động; câu hơi sát chữ, không thay nhân quả.
154|Đủ búp bê cũ, mắt cúc đen rỗng và nhìn thẳng; “cúc nút” có thể gọn nhưng không sai vật thể.
155|Giữ muốn nhớ, càng nghĩ càng đau/chóng mặt.
156|Đúng không khí kỳ quái tăng, ôm đầu và cảm giác quay cuồng.
157|Đúng hoàn hồn mới biết đã mơ màng rời sân thượng về cửa nhà; không thêm hành trình nhớ rõ.
158|Đủ thông báo thuê, bước vào và chỉ bàn/giường; vẫn cùng người quan sát.
159|Giữ câu tự hỏi nhà mình, giọng người xuyên việt hiện đại.
160|Đủ mồ hôi nhớp, nóng, tìm điều khiển rồi nhớ không có điều hòa.
161|Đúng muốn dội/tắm nước rồi biết nước đã bị cắt.
163|Lời chửi địa điểm có căn cứ 破地方; không tự tăng độ thô quá mức.
164|Giữ tiên nhân vẫn không làm cuộc sống tốt hơn thế giới không tiên.
165|Đúng quét nhìn tường, phía sau bàn đầy giấy khen từ nhỏ.
166|Giữ lớp một đến lớp chín và gần như hằng năm nhất khối, không nâng thành luôn luôn.
167|Giữ ký ức nhận thưởng và đánh giá nguyên chủ chăm chỉ, học giỏi từ nhỏ; ngoặc theo nguồn không gán thành nói thành tiếng.
168|Đúng Tung Dương đang theo học là trường trọng điểm thành phố.
169|Giữ lời tự đắc của gamer; “ông nội/học bá” có thể nhuận sắc, không đủ căn cứ coi là lỗi nghĩa chắc chắn.
170|Đủ đỗ đại học/Trúc Cơ, vào tông môn/Kết Đan, leo tầng, rời ổ chuột, phúc lợi và sống thêm vài trăm năm.
171|Giữ nhận định bỗng thấy “xem ra” thế giới này không tệ.
172|Đúng đang nghĩ thì chuông điện thoại đột ngột vang.
173|Đúng trả lời điện thoại “A lô”.
174|Đủ lời chào anh Trương Vũ, khoản vay nền tảng và quá hạn 3 ngày.
175|Giữ cúp máy, kiểm SMS, dày đặc đòi nợ và nguyên chủ vay quá hạn nhiều nền tảng.
176|Giữ ký ức liên quan đến đồng thời, không đảo trình tự.
178|Giữ chửi nguyên chủ và thiên tài tu tiên giả nhờ vay nền tảng; nguồn có tục nên giọng thô có căn cứ.
179|Giữ đến mẹ cũng chịu không nổi và bỏ đi, không thêm điểm đến hay lý do khác.
180|Đúng tính khoản quá hạn rồi mồ hôi lạnh liên tục.
181|Giữ lãi chồng lãi, tổng hơn 70 vạn; không tự đổi thành hàng trăm triệu.
182|Giữ tài khoản còn hơn 50, không làm thành đúng 50 hoặc hơn 500.
183|Giữ lời kinh ngạc 70 vạn và tiếng chửi, không sửa lời nhân vật thành con số khác p0181.
184|Giữ đập giường giận, ngay cả người ưu tú tốt nghiệp cấp ba cũng xem là nợ lớn.
185|Giữ suy luận nghi lễ do tuyệt vọng và con nợ hết hy vọng; hạ nhẹ “狗” vẫn giữ thái độ khinh miệt.
186|Giữ hắn đã hưởng và người xuyên việt phải trả thay; “ta” có thể thống nhất thành “mình” theo giọng hiện đại, chưa đủ căn cứ báo sai nghĩa.
187|Giữ cùng lúc đèn tắt đột ngột.
188|Đủ thử công tắc nhiều lần, so hàng xóm rồi xác định bị cắt điện riêng mình.
189|Giữ lặp chửi địa điểm, nhịp thất vọng có căn cứ nguồn.
190|Giữ mong muốn có điều kiện sáng mai tỉnh lại trở về, không khẳng định sẽ về.
191|Giữ suy nghĩ hỗn loạn rồi ngủ lịm trên giường, kết thúc đêm.
192|Giữ dấu lòng bàn tay từ trong suốt đã đen đúng một phần mười.
'''

notes = {}
for line in pass_notes_text.strip().splitlines():
    num, note = line.split('|', 1)
    notes[int(num)] = note

issues = []
issue_by_num = {}
for num, severity, reason, correction in issue_specs:
    s, d = source['segments'][num - 1], draft['segments'][num - 1]
    issue = {'id': s['id'], 'reason': reason, 'severity': severity,
             'correction': correction, 'source_quote': s['source'], 'target_quote': d['text']}
    issues.append(issue)
    issue_by_num[num] = issue

rows = []
for num, (s, d) in enumerate(zip(source['segments'], draft['segments']), 1):
    assert s['id'] == d['id']
    issue = issue_by_num.get(num)
    assert issue is not None or num in notes, f'Missing independent reason for paragraph {num}'
    rows.append({'id': s['id'], 'verdict': 'FAIL' if issue else 'PASS',
                 'source_quote': s['source'], 'target_quote': d['text'],
                 'reason': issue['reason'] if issue else notes[num]})

review = {'package_hash': source['package_hash'], 'candidate_hash': digest(draft),
          'verdict': 'FAIL', 'checks': {name: True for name in CHECKS},
          'literary_checks': {name: True for name in ['natural_vietnamese', 'spelling_grammar',
                              'genre_voice', 'address_consistency', 'dialogue_format']},
          'segments': rows, 'issues': issues, 'model': 'codex/gpt-inherited',
          'identity_basis': 'codex_subagent', 'agent_session': '/root/gpt_literary_audit',
          'scope': 'Independent local source-bound semantic and literary review; not official BNS certification.',
          'independence': 'Read only source.json, draft.json, genre_profiles.json and semantic_gate.py; no peer reviews, auditor files or semantic_findings.md.'}

assert len(rows) == len(source['segments']) == len(draft['segments']) == 192
validate_package(source)
validate_review(source, draft, review)
for issue in issues:
    i = next(i for i, s in enumerate(source['segments']) if s['id'] == issue['id'])
    assert issue['source_quote'] in source['segments'][i]['source']
    assert issue['target_quote'] in draft['segments'][i]['text']

OUT.mkdir(parents=True, exist_ok=True)
(OUT / 'literary_review.json').write_text(json.dumps(review, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')

lines = [
    '# Audit độc lập văn phong và ngữ nghĩa – Chương 1', '',
    'Kết luận: **FAIL** cho đúng candidate hash bên dưới. Đã đọc và đối chiếu đủ 192 đoạn, theo thứ tự; kiểm cả tám chiều ngữ nghĩa và năm chiều văn phong. Các cờ true chỉ xác nhận đã kiểm, không phải không có lỗi.', '',
    f'- Source package hash: `{source["package_hash"]}`',
    f'- Candidate hash: `{digest(draft)}`',
    '- Model: `codex/gpt-inherited`; identity basis: `codex_subagent`; agent session: `/root/gpt_literary_audit`.',
    '- Phạm vi: source và draft của chapter1; genre `hybrid_cyberpunk_tu_tien`; quy trình `semantic_gate.py`.',
    '- Độc lập: không đọc báo cáo kiểm dịch của người/model khác, auditor files hay semantic_findings.md; không dùng model API/OAuth; không sửa bản truyện.',
    '- Đây là audit biên tập cục bộ, không phải chứng nhận hay phê duyệt chính thức BNS.', '',
    '## Lỗi có chứng cứ – cần sửa', '',
    f'Có {len(issues)} đoạn FAIL. Các câu thay thế dưới đây là đề xuất sửa đầy đủ đoạn, không phải bản dịch đã được xuất bản hay kiểm lại.', '',
]
for issue in issues:
    lines.extend([f'### {issue["id"]} — {issue["severity"]}', '',
                  f'- Nguyên văn: {issue["source_quote"]}',
                  f'- Bản dịch hiện tại: {issue["target_quote"]}',
                  f'- Lỗi: {issue["reason"]}',
                  f'- Đề xuất thay toàn đoạn: {issue["correction"]}', ''])

lines.extend([
    '## Lựa chọn văn phong hợp lệ hoặc chỉnh tùy chọn – không dùng để reject', '',
    '- p0002–p0004: nguồn dùng ngoặc kép cho các tin mẹ gửi, rồi p0005 xác nhận đây là tin nhắn. Draft giữ cấu trúc đó là hợp lệ. p0058–p0061 dùng nhãn Mẹ đúng nguồn; không cần đồng nhất SMS với thoại trực tiếp.',
    '- p0042–p0047: một lượt thoại xuyên nhiều đoạn, ngoặc mở ở đầu và đóng ở cuối đúng nguồn. Không báo thiếu ngoặc ở từng đoạn giữa.',
    '- p0129–p0141 dùng “anh ta”, sau khi nhận ký ức học sinh dùng “cậu” ở p0145 trở đi: sự thay đổi giai đoạn nhận diện có căn cứ. Không replace toàn truyện thành ta/ngươi.',
    '- Người xuyên việt tự xưng “mình” ở p0133/p0159 nhưng “ta” ở p0149/p0186. Đề xuất thống nhất thành “mình” để giữ nhịp hiện đại; có thể giữ “ta” nếu chủ ý giọng tự giễu, miễn nhất quán và không cổ phong hóa mọi nhân vật. Không reject riêng biến thể tự xưng này; p0149 FAIL vì dấu phẩy tách chủ ngữ-vị ngữ.',
    '- p0133–p0190: những câu nguồn đặt trong ngoặc có thể là tự nói hoặc tự nghĩ; draft không tự thêm “nói thành tiếng” nên không đủ căn cứ báo chuyển suy nghĩ thành lời thoại. p0068 vốn có 心想 đã được giữ “nghĩ thầm”.',
    '- p0169 “Ông nội là học bá đây” giữ giọng khoác lác đời thường, không tự kết luận người nói là ông nội thật. Có thể nhuận sắc thành “Ông đây là học bá cơ đấy!” hoặc “Ông đây đúng là học sinh giỏi!”, tùy lựa chọn thuật ngữ học bá. Không coi riêng lựa chọn này là lỗi nghĩa chắc chắn.',
    '- p0010 có thể sửa “Em tại sao…” thành “Tại sao em…”; p0016 “tùy tiện hỏi” thành “hỏi bâng quơ”; p0031 “gật đầu một cách không rõ thái độ” thành “gật đầu, không tỏ ý đồng tình hay phản đối”. Đây là nhuận sắc tùy chọn.',
    '- p0080 “các môn giáo dục đại cương cấp ba” có thể gọn thành “các môn kiến thức chung ở cấp ba”; p0086 “được trân trọng” thành “được đánh giá cao”; p0124 nên viết “Thoáng cái, ba tháng kể từ ngày nhập học đã trôi qua…”. Chưa cần reject riêng các lựa chọn đó.',
    '- p0132 “phi thiên độn địa”, p0140 “xuyên việt”, p0143 “thiên địa”, p0184 “thiên chi kiêu tử” phù hợp hoặc chấp nhận được trong lớp từ tu tiên; có thể dùng “bay lên trời, chui xuống đất”, “xuyên sang thế giới khác”, “một cõi mới”, “những người ưu tú” nếu muốn giọng kể hiện đại hơn. Không thay thuật ngữ khóa tùy hứng.',
    '- p0146 có thể nhuận sắc “Các đại tông môn ở vị trí cao” thành “Các đại tông môn đứng trên tất cả”; p0154 “hai cúc nút đen” thành “hai chiếc cúc đen”; p0175 “lật hộp tin nhắn” thành “mở mục tin nhắn”. Các trường hợp này không gây lỗi sự kiện chắc chắn.',
    '- p0183 “khỉ thật” là mức Việt hóa chấp nhận được của 靠; p0185 “con nợ” là cách hạ nhẹ 借贷狗 nhưng vẫn giữ giọng khinh miệt. Không bắt buộc phải tăng lời tục.', '',
    '## Nhận xét toàn chương', '',
    'Trục châm biếm về giáo dục, vay nợ và tu tiên được giữ: yêu cầu triệt sản, chuyển giới, học trong Vạn Hồn Phiên, thuốc miễn phí nhưng cấy pháp khí có bảng giá, vòng trả/vay và cắt điện cuối chương. Không có căn cứ thêm hào khí hoặc diễn giải đạo lý. Lỗi sọt rác ở p0037 cần sửa để cú châm biếm hồ sơ dự phòng còn nguyên.', '',
    'Tên khóa xuất hiện như Trương Vũ, Trường cấp hai Đông Dương, Trường cấp ba Tung Dương, Côn Khư, Hắc Ma Hầu và các thuật ngữ Thiên Linh Căn, Nguyên Âm Luyện Khí Chi Thuật, Hồn Tu, Vạn Hồn Phiên, Trúc Cơ, Kết Đan, khoản vay tu tiên được giữ đúng. Không phát hiện nhầm tên có căn cứ. Dùng mẹ/con trong nhà và em/thầy cô tại cuộc phỏng vấn đầu có căn cứ; các lời quảng cáo của trường khác xưng bạn/chúng tôi vẫn là lựa chọn phù hợp giọng bán hàng.', '',
    'Các mốc 989, 5/2/3 giờ, 9 năm, gần một vạn giờ, nửa giờ, 1.000, quá hạn 30/3 ngày, một năm hơn, ba tháng, 36/18 tầng, hơn 70 vạn, hơn 50 và dấu đen một phần mười được kiểm trong ngữ cảnh. Chỉ p0103 sai lớn; p0044 sai biên so sánh. “đồng” ở đây đọc như đơn vị tiền trong thế giới truyện, không phải phép quy đổi sang VND; nguồn không cho tỷ giá để quy đổi.', '',
    'Không có context chương trước ở chương 1; kiểm continuity thực hiện trong toàn chương. Không nâng phỏng đoán hồ sơ bị bán hay các lời hứa của lớp luyện thi thành sự thật; không suy đoán mẹ chết, đi đâu hoặc nghi lễ chính xác là gì.', '',
    'Sau khi parent sửa cần tạo candidate hash mới và kiểm lại bản đã sửa. Báo cáo này không tự chuyển sang PASS cho một candidate khác.', ''
])
(OUT / 'literary_findings.md').write_text('\n'.join(lines), encoding='utf-8')
print(json.dumps({'source_count': len(source['segments']), 'review_count': len(rows),
                  'issues': len(issues), 'package_hash': source['package_hash'],
                  'candidate_hash': digest(draft), 'schema_validation': 'PASS',
                  'files': [str(OUT / 'literary_review.json'), str(OUT / 'literary_findings.md')]}, ensure_ascii=False))
