# GPT audit mù phase 2: style và mạch truyện

Đã đối chiếu **104 target**: V2-X 52, V2-R 4, CTRL-Y 48, với nguồn Trung văn được bundle chỉ định. Không đọc route/model/mapping/private paths/code/gold/peer review; không chỉnh target hoặc đề xuất câu thay thế.

V2-X có cải thiện chẩn đoán: không thêm quỵt nợ, trả lại lượng từ chung cho 300 món ở synthetic103 và giữ cậu nhất quán trong cảnh thuốc. Cụm thành ngữ tại c0003p0081 vẫn convert trong cả V2-X lẫn control một worker; đây là lỗi style chưa giải được chỉ bằng thêm context.

## V2-X

Coverage 52; không xác nhận đảo nghĩa nghiêm trọng trong lượt này; style lớn 1. Bất định có quote bên dưới không tương đương semantic PASS.

- c0003p0081 — syntactic_calque_and_pragmatic_ambiguity / major_style: CN `周天翊不以为然道` → VI `Chu Thiên Dực không cho là đúng nói`. Cụm kể thái độ thiếu cấu trúc Việt tự nhiên, đối tượng không cho là đúng bị bỏ ngỏ. Trong cảnh bạn hỏi vì sao giáo viên chưa bị xử lý, người nói tiếp tục giải thích bảo trợ/lợi ích. Cần làm rõ thái độ trong decoding; không tự kết luận đảo nghĩa chắc chắn vì nguồn cũng dùng thành ngữ có thể đa nghĩa theo văn cảnh.
- c0002p0057 — lending_network_role_ambiguity / moderate: CN `对方是自己上线` → VI `đối phương là cấp trên của cậu`. Nguồn gắn 上线 với bạn cùng lớp chào mời khoản vay. Cấp trên dễ được hiểu thành quyền hạn nhà trường/công việc, thay vì vai mạng giới thiệu vay; quan hệ tài chính chưa được xác định rõ. Không khẳng định mọi cách đọc cấp trên đều là boss công việc.
- c0002p0055 — loan_category_specificity / moderate: CN `小贷` → VI `khoản vay tiêu dùng vi mô`. Nguồn không tự xác nhận loại sản phẩm tiêu dùng hay mô hình vi mô; bản Việt gộp cả hai phân loại. Cần hồ sơ thuật ngữ có bằng chứng, tránh thêm mục đích vay từ suy luận bối cảnh.
- c0003p0083 — friendly_warning_register / minor_style: CN `告诫` → VI `cảnh cáo`. Giọng cảnh cáo khá nặng so với người bạn chân thành sau đó đề nghị cho vay/cho dùng thuốc. Đây là vấn đề register, không chứng minh đổi ai đe dọa ai.
- c0004p0047 — awkward_finance_coordination / minor_style: CN `硬着头皮撸小贷也要修仙` → VI `bấm bụng đi vay các khoản vay nhỏ cũng phải tu tiên`. Động tác vay và rollover giữ đúng, nhưng phối hợp cũng phải tu tiên vẫn mang cú pháp nguồn. Ít nghiêm trọng hơn cụm vơ vét/quỵt nợ của các bản cũ.
- c0003p0076 — dialogue_punctuation_seam / minor_style: CN `周天翊说道` → VI `Chu Thiên Dực nói: "`. Đoạn cảnh chương 3 dùng dấu thoại thẳng trong khi các cảnh chương 2/4 dùng dấu cong. Không mất nghĩa, nhưng hợp đồng định dạng xuyên batch chưa đồng nhất.

Boundary: Loan already overdue nearly a month is explicit; BaiZhenZhen remains female classmate and comic father appeal, not literal parentage. ChuTianYi speaks, warns about WangHai and offers help; original-body drug overload and seventy-wan debt retained; cau narrative remains stable. Mother/father do not answer, elder sister coldly refuses ongoing support but sends500; friend500 plus sister500 brings balance above1000. Synthetic103:20000 repaid to sister removed, younger brother500 remains due/no waiver, rent2000 remains recorded, 300items are ordered by younger brother not the elder helper.

## V2-R

Coverage 4; không xác nhận đảo nghĩa nghiêm trọng trong lượt này; style lớn 0. Bất định có quote bên dưới không tương đương semantic PASS.

