# native_oauth/cartridges/base_cartridge.py
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Tuple


@dataclass(frozen=True)
class GenreConstraintSpec:
    genre_id: str
    min_sino_viet_ratio: float
    max_sino_viet_ratio: float
    forbidden_terms_vi: Tuple[str, ...]
    preferred_replacements_vi: Dict[str, str]


class BaseGenreCartridge(ABC):
    """Giao diện chuẩn cho mọi Hộp băng Thể loại (Pluggable Genre Cartridge)."""

    @abstractmethod
    def get_constraint_spec(self) -> GenreConstraintSpec:
        raise NotImplementedError

    @abstractmethod
    def pre_process_entities(self, raw_zh: str) -> Tuple[str, Dict[str, str]]:
        """Giải mã tên riêng / thuật ngữ đặc thù trước khi dịch."""
        raise NotImplementedError

    @abstractmethod
    def post_process_register(self, translated_vi: str) -> str:
        """Chuẩn hóa từ vựng và mật độ Hán-Việt sau khi dịch."""
        raise NotImplementedError
