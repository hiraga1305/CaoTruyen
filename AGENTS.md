# Workflow mặc định đã chốt — 26/10/2026

- Repository chuẩn cho mọi tác vụ dịch trong CaoTruyen: **https://github.com/hiraga1305/CaoTruyen**.
- Đọc `WORKFLOW.md` và `workflow.json` trước khi chạy. Entry point: `python -X utf8 translate.py`; policy `resilient-content-2` / `resilient-review-2`.
- Mặc định bốn translator MEDIUM, tối đa năm chương/wave tự co theo ngân sách, hai reviewer MEDIUM độc lập, HIGH fallback/sửa tập trung. Không quay về runner cũ hoặc pilot trừ khi người dùng yêu cầu rõ.
- Checkpoint approved mỗi 100 chương là bản ghi tự động, không thêm audit hoặc chờ Codex. Cập nhật workflow/GitHub không tự cấp quyền bắt đầu dịch toàn sách.
- Giữ nguồn/truyện, runtime/bundle, database và credential ở local. Chỉ commit mã nguồn, test và docs; không `git add .` để đẩy dữ liệu truyện.
- Code/canon/config đổi thì tạo job revision mới; tái sử dụng prefix approved đã xác minh, không đổi hash/runtime cũ hoặc duyệt lại bằng host.

# Phạm vi vận hành đã xác nhận — 22/10/2026

- Toàn bộ workflow cào → dịch → review → sửa → phê duyệt → xuất bản chạy độc lập trong **Antigravity**.
- Không ràng buộc Codex, session GPT/Codex, dịch vụ duyệt ngoài hoặc một lượt audit định kỳ vào workflow. Việc kiểm tra chéo ngoài luồng trong phiên này là một lần kiểm thử/sửa rồi push GitHub, không phải thành phần vận hành.
- Hướng dẫn hiện hành: `native_oauth/ANTIGRAVITY_WORKFLOW.md`. Hai native reviewer chạy độc lập trong Antigravity và phải có evidence runtime thật; không tự khai identity hay bỏ gate để đổi nền tảng.
- Giữ nguồn/ID/hash, chống partial/mất đoạn, lịch sử revision, continuity và approved manifest trước xuất bản. Không sửa bản truyện cũ hoặc chạy model thật chỉ để kiểm thử code nếu chưa nằm trong phạm vi yêu cầu.

---

# QUY TẮC BẮT BUỘC CHO AGENTS & MỌI LUỒNG LÀM VIỆC — CAOTRUYEN ANTIGRAVITY SESSION VISIBILITY

Tất cả các agents, subagents và script xử lý dịch thuật (Wave Orchestrator, Batch Pipelines, Worker Pools) trong dự án CaoTruyen **BẮT BUỘC TUÂN THỦ** cơ chế hiển thị tiến độ trực tiếp trong session Antigravity:

---

## 1. Hiển Thị Tiến Độ Trực Tiếp Trong Chat / Session (In-Session Visibility)

Mỗi khi thực thi, bắt đầu, hoặc kết thúc bất kỳ lượt dịch chương hay wave nào:
1. **Bảng / Badge Tiến Độ Trong Chat**:
   - Phải hiển thị rõ:
     - Tên tác phẩm & thể loại.
     - Chương hiện tại (`Current Chapter`) & Khoảng chương (`Range`).
     - Wave hiện tại (`Wave X / Y`).
     - Thanh tiến độ & phần trăm (`[████████░░░] XX.X%`).
     - Tổng số từ & số đoạn lũy kế.
     - Trạng thái các luồng Worker song song.
   - Có thể lấy nhanh từ `SessionMonitor.render_markdown_badge()`.

2. **Artifact Dashboard Tự Động (Generative UI & Markdown)**:
   - Hệ thống tự động đồng bộ vào thư mục `<appDataDir>\brain\<conversation-id>`:
     - `translation_live_dashboard.html`: Widget Generative UI tương thích Tailwind CSS và biến theme Antigravity (`--card`, `--foreground`, `--border`, `--background`). Hỗ trợ nhúng qua thẻ `<agent-embed src="file:///.../translation_live_dashboard.html"></agent-embed>`.
     - `translation_session_dashboard.md`: Bảng điều khiển chi tiết cho người dùng theo dõi ở side pane.

---

## 2. Tích Hợp Vào Mọi Pipeline & Script Sau Này (Pipeline Discipline)

Mọi file runner hoặc bộ điều phối mới tạo sau này **BẮT BUỘC** gọi `SessionMonitor`:

```python
from native_oauth.session_monitor import get_session_monitor

# Khởi tạo hoặc lấy monitor
mon = get_session_monitor(book_id=BOOK_ID, book_title=BOOK_TITLE, total_chapters=TOTAL_CHAPS)

# Khi bắt đầu dịch chương/wave
mon.record_worker_active(worker_id="Worker-1", chapter_num=chap_num, wave_num=wave_idx)

# Khi dịch xong một chương
mon.record_chapter_done(
    chapter_num=chap_num,
    title=title,
    wave_num=wave_idx,
    worker_id="Worker-1",
    paragraphs=len(paras),
    words=word_count,
    duration_seconds=elapsed,
    gate_pass=is_pass,
    prosody_anomalies=anomalies_count
)
```

Tuyệt đối không chạy luồng dịch ngầm mà không có cơ chế xuất trạng thái hiển thị trực tiếp cho phiên làm việc Antigravity của người dùng.
