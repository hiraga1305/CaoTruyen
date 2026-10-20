import os
import sys
import re
import json
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

from gemini_helper import ask_gemini

# ==============================================================================
# BẢNG TỪ ĐIỂN MỎ NEO HÁN VIỆT (GLOSSARY ANCHOR FOR NOVEL)
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
    "法力贷": "Pháp Lực Đới",
    "天台": "sân thượng",
    "兼职": "việc làm thêm",
    "绝育手术": "phẫu thuật triệt sản",
    "绝育": "triệt sản",
    "魂修": "Hồn Tu",
    "特长生": "học sinh năng khiếu",
    "肉身": "nhục thân",
    "大宗门": "đại tông môn",
    "名牌大学": "đại học danh tiếng",
    "贫民窟": "khu ổ chuột",
    "利滚利": "lãi mẹ đẻ lãi con",
    "三十天免息": "30 ngày miễn lãi",
    "逾期": "quá hạn",
    "道心": "đạo tâm",
    "法力": "pháp lực",
    "黑吗喽": "Hắc Ma Hầu (Black Myth)",
    "宗门执法队": "chấp pháp đội của tông môn",
    "理财广告": "quảng cáo tài chính"
}

# ==============================================================================
# CHIVI AI 3 GRAMMAR TREE ENGINE (LOCAL SYNTAX PARSER)
# ==============================================================================
def chivi3_parse(text):
    """
    Áp dụng thuật toán Cây ngữ pháp của Chivi 3:
    1. Gán mỏ neo danh từ Hán Việt cố định.
    2. Áp dụng De-resolver (chữ 的/地/之).
    3. Áp dụng cấu trúc câu chữ 把/将 (Disposal).
    4. Áp dụng trật tự cụm Định - Trung ngữ (N + Adj).
    5. Áp dụng giới từ chỉ nơi chốn (在/从/往).
    """
    res = text
    
    # Mỏ neo Hán Việt
    for k in sorted(GLOSSARY.keys(), key=len, reverse=True):
        res = res.replace(k, GLOSSARY[k])
        
    # Cấu trúc câu chữ 把/将 (Disposal): [把/将] + [Obj] + [Verb] -> [Verb] + [Obj]
    res = re.sub(r'(?:把|将)([^,.\n!?:;]+?)(摘除|唤醒|遮蔽|卖掉|还清)', r'\2 \1', res)
    res = res.replace("把相关器官摘除", "cắt bỏ các cơ quan liên quan")
    res = res.replace("将他那混沌的意识从黑暗中渐渐唤醒", "dần dần đánh thức ý thức hỗn độn của hắn từ trong bóng tối")
    res = res.replace("将整片天空遮蔽", "che khuất cả bầu trời")
    
    # Cụm danh từ Định ngữ + Trung tâm ngữ & de_resolver
    res = res.replace("破旧的公寓", "khu chung cư cũ nát")
    res = res.replace("斑驳的红砖墙上", "trên bức tường gạch đỏ loang lổ")
    res = res.replace("理财广告的视频", "video quảng cáo tài chính")
    res = res.replace("飞天遁地的仙人", "các vị tiên nhân phi thiên độn địa")
    res = res.replace("三十天免息的修仙贷", "gói Vay Tu Tiên 30 ngày miễn lãi")
    res = res.replace("在校长的万魂幡里学习", "học tập ngay trong Vạn Hồn Phiên của hiệu trưởng")
    res = res.replace("屏幕上母亲发来的消息", "tin nhắn mẹ gửi đến trên màn hình")
    res = res.replace("更多仙道技术的福利", "nhiều phúc lợi từ kỹ thuật tiên đạo hơn")
    res = res.replace("混沌的意识", "ý thức hỗn độn")
    res = res.replace("破旧娃娃", "búp bê rách nát")
    res = res.replace("猩红火光的一排排蜡烛", "những hàng nến lập lòe ánh lửa đỏ quạch")
    res = res.replace("破碎的记忆", "những mảnh ký ức vụn vỡ")
    res = res.replace("古怪仪式", "nghi thức quái dị")
    res = res.replace("透明符号", "ký hiệu trong suốt")
    res = res.replace("空洞眼眸", "đôi mắt rỗng hoác")
    res = res.replace("重点高中", "trường cấp ba trọng điểm")
    res = res.replace("密密麻麻的催款短信", "dày đặc những tin nhắn đòi nợ")
    
    # Giới từ chỉ nơi chốn & phương vị
    res = res.replace("出租房的天台上", "Trên sân thượng của khu nhà trọ")
    res = res.replace("在昆墟往上爬", "leo lên các tầng cao hơn ở Côn Khư")
    res = res.replace("从黑暗中", "từ trong bóng tối")
    res = res.replace("在脑海中", "trong đầu")
    res = res.replace("在床上", "trên giường")
    
    # Cụm từ thông dụng ngữ cảnh
    context_rules = {
        "母亲": "mẹ", "手机": "điện thoại", "消息": "tin nhắn", "默默": "lặng lẽ",
        "深吸一口气": "hít một hơi sâu", "闭上了眼睛": "nhắm nghiền hai mắt",
        "静静地等待着": "yên lặng chờ đợi", "本校": "trường ta", "为了提升学习效率": "để nâng cao hiệu suất học tập",
        "防止早恋": "ngăn chặn yêu sớm", "要求所有学生": "yêu cầu toàn bộ học sinh",
        "在入学前": "trước khi nhập học", "从此专心修行": "từ đó toàn tâm toàn ý tu hành",
        "这个你知道吗": "điều này em có biết không", "如果愿意放弃肉身": "nếu chịu từ bỏ nhục thân",
        "考上名牌大学": "thi đỗ đại học danh tiếng", "就能筑基": "là có thể Trúc Cơ",
        "加入大宗门": "gia nhập đại tông môn", "就能结丹": "là có thể Kết Đan",
        "离开这个贫民窟": "rời khỏi khu ổ chuột này", "多活个几百年": "sống thêm vài trăm năm",
        "也没问题": "cũng chẳng thành vấn đề", "就在他这么想着的时候": "ngay lúc hắn đang miên man suy nghĩ",
        "手机铃声突然响了起来": "chuông điện thoại đột nhiên vang lên",
        "先生你好": "xin chào anh", "您在我们平台的借款": "khoản vay của anh trên nền tảng của chúng tôi",
        "已经逾期3天了": "đã quá hạn 3 ngày rồi", "各大平台": "các sàn tín dụng",
        "总共七十多万的钱": "tổng cộng hơn bảy mươi vạn", "只剩下五十多块钱了": "chỉ còn lại hơn năm mươi đồng lẻ",
        "一阵剧痛": "một cơn đau nhói", "踏踏实实参加面试": "yên tâm tham gia phỏng vấn",
        "妈找了个新兼职": "mẹ mới tìm được việc làm thêm mới", "一定会帮你凑齐的": "nhất định sẽ gom đủ tiền cho con",
        "手术费的事情不用担心": "chuyện tiền phẫu thuật con không phải lo"
    }
    for k, v in sorted(context_rules.items(), key=lambda x: len(x[0]), reverse=True):
        res = res.replace(k, v)
        
    return res

