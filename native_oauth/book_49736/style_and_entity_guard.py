"""CAOTRUYEN V2.0 - STYLE AND ENTITY GUARD (0-TOKEN QUALITY FIREWALL)
Co-engineered with Gemini 4 Argon Architecture Blueprint.

Capabilities:
1. StrictEntityParityRule: Guarantees zero dropped entities (C_zh >= 1 -> C_vi >= 1).
2. DialoguePronounScanner: Detects unauthorized pronoun mutations inside dialogue quotes.
3. AntiStyleDrift: Flags out-of-genre calques, archaic chivalric slang, or internet slangs.
4. SurgicalRepairPrompt: Generates ultra-compact sub-200-token prompts for SpotAuditor4B.
"""
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple, Set


class StyleAndEntityGuard:
    def __init__(self, seed_file: str | Path | None = None):
        self.entity_map: Dict[str, str] = {
            "云千峰": "Vân Thiên Phong",
            "雲千峰": "Vân Thiên Phong",
            "姜柔甲": "Khương Nhu Giáp",
            "薑柔甲": "Khương Nhu Giáp",
            "秦疏影": "Tần Sơ Ảnh",
            "罗琳娜": "La Lâm Na",
            "羅琳娜": "La Lâm Na",
            "小神经": "Tiểu Thần Kinh",
            "姜玉林": "Khương Ngọc Lâm",
            "薑玉林": "Khương Ngọc Lâm",
            "满都拉图": "Mãn Đô Lạp Đồ",
            "滿都拉圖": "Mãn Đô Lạp Đồ",
            "安德": "An Đức",
        }
        
        self.forbidden_dialogue_pronouns: Set[str] = {
            "nàng", "thiếp", "bổn tọa", "các hạ", "tại hạ", "tiểu nữ", "huynh", "muội"
        }
        
        self.style_blacklist: Set[str] = {
            "ok", "okay", "ảo ma", "cực gắt", "pro", "vãi"
        }
        
        if seed_file and Path(seed_file).exists():
            try:
                cfg = json.loads(Path(seed_file).read_text(encoding="utf-8"))
                for word in cfg.get("forbidden_words", []):
                    self.style_blacklist.add(word.lower())
            except Exception:
                pass

    def audit_paragraph(
        self,
        para_id: str,
        zh_text: str,
        vi_text: str,
        is_intense_combat: bool = False
    ) -> Tuple[bool, List[dict]]:
        issues = []

        # 1. KIỂM TRA BẢO TOÀN THỰC THỂ (STRICT ENTITY PARITY)
        for zh_name, vi_name in self.entity_map.items():
            zh_count = zh_text.count(zh_name)
            if zh_count > 0:
                vi_count = len(re.findall(re.escape(vi_name), vi_text, flags=re.IGNORECASE))
                if vi_count == 0:
                    issues.append({
                        "para_id": para_id,
                        "code": "ERR_ENTITY_DROPPED",
                        "detail": f"Thực thể '{zh_name}' xuất hiện {zh_count} lần trong bản gốc nhưng mất dấu '{vi_name}' trong câu dịch.",
                        "expected_vi": vi_name,
                        "zh_source": zh_name
                    })

        # 2. KIỂM TRA ĐỘT BIẾN XƯNG HÔ TRONG HỘI THOẠI (DIALOGUE PRONOUN SCANNER)
        dialogues = re.findall(r'[“"”]([^“"”]+)[“"”]', vi_text)
        for dlg in dialogues:
            words = set(re.findall(r'\b\w+\b', dlg.lower()))
            active_forbidden = set(self.forbidden_dialogue_pronouns)
            # Trong bối cảnh đô thị hiện đại, cấm cả "ta / ngươi" trừ khi đang trong cảnh giao chiến sinh tử
            if not is_intense_combat:
                active_forbidden.update({"ta", "ngươi"})

            mutated = words.intersection(active_forbidden)
            if mutated:
                issues.append({
                    "para_id": para_id,
                    "code": "ERR_PRONOUN_MUTATION",
                    "detail": f"Phát hiện đại từ lệch chuẩn {list(mutated)} trong câu thoại: \"{dlg[:60]}\"",
                    "mutated_tokens": list(mutated)
                })

        # 3. KIỂM TRA LỆCH TÔNG VĂN PHONG (ANTI-STYLE DRIFT)
        all_words = set(re.findall(r'\b\w+\b', vi_text.lower()))
        drifted = all_words.intersection(self.style_blacklist)
        if drifted:
            issues.append({
                "para_id": para_id,
                "code": "ERR_STYLE_DRIFT",
                "detail": f"Từ vựng lệch giọng văn nghiêm túc: {list(drifted)}",
                "drifted_tokens": list(drifted)
            })

        return (len(issues) == 0), issues

    def build_surgical_repair_prompt(self, para_id: str, zh_text: str, broken_vi: str, issues: List[dict]) -> str:
        constraints = [f"- {item['detail']}" for item in issues]
        constraint_block = "\n".join(constraints)
        return (
            f"[NHIỆM VỤ VI PHẪU ĐOẠN {para_id}]\n"
            f"Câu gốc (ZH): {zh_text}\n"
            f"Bản dịch lỗi (VI): {broken_vi}\n"
            f"LỖI CẦN KHẮC PHỤC NGAY:\n{constraint_block}\n"
            f"YÊU CẦU: Chỉ trả về duy nhất đoạn tiếng Việt đã sửa chuẩn xác, giữ nguyên giọng văn trầm mặc, "
            f"bắt buộc khôi phục đúng tên nhân vật và xưng hô chuẩn (tôi - cô / tôi - anh)."
        )
