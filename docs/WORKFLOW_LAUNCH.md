# Khởi động và tiếp tục bằng workflow hiện hành

Áp dụng cho mọi sách và mọi phiên bản sau này. Đọc phiên bản từ canonical GitHub main và workflow.json, không ghi cứng 2.1/2.2/2.3 trong yêu cầu vận hành.

## Vì sao một chiến dịch vẫn có thể dùng bản cũ

Prompt là chỉ dẫn; job freeze, code đã import và tiến trình đang chạy là trạng thái thật. Một lệnh watch có thể gọi nhiều invocation trên cùng Runner/Python process. Push commit không thay những module đã nằm trong bộ nhớ. Tiếp tục một snapshot cũ vẫn có thể tự nhất quán với configuration cũ. Chỉ kiểm file version hoặc in một badge “bản mới” không chứng minh đã đổi runtime.

Guard bổ sung ba bước: xác minh release, chọn job, và chặn tại native gateway. Không gọi model để kiểm phiên bản. Đây là kiểm code vận hành, không là reviewer/approval nội dung và không phụ thuộc Codex.

## Đồng bộ an toàn và kiểm tra

Antigravity fetch canonical main và đọc hướng dẫn mới nhất từ đó trước khi chọn lệnh. Repo chuẩn là https://github.com/hiraga1305/CaoTruyen. Nếu local chưa khớp, cập nhật workflow an toàn; giữ source, approved, credential, runtime, bundle và thay đổi ngoài workflow. Không dùng reset --hard, không xóa job, không ghi đè code người dùng đang sửa để vượt gate.

```powershell
git fetch origin main
git show origin/main:workflow.json
git show origin/main:docs/prompts/continue-translation.md
# Sau khi đồng bộ code/hướng dẫn mà vẫn bảo toàn dữ liệu:
python -X utf8 translate.py doctor
```

Doctor kiểm hash code/hướng dẫn theo workflow_release.json, policy implementation và version; root phải là Git checkout thật, HEAD phải trùng canonical GitHub main và lock phải đúng blob trong commit đó. Không tin chỉ tên nhánh origin hoặc chữ version. Thay đổi không liên quan trong các thư mục sách không làm gate lỗi. Doctor không dịch hoặc sửa approved.

`doctor --job LAST_JOB` còn báo job có cùng release hay cần revision. CURRENT là trạng thái checkout; hãy đọc thêm job_action. Không được dùng kết quả CURRENT để sửa nhãn job cũ.

## Một lệnh live dùng chung

```powershell
python -X utf8 translate.py launch --book-dir BOOK_DIR --job LAST_JOB --through-chapter AUTHORIZED_END
```

AUTHORIZED_END là chương cuối người dùng đã giao; không tự lấy một con số cố định của sách khác. Với sách mới có thể bỏ --job. Với sách đang dịch, LAST_JOB là đường dẫn selected_job đã được trả lần gần nhất, không phải thư mục pilot ghi trong hội thoại cũ.

Launch xác minh canonical release trước, thử resume khi code/canon/phạm vi/cấu hình khớp. Nếu configuration cũ không khớp, tự chọn thư mục revision mới, giữ nguyên job cũ và tái sử dụng prefix approved được runner xác minh. Nếu job cũ có effective_sources, chỉ import replacement qua validator có lineage. Nháp/evidence cũ giữ lại; chỉ tái sử dụng khi proof/source/canon/policy thực sự còn hợp lệ, không đổi hash để giữ cache.

Startup in JSON WORKFLOW_CURRENT và ghi workflow_startup.json, workflow_starts/*.json: version thực, Git commit, release hash, policy, job, book, phạm vi, PID và configuration hash. Đây là evidence host về code, không giả identity/model native. File JSON không cấp quyền: quyền gọi model chỉ tồn tại trong invocation của process đã xác minh.

Đầu mỗi invocation và biên wave kiểm canonical GitHub main; trước mỗi native call kiểm code/lock, job configuration, owned workspace, role/model và policy packet. Code/upstream mới hoặc configuration bị đổi thì dừng request tiếp theo, lưu hành động sync/restart/new revision. Không hạ về bản cũ để tiếp tục. Run/watch/API vẫn qua cùng guard, nên CLI nâng cao không là đường bỏ kiểm tra. Report/status/seal và replay evidence lịch sử vẫn dùng được offline; chúng không biến evidence cũ thành policy mới.

GitHub không truy cập được thì chưa thể chứng minh “current”: giữ queue và kiểm lại sau, không chuyển sang snapshot cũ. Không có --skip-gate/--force-version hoặc biến môi trường để bỏ kiểm tra. Không dựng receipt giả hoặc tái sinh lock chỉ để khớp code local.

## Chuyển một process đang chạy

Không chạy hai orchestrator đồng thời trên cùng sách. Lưu trạng thái tại biên an toàn, dừng process cũ rồi chạy launch mới. Process đã nạp code trước thời điểm guard được triển khai không thể tự nhận bản vá này; CLI/script nằm ngoài repo hoặc bản snapshot hoàn toàn độc lập cũng không chịu sự kiểm soát của gateway mới. Vì vậy lệnh chuẩn và prompt phải cấm các đường này, không hứa kiểm soát mọi executable trên máy.

Vẫn dùng bốn translator, tối đa năm chương/wave, hai reviewer độc lập chạy đồng thời và HIGH sửa tập trung; continuity theo hướng dẫn chung. Guard phiên bản không tự sửa danh xưng và không thay đổi approval cũ. Không thêm một native audit để lập biên bản phiên bản.

## Khi phát hành workflow tiếp theo

Người phát triển thay code/docs/version và chạy `python tools/update_workflow_release.py` để tạo lock từ các file workflow được quản lý; commit/push cùng nhau rồi kiểm CI. Người vận hành không chạy lệnh tái sinh lock để vượt mismatch. Các test offline mock ranh giới mạng/transport có kiểm soát, không có bypass production. Nhờ đọc metadata/lock từ main, prompt vẫn dùng được cho 2.4 hoặc phiên bản sau mà không cần sửa con số.
