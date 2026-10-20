"""Deterministic Numeric Extractor & Converter for Xianxia / Ancient Novels.
Strictly converts Chinese numeric expressions and Xianxia units to Vietnamese standard.
Part of CaoTruyen Module 1.
"""

from __future__ import annotations
import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass

CH_DIGITS: Dict[str, int] = {
    "零": 0, "〇": 0,
    "一": 1, "壹": 1,
    "二": 2, "两": 2, "兩": 2, "貳": 2,
    "三": 3, "叁": 3,
    "四": 4, "肆": 4,
    "五": 5, "伍": 5,
    "六": 6, "陸": 6,
    "七": 7, "柒": 7,
    "八": 8, "捌": 8,
    "九": 9, "玖": 9,
}

VI_DIGITS: Dict[int, str] = {
    0: "không", 1: "một", 2: "hai", 3: "ba", 4: "bốn",
    5: "năm", 6: "sáu", 7: "bảy", 8: "tám", 9: "chín"
}

UNIT_MAP_BNS: Dict[str, str] = {
    "丈": "trượng",
    "尺": "thước",
    "寸": "tấc",
    "里": "dặm",
    "斤": "cân",
    "息": "hơi thở",
    "炷香": "nén nhang",
    "盞茶": "tuần trà",
    "盏茶": "tuần trà",
    "甲子": "giáp tý",
    "成": "phần",
    "枚": "viên",
    "株": "gốc",
    "柄": "thanh",
    "尊": "pho",
    "道": "luồng",
    "滴": "giọt",
    "粒": "hạt",
    "張": "tấm",
    "张": "tấm",
    "座": "tòa",
}

def parse_chinese_integer(ch_str: str) -> Optional[int]:
    """Parse standard Chinese integer string into integer value."""
    if not ch_str:
        return None
    # Handle pure Arabic digits
    if ch_str.isdigit():
        return int(ch_str)
    
    total = 0
    section = 0
    current_num = 0
    
    for char in ch_str:
        if char in CH_DIGITS:
            current_num = CH_DIGITS[char]
        elif char == "十" or char == "拾":
            if current_num == 0:
                current_num = 1
            section += current_num * 10
            current_num = 0
        elif char == "百" or char == "佰":
            if current_num == 0:
                current_num = 1
            section += current_num * 100
            current_num = 0
        elif char == "千" or char == "仟":
            if current_num == 0:
                current_num = 1
            section += current_num * 1000
            current_num = 0
        elif char == "萬" or char == "万":
            section += current_num
            total += section * 10000
            section = 0
            current_num = 0
        elif char == "億" or char == "亿":
            section += current_num
            total += section * 100000000
            section = 0
            current_num = 0
        else:
            return None
            
    section += current_num
    total += section
    return total

def int_to_vietnamese(n: int) -> str:
    """Convert integer to natural literary Vietnamese words."""
    if n == 0:
        return "không"
    
    # Specific common mappings in Xianxia
    if n == 100000:
        return "mười vạn"
    if n == 1000000:
        return "trăm vạn"
    if n == 10000000:
        return "ngàn vạn"
    if n == 100000000:
        return "một ức"

    def read_three_digits(num: int, is_highest: bool = False) -> str:
        hundreds = num // 100
        tens = (num % 100) // 10
        units = num % 10
        words = []
        
        if hundreds > 0:
            words.append(f"{VI_DIGITS[hundreds]} trăm")
        elif not is_highest:
            words.append("không trăm")
            
        if tens > 1:
            words.append(f"{VI_DIGITS[tens]} mươi")
            if units == 1:
                words.append("mốt")
            elif units == 5:
                words.append("lăm")
            elif units > 0:
                words.append(VI_DIGITS[units])
        elif tens == 1:
            words.append("mười")
            if units == 5:
                words.append("lăm")
            elif units > 0:
                words.append(VI_DIGITS[units])
        elif tens == 0:
            if units > 0:
                if not is_highest or hundreds > 0:
                    words.append("lẻ")
                words.append(VI_DIGITS[units])
                
        return " ".join(words)

    units_scale = ["", "ngàn", "triệu", "tỷ", "ngàn tỷ", "triệu tỷ"]
    chunks = []
    temp = n
    while temp > 0:
        chunks.append(temp % 1000)
        temp //= 1000

    parts = []
    for i in reversed(range(len(chunks))):
        c = chunks[i]
        if c > 0:
            s = read_three_digits(c, is_highest=(i == len(chunks) - 1))
            scale = units_scale[i]
            if scale:
                parts.append(f"{s} {scale}")
            else:
                parts.append(s)
                
    return " ".join(parts).replace("mươi năm", "mươi lăm").strip()


