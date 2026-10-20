# Audit ngữ nghĩa độc lập chương 1

Kết luận: **FAIL**. Đã đọc và đối chiếu đủ 192/192 đoạn theo thứ tự nguồn, kiểm nghĩa, độ đầy đủ, tên, người nói/đại từ, số/đơn vị, phủ định/modality, thời gian/nhân quả và continuity. Có 5 lỗi xác nhận; 187 đoạn còn lại không thấy lỗi ngữ nghĩa đủ căn cứ để đánh FAIL trong lượt kiểm này. Đây là kết quả audit theo nguồn, không phải chứng minh độ chính xác 100%.

- Model: `codex/gpt-inherited`; identity basis: `codex_subagent`; session: `/root/gpt_semantics`.
- Package hash: `b7a650c0b08b5e892f1e0a8ef38ea37ac6e4763892644f7ad517058faf555c2d`.
- Candidate hash: `462b3f9c356893bf07671eb3fecdde4f1c8534a24a7f1cf44eb800ec6d6a249d`.
- Nguyên văn ưu tiên hơn LTP. Đã xem dữ liệu LTP dự đoán cho 0019/0044/0090/0103/0105/0169 để tham khảo ranh giới cụm; không coi cây dự đoán là chứng cứ chân lý. LTP ghi package hash khác package đang audit; đã đối chiếu source_hash của cả sáu đoạn tham khảo với digest nguyên văn hiện tại và đều khớp, nên chỉ dùng phân tích ở mức đoạn ấy, không coi metadata package LTP là nguồn hiện hành. Không đọc peer/auditor review hoặc báo cáo peer; không sửa source/draft/gate/test.

## Lỗi xác nhận

| Đoạn | Mức | Nguồn → Draft | Vấn đề và sửa đề nghị |
|---|---|---|---|
| c0001p0019 | minor | 历届的优秀毕业生 → những học sinh xuất sắc các khóa trước | Bỏ tư cách đã tốt nghiệp. Sửa thành “những học sinh tốt nghiệp xuất sắc các khóa trước”. |
| c0001p0044 | major | 900克以上 → hơn 900 gram | Đổi ≥900 thành >900. Sửa “từ 900 gram trở lên”. |
| c0001p0090 | minor | 好人缘 → khả năng giao tiếp tốt | Quan hệ tốt/được quý mến không đồng nghĩa kỹ năng giao tiếp. Sửa “được mọi người quý mến”. |
| c0001p0103 | critical | 两万块钱 → hai mươi triệu đồng | 20.000 bị đổi thành 20.000.000, sai 1.000 lần. Sửa “hai mươi nghìn”/“hai vạn” và không tự quy đổi tiền tệ. Lỗi gây bất hợp lý tương quan tổng nợ hơn 70 vạn ở đoạn 181. |
| c0001p0105 | minor | 学杂费 → phí tạp vụ | Nhầm các khoản phụ phí học tập với dịch vụ tạp vụ. Sửa “các khoản phụ phí học tập”. |

## Các điểm cân nhắc, không quy thành lỗi xác nhận

- c0001p0006: “良久” là đợi khá lâu; “một lúc” làm nhẹ sắc thái nhưng không đảo thời gian/diễn tiến. Có thể chỉnh “hồi lâu” để sát hơn.
- c0001p0066: “小贷” nhấn khoản vay nhỏ, trong khi “vay tiêu dùng” nhấn mục đích/loại dịch vụ. Quảng cáo này nhắm cá nhân; chưa đủ căn cứ kết luận sai mạch truyện. “Quảng cáo cho vay nhỏ à?” sẽ sát hơn.
- c0001p0091/0181/0182: “đồng” có thể dùng như đơn vị tiền chung trong văn Việt, nên không mặc định đó là VND và không tự coi là lỗi. Riêng 0103 có số đổi rõ ràng, không thể bảo vệ bằng lựa chọn đơn vị.
- c0001p0169: “老子” là tự xưng ngạo nghễ, không có nhân vật ông nội mới. “Ông nội” trong draft có thể đọc như lối tự xưng khẩu ngữ; “Ông đây là học bá” rõ hơn, nhưng không đánh lỗi thêm nhân vật khi toàn cảnh vẫn là độc thoại.
- c0001p0005/0162: “vào túi”/“thở dài” là tiểu tiết diễn đạt thêm nhẹ; không coi mọi diễn đạt tự nhiên là lỗi ngữ nghĩa đáng chặn.

## Đối chiếu xuyên chương

Phần đầu là quá khứ nguyên thân cùng mẹ; sau 0129 là người xuyên việt tỉnh lại, hiểu ký ức nguyên thân và tự đánh giá. Draft vẫn giữ chuyển cảnh và phân biệt lời mẹ tin con, lời con quảng cáo học phí/thuốc miễn phí, rồi thú nhận vay nợ. Cuộc gọi quá hạn 30 ngày cho mẹ (0109) và 3 ngày cho người xuyên việt (0174) không bị nhập làm một. Thế giới Côn Khư giữ tầng 1, 36 tầng trên đất/18 tầng ngầm, lợi ích tu tiên và trạng thái ký hiệu đen một phần mười ở cuối chương. Lỗi 0103 là mâu thuẫn số tiền nổi bật trong chuỗi phí thuê Thiên Linh Căn và tổng nợ 0181.

Schema và mọi quote đã được kiểm bằng `validate_review` cùng kiểm substring; đó là kiểm artifact, không thay thế việc đọc nghĩa. Chỉ hai artifact riêng được ghi. Review chỉ gắn đúng candidate hash trên và cần kiểm lại nếu draft được sửa.
