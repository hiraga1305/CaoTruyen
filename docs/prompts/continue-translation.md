Tiếp tục sách hiện tại theo AGENTS.md, WORKFLOW.md, workflow.json và docs/CONTINUITY_CONVENTIONS.md. Chỉ chạy trong phạm vi chương tôi đã giao; chưa có phạm vi thì xác nhận trước khi gọi model.

- Xác minh prefix approved, nguồn và TOC; bắt đầu từ chương kế tiếp. Không mặc định tổng chương của một sách khác.
- Antigravity chuẩn bị/đối chiếu canon local từ ID/quote nguồn và bản approved của chính sách. Giữ thống nhất tên/biệt danh, nhãn nghề/vật phẩm/địa danh/tổ chức; phân biệt nickname với cách xưng hô. Không suy giới tính, quan hệ hoặc danh tính từ tên. Bảng có thể rỗng lúc bắt đầu; hai reviewer vẫn phải kiểm các tên mới.
- Giữ bốn translator MEDIUM, tối đa năm chương/wave và hai reviewer MEDIUM đồng thời, độc lập. Mỗi reviewer phải trả continuity_checks và continuity_decisions theo contract; vi phạm cùng thực thể/phạm vi là issue bắt buộc, không hạ thành style. Đại từ/biệt danh hợp ngữ cảnh cần giải thích. HIGH chỉ phục hồi/sửa đúng ID rồi review lại bản ghép.
- Đổi code/canon/config dùng job revision mới, giữ prefix và lịch sử; không ghi đè approved hoặc bundle. Không tự nhập mọi suggestion làm canon.
- Timeout/partial chia nhỏ và retry hữu hạn; quota/network backoff rồi resume. Auth/integrity chưa khôi phục thì lưu next_actions cụ thể; không bỏ chương, bỏ gate hoặc báo hoàn tất giả.
- Hiển thị tiến độ trong session thật, đồng bộ dashboard, checkpoint mỗi 100 chương; không thêm audit phụ thuộc Codex hoặc xin duyệt định kỳ.
- Kết thúc phạm vi thì report/seal bundle mới, SHA-256, wall time, số chương mới approved, suggestions và lỗi tồn. Không tự xuất bản hoặc push dữ liệu truyện.