@dataclass
class ExtractedMetric:
    tag_id: str
    raw_zh: str
    numeric_val: Optional[int]
    unit_vi: str
    locked_vi: str


class DeterministicNumericExtractor:
    """Extracts numbers and units from Chinese text and produces deterministic locked Vietnamese strings."""

    NUM_PATTERN = re.compile(
        r"([零〇一壹二两兩貳三叁四肆五伍六陸七柒八捌九玖十拾百佰千仟萬万億亿\d]+)"
        r"\s*(丈許|丈|尺許|尺|寸|里|斤|息|炷香|盞茶|盏茶|甲子|成|枚|株|柄|尊|道|滴|粒|張|张|座)"
    )

    def __init__(self):
        pass

    def extract_metrics(self, text: str, start_index: int = 1) -> List[ExtractedMetric]:
        metrics: List[ExtractedMetric] = []
        idx = start_index

        for match in self.NUM_PATTERN.finditer(text):
            raw_zh = match.group(0)
            raw_num = match.group(1)
            raw_unit = match.group(2)

            is_approx = "許" in raw_unit
            clean_unit = raw_unit.replace("許", "")
            unit_vi = UNIT_MAP_BNS.get(clean_unit, clean_unit)

            num_val = parse_chinese_integer(raw_num)
            if num_val is not None:
                # Format literary Vietnamese
                if raw_num == "一" and clean_unit in ["炷香", "盞茶", "盏茶"]:
                    num_vi = "một"
                elif raw_num.endswith("萬") or raw_num.endswith("万"):
                    prefix = raw_num[:-1]
                    val_prefix = parse_chinese_integer(prefix) or 1
                    num_vi = f"{int_to_vietnamese(val_prefix)} vạn"
                else:
                    num_vi = int_to_vietnamese(num_val)

                if is_approx:
                    locked_vi = f"chừng {num_vi} {unit_vi}"
                elif clean_unit == "成":
                    locked_vi = f"{num_vi} phần"
                elif clean_unit in ["炷香", "盞茶", "盏茶"]:
                    locked_vi = f"thời gian {num_vi} {unit_vi}"
                else:
                    locked_vi = f"{num_vi} {unit_vi}"
            else:
                locked_vi = f"{raw_num} {unit_vi}"

            tag_id = f"M{idx}"
            idx += 1
            metrics.append(ExtractedMetric(
                tag_id=tag_id,
                raw_zh=raw_zh,
                numeric_val=num_val,
                unit_vi=unit_vi,
                locked_vi=locked_vi
            ))

        return metrics

    def annotate_text(self, text: str, metrics: List[ExtractedMetric]) -> str:
        """Inject [Mk:locked_vi] right after raw_zh in the Chinese source text."""
        annotated = text
        for m in sorted(metrics, key=lambda x: len(x.raw_zh), reverse=True):
            annotated = annotated.replace(m.raw_zh, f"{m.raw_zh}[{m.tag_id}:{m.locked_vi}]")
        return annotated

    def verify_vietnamese(self, vi_text: str, metric: Any) -> bool:
        """Check if the locked Vietnamese string (or close normalized equivalent) is preserved."""
        locked_vi = getattr(metric, "locked_vi", str(metric))
        needle = locked_vi.lower().strip()
        text_lower = vi_text.lower()
        
        if needle in text_lower:
            return True
        
        # Check alternates like 'ngàn' vs 'nghìn'
        alt_needle = needle.replace("ngàn", "nghìn")
        if alt_needle in text_lower:
            return True
            
        alt_needle2 = needle.replace("nghìn", "ngàn")
        if alt_needle2 in text_lower:
            return True
            
        # Check unit and number presence if available
        unit_vi = getattr(metric, "unit_vi", "")
        numeric_val = getattr(metric, "numeric_val", None)
        if unit_vi and unit_vi in text_lower and (numeric_val is not None and str(numeric_val) in text_lower):
            return True

        return False
