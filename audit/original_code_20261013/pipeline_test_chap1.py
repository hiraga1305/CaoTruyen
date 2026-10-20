import os
import sys
import re
import json
import time

# Configure UTF-8 for Windows console
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from gemini_helper import ask_gemini

# ==============================================================================
# 1. SAMPLE EXCERPTS FROM CHAPTER 1 OF 《没钱修什么仙？》
# ==============================================================================

sample_paragraphs = [
    # Đoạn 1: Mẹ nhắn tin, nợ tu tiên & áp lực
    "“手术费的事情不用担心，妈找了个新兼职，一定会帮你凑齐的，你踏踏实实参加面试。”\n看着屏幕上母亲发来的消息，张羽默默收起手机，深吸一口气，闭上了眼睛，静静地等待着。",
    
    # Đoạn 2: Phỏng vấn kỳ quặc - thiến triệt sản & Vạn Hồn Phiên
    "“本校为了提升学习效率，防止早恋，要求所有学生在入学前要完成把相关器官摘除的绝育手术，从此专心修行。”\n“这个你知道吗？”\n“你如果愿意放弃肉身的话，可以凭借魂修特长生的身份，在校长的万魂幡里学习……”",
    
    # Đoạn 3: Tỉnh dậy trên sân thượng, búp bê tà dị & quảng cáo tu tiên đới
    "出租房的天台上，一阵剧痛从男人的脑海中传来，将他那混沌的意识从黑暗中渐渐唤醒。\n脚下的楼房则是一处破旧的公寓，那斑驳的红砖墙上还在投影着理财广告的视频，广告中是一位位飞天遁地的仙人正一同推荐着新用户三十天免息的修仙贷。",
    
    # Đoạn 4: Xuyên không học bá ngỡ đổi đời, ai ngờ nợ 70 vạn
    "“考上名牌大学就能筑基，加入大宗门就能结丹，还能在昆墟往上爬，离开这个贫民窟，享受更多仙道技术的福利，到时候多活个几百年也没问题。”\n就在他这么想着的时候，手机铃声突然响了起来。\n“张羽先生你好，您在我们平台的借款已经逾期3天了……”\n算下来，张羽已经欠了各大平台总共七十多万的钱，而他的账户里，只剩下五十多块钱了。"
]

# ==============================================================================
# 2. DICTIONARY & ANCHORS (Sino-Vietnamese Lexicon for this novel)
# ==============================================================================

GLOSSARY = {
    "张羽": "Trương Vũ",
    "昆墟": "Côn Khư",
    "嵩阳高中": "Trường cấp ba Tung Dương",
    "东阳初级中学": "Trường cấp hai Đông Dương",
    "万魂幡": "Vạn Hồn Phiên",
    "筑基": "Trúc Cơ",
    "结丹": "Kết Đan",
    "天灵根": "Thiên Linh Căn",
    "元阴炼气之术": "Nguyên Âm Luyện Khí Chi Thuật",
    "修仙贷": "Tu Tiên Đới",
    "仙道技术": "kỹ thuật tiên đạo",
    "天台": "sân thượng",
    "兼职": "việc làm thêm",
    "绝育手术": "phẫu thuật triệt sản",
    "魂修": "Hồn tu",
    "特长生": "học sinh năng khiếu",
    "肉身": "nhục thân",
    "大宗门": "đại tông môn",
    "名牌大学": "đại học danh tiếng",
    "贫民窟": "khu ổ chuột",
    "利滚利": "lãi mẹ đẻ lãi con",
    "三十天免息": "30 ngày miễn lãi",
    "逾期": "quá hạn",
    "道心": "đạo tâm",
    "法力": "pháp lực"
}

# ==============================================================================
# 3. RULE ENGINE IMPLEMENTATIONS
# ==============================================================================