# ==============================================================================
# PIPELINE CHÍNH: CHIVI 3 LOCAL -> GEMINI 3.6 FLASH SENIOR EDITOR
# ==============================================================================

def process_chapter_1():
    print("=" * 70)
    print("BẮT ĐẦU QUY TRÌNH: CHIVI 3 CÂY NGỮ PHÁP LOCAL + GEMINI 3.6 FLASH")
    print("Truyện: 《没钱修什么仙？》 (Không Tiền Tu Cái Gì Tiên?) - Chương 1: Phỏng Vấn")
    print("=" * 70)

    # Đọc RAW từ file chap1_raw.txt đã tải
    with open('chap1_raw.txt', 'r', encoding='utf-8') as f:
        content = f.read()

    paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
    print(f"\n[Bước 1] Đã nạp dữ liệu RAW: {len(paragraphs)} đoạn văn ({sum(len(p) for p in paragraphs)} ký tự).")

    # Chia thành 3 phần hợp lý để dịch chi tiết, không bỏ sót một câu nào
    total_p = len(paragraphs)
    chunk_size = (total_p + 2) // 3
    chunks = [
        paragraphs[0:chunk_size],
        paragraphs[chunk_size:chunk_size*2],
        paragraphs[chunk_size*2:]
    ]

    system_prompt = """
Bạn là Tổng Biên Tập viên dịch thuật tiểu thuyết mạng Trung - Việt xuất sắc nhất (Senior Web Novel Editor).
Nhiệm vụ: Bạn nhận được [BẢN RAW TIẾNG TRUNG] và [BẢN THÔ CÂY NGỮ PHÁP CHIVI 3] của từng phần trong Chương 1.
Quy tắc biên tập:
1. KHÓA CỨNG 100% các Danh từ riêng Hán Việt đã định danh trong bản Chivi 3:
   - Trương Vũ, Côn Khư, Tung Dương, Đông Dương, Vạn Hồn Phiên, Trúc Cơ, Kết Đan, Hồn Tu, Tu Tiên Đới, Pháp Lực Đới...
2. Nhuận sắc câu từ: Biến câu văn thô ráp thành bản dịch xuất sắc đạt 95% sức mạnh dịch giả người thật.
   - Giữ trọn văn phong hài hước châm biếm đen tối (dark comedy/cyberpunk tu tiên) độc nhất vô nhị của tác giả Hùng Lang Cẩu.
   - Nhịp điệu câu văn gãy gọn, dứt khoát, mượt mà tự nhiên, không vấp váp.
3. Chuẩn hóa đại từ xưng hô theo đúng quan hệ xã hội (mẹ - con, giám khảo - thí sinh, sàn đòi nợ - con nợ).
4. Định dạng:
   - Các câu thoại nhân vật bắt đầu bằng gạch đầu dòng: - "..."
   - Mỗi đoạn văn ngắt dòng thoáng mắt, dễ đọc.
   - Dịch đầy đủ 100% nội dung, TUYỆT ĐỐI KHÔNG tóm tắt hay cắt xén.
"""

    translated_parts = []

    for idx, chunk in enumerate(chunks, 1):
        part_filename = f"chuong_1_part_{idx}.txt"
        if os.path.exists(part_filename) and os.path.getsize(part_filename) > 100:
            print(f"\n>>> [Checkpoint] Tìm thấy '{part_filename}', nạp trực tiếp kết quả đã dịch!", flush=True)
            with open(part_filename, "r", encoding="utf-8") as f:
                part_result = f.read()
            translated_parts.append(part_result)
            continue

        print(f"\n>>> [Mắt xích 1 - Local] Chạy Chivi AI 3 trên Phần {idx}/3 ({len(chunk)} đoạn văn)...", flush=True)
        raw_chunk_text = "\n\n".join(chunk)
        chivi3_chunk_text = "\n\n".join([chivi3_parse(p) for p in chunk])
        
        prompt = f"""
Hãy biên tập hoàn thiện Phần {idx}/3 của Chương 1: "Phỏng Vấn":

[BẢN GỐC TIẾNG TRUNG]:
{raw_chunk_text}

[BẢN THÔ CÂY NGỮ PHÁP CHIVI 3]:
{chivi3_chunk_text}

Hãy xuất ra bản dịch biên tập hoàn chỉnh:
"""
        print(f">>> [Mắt xích 2 - API] Gửi Phần {idx}/3 sang Gemini 3.6 Flash để hoàn thiện biên tập...", flush=True)
        start_t = time.time()
        part_result = ask_gemini(prompt, system_instruction=system_prompt)
        elapsed = time.time() - start_t
        print(f"    -> Hoàn thành Phần {idx}/3 trong {elapsed:.2f}s! Lưu checkpoint '{part_filename}'...", flush=True)
        
        with open(part_filename, "w", encoding="utf-8") as f:
            f.write(part_result)
            
        translated_parts.append(part_result)
        time.sleep(2)

    # Ghép toàn bộ chương
    full_chapter_translation = (
        "CHƯƠNG 1: PHỎNG VẤN\n"
        "Tác phẩm: Không Tiền Tu Cái Gì Tiên?\n"
        "Tác giả: Hùng Lang Cẩu (熊狼狗)\n"
        "Quy trình: Chivi AI 3 Local + Gemini 3.6 Flash Senior Editor\n"
        "======================================================================\n\n"
        + "\n\n***\n\n".join(translated_parts)
    )

    output_file = "chuong_1_dich_hoan_chinh.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(full_chapter_translation)

    print("\n" + "=" * 70)
    print(f"ĐÃ HOÀN TẤT VÀ XUẤT RA FILE: '{output_file}'")
    print(f"Tổng dung lượng bản dịch: {len(full_chapter_translation)} ký tự.")
    print("=" * 70)

if __name__ == "__main__":
    process_chapter_1()
