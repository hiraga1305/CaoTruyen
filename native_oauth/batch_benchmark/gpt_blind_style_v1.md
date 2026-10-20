# GPT audit mù: văn phong và ngữ cảnh

Đã đọc đối chiếu đủ **208 đoạn**, 52 đoạn mỗi nhóm ẩn danh; chỉ đọc bundle mù, các nguồn Trung văn được bundle chỉ định và rubric thể loại công khai. Không đọc mapping/model/route, output worker riêng, gold hay review khác; không sửa target, không đề xuất câu Việt thay thế.

Có một lỗi nghĩa xác nhận rõ ở V1-B: thêm hành vi quỵt nợ vào cảnh vay nợ xoay vòng. Các vấn đề còn lại được phân biệt thành lỗi cấu trúc/collocation hoặc bất định ngữ nghĩa; không gom lựa chọn văn phong hợp lệ thành semantic FAIL.

## V1-A

Coverage: 52/52; lỗi nghĩa xác nhận: 0; lỗi style lớn: 2.

- c0003p0081 — syntactic_calque_and_pragmatic_ambiguity / major_style: CN `周天翊不以为然道` → VI `Chu Thiên Dực chẳng cho là đúng bảo`. Cụm kể thái độ được bê theo cú pháp Hán, thiếu cấu trúc Việt tự nhiên và đối tượng của sự không đồng tình. Trong cảnh, người nói bác sự ngạc nhiên của bạn rồi giải thích quyền lợi nhà trường; cách viết Việt không truyền thái độ rõ. Không coi đây là đảo nghĩa chắc chắn chỉ vì một cách hiểu thành ngữ.
- c0103p0003 — unit_specificity_risk / moderate: CN `那三百件` → VI `Ba trăm kiện`. Nguồn chỉ dùng lượng từ 件; các chương gốc trước nói từng món thuốc được cân. Kiện thêm cách đóng gói không được nêu rõ. Cần kiểm tra với hồ sơ vật phẩm; chưa đủ căn cứ khẳng định một phép đổi số hay sai người đặt hàng.
- c0002p0055 — temporal_state_ambiguity / moderate: CN `逾期快一个月了` → VI `sắp quá hạn một tháng rồi`. Nguồn xác định đã quá hạn gần một tháng. Vị trí sắp trước quá hạn làm bản Việt dễ bị đọc thành trạng thái chưa quá hạn; đây là rủi ro thời gian và câu vụng, không khẳng định mọi độc giả đều đọc thành đảo nghĩa.
- c0004p0047 — malformed_finance_action / major_style: CN `撸小贷` → VI `vơ vét cả vay nợ nhỏ`. Cụm động tác tài chính thiếu cấu trúc Việt rõ ràng, làm khó hiểu việc nhân vật tiếp tục tiếp cận khoản vay. Không sửa câu; cần chuẩn hóa cách phân tích hành động rồi sinh lại scene.
- c0003p0089 — literal_collocation / minor_style: CN `络绎不绝` → VI `nối liền không dứt`. Cụm diễn tả dòng học sinh tiếp tục dùng thuốc còn giọng convert. Nghĩa đại thể giữ được; không phải semantic FAIL.
- c0004p0054 — literal_finance_register / minor_style: CN `终于突破1000` → VI `rốt cuộc đã đột phá 1000`. Đột phá cho số dư là cách nói convert trong ngữ cảnh tài chính hiện đại; số/ngưỡng không bị đổi.
- c0002p0057 — loan_category_specificity / moderate: CN `小贷` → VI `khoản vay tiêu dùng`. Tiểu khoản vay không tự xác nhận loại mục đích tiêu dùng. Bản Việt thêm phân loại khoản vay; đây là điểm bất định thuật ngữ cần hồ sơ tài chính, không chứng minh phép đổi số.

Debt/actor boundary: giữ các quan hệ, khoản nợ 70 vạn, khoản 500 của chị và bạn; synthetic giữ đúng khoản 20.000 đã trả, 500 chưa trả và 2.000 còn nợ. Chưa có chuỗi target trước để kiểm chứng seam toàn truyện.