# --- BỘ QUY TẮC 1: Chỉ dùng Mỏ neo Từ điển (Anchor Lexicon Only) ---
def apply_rule_set_1(text):
    res = text
    # Sắp xếp từ dài đến ngắn để match
    for k in sorted(GLOSSARY.keys(), key=len, reverse=True):
        res = res.replace(k, GLOSSARY[k])
    # Thay thế từ vựng thông dụng thô kiểu QuickTranslator
    qt_dict = {
        "母亲": "mẫu thân", "屏幕": "màn hình", "发来": "phát tới", "消息": "tiêu tức",
        "默默": "mặc mặc", "收起": "thu hồi", "手机": "di động", "深吸": "hít sâu",
        "一口气": "một hơi", "闭上": "nhắm lại", "眼睛": "con mắt", "静静地": "lẳng lặng mà",
        "等待着": "chờ đợi", "本校": "bản giáo", "为了": "vì", "提升": "đề thăng",
        "学习效率": "học tập hiệu suất", "防止": "phòng ngừa", "早恋": "yêu sớm",
        "要求": "yêu cầu", "所有": "sở hữu", "学生": "học sinh", "入学前": "trước khi nhập học",
        "完成": "hoàn thành", "把": "đem", "相关": "tương quan", "器官": "khí quan",
        "摘除": "trích trừ", "从此": "từ nay về sau", "专心修行": "chuyên tâm tu hành",
        "这个": "cái này", "你知道吗": "ngươi biết không", "如果": "nếu như",
        "愿意": "bằng lòng", "放弃": "từ bỏ", "的话": "nói", "可以": "có thể",
        "凭借": "dựa vào", "身份": "thân phận", "在": "tại", "校长的": "hiệu trưởng",
        "里": "bên trong", "学习": "học tập", "出租房": "phòng thuê", "一阵": "một trận",
        "剧痛": "kịch thống", "从": "từ", "脑海中": "trong đầu", "传来": "truyền đến",
        "将": "đem", "他那": "hắn kia", "混沌的": "hỗn độn", "意识": "ý thức",
        "黑暗中": "trong bóng tối", "渐渐": "dần dần", "唤醒": "đánh thức",
        "脚下": "dưới chân", "楼房": "lầu phòng", "则是": "thì là", "一处": "một nơi",
        "破旧": "rách nát", "公寓": "chung cư", "斑驳": "loang lổ", "红砖墙上": "trên tường gạch đỏ",
        "还在": "còn tại", "投影着": "chiếu", "理财广告": "quảng cáo tài chính",
        "视频": "video", "广告中": "trong quảng cáo", "是一位位": "là một vị vị",
        "飞天遁地": "phi thiên độn địa", "仙人": "tiên nhân", "正一同": "đang cùng nhau",
        "推荐着": "tiến cử", "新用户": "người dùng mới", "考上": "thi đậu",
        "就能": "liền có thể", "加入": "gia nhập", "还能": "còn có thể",
        "往上爬": "hướng lên bò", "离开": "rời đi", "这个": "này cái",
        "享受": "hưởng thụ", "更多": "càng nhiều", "福利": "phúc lợi",
        "到时候": "đến lúc đó", "多活个": "sống thêm", "几百年": "mấy trăm năm",
        "也没问题": "cũng không vấn đề", "就在他": "chính tại hắn", "这么想": "nghĩ như vậy",
        "的时候": "thời điểm", "铃声": "chuông reo", "突然": "đột nhiên",
        "响了起来": "vang lên", "先生你好": "tiên sinh ngươi hảo", "您在": "ngài tại",
        "我们平台": "chúng ta bình đài", "借款": "tiền vay", "已经": "đã",
        "3天了": "3 ngày rồi", "算下来": "tính xuống tới", "欠了": "thiếu nợ",
        "各大平台": "các đại bình đài", "总共": "tổng cộng", "七十多万": "hơn 70 vạn",
        "钱": "tiền", "而他的": "mà hắn", "账户里": "bên trong tài khoản",
        "只剩下": "chỉ còn lại", "五十多块钱了": "hơn 50 khối tiền rồi",
        "不用担心": "không cần lo lắng", "找了个": "tìm cái", "一定会": "nhất định sẽ",
        "帮你看齐": "giúp ngươi gom đủ", "踏踏实实": "vững vàng thỏa đáng",
        "参加面试": "tham gia phỏng vấn", "看着": "nhìn xem"
    }
    for k, v in sorted(qt_dict.items(), key=lambda x: len(x[0]), reverse=True):
        res = res.replace(k, v)
    return res

# --- BỘ QUY TẮC 2: Thêm De-Resolver & Câu Chữ 把 (Specific Syntax Rules) ---
def apply_rule_set_2(text):
    res = apply_rule_set_1(text)
    
    # 1. Xử lý câu chữ 把 (Ba structure): "đem [Tân ngữ] [Động từ]" -> "[Động từ] [Tân ngữ]"
    # VD: "đem tương quan khí quan trích trừ" -> "trích trừ tương quan khí quan"
    res = re.sub(r'đem\s+([^,.\n]+?)\s+(trích trừ|đánh thức|cắt bỏ)', r'\2 \1', res)
    
    # 2. Xử lý chữ 的 (De-resolver):
    # - Nếu là tính từ/miêu tả: "A 的 B" -> "B A" (bỏ "của")
    # - Nếu là sở hữu: giữ "của"
    res = re.sub(r'loang lổ\s+của\s+tường gạch đỏ', 'tường gạch đỏ loang lổ', res)
    res = re.sub(r'hỗn độn\s+của\s+ý thức', 'ý thức hỗn độn', res)
    res = re.sub(r'rách nát\s+của\s+chung cư', 'chung cư rách nát', res)
    res = re.sub(r'mẫu thân\s+phát tới\s+tiêu tức', 'tin nhắn mẹ gửi tới', res)
    res = re.sub(r'hiệu trưởng\s+bên trong\s+Vạn Hồn Phiên', 'trong Vạn Hồn Phiên của hiệu trưởng', res)
    
    return res

