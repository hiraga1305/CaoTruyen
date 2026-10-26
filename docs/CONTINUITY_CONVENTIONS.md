# Quy ước tên, thuật ngữ và xưng hô cho mọi truyện

Áp dụng cho mọi sách/thể loại chạy workflow 2.2, không cần nhánh theo tên truyện hoặc book_id. Antigravity thực hiện các bước dưới đây trong phiên vận hành; không có bước duyệt phụ thuộc Codex.

## Mục tiêu và giới hạn

Giữ một cách viết nhất quán cho cùng tên riêng, nickname, danh hiệu, nhãn nghề/năng lực, vật phẩm, địa danh và tổ chức. Giữ xưng hô đúng người nói, người nghe, ngôi kể và thời điểm. Cách viết là quy ước biên tập, không phải bằng chứng một người thật sự mang nghề, giới tính, quan hệ hoặc danh tính được nhắc đến. Lời giả mạo, suy đoán và lời kể không đáng tin vẫn là lời giả mạo/suy đoán.

Không ép một từ Việt ở mọi chỗ có cùng chữ Trung. Chức nghiệp được đặt tên khác mô tả nghề thông thường; nickname khác lời gọi chú/bác/anh; trích dẫn và cách nhân vật cố ý gọi sai cần giữ đúng ý nguồn. Không suy giới tính/tuổi/quan hệ từ âm Hán–Việt, không coi mọi “hắn/cô ấy/anh” là nhân vật chính.

## Chuẩn bị bảng cho một sách

1. Antigravity đọc lore, canon local và prefix approved đã xác minh của chính sách đang dịch. Với sách mới, chọn cách viết từ các đoạn nguồn được giao, không mượn bảng của sách khác. Không cần lập từ điển toàn bộ sách trước khi bắt đầu.
2. Mỗi quy ước cần ID và trích dẫn nguyên văn nguồn, cách viết Việt, loại mục, khóa ổn định và phạm vi. Bản approved nhất quán đầu tiên là ứng viên để kế thừa, không là chân lý nếu chính prefix đã mâu thuẫn. Cách viết Việt là lựa chọn biên tập; nguồn chứng minh chữ Trung và ngữ cảnh chứ không tự chứng minh chính tả Việt.
3. Xác minh lại nguồn và thực thể trước khi nhập một suggestion. Hai tên Việt khác nhau không tự chứng minh hai người; cùng chữ Trung hoặc cùng âm Việt không tự chứng minh cùng người. Alias tiếng Trung phải có chứng cứ cùng thực thể trong trích dẫn; nếu chưa đủ, giữ hai mục riêng và yêu cầu context.
4. Chỉ khóa xưng hô khi có bằng chứng về người nói–người nghe và phạm vi; giữ trung tính khi nguồn chưa đủ. Quy tắc đại từ ngôi kể không thay tên trong lời thoại. Mốc áp dụng không được sớm hơn chương chứa chứng cứ; không đưa tiết lộ tương lai vào prompt trước thời điểm.
5. Lưu vào `BOOK_DIR/translation_canon.json`, trường `continuity_entries`. `lore.json` vẫn là gợi ý từ vựng; không tự trở thành một tập luật thực thể bắt buộc thiếu nguồn. Bảng có thể rỗng; cả hai reviewer vẫn phải kiểm nhất quán và xưng hô.

## Schema dùng chung

Ví dụ hư cấu minh họa, chỉ chạy được sau khi sách thật có đúng ID/quote tương ứng:

```json
{
  "continuity_entries": [
    {
      "key": "person-001",
      "kind": "name",
      "zh": "江月",
      "vi": "Giang Nguyệt",
      "scope": "Tên nhân vật này trong lời kể và lời thoại. Đại từ rõ chủ thể được phép; không suy giới tính từ tên.",
      "source_id": "c0002p0001",
      "source_quote": "江月走了。",
      "aliases_vi": [],
      "valid_from_chapter": 2
    }
  ]
}
```

Các trường bắt buộc: `key`, `kind`, `zh`, `vi`, `scope`, `source_id`, `source_quote`.

| Trường | Quy tắc |
|---|---|
| `key` | Khóa riêng trong sách; không đổi chỉ vì chữ Việt thay đổi |
| `kind` | `name`, `title`, `profession`, `item`, `place`, `faction`, `address`, `pronoun`, `term` |
| `zh` / `vi` | Cách gọi nguồn và cách viết Việt đã chọn; phạm vi quyết định lúc nào áp dụng |
| `scope` | Nêu thực thể/ngữ cảnh, biệt danh hay cách gọi, nghĩa thông thường hay nhãn đặt tên; ghi ngoại lệ rõ |
| `source_id` / `source_quote` | ID đoạn thật của cùng sách và trích dẫn nằm nguyên văn trong đoạn đó, có chứa `zh` |
| `aliases_zh` | Tùy chọn; từng alias phải có mặt trong cùng trích dẫn chứng minh danh tính. Chưa đủ chứng cứ thì chưa nhập alias |
| `aliases_vi` | Tùy chọn; cách gọi Việt được phép trong phạm vi, không tự gộp thực thể |
| `valid_from_chapter` | Tùy chọn, mặc định chương chứng cứ; không được sớm hơn |
| `valid_to_chapter` | Tùy chọn; kết thúc hiệu lực, không trước mốc bắt đầu |
| `speaker_zh` / `addressee_zh` | Bắt buộc với `kind: address`; cả hai phải xuất hiện trong trích dẫn chứng cứ. Phạm vi vẫn do reviewer kiểm |