## V1-B

Coverage: 52/52; lỗi nghĩa xác nhận: 1; lỗi style lớn: 2.

- c0003p0081 — syntactic_calque_and_pragmatic_ambiguity / major_style: CN `周天翊不以为然道` → VI `Chu Thiên Dực chẳng cho là đúng`. Cụm kể thái độ được bê theo cú pháp Hán, thiếu cấu trúc Việt tự nhiên và đối tượng của sự không đồng tình. Trong cảnh, người nói bác sự ngạc nhiên của bạn rồi giải thích quyền lợi nhà trường; cách viết Việt không truyền thái độ rõ. Không coi đây là đảo nghĩa chắc chắn chỉ vì một cách hiểu thành ngữ.
- c0103p0003 — unit_specificity_risk / moderate: CN `那三百件` → VI `Ba trăm kiện`. Nguồn chỉ dùng lượng từ 件; các chương gốc trước nói từng món thuốc được cân. Kiện thêm cách đóng gói không được nêu rõ. Cần kiểm tra với hồ sơ vật phẩm; chưa đủ căn cứ khẳng định một phép đổi số hay sai người đặt hàng.
- c0004p0047 — unsupported_debt_action / major: CN `硬着头皮撸小贷也要修仙，一路以贷养贷到现在` → VI `quỵt nợ vay khoản vay nhỏ`. Nguồn mô tả tiếp cận khoản vay và lấy vay nuôi vay; không xác nhận chủ ý quỵt nợ. Bản Việt thêm hành vi không trả nợ, đổi đặc điểm hành động/đạo đức nhân vật.
- c0002p0059 — literal_idiom_image / major_style: CN `冷冰冰的扑克脸` → VI `gương mặt lạnh tanh như bài tây`. Poker face chỉ nét mặt không biểu lộ cảm xúc; bản Việt tạo một phép so sánh với lá bài không tự nhiên và không làm rõ thái độ.
- c0003p0091 — unnatural_collocation / minor_style: CN `这么一具肉身` → VI `một khối nhục thân`. Cách kết hợp khối với nhục thân còn convert; vật thể và người nhận thân xác vẫn đúng.
- c0002p0057 — loan_category_specificity / moderate: CN `小贷` → VI `khoản vay tiêu dùng`. Tiểu khoản vay không tự xác nhận loại mục đích tiêu dùng. Bản Việt thêm phân loại khoản vay; đây là điểm bất định thuật ngữ cần hồ sơ tài chính, không chứng minh phép đổi số.

Debt/actor boundary: giữ các quan hệ, khoản nợ 70 vạn, khoản 500 của chị và bạn; synthetic giữ đúng khoản 20.000 đã trả, 500 chưa trả và 2.000 còn nợ. Chưa có chuỗi target trước để kiểm chứng seam toàn truyện.

## V1-C

Coverage: 52/52; lỗi nghĩa xác nhận: 0; lỗi style lớn: 1.

- c0003p0081 — syntactic_calque_and_pragmatic_ambiguity / major_style: CN `周天翊不以为然道` → VI `Chu Thiên Dực chẳng cho là đúng, nói`. Cụm kể thái độ được bê theo cú pháp Hán, thiếu cấu trúc Việt tự nhiên và đối tượng của sự không đồng tình. Trong cảnh, người nói bác sự ngạc nhiên của bạn rồi giải thích quyền lợi nhà trường; cách viết Việt không truyền thái độ rõ. Không coi đây là đảo nghĩa chắc chắn chỉ vì một cách hiểu thành ngữ.
- c0103p0003 — unit_specificity_risk / moderate: CN `那三百件` → VI `Ba trăm kiện`. Nguồn chỉ dùng lượng từ 件; các chương gốc trước nói từng món thuốc được cân. Kiện thêm cách đóng gói không được nêu rõ. Cần kiểm tra với hồ sơ vật phẩm; chưa đủ căn cứ khẳng định một phép đổi số hay sai người đặt hàng.
- c0003p0087 — narrator_pronoun_drift / minor_style: CN `张羽自然连连摇头，他真怕自己` → VI `Trương Vũ đương nhiên lắc đầu liên tục, hắn`. Trong cùng cảnh giọng kể chuyển cậu sang hắn mà không có biến cố đổi ngôi. Không làm sai nhân vật nhưng khó khóa văn phong cho bản dài.