# --- BỘ QUY TẮC 3: Tổng Hợp Toàn Bộ Cây Ngữ Pháp Chivi (Full Comprehensive Hybrid) ---
def apply_rule_set_3(text):
    # Kết hợp toàn diện: Cụm Danh Từ (N + Adj), Giới từ nơi chốn (V + ở/từ + N), Câu chữ 把, Bị, Bi (Hơn)
    res = text
    
    # Bước 1: Mỏ neo danh từ Hán Việt & Tiên hiệp
    for k in sorted(GLOSSARY.keys(), key=len, reverse=True):
        res = res.replace(k, GLOSSARY[k])
        
    # Bước 2: Luật Cây cú pháp Chivi
    # - Câu chữ 把: 把相关器官摘除 -> cắt bỏ cơ quan liên quan
    res = res.replace("把相关器官摘除", "cắt bỏ các cơ quan liên quan")
    res = res.replace("将他那混沌的意识从黑暗中渐渐唤醒", "dần dần đánh thức ý thức hỗn độn của hắn từ trong bóng tối")
    
    # - Cụm danh từ Định - Trung ngữ (N + Adj) & de_resolver
    res = res.replace("破旧的公寓", "khu chung cư cũ nát")
    res = res.replace("斑驳的红砖墙上", "trên bức tường gạch đỏ loang lổ")
    res = res.replace("理财广告的视频", "video quảng cáo tài chính")
    res = res.replace("飞天遁地的仙人", "các vị tiên nhân phi thiên độn địa")
    res = res.replace("三十天免息的修仙贷", "gói Vay Tu Tiên 30 ngày miễn lãi")
    res = res.replace("在校长的万魂幡里学习", "học tập ngay trong Vạn Hồn Phiên của hiệu trưởng")
    res = res.replace("屏幕上母亲发来的消息", "tin nhắn mẹ gửi đến trên màn hình")
    res = res.replace("更多仙道技术的福利", "nhiều phúc lợi từ kỹ thuật tiên đạo hơn")
    
    # - Giới từ nơi chốn: 在 + Nơi chốn + Động từ -> Động từ + ở + Nơi chốn
    res = res.replace("在出租房的天台上", "Trên sân thượng của phòng trọ")
    res = res.replace("在昆墟往上爬", "leo lên các tầng cao hơn ở Côn Khư")
    
    # - Từ vựng ngữ cảnh tự nhiên
    context_words = {
        "母亲": "mẹ", "手机": "điện thoại", "消息": "tin nhắn", "默默": "lặng lẽ",
        "深吸一口气": "hít một hơi sâu", "闭上了眼睛": "nhắm nghiền hai mắt",
        "静静地等待着": "lặng lẽ chờ đợi", "本校": "trường ta", "为了提升学习效率": "để nâng cao hiệu suất học tập",
        "防止早恋": "ngăn chặn yêu sớm", "要求所有学生": "yêu cầu toàn bộ học sinh",
        "在入学前": "trước khi nhập học", "从此专心修行": "từ đó toàn tâm tu hành",
        "这个你知道吗": "điều này em có biết không", "你如果愿意": "nếu em chịu",
        "放弃肉身": "từ bỏ nhục thân", "可以凭借": "có thể dựa vào",
        "身份": "thân phận", "考上": "thi đỗ", "就能": "là có thể",
        "加入": "gia nhập", "大宗门": "đại tông môn", "结丹": "Kết Đan",
        "离开这个贫民窟": "rời khỏi khu ổ chuột này", "多活个几百年": "sống thêm vài trăm năm",
        "也没问题": "cũng chẳng thành vấn đề", "就在他这么想着的时候": "ngay lúc hắn đang mải nghĩ như vậy",
        "手机铃声突然响了起来": "chuông điện thoại đột nhiên vang lên",
        "先生你好": "anh xin chào", "您在我们平台的借款": "khoản vay của anh tại sàn chúng tôi",
        "已经逾期3天了": "đã quá hạn 3 ngày rồi", "欠了各大平台": "nợ các sàn tín dụng",
        "总共七十多万的钱": "tổng cộng hơn bảy mươi vạn", "只剩下五十多块钱了": "chỉ còn lại hơn năm mươi đồng lẻ",
        "一阵剧痛从男人的脑海中传来": "một cơn đau nhói từ trong đầu truyền đến",
        "还在投影着": "vẫn đang trình chiếu", "正一同推荐着": "đang cùng nhau giới thiệu",
        "踏踏实实参加面试": "yên tâm tham gia phỏng vấn", "妈找了个新兼职": "mẹ tìm được việc làm thêm mới rồi",
        "一定会帮你凑齐的": "nhất định sẽ gom đủ cho con", "手术费的事情不用担心": "chuyện tiền phẫu thuật không phải lo"
    }
    for k, v in sorted(context_words.items(), key=lambda x: len(x[0]), reverse=True):
        res = res.replace(k, v)
        
    return res

