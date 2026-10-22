# Đánh giá ngữ nghĩa, tên riêng và xưng hô — 21/10/2026

## Kết luận

**Chưa đủ hợp lý và nhất quán để coi phần ngữ nghĩa đã được giải quyết.** Bản vá trước sửa tính đầy đủ, provenance, cache và điều kiện xuất bản. Bộ sinh hiện vẫn có tín hiệu phân vai sai, prompt mâu thuẫn và danh mục nhân vật/quan hệ chưa đủ để điều khiển 325 chương.

Có đoạn dịch thực tế xử lý tốt cách xưng hô. Điều đó không chứng minh bộ phân vai đúng: cùng câu nguồn, router hiện tại gắn sai người nói/nghe nhưng model trước đây vẫn có thể tự đọc đúng nguồn. Những thẻ đoán sai rồi bị prompt yêu cầu tuân thủ tuyệt đối có thể làm chất lượng kém đi.

Phạm vi: đọc mã/config hiện tại, kiểm 16 đoạn song ngữ được chọn theo rủi ro trong dữ liệu cũ của book 49736, rà biến thể tên trong TXT và tái hiện router/gate bằng nguồn tổng hợp. Cả 16 quote đều tìm thấy nguyên văn trong source hiện có. Kiểm thêm cấu hình runner 14713/16014; không chấm toàn bộ hai truyện đó. Không gọi model hoặc tạo bản dịch mới sau vá; không suy ra tỷ lệ đúng toàn truyện.

## Các lỗi cơ chế đã tái hiện

### 1. Router đoán người nói/nghe từ thứ tự entity

`bns_prepass.py:432` mặc định speaker là entity đầu và listener là entity thứ hai. Khi thấy tên quanh quote, nó vẫn thường chọn listener là người đầu tiên khác tên speaker, không phân tích vai của `A đối với B nói`.

| Nguyên văn thử | Vai đúng | Kết quả hiện tại |
|---|---|---|
| `姜柔甲对秦疏影说：“你先坐。”` | Khương Nhu Giáp → Tần Sơ Ảnh | Khương Nhu Giáp → Vân Thiên Phong |
| `秦疏影对云千峰说：“我去接孩子。”` | Tần Sơ Ảnh → Vân Thiên Phong | Vân Thiên Phong → Khương Nhu Giáp |

Mẫu thật chương 1, `c0001p0018`, là lời người phụ nữ nói “Anh trai tôi biến mất rồi…”. Đoạn trước chỉ rõ bà/cô ấy ngắt lời nam chính. Router vẫn gắn `云千峰->姜柔甲`.

Mẫu thật chương 43, `c0043p0049`, là Tần Sơ Ảnh gọi điện cho con. Bản dịch “Tiểu Trăn… mẹ đang tăng ca…” phù hợp ngữ cảnh, nhưng router vẫn gắn cặp Vân Thiên Phong → Khương Nhu Giáp. Hàm gọi router riêng cho từng đoạn, chưa mang trạng thái người nói liên đoạn vào bước này.

### 2. Giản thể/phồn thể và chức danh bị coi như người khác

Entity metadata của wujian lấy từ lore chỉ có `云千峰` và `姜柔甲`; trong toàn bộ source 49736, các dạng này xuất hiện 0 lần, còn `雲千峰` có 8.656 và `薑柔甲` có 668 lần. Model có thể đọc hai dạng chữ, nhưng phép tìm tên literal trong prepass thì không tự đồng nhất chúng.

Batch runner thêm cả giản/phồn như hai EntityRecord độc lập. Tái hiện với cùng câu Tần Sơ Ảnh nói với Vân Thiên Phong, router cho `云千峰->雲千峰`: cùng một người bị coi thành hai phía hội thoại. Cấu hình 14713 cũng tách `萧羽` và chức danh `萧大师` thành hai record mà chưa có identity chung trong runner.

Cần một entity ID với nhiều alias có chứng cứ; không sửa raw để giải quyết vấn đề này. Module vault/TEKG đã có một phần schema alias, nhưng runner đang xét không dùng nó để phân vai.

### 3. Từ khóa giận dữ không đủ để đổi cặp xưng hô

`云千峰对姜柔甲说：“别找死，快回来！”` có thể là lời cảnh báo bảo vệ: “Đừng liều mạng, quay lại mau!”. Router thấy `找死` và gắn HOSTILE_SHIFT/sát phạt. Đây là ví dụ tổng hợp chứng minh thiếu xử lý ngữ cảnh, không phải kết luận mọi lần gặp từ này đều bảo vệ.

