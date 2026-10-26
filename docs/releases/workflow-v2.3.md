# Workflow 2.3.1 — bắt buộc xác minh release trước native calls

Giải quyết việc chỉ đổi tài liệu/prompt mà process/job vẫn giữ code cũ. workflow.json trỏ metadata hiện hành; workflow_release.json giữ hash code/hướng dẫn với chuẩn LF dùng được trên Windows/Linux. Doctor kiểm đúng Git root, HEAD bằng canonical GitHub main và lock bằng blob trong commit, không bị ảnh hưởng bởi dữ liệu truyện dirty không liên quan.

Launch resume configuration tương thích hoặc tự chọn job revision mới, giữ nguyên job cũ/prefix approved và import verified effective_sources có lineage khi cần. Process nhận lease trong invocation, ghi startup/version/commit/policy/job thực. Receipt trên đĩa không cấp quyền. Native gateway từ chối legacy/unleased workspace, code/config đổi, role/model sai, packet thiếu policy và request tool-enabled/không finite JSON. Biên wave kiểm lại upstream; report lịch sử không bị đổi nhãn thành bản hiện hành.

Patch 2.3.1 sửa assertion đường dẫn ngắn/dài trên Windows trong test bootstrap. Thêm --canon-file và kế thừa canon revision từ LAST_JOB: tạo job mới không cho phép ghi đè file canon mà evidence cũ đã bind. Kiểm thử chứng minh chọn file canon mới vẫn giữ prefix hợp lệ và không dịch lại chương approved.

Ví dụ nguyên nhân đã quan sát: campaign 2.1 bắt đầu 22:25 ngày 26/10, trước commit 2.2 lúc 23:20; cả 335 attempts thuộc một PID. Ba invocation trong watch không có nghĩa đã nạp lại code mới. Gate mới không thể vá ngược process/CLI snapshot hoàn toàn cũ đang chạy; phải dừng ở biên an toàn và khởi động entry point mới. Không tuyên bố kiểm soát mọi executable ngoài repo.

Không thêm model audit/Codex dependency; giữ 4 translator, tối đa 5 chương/wave, hai reviewer đồng thời, HIGH phục hồi và continuity 2.2. Phần HIGH sửa theo chương vẫn tuần tự trong release này. Không dùng thông lượng của 2.1 làm benchmark 2.3; cập nhật code này không gọi model thật hoặc sửa truyện/approved.

Xem [quy trình khởi động](../WORKFLOW_LAUNCH.md) và [prompt dùng chung không ghim version](../prompts/continue-translation.md). Future releases cần cập nhật code/docs/metadata/lock cùng một commit; prompt tiếp tục đọc bản hiện hành thay vì một số 2.x cố định.