Một tên Trung trùng nhau có thể có nhiều `key` nếu là các thực thể/phạm vi khác nhau; không host merge tự động. Các alias chưa được nguồn xác minh không được nhập chỉ vì “nghe giống”. Thêm quan hệ/giới tính vào scope vẫn phải có chứng cứ thật, không suy từ tên hoặc một câu thoại mơ hồ.

## Trong dịch và review

- Runner chọn những mục đã có hiệu lực và xuất hiện trong chương, bind nguồn và snapshot/hash. Prompt chỉ mang quy ước liên quan; không bơm toàn bộ từ điển vào mỗi request. Source/canon thuộc sách khác, trích dẫn bịa, thiếu hash hoặc proof bị đổi không được dùng.
- Khớp chữ Trung chỉ tạo nghĩa vụ kiểm tra, không chứng minh đúng thực thể hoặc phạm vi. Đoạn chỉ có đại từ và tên mới chưa khai trong bảng vẫn do hai reviewer đọc toàn cảnh, không được tự PASS vì không có mục khớp. Thiếu/đổi cách viết không tự thành lỗi cứng bằng tìm chuỗi.
- Translator giữ tên/nhãn theo phạm vi, đọc nguồn lân cận trước khi chọn xưng hô. Không sửa nháp của worker khác để tạo “canon”; cùng wave vẫn là bản chưa duyệt.
- Hai reviewer độc lập kiểm đủ nguồn–đích, cả tên mới chưa có bảng, sự thống nhất trong wave và prefix/context được cung cấp. Cùng thực thể/nhãn bị đổi cách gọi không có lý do nguồn là lỗi `continuity` hoặc `entities`, không hạ thành “văn phong”. Sai người nói/người nghe là `speaker_pronouns`. Không đủ context dùng `needs_context` với query nguyên văn.
- Mỗi reviewer trả `continuity_checks` với ba chiều `names_and_labels`, `aliases_and_viewpoint`, `speaker_and_addressee`. Đây là xác nhận đã kiểm, không tự chứng minh không còn lỗi.
- Với từng obligation `continuity_convention` trong slot được giao, trả `continuity_decisions: [{slot,key,status,reason}]`. Thứ tự theo catalog rồi obligation; không bỏ/nhân đôi/chuyển slot. Cả hai reviewer đều phải trả, không xem kết luận peer.

| `status` | Yêu cầu |
|---|---|
| `consistent` | Cách viết chuẩn hoặc một `aliases_vi` có mặt trong đích và đúng phạm vi/thực thể theo đánh giá native |
| `valid_variation` | Giải thích chủ thể và vì sao đại từ, nickname, lời gọi, trích dẫn hoặc nghĩa ngoài phạm vi được phép; không chặn chỉ vì thiếu chuỗi tên |
| `violation` | Có issue bắt buộc cùng slot: `continuity`, `entities` hoặc `speaker_pronouns`; row và verdict phải FAIL |
| `needs_context` | Có issue `needs_context` và `context_query` ngắn nguyên văn thuộc nguồn được phép tra |

Việc chỉ đánh dấu đã kiểm hoặc viết một lý do không bảo đảm đánh giá ngữ nghĩa đúng. Host kiểm ownership/schema/bằng chứng; native reviewer chịu trách nhiệm quyết định phạm vi và danh tính. Không thay quyết định bằng regex hoặc mặc định PASS.

## Sửa và tích lũy quy ước

Sửa đúng ID lỗi bằng native HIGH, giữ nguyên các đoạn tốt có proof, rồi cả hai reviewer kiểm bản ghép. Không sửa approved bằng replace và không đổi verdict trong runtime cũ. Hai PASS và `next_actions: []` không phải chứng nhận hết sạn; báo cả suggestions và giới hạn lấy mẫu.

Antigravity bổ sung bảng khi gặp tên/nhãn lặp lại có nguy cơ trôi hoặc khi review phát hiện mâu thuẫn. Chỉ kế thừa cách dùng từ source/approved đã xác minh, ghi rõ alias/phạm vi; suggestion không tự thành canon. Quy ước chưa rõ phải giữ vấn đề cần đối chiếu thay vì chọn bừa biến thể.

Canon được freeze theo job. Nếu cần đổi, tạo job revision mới tại prefix hợp lệ, lưu lịch sử thay đổi và tái sử dụng các chương đã duyệt. Không đổi file canon giữa run, không mở lại hàng nghìn chương đã duyệt chỉ để đổi nhãn job. Chỉnh bản cũ cần revision và review riêng có bằng chứng. Checkpoint 100 chương không thêm lượt model audit, không chờ người dùng/Codex duyệt định kỳ.

Mặc định vẫn bốn translator MEDIUM, tối đa năm chương/wave, hai reviewer MEDIUM đồng thời; HIGH phục hồi tập trung. Không thêm model call riêng chỉ để đánh dấu đã kiểm continuity. Bản approved cũ giữ schema/policy cũ; muốn kiểm theo policy mới phải tạo revision thật, không đổi nhãn bằng host.