`route_dialogues` tạo rule `ta–ngươi` khi hostile, kể cả khi gọi từ runner đô thị. `build_scene_contract` lại không nhập `new_p_rules` vào matrix. Ngoài ra tag mặc định COURTEOUS trong khi lore dùng COURTEOUS_MODERN. Kết quả là tag và matrix có thể không có hàng tương ứng; model phải tự giải mâu thuẫn.

### 4. Prompt của các route mâu thuẫn

Wujian có prompt riêng theo đô thị, định hướng tôi–anh/cô tốt cho cảnh giao tiếp ban đầu. Nhưng câu cố định yêu cầu cặp đó cho Vân Thiên Phong/Khương Nhu Giáp vẫn đi vào mọi scene, không có thời điểm hoặc phạm vi quan hệ.

Các batch runner dùng `bns_system_cache_v1.md`. Prompt này yêu cầu tuân thẻ 100%, đồng thời cấm tôi–anh/cô/bạn và các trợ từ hiện đại ở phần đối thoại. Trong khi matrix của 14713/49736 lại cho tôi–anh/cô; matrix 16014 cho em–thầy và tôi–ông giữa bạn học. Chỉ đổi trường genre không xóa được chỉ dẫn ngôn ngữ mâu thuẫn trong prompt.

Prepass còn chọn chủ thể ẩn theo entity đầu tiên xuất hiện hoặc người đầu danh sách. Những thẻ đó là dự đoán heuristic; không được nâng thành sự thật cao hơn nguyên văn.

### 5. Gate cơ học chưa kiểm được vai nghĩa

Với nguồn “Tần Sơ Ảnh nói với Vân Thiên Phong: Tôi đi đón con”, cố tình đưa bản dịch “Vân Thiên Phong nói với Khương Nhu Giáp: Tôi đi đón con”: QualityGate4A hiện PASS, không có violation.

Đây là **PASS cơ học**, không phải được phép xuất bản: bản vá trước vẫn buộc review nguồn–đích riêng trước publisher. Cờ `speaker_pronouns` trong protocol cũng chỉ có ý nghĩa khi reviewer thực sự đối chiếu từng đoạn; schema/hash không tự hiểu người nói. Kiểm tên có xuất hiện không còn chưa đủ, vì giữ nguyên cả hai tên nhưng đảo chủ thể/tân ngữ vẫn sai.

## Kết quả ở bản dịch thực tế

### Tên riêng: có trôi cách gọi

TXT hiện dùng ba dạng cho cùng chuỗi nguồn `羅琳娜`:

| Dạng tiếng Việt | Số lần xuất hiện trong TXT | Số chương có dạng này |
|---|---:|---:|
| La Lâm Na | 43 | 7 |
| Lorina | 701 | 56 |
| Lorinna | 6 | 1 |

Các quote kiểm trực tiếp: chương 8 dùng La Lâm Na, chương 84 dùng Lorina, chương 294 dùng Lorinna. Nhân vật được giới thiệu là người ở châu Âu, có tước vị. Dùng tên Latin có thể hợp phong cách; bản thân chữ Hán không chứng minh duy nhất phải viết Lorina hay Lorinna. Vấn đề xác nhận được là chưa có quy tắc canonical/alias xuyên chương đủ rõ để giải thích sự đổi tên.

`法緹娜` có Fatina trong TXT. JSON vẫn có ba đoạn Pháp Đề Na, còn TXT hiện không có dạng đó: phải phân biệt lỗi đồng bộ sidecar với lỗi tên đang đến tay người đọc. Không gộp hai loại này thành một thống kê.

Trường hợp Sophie Chung có căn cứ trực tiếp từ nguồn `蘇菲.鍾` (chương 223); không được xem mọi tên Latin là bịa hoặc ép mọi tên nước ngoài thành Hán–Việt.

### Xưng hô: nhiều mẫu đúng, nhưng chưa được quản lý bằng quan hệ có nguồn

- Chương 1: tôi–cô/anh giữa khách và chủ tiệm hợp tình huống ban đầu.
- Chương 43: mẹ–con ở cuộc điện thoại hợp ngữ cảnh.
- Chương 26: chồng chị giữ được quan hệ được nêu trong câu.
- Chương 3: “chị dâu tương lai” giữ đúng `準嫂子` ở một số câu; `c0003p0055` rút xuống “chị dâu trong ký ức”, nên cân nhắc giữ rõ yếu tố tương lai. Đây là nhận xét về sắc thái quan hệ ở câu cụ thể, không kết luận cả mạch đã hiểu sai.
- Nguồn `c0003p0004` giới thiệu Khương Ngọc Lâm là anh trai Khương Nhu Giáp. BASE_ENTITIES lại ghi “Trưởng bối Khương gia”/narr_lock “ông”. Metadata chưa đủ căn cứ để áp cho mọi scene. Không đồng nhất từ “ông” với một tuổi cố định: trong lời bạn bè, tôi–ông còn có thể là xưng hô ngang hàng.