Debt/actor boundary: giữ các quan hệ, khoản nợ 70 vạn, khoản 500 của chị và bạn; synthetic giữ đúng khoản 20.000 đã trả, 500 chưa trả và 2.000 còn nợ. Chưa có chuỗi target trước để kiểm chứng seam toàn truyện.

## V1-D

Coverage: 52/52; lỗi nghĩa xác nhận: 0; lỗi style lớn: 2.

- c0003p0081 — syntactic_calque_and_pragmatic_ambiguity / major_style: CN `周天翊不以为然道` → VI `Chu Thiên Dực không cho là đúng nói`. Cụm kể thái độ được bê theo cú pháp Hán, thiếu cấu trúc Việt tự nhiên và đối tượng của sự không đồng tình. Trong cảnh, người nói bác sự ngạc nhiên của bạn rồi giải thích quyền lợi nhà trường; cách viết Việt không truyền thái độ rõ. Không coi đây là đảo nghĩa chắc chắn chỉ vì một cách hiểu thành ngữ.
- c0103p0003 — unit_specificity_risk / moderate: CN `那三百件` → VI `Ba trăm kiện`. Nguồn chỉ dùng lượng từ 件; các chương gốc trước nói từng món thuốc được cân. Kiện thêm cách đóng gói không được nêu rõ. Cần kiểm tra với hồ sơ vật phẩm; chưa đủ căn cứ khẳng định một phép đổi số hay sai người đặt hàng.
- c0002p0058 — dangling_coordinate_structure / major_style: CN `和张羽是一起分享各大平台借贷情报的好兄弟` → VI `và Trương Vũ là anh em tốt`. Phối hợp và Trương Vũ khiến cấu trúc quan hệ anh em tốt chông chênh; nguồn mô tả quan hệ giữa hai người. Không đủ để kết luận bản Việt biến người bạn thành nhân vật khác.
- c0002p0059 — unresolved_loan_expression / minor_style: CN `扑克脸` → VI `khuôn mặt poker`. Giữ poker mà không rõ biểu cảm làm câu thiếu tự nhiên; có thể là lựa chọn khẩu ngữ, không tự coi là sai sự kiện.
- c0003p0084 — peer_register_risk / minor_style: CN `你小子` → VI `thằng nhóc mày`. Tao/mày trong cảnh bạn học có thể hợp văn cảnh Việt, nhưng nguồn mô tả tình bạn còn mong manh. Cần khóa mức thân mật theo quan hệ, không tự đánh dấu sai nghĩa chỉ vì đại từ mạnh.

Debt/actor boundary: giữ các quan hệ, khoản nợ 70 vạn, khoản 500 của chị và bạn; synthetic giữ đúng khoản 20.000 đã trả, 500 chưa trả và 2.000 còn nợ. Chưa có chuỗi target trước để kiểm chứng seam toàn truyện.

## Chẩn đoán phòng ngừa

Các nhóm đều còn cú pháp và biểu đạt thành ngữ có dấu convert. Dữ liệu ngữ cảnh chung không tự bảo đảm tiếng Việt tự nhiên; cần hợp đồng phong cách kiểm được, kiểm tra động tác tài chính và mốc thời gian, cùng truy hồi quan hệ có mốc nguồn. 件 cần hồ sơ vật phẩm để tránh tự chọn đơn vị đóng gói.

Nếu thất bại, cập nhật retrieval/scene/risk routing bằng chứng cứ Trung văn và sinh lại nguyên scene trên heldout mới. Không patch những đoạn ghi ở trên. GPT audit này dùng để hiệu chỉnh route, không phải quy trình GPT sửa mọi chương.

JSON kèm 52 coverage rows/nhóm, hash source/target, quote lỗi và các ghi chú boundary. Không có chứng nhận Bạch Ngọc Sách hay suy rộng sang hàng nghìn chương.
