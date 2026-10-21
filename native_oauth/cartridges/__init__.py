# native_oauth/cartridges package
from .base_cartridge import BaseGenreCartridge, GenreConstraintSpec
from .western_occult import WesternOccultCartridge, PhoneticBackTransliterator
from .classical_xianxia import ClassicalXianxiaCartridge

__all__ = [
    "BaseGenreCartridge",
    "GenreConstraintSpec",
    "WesternOccultCartridge",
    "PhoneticBackTransliterator",
    "ClassicalXianxiaCartridge",
]
