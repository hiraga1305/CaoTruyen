# HƯỚNG DẪN ĐIỀU PHỐI 2 PIPELINE DỊCH THUẬT TIỂU THUYẾT
**Tác phẩm:** 《没钱修什么仙？》 (Không Tiền Tu Cái Gì Tiên?) - Tác giả Hùng Lang Cẩu  
**Thư mục làm việc:** `i:\Softs\Antigravity\CaoTruyen\`

Dự án được thiết kế phân tách hoàn toàn thành **2 Pipeline độc lập**, dùng chung kho dữ liệu và có thể luân phiên kích hoạt tùy theo quyết định của bạn:

---

## 1. SO SÁNH & NGUYÊN TẮC LỰA CHỌN PIPELINE

| Tiêu chí | PIPELINE 1: LOCAL NATIVE SWARM | PIPELINE 2: MULTI-PROVIDER API |
|---|---|---|
| **Nền tảng chạy** | Chạy trực tiếp trong **Antigravity IDE** trên PC | Chạy độc lập trên **bất kỳ máy tính nào** hoặc **VPS Cloud** (Linux/Windows) |
| **Model xử lý** | **Gemini 3.8 Flash Native** của Antigravity | **Tùy chọn đa nguồn:** Gemini API, DeepSeek V3/R1, OpenRouter, Qwen, Ollama... |
| **Tài nguyên tiêu tốn** | Hạn mức Rolling Quota 5 giờ của Antigravity (0 đồng) | API Key do bạn cung cấp (Free tier hoặc trả phí theo token) |
| **Tốc độ xử lý** | **Siêu tốc (~10s/chương)**, chạy song song 10 Subagent | Tùy thuộc vào tốc độ mạng và rate-limit của từng Provider API |
| **Nguy cơ lỗi 429** | **0%** (Hạ tầng Enterprise Agent của Google) | Phụ thuộc vào giới hạn RPM của Provider bạn chọn |
| **KHI NÀO NÊN DÙNG?** | **Dùng khi còn Quota 5h trên Antigravity** để dịch với tốc độ và chất lượng tối đa. | **Dùng khi hết Quota 5h**, hoặc khi muốn **treo máy ban đêm/đưa lên VPS Oracle** để dịch ngầm độc lập. |

---

## 2. HƯỚNG DẪN PIPELINE 1: LOCAL NATIVE SUBAGENT (TRÊN ANTIGRAVITY)

Quy trình gồm 2 bước tự động:

### Bước 1: Chuẩn bị nguyên liệu bằng Chivi 3 Local (0ms, 0 RAM, 0% Quota)
Chạy script để cào RAW từ web, bóc tách cây ngữ pháp Chivi 3 AST và gán nhãn thực thể từ `novel_lore.json`:
```powershell
# Chuẩn bị 1 chương
python prepare_for_agent.py --chap 82

# Hoặc chuẩn bị hàng loạt 100 chương (chỉ mất ~1-2 phút)
python prepare_for_agent.py --from_chap 82 --to_chap 181
```
Nguyên liệu sạch sẽ được lưu tại thư mục: `prepared_input/chap_XXX_....txt`.

### Bước 2: Sinh cụm Subagent Native dịch song song
Yêu cầu Antigravity sinh cụm Subagent kiểu `native_novel_translator` (mỗi subagent nhận 2 chương).
Subagent sẽ tự động dùng trí tuệ **Gemini 3.8 Flash nội tại**, đọc file từ `prepared_input/` và ghi thẳng vào `output_dich/chuong_XXX.txt`.

---

## 3. HƯỚNG DẪN PIPELINE 2: MULTI-PROVIDER API (ĐEM SANG MÁY KHÁC / VPS)

Pipeline này hoàn toàn độc lập, không cần mở Antigravity IDE, có thể copy toàn bộ thư mục sang máy khác hoặc VPS Linux.

### Cài đặt thư viện (nếu mang sang máy mới / VPS):
```bash
pip install -r requirements.txt
```

### Cấu hình đa nhà cung cấp trong `api_config.json`:
Bạn có thể mở file [`api_config.json`](api_config.json) để điền API Keys hoặc đổi Provider mặc định:

```json
{
  "active_provider": "gemini",
  "providers": {
    "gemini": {
      "api_keys": [
        "YOUR_GEMINI_API_KEY"
      ],
      "models": ["gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.1-flash-lite"]
    },
    "deepseek": {
      "api_key": "sk-xxxxxx",
      "base_url": "https://api.deepseek.com/v1",
      "models": ["deepseek-chat", "deepseek-reasoner"]
    },
    "openrouter": {
      "api_key": "sk-or-v1-xxxxxx",
      "base_url": "https://openrouter.ai/api/v1",
      "models": ["deepseek/deepseek-chat", "qwen/qwen-2.5-72b-instruct"]
    },
    "custom_openai": {
      "api_key": "gsk_xxxxxx",
      "base_url": "https://api.groq.com/openai/v1",
      "models": ["llama-3.3-70b-versatile"]
    }
  }
}
```

### Lệnh chạy CLI của Pipeline 2:

1. **Chạy theo Provider mặc định được cấu hình trong `api_config.json`:**
   ```bash
   python pipeline_api.py --from_chap 82 --to_chap 100
   ```

2. **Chỉ định trực tiếp Provider qua lệnh CLI:**
   ```bash
   # Dùng DeepSeek V3 / R1
   python pipeline_api.py --from_chap 82 --to_chap 100 --provider deepseek

   # Dùng OpenRouter (Qwen 2.5 72B / Claude...)
   python pipeline_api.py --from_chap 82 --to_chap 100 --provider openrouter

   # Dùng Google Gemini API
   python pipeline_api.py --from_chap 82 --to_chap 100 --provider gemini
   ```

3. **Chạy đúng 1 chương cụ thể:**
   ```bash
   python pipeline_api.py --chap 82
   ```

---

## 4. CƠ CHẾ ĐỒNG BỘ THÔNG MINH (CHỐNG DỊCH TRÙNG)

- Cả **Pipeline 1** và **Pipeline 2** đều xuất bản phẩm vào chung một thư mục: [`output_dich/`](output_dich/).
- Cả hai pipeline đều có cơ chế **Smart Skip**: Khi gặp một chương đã có file trong `output_dich/` và dung lượng > 1KB, hệ thống sẽ **tự động bỏ qua trong 0.01 giây**.
- **Ý nghĩa thực tế:** Bạn có thể dùng Pipeline 1 dịch 150 chương ban ngày trên PC. Ban đêm khi hết Quota, bạn bật Pipeline 2 lên (hoặc chạy trên VPS), Pipeline 2 sẽ tự động nhận biết 150 chương đã xong và tiếp tục dịch từ chương 151 trở đi mà không bị trùng lặp hay ghi đè!

---

## 5. TÀI LIỆU HƯỚNG DẪN TRIỂN KHAI SANG MÁY KHÁC / VPS

Xem tài liệu đầy đủ chi tiết tại: [`DEPLOYMENT_GUIDE.md`](DEPLOYMENT_GUIDE.md)

Lệnh đóng gói 1-Click để chuyển máy:
```powershell
# Nén toàn bộ mã nguồn + cấu hình + từ điển (chỉ ~50KB)
python package_project.py

# Hoặc nén kèm toàn bộ các chương đã dịch (1..81):
python package_project.py --include-output
```