- c0102p0003 — speech_time_indexical_ambiguity / moderate: CN `他昨晚的拒绝只说了今晚` → VI `lời từ chối tối qua của anh chỉ nói tối nay`. Chỉ xuất tối nay cần neo vào thời điểm lời từ chối ở tối hôm trước. Bản Việt đặt tối qua và tối nay cạnh nhau mà không đánh dấu trích lời, dễ làm lệch phạm vi một đêm. Nguồn cũng giữ chữ 今晚 của lời nói; vì vậy đây là ambiguity cần kiểm tra, không tự coi thành đảo ngày chắc chắn.
- c0102p0004 — unit_specificity_risk / moderate: CN `三百件药` → VI `ba trăm kiện thuốc`. 件 là lượng từ cho món/đơn vị, nguồn không xác nhận đóng thành kiện. Kiện thêm cách đóng gói; chín trăm gam và không dưới vẫn giữ đúng. Đây là bất định đơn vị, không phép đổi số đã chứng minh sai.
- c0102p0003 — promise_scope_collocation / minor_style: CN `并没有答应以后永远不借` → VI `không hề đồng ý sau này sẽ mãi mãi không mượn`. Lời phủ định hứa vĩnh viễn không vay giữ phạm vi mở cho các khoản vay sau, nhưng cách ghép đồng ý và mãi mãi khá cứng trong tiếng Việt.

Boundary: Younger brother borrows500 from middle brother; elder sister previous20000 still outstanding. Older sister receives call after returning to factory; younger caller asks about older brother; no actor reversal identified. Middle brother takes another2000 rent loan; last-night refusal is not a perpetual no-borrow promise. 300medicine units weighed individually; threshold no lower than900g preserved, packaging unspecified.

## CTRL-Y

Coverage 48; không xác nhận đảo nghĩa nghiêm trọng trong lượt này; style lớn 2. Bất định có quote bên dưới không tương đương semantic PASS.

- c0003p0081 — syntactic_calque_and_pragmatic_ambiguity / major_style: CN `周天翊不以为然道` → VI `Chu Thiên Dực chẳng cho là đúng nói`. Cụm kể thái độ thiếu cấu trúc Việt tự nhiên, đối tượng không cho là đúng bị bỏ ngỏ. Trong cảnh bạn hỏi vì sao giáo viên chưa bị xử lý, người nói tiếp tục giải thích bảo trợ/lợi ích. Cần làm rõ thái độ trong decoding; không tự kết luận đảo nghĩa chắc chắn vì nguồn cũng dùng thành ngữ có thể đa nghĩa theo văn cảnh.
- c0004p0047 — finance_action_collocation / major_style: CN `撸小贷` → VI `quẹt các khoản vay nhỏ`. Quẹt kết hợp khoản vay không tự nhiên và dễ gợi hành động quẹt thẻ mà nguồn chưa nói. Rollover vẫn hiện diện; chưa đủ bằng chứng coi đây là đảo trạng thái nợ.
- c0003p0089 — literal_collocation / minor_style: CN `络绎不绝` → VI `nối liền không dứt`. Dòng học sinh dùng thuốc được chuyển thành cụm nối liền còn giọng convert; số người và hành động không bị đổi.
- c0003p0076 — teacher_reference_register / minor_style: CN `王海` → VI `thầy ta`. Thầy ta là cách ghép xưng hô vụng trong thoại hiện đại; vẫn quy đúng Vương Hải, không phải lỗi nhận diện nhân vật.

Boundary: Loan already overdue nearly a month is explicit; BaiZhenZhen remains female classmate and comic father appeal, not literal parentage. ChuTianYi speaks, warns about WangHai and offers help; original-body drug overload and seventy-wan debt retained; cau narrative remains stable. Mother/father do not answer, elder sister coldly refuses ongoing support but sends500; friend500 plus sister500 brings balance above1000.

## Ý nghĩa đối với route

V2-X là chạy lại các đoạn chẩn đoán cũ, không phải heldout mới. V2-R chỉ có 4 đoạn synthetic chưa sinh trước đó; control một worker có context rộng hơn nên không cô lập riêng tác động của song song. Không suy từ các cải thiện này rằng hàng nghìn chương sẽ sạch lỗi.

Cần hợp đồng có chứng cứ cho vai mạng vay, phân loại khoản vay, lượng từ vật phẩm và chỉ xuất thời gian của lời kể/lời thoại. Kiểm tra style cần bao phủ thành ngữ/cấu trúc tiếng Việt và seam dấu thoại. Nếu không đạt, cập nhật hợp đồng rồi sinh lại nguyên scene, đổi routing/verifier theo rủi ro; không patch các câu trên.

Audit văn bản mù này không tự xác minh metadata runtime về sinh lại pipeline; chứng cứ đó phải được kiểm tra riêng. Các bản vẫn cần gate đã hiệu chỉnh; không có chứng nhận Bạch Ngọc Sách.
