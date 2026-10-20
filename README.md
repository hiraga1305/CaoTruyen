# CaoTruyen v2.0 — High-Fidelity Agentic Web Novel Translation Engine

> **Kiến trúc dịch thuật tiểu thuyết mạng đa tác tử tiệm cận hoàn hảo (Co-engineered with Gemini 4 Argon)**  
> *Đạt chuẩn kiểm thử tự động 120/120 Unit Tests Green (100% Pass in 0.745s)*

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![Tests](https://img.shields.io/badge/Unit%20Tests-120%2F120%20Passing-brightgreen.svg)]()
[![Architecture](https://img.shields.io/badge/Architecture-Agentic%20Zipper%20v2.0-orange.svg)]()
[![License](https://img.shields.io/badge/License-MIT-lightgrey.svg)](LICENSE)

---

## 1. Tổng Quan Kiến Trúc (Architecture Overview)

**CaoTruyen v2.0** là giải pháp dịch thuật văn học mạng (Tiên hiệp, Đô thị, Huyền huyễn, Dã sử...) chuyên sâu từ Trung Văn sang Việt Văn. Hệ thống kết hợp giữa tính xác thực và tốc độ xử lý $O(N)$ của **Rule-based CSDL WAL** với năng lực cảm thụ văn chương tinh tế của **Mạng lưới Đa Tác tử (Multi-Agent Swarm)**.

Khác với các hệ thống dịch thuật dựa thuần vào từ điển máy (như ChiVi/QuickTranslator) hoặc các giải pháp LLM dịch đơn lẻ dễ bị ảo giác và trôi lệch ngữ cảnh (context drift), CaoTruyen v2.0 áp dụng **4 Trụ Cột Đột Phá** được cố vấn thiết kế bởi siêu mô hình tư duy sâu **Gemini 4 Argon**.

```mermaid
flowchart TD
    Raw[50+ Raw Chinese Chapters] --> Prescan[Phase 1: Zipper Pre-Scan<br/>0-Token AST & Regex Extraction]
    Prescan --> Candidates[Discovered Candidates<br/>Guests, Gifts, Skills, Factions]
    Candidates --> LockCall[Phase 1.5: Micro-Lock Call<br/>1 Cheap Call to Approve Batch Glossary]
    LockCall --> Vault[(GlobalEntityVault<br/>SQLite WAL + In-Memory Aho-Corasick)]
    
    Vault --> Hydrate[Hydrate Scene Contracts<br/>O(N) Exact Matching per Chapter]
    Hydrate --> Subagents[Parallel Subagents Dispatch<br/>Subagent 1..N: 5-10 Chapters/Agent]
    
    Subagents --> Gatekeeper[Deterministic Delta Gatekeeper<br/>0-Token Rule Firewall]
    Gatekeeper --> |Reject Phantom Entity| Block1[ERR_HALLUCINATED_ZH]
    Gatekeeper --> |Reject Pronoun Drift| Block2[ERR_LOCKED_MATRIX_PROTECTED]
    Gatekeeper --> |Approved Deltas| VaultSync[Atomic Commit to Vault & StoryStore]
    Gatekeeper --> CleanDraft[Approved Vietnamese Chapters]
```

---

## 2. Bốn Trụ Cột Đột Phá (The 4 Argon Pillars)

### 🏛️ Trụ Cột 1: `GlobalEntityVault` (`native_oauth/global_vault.py`)
- **Khắc phục hội chứng "Nhân vật Boomerang"**: Trong các bộ truyện dài hàng triệu từ, một nhân vật phụ xuất hiện ở Chương 5 có thể biến mất 200 chương và tái xuất ở Chương 205.
- **Giải pháp**: Cơ sở dữ liệu SQLite WAL duy trì trạng thái dài hạn kết hợp với cấu trúc cây **Aho-Corasick Automaton** trong bộ nhớ RAM. Cung cấp khả năng rà quét và đánh thức thực thể (wake-up) với độ phức tạp $O(N)$ theo độ dài văn bản gốc, tự động khóa ma trận xưng hô gốc vào `@LOCKED_GLOSSARY`.

### ⚡ Trụ Cột 2: `TwoPhaseZipperCoordinator` (`native_oauth/zipper_coordinator.py`)
- **Dịch song song Zero-Drift**: Giải quyết triệt để nguy cơ phân nhánh thuật ngữ khi giao các cụm chương cho nhiều Subagents xử lý cùng lúc.
- **Quy trình 2 pha**:
  1. *Phase 1 (Pre-Scan 0-Token)*: Quét toàn bộ batch chương bằng Regex AST để trích xuất trước danh xưng khách vãng lai, bảo bối, pháp bảo, công pháp.
  2. *Phase 1.5 (Micro-Lock)*: Thực hiện 1 lệnh LLM giá rẻ duyệt khóa nghĩa chuẩn cho toàn batch.
  3. *Phase 2 (Parallel Dispatch)*: Bơm các SceneContract đã khóa thuật ngữ vào các Subagents (5-10 chương/agent), cam kết 100% đồng nhất từ vựng.

### 🛡️ Trụ Cột 3: `DeterministicDeltaGatekeeper` (`native_oauth/delta_gatekeeper.py`)
- **Tường lửa 0-Token chống Ảo giác**:
  1. *Chặn thực thể ma (`ERR_HALLUCINATED_ZH`)*: Bắt buộc chuỗi `chinese_name` do LLM đề xuất phải tồn tại nguyên vẹn trong văn bản thô tiếng Trung.
  2. *Bảo vệ ma trận xưng hô (`ERR_LOCKED_MATRIX_PROTECTED`)*: Không cho phép LLM tự tiện hoán đổi ngôi xưng (ví dụ: *sư phụ - đồ nhi* thành *chàng - thiếp*) trừ khi có bằng chứng sự kiện rạn nứt (`break_event`) được trích dẫn cụ thể.

### 🔮 Trụ Cột 4: `PendingProphecyBuffer` (`native_oauth/scene_contract.py`)
- **Đồng bộ Sấm truyền / Điềm báo Cốt truyện**: Bắt trọn vẹn các điềm báo, sấm ngôn cài cắm từ các chương đầu (`@PENDING_OMENS`) và tự động kích hoạt câu dịch dội âm (echo match) chính xác từng từ khi biến cố ứng nghiệm ở các chương sau.

---

## 3. Hệ Thống Subagents Chuyên Biệt (`.agents/agents/`)

CaoTruyen phân rã tác vụ dịch văn học thành 5 vai trò tác tử độc lập:

1. **`novel-crawler`**: Tự động bóc tách và chuẩn hóa chương từ các nguồn web công khai, loại bỏ rác quảng cáo và kiểm tra tính toàn vẹn của mã nguồn.
2. **`novel-research`**: Tra cứu căn nguyên ngữ cảnh văn hóa, điển tích, phương ngữ và tiêu chuẩn Hán-Việt cổ/hiện đại.
3. **`novel-translator`**: Dịch văn học theo từng phân đoạn, bám sát hợp đồng phân cảnh `SceneContract` và ma trận xưng hô cố định.
4. **`novel-reviewer`**: Phản biện độc lập song ngữ, đối chiếu từng câu tiếng Trung và bản nháp tiếng Việt để phát hiện sót nghĩa hoặc dịch nhầm thể loại.
5. **`novel-auditor`**: Kiểm định độ mượt của văn phong tiếng Việt thuần thục, tinh chỉnh nhịp điệu và cảm xúc văn học trước khi phát hành.

---

## 4. Cấu Trúc Thư Mục Dự Án

```
CaoTruyen/
├── .agents/agents/               # Định nghĩa các chuyên gia Subagents
├── native_oauth/                 # Lõi xử lý ngôn ngữ & điều phối cấp cao
│   ├── global_vault.py           # SQLite WAL + In-Memory Aho-Corasick
│   ├── zipper_coordinator.py     # Bộ điều phối dịch song song 2 pha Zero-Drift
│   ├── delta_gatekeeper.py       # Tường lửa 0-token chống ảo giác LLM
│   ├── scene_contract.py         # Cấu trúc Hợp đồng phân cảnh SceneContract DSL
│   ├── bns_prepass.py            # Tiền xử lý cấu trúc nguồn & thực thể
│   ├── story_store.py            # Lưu trữ trạng thái và chỉ mục ngữ cảnh
│   └── quality_gate.py           # Cổng chất lượng văn học đa tiêu chí
├── tests/                        # 120 Unit tests bao phủ toàn diện
│   ├── test_perfection_architecture.py
│   ├── test_batch_contract.py
│   ├── test_batch_experiment.py
│   ├── test_batch_policy.py
│   ├── test_semantic_gate.py
│   ├── test_story_store.py
│   └── test_urban_gate.py
├── api_config.example.json       # Cấu hình đa nhà cung cấp LLM (Gemini, DeepSeek...)
├── requirements.txt              # Thư viện phụ thuộc Python
└── README.md                     # Tài liệu hướng dẫn hệ thống
```

---

## 5. Hướng Dẫn Cài Đặt & Sử Dụng

### 5.1. Yêu Cầu Môi Trường
- Python 3.10 trở lên.
- Git & Git CLI.

### 5.2. Cài Đặt
```bash
# Clone repository
git clone https://github.com/hiraga1305/CaoTruyen.git
cd CaoTruyen

# Cài đặt thư viện phụ thuộc
pip install -r requirements.txt

# Tạo cấu hình API cá nhân từ file mẫu
cp api_config.example.json api_config.json
# (Điền API Key của Gemini, DeepSeek, hoặc OpenRouter vào api_config.json)
```

### 5.3. Chạy Kiểm Thử Tự Động (Test Suite)
```bash
# Chạy toàn bộ 120 Unit Tests
python -X utf8 -m unittest discover -s tests -v

# Chạy riêng bộ kiểm thử Kiến trúc Hoàn hảo v2.0
python -X utf8 -m unittest tests.test_perfection_architecture -v
```

---

## 6. So Sánh Tính Năng

| Tiêu Chí | ChiVi / QuickTranslator | Dịch LLM Truyền Thống | CaoTruyen v2.0 (Argon) |
| :--- | :--- | :--- | :--- |
| **Bảo lưu quan hệ xưng hô** | Tĩnh, không thay đổi theo tình tiết | Hay quên xưng hô sau vài chương | **Ma trận xưng hô khóa chặt theo Vault** |
| **Nhân vật Boomerang (200 chương)** | Phụ thuộc gán nhãn thủ công | Mất trí nhớ tập (Episodic amnesia) | **Thức tỉnh tự động bằng Aho-Corasick $O(N)$** |
| **Dịch song song đa chương** | Không hỗ trợ | Dễ xung đột thuật ngữ giữa các nhánh | **Two-Phase Zipper (Zero-Drift song song)** |
| **Chi phí kiểm duyệt ảo giác** | Không có (Rule-based) | Tốn Token LLM cho Reviewer | **Tường lửa 0-Token Gatekeeper** |
| **Văn phong thể loại** | Thô cứng máy móc | Không ổn định | **Genre Gate thích ứng từng thể loại** |

---

## 7. Giấy Phép (License)
Dự án được phân phối theo giấy phép MIT License.
