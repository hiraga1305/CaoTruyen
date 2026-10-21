# native_oauth/cartridges/urban_suspense.py
from __future__ import annotations

import re
from typing import Dict, Tuple
from native_oauth.cartridges.base_cartridge import BaseGenreCartridge, GenreConstraintSpec


class UrbanSuspenseCartridge(BaseGenreCartridge):
    """
    Cartridge Đô thị Huyền Nghi / Linh Dị / Đoạt Bảo Thám Hiểm.
    Đặc thù:
    - Nhịp điệu sắc lạnh, hồi hộp, gay cấn, khẩu ngữ đô thị hiện đại tự nhiên.
    - Mật độ Hán-Việt vừa phải (25% - 45%), tránh văn phong cổ trang kiếm hiệp sáo rỗng.
    - Giữ trọn các thuật ngữ phong thủy, bói toán, chúc do thuật, kỳ môn cổ xưa trong bối cảnh đời thường.
    """

    SUSPENSE_TERM_MAP: Dict[str, str] = {
        "三钱济世": "Tam Tiền Tế Thế",
        "三錢濟世": "Tam Tiền Tế Thế",
        "无间地狱": "Vô Gian Địa Ngục",
        "無間地獄": "Vô Gian Địa Ngục",
        "祝由术": "Chúc Do thuật",
        "祝由術": "Chúc Do thuật",
        "推拿": "xoa bóp",
        "正骨": "nắn xương",
        "家电维修": "sửa đồ điện",
        "家電維修": "sửa đồ điện",
        "测字": "chiết tự",
        "測字": "chiết tự",
        "卜祸福": "bói họa phúc",
        "卜禍福": "bói họa phúc",
        "毛骨悚然": "rợn tóc gáy",
        "不寒而栗": "ớn lạnh thấu xương",
        "不寒而慄": "ớn lạnh thấu xương",
        "莫名其妙": "chẳng hiểu ra sao",
        "心惊肉跳": "tim đập chân run",
        "心驚肉跳": "tim đập chân run",
    }

    def __init__(self) -> None:
        self._spec = GenreConstraintSpec(
            genre_id="URBAN_SUSPENSE_MYSTERY",
            min_sino_viet_ratio=0.25,
            max_sino_viet_ratio=0.45,
            forbidden_terms_vi=(
                "tiểu nhị",
                "chưởng quầy",
                "nội lực",
                "vẫn lạc",
                "đạo hữu",
                "tiểu hữu",
                "lão phu",
                "ngươi ngươi ta ta",
            ),
            preferred_replacements_vi={
                "tiểu tử": "cậu ta",
                "lão nhân gia": "ông cụ",
                "tại hạ": "tôi",
                "các hạ": "anh / bạn",
            },
        )

    def get_constraint_spec(self) -> GenreConstraintSpec:
        return self._spec

    def pre_process_entities(self, raw_zh: str) -> Tuple[str, Dict[str, str]]:
        glossary = {k: v for k, v in self.SUSPENSE_TERM_MAP.items() if k in raw_zh}
        return raw_zh, glossary

    def post_process_register(self, translated_vi: str) -> str:
        out = translated_vi
        for archaic, modern in self._spec.preferred_replacements_vi.items():
            pattern = re.compile(r"\b" + re.escape(archaic) + r"\b", re.IGNORECASE)
            # Preserve capitalization if the matched text starts with uppercase
            def _repl(m):
                matched = m.group(0)
                if matched[0].isupper():
                    return modern.capitalize()
                return modern
            out = pattern.sub(_repl, out)
        return out
