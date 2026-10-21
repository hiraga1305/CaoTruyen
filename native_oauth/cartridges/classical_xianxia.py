# native_oauth/cartridges/classical_xianxia.py
from __future__ import annotations

from typing import Dict, Tuple
from native_oauth.cartridges.base_cartridge import BaseGenreCartridge, GenreConstraintSpec


class ClassicalXianxiaCartridge(BaseGenreCartridge):
    """
    Cartridge Tiên hiệp / Kiếm hiệp Kinh điển.
    Bảo toàn nhịp điệu biền ngẫu (tứ tự thành ngữ) và mật độ từ Hán-Việt cổ phong (60%-75%).
    """

    FOUR_CHAR_IDIOM_MAP: Dict[str, str] = {
        "杀人夺宝": "sát nhân đoạt bảo",
        "斩草除根": "trảm thảo trừ căn",
        "灰飞烟灭": "khói tan mây tạnh",
        "神魂俱灭": "thần hồn câu diệt",
        "逆天而行": "nghịch thiên nhi hành",
        "道心稳固": "đạo tâm vững chắc",
    }

    def __init__(self) -> None:
        self._spec = GenreConstraintSpec(
            genre_id="CLASSICAL_XIANXIA",
            min_sino_viet_ratio=0.60,
            max_sino_viet_ratio=0.75,
            forbidden_terms_vi=("ok", "pro", "level", "cực gắt", "ảo ma"),
            preferred_replacements_vi={
                "cấp độ": "cảnh giới",
                "năng lượng": "linh lực",
                "chết": "vẫn lạc",
            },
        )

    def get_constraint_spec(self) -> GenreConstraintSpec:
        return self._spec

    def pre_process_entities(self, raw_zh: str) -> Tuple[str, Dict[str, str]]:
        glossary = {k: v for k, v in self.FOUR_CHAR_IDIOM_MAP.items() if k in raw_zh}
        return raw_zh, glossary

    def post_process_register(self, translated_vi: str) -> str:
        out = translated_vi
        for modern_slang, classical_term in self._spec.preferred_replacements_vi.items():
            out = out.replace(modern_slang, classical_term)
        return out