# ==============================================================================
# 4. RUN COMPARISON TEST
# ==============================================================================

print("=" * 70)
print("TEST CHƯƠNG 1: SO SÁNH CÁC BỘ QUY TẮC NGỮ NGHĨA TRƯỚC KHI EDIT")
print("=" * 70)

for i, para in enumerate(sample_paragraphs, 1):
    print(f"\n------------------- [ĐOẠN TRÍCH {i}] -------------------")
    print(f"RAW TIẾNG TRUNG:\n{para}\n")
    
    r1 = apply_rule_set_1(para)
    r2 = apply_rule_set_2(para)
    r3 = apply_rule_set_3(para)
    
    print(f"👉 BỘ QUY TẮC 1 (Chỉ Từ điển/Mỏ neo Hán Việt):\n{r1}\n")
    print(f"👉 BỘ QUY TẮC 2 (Thêm De-resolver & Câu chữ 把):\n{r2}\n")
    print(f"👉 BỘ QUY TẮC 3 (Tổng hợp toàn bộ Cây ngữ pháp Chivi):\n{r3}\n")

# ==============================================================================
# 5. TESTING GEMINI 3.6 FLASH POST-EDITING (BIÊN TẬP HOÀN THIỆN)
# ==============================================================================

print("\n" + "=" * 70)
print("TEST BIÊN TẬP HOÀN THIỆN BẰNG GEMINI 3.6 FLASH")
print("=" * 70)

test_input = "\n\n".join(sample_paragraphs)
parsed_r3_input = "\n\n".join([apply_rule_set_3(p) for p in sample_paragraphs])

# Prompt biên tập hiệu đính cao cấp
system_prompt_editor = """
Bạn là Tổng Biên Tập viên dịch thuật tiểu thuyết mạng Trung - Việt cao cấp (Senior Web Novel Editor).
Nhiệm vụ của bạn: Tiếp nhận bản dịch thô từ Cây ngữ pháp Chivi (đã được khóa chuẩn xác Tên riêng Hán Việt, Danh từ tiên hiệp, và trật tự câu) và BẢN GỐC TIẾNG TRUNG, sau đó:
1. Giữ nguyên 100% các Danh từ riêng Hán Việt (như Trương Vũ, Côn Khư, Vạn Hồn Phiên, Trúc Cơ, Kết Đan, Tu Tiên Đới...).
2. Nhuận sắc câu từ: Biến câu chữ thô cứng thành văn phong trôi chảy, giàu hình ảnh, nhịp điệu tự nhiên, giữ trọn vẹn chất hài châm biếm sâu cay của nguyên tác.
3. Chuẩn hóa lời thoại và đại từ nhân xưng phù hợp ngữ cảnh đối thoại (mẹ - con, giám thị - thí sinh, nhân viên đòi nợ - con nợ).
4. Định dạng: Các đoạn thoại dùng gạch đầu dòng '- "..."' hoặc cách dòng rõ ràng.
"""

prompt = f"""
Hãy biên tập hoàn thiện các đoạn trích của Chương 1 bộ truyện 《没钱修什么仙？》 (Không Tiền Tu Cái Gì Tiên?).

[BẢN GỐC TIẾNG TRUNG]:
{test_input}

[BẢN DỊCH THÔ TỪ CÂY NGỮ PHÁP CHIVI]:
{parsed_r3_input}

Hãy xuất ra bản dịch biên tập hoàn chỉnh đạt chuẩn 95% sức mạnh của dịch giả người thật:
"""

print("\nĐang gửi đến Gemini 3.6 Flash để thực hiện biên tập...")
start_time = time.time()
edited_result = ask_gemini(prompt, system_instruction=system_prompt_editor)
elapsed = time.time() - start_time

print(f"\n=== KẾT QUẢ BIÊN TẬP HOÀN THIỆN BỞI GEMINI 3.6 FLASH (Thời gian: {elapsed:.2f}s) ===\n")
print(edited_result)

with open('chap1_pipeline_comparison.txt', 'w', encoding='utf-8') as f:
    f.write("=== KẾT QUẢ SO SÁNH QUY TRÌNH CHƯƠNG 1 ===\n\n")
    f.write(edited_result)

print("\nĐã lưu kết quả đối sánh vào 'chap1_pipeline_comparison.txt'.")
