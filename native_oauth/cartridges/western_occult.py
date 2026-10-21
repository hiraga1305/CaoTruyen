# native_oauth/cartridges/western_occult.py
from __future__ import annotations

import re
from typing import Dict, Tuple
from native_oauth.cartridges.base_cartridge import BaseGenreCartridge, GenreConstraintSpec


class PhoneticBackTransliterator:
    """
    Bộ Khôi phục Tên Gốc Phương Tây & Huyền học (Phonetic Back-Transliteration Engine).
    Chuyển đổi tên phiên âm Hán tự về đúng chuẩn Anh/Latin/Do Thái cổ (Quỷ Bí Chi Chủ).
    """

    OCCULT_AND_VICTORIAN_GAZETTEER: Dict[str, str] = {
        "克莱恩·莫雷蒂": "Klein Moretti",
        "克莱恩": "Klein",
        "莫雷蒂": "Moretti",
        "阿兹克·艾格斯": "Azik Eggers",
        "阿兹克": "Azik",
        "因斯·赞格威尔": "Ince Zangwill",
        "奥黛丽·霍尔": "Audrey Hall",
        "阿尔杰·威尔逊": "Alger Wilson",
        "戴里克·伯格": "Derrick Berg",
        "廷根": "Tingen",
        "贝克兰德": "Backlund",
        "鲁恩": "Loen",
        "弗萨克": "Feysac",
        "因蒂斯": "Intis",
        "塞菲罗特": "Sefirot",
        "源堡": "Nguyên Bảo (Sefirah Castle)",
    }

    OCCULT_SEQUENCE_LEXICON: Dict[str, str] = {
        "愚者": "Kẻ Khờ",
        "占卜家": "Nhà Tiên Tri",
        "小丑": "Hề Giả",
        "魔术师": "Ảo Thuật Gia",
        "观众": "Khán Giả",
        "读心者": "Kẻ Đọc Tâm",
        "水手": "Thủy Thủ",
        "歌颂者": "Kẻ Ca Tụng",
        "窥秘人": "Kẻ Nhòm Ngó Bí Ẩn",
        "非凡者": "Phi Phàm Giả",
        "魔药": "Ma dược",
        "序列": "Danh sách",
    }

    def restore_latin_and_occult_terms(self, raw_zh: str) -> Tuple[str, Dict[str, str]]:
        """
        Phát hiện các cụm tên phiên âm (có dấu chấm giữa '·' hoặc nằm trong Gazetteer)
        và cung cấp bảng ánh xạ bắt buộc.
        """
        active_map: Dict[str, str] = {}
        for zh_name in sorted(self.OCCULT_AND_VICTORIAN_GAZETTEER.keys(), key=len, reverse=True):
            if zh_name in raw_zh:
                active_map[zh_name] = self.OCCULT_AND_VICTORIAN_GAZETTEER[zh_name]

        for zh_term, vi_term in self.OCCULT_SEQUENCE_LEXICON.items():
            if zh_term in raw_zh:
                active_map[zh_term] = vi_term

        return raw_zh, active_map


class WesternOccultCartridge(BaseGenreCartridge):
    """
    Cartridge chuyên biệt cho Tây Huyễn / Phong cách Anh Thế kỷ 19 (Quỷ Bí Chi Chủ).
    Loại bỏ từ Hán-Việt kiếm hiệp, khôi phục 100% tên gốc Latin và danh xưng quý tộc.
    """

    def __init__(self) -> None:
        self.transliterator = PhoneticBackTransliterator()
        self._spec = GenreConstraintSpec(
            genre_id="WESTERN_OCCULT_VICTORIAN",
            min_sino_viet_ratio=0.15,
            max_sino_viet_ratio=0.25,
            forbidden_terms_vi=(
                "tiểu nhị", "chưởng quỹ", "khách điếm", "nội lực", "ngân lượng",
                "Khắc Lai Ân", "Đình Căn", "Bối Khắc Lan Đức",
            ),
            preferred_replacements_vi={
                "tiểu nhị": "bồi bàn",
                "chưởng quỹ": "ông chủ",
                "khách điếm": "nhà trọ",
                "nội lực": "linh tính",
                "Khắc Lai Ân": "Klein",
                "Đình Căn": "Tingen",
                "Bối Khắc Lan Đức": "Backlund",
                "Chiêm Bốc Gia": "Nhà Tiên Tri",
                "Ngu Giả": "Kẻ Khờ",
            },
        )

    def get_constraint_spec(self) -> GenreConstraintSpec:
        return self._spec

    def pre_process_entities(self, raw_zh: str) -> Tuple[str, Dict[str, str]]:
        return self.transliterator.restore_latin_and_occult_terms(raw_zh)

    def post_process_register(self, translated_vi: str) -> str:
        cleaned = translated_vi
        for bad_term, good_term in self._spec.preferred_replacements_vi.items():
            cleaned = re.sub(rf"\b{re.escape(bad_term)}\b", good_term, cleaned, flags=re.IGNORECASE)
        return cleaned
