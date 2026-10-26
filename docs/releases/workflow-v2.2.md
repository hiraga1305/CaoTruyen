# CaoTruyen workflow 2.2.0

Chuẩn hóa continuity cho mọi sách/thể loại, policy bổ sung `scoped-continuity-1`. Giữ content/review v2, bốn translator, tối đa năm chương/wave, hai reviewer đồng thời và HIGH sửa tập trung.

- `translation_canon.json` hỗ trợ `continuity_entries`: key, loại mục, chữ nguồn/cách viết Việt, scope, ID/quote và mốc áp dụng; xưng hô cần chứng cứ người nói–người nghe. Không mặc định tên/giới tính/quan hệ của một truyện cho truyện khác.
- Runner xác minh cùng sách, ID/trích dẫn, snapshot/hash; chỉ chọn các mục liên quan đã có hiệu lực. Không tự suy alias hoặc nhận diện tất cả thực thể bằng host.
- Cả hai native reviewer phải kiểm tên/nhãn, alias/góc nhìn, người nói–người nghe ngay cả khi bảng rỗng. Từng mục đang áp dụng có quyết định giải thích theo slot/key; vi phạm/ngữ cảnh thiếu phải có issue bắt buộc, không chỉ style suggestion. Đại từ và biến thể hợp lệ được kiểm ngữ cảnh, không thất bại chỉ vì thiếu chuỗi tên.
- Hướng dẫn chung quy định cách Antigravity chuẩn bị/cập nhật bảng bằng nguồn/approved đã xác minh, tạo job revision khi canon đổi và sửa đúng ID. Không thêm model call hoặc reviewer thứ ba.

Code và tài liệu mới không sửa dữ liệu truyện, source/approved hoặc bundle cũ. Policy mới chỉ áp dụng packet mới; evidence cũ vẫn replay theo schema cũ, không được đổi nhãn thành đã qua continuity policy mới. Native benchmark 2.1 không phải benchmark 2.2; phần output review mới có overhead, cần đo trong phạm vi người dùng giao.

Hướng dẫn: [CONTINUITY_CONVENTIONS.md](../CONTINUITY_CONVENTIONS.md). Prompt dùng chung: [continue-translation.md](../prompts/continue-translation.md).
