# QUY TẮC HIỂN THỊ TIẾN ĐỘ DỊCH TRỰC TIẾP TRONG SESSION ANTIGRAVITY

Bất kỳ luồng dịch thuật nào (từng chương, wave 5 chương, hay batch lớn) đều **BẮT BUỘC** cập nhật và hiển thị trực tiếp tiến độ cho người dùng trong session Antigravity hiện tại:

1. **Hiển thị tiến độ rõ ràng trong phản hồi Chat**:
   - Tên tác phẩm, chương đang dịch, wave hiện tại (`Wave X / Y`).
   - Thanh tiến độ `[████████░░░░] XX.X%`.
   - Tổng số từ, tổng số đoạn, trạng thái Quality Gate và âm vận Prosody.
2. **Cập nhật Artifact Dashboard**:
   - Tự động gọi `SessionMonitor.sync_session_artifacts()` ghi ra:
     - `translation_live_dashboard.html` (Generative UI Card).
     - `translation_session_dashboard.md`.
3. **Mọi script và subagent**:
   - Phải tích hợp `native_oauth.session_monitor.SessionMonitor` để lưu vết và đồng bộ liên tục.