### Ngôi kể phải tách khỏi đối thoại

“Hắn/nàng” trong ngôi kể không tự động sai chỉ vì truyện đô thị. “Anh/cô”, “hắn/nàng” đều có thể là lựa chọn biên tập nếu nhất quán và phù hợp giọng truyện. Đối thoại phải theo cặp nhân vật và tình huống, không suy từ narr_lock.

“Ả/mụ/gã/lão” có thêm thái độ. Ví dụ chương 8 dịch `她` thành “ả ta”; cần xét giọng kể toàn cảnh, không coi đó là phép đổi đại từ trung tính mặc định. Không thay tất cả “nàng” thành “cô”, hoặc thay tên thành đại từ hàng loạt.

Khi nhiều nhân vật cùng giới xuất hiện, cần lặp tên/định danh ở điểm chuyển chủ thể để người đọc biết ai tác động lên ai. Không tối ưu bằng cách đếm tên hoặc ép một nhân vật luôn có cùng một từ gọi trong mọi ngôi kể và lời thoại.

## Cơ chế cần có trước khi khẳng định ngữ nghĩa ổn

1. **Danh mục người có identity ổn định:** canonical name, alias giản/phồn, chức danh/biệt hiệu, giới tính đã biết, quote/ID nguồn và thời điểm được biết. Tên riêng ổn định; bí danh có phạm vi, không tự đổi người vì khác cách viết.
2. **Phân vai theo nhóm hội thoại:** speaker, addressee, lời nói/tự nhủ/trích dẫn, chủ thể/đối tượng và bằng chứng nguồn. Chưa rõ thì UNRESOLVED, không mặc định người đầu danh sách. Thẻ dự đoán phải là advisory.
3. **Quan hệ có chiều và phạm vi:** A→B khác B→A; tự xưng/gọi đối phương phụ thuộc vai vế, thân mật, hoàn cảnh riêng tư/công khai, trêu chọc/mắng/cảnh báo. Thay đổi cần chứng cứ theo scene/chapter; không từ một từ khóa giận dữ mà đổi vĩnh viễn.
4. **Tách sự thật với điều nhân vật tin:** truyện này có ký ức bị can thiệp và quan hệ được nhận thức khác nhau. Cần giữ viewpoint/known_by/valid_from; biết bí mật tương lai không có nghĩa được đổi xưng hô quá khứ làm lộ twist.
5. **Context và ranh scene hợp ngữ nghĩa:** giới hạn 20 đoạn là biện pháp vận hành, chưa phải phân cảnh/hội thoại. Cần overlap nguồn chỉ đọc hoặc giữ nguyên nhóm thoại khi chia. Bốn đoạn cuối chương có thể chứa cảm ơn/vé tháng/lời chúc tác giả; phải phân loại, không xóa raw hoặc coi những dòng đó là memory quan hệ.
6. **Review nghĩa và tiếng Việt độc lập:** đối chiếu actor/recipient, người nói/nghe, phủ định, mức chắc chắn, quan hệ, tên và thêm/bớt ý; kiểm seam trước–sau. Dùng ca chưa xuất hiện khi viết prompt, đo cả lỗi lọt lẫn chặn nhầm. Không lấy regex hoặc điểm tự chấm làm xác suất đúng.

Ưu tiên thực tế là bỏ suy đoán phân vai mang tính bắt buộc, hợp nhất identity/alias và sửa prompt xưng hô trước; sau đó mới nối memory quan hệ có chứng cứ. Không cần thêm một lớp tên gọi kiến trúc mới để giải những lỗi cơ bản này.

## Bằng chứng và phạm vi thay đổi

`audit/semantic_address_review_20261021.evidence.json` chứa 16 quote Trung–Việt, ID nguồn đối chiếu, kết quả router hiện tại, ví dụ gate bỏ lọt và thống kê tên TXT. Thống kê biến thể chỉ là đếm literal, không phải tỷ lệ sai nghĩa.

Lượt này chỉ đánh giá và tạo hai artifact audit; không sửa tiếp code, lore, bản dịch hoặc sách, không gọi model, không đẩy GitHub. Các thay đổi ở working tree từ lượt trước được giữ nguyên. Chưa có bản sinh live sau vá để chấm chất lượng mới; bằng chứng đủ để kết luận cơ chế ngữ nghĩa hiện tại chưa đáng tin dù vận hành đã được siết lại.
