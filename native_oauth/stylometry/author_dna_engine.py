# native_oauth/stylometry/author_dna_engine.py
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import List, Tuple


@dataclass(frozen=True)
class AuthorDNAProfile:
    author_id: str
    author_name: str
    target_avg_sentence_words: Tuple[float, float]  # (min, max)
    min_single_sentence_para_ratio: float
    signature_particles: Tuple[str, ...]
    stylistic_directive: str


ER_GEN_PROFILE = AuthorDNAProfile(
    author_id="ER_GEN",
    author_name="Nhĩ Căn",
    target_avg_sentence_words=(12.0, 28.0),
    min_single_sentence_para_ratio=0.15,
    signature_particles=("a", "nha", "chậc chậc", "hắc hắc", "sợ gì"),
    stylistic_directive=(
        "Giữ sự tương phản cực đại giữa giọng điệu vô sỉ, lươn lẹo, tự luyến trong lúc bình thường "
        "với nhịp văn bi tráng, cô độc, dứt khoát khi bước vào sinh tử hoặc vấn đạo."
    ),
)

GU_LONG_PROFILE = AuthorDNAProfile(
    author_id="GU_LONG",
    author_name="Cổ Long",
    target_avg_sentence_words=(3.0, 9.5),
    min_single_sentence_para_ratio=0.60,
    signature_particles=(),
    stylistic_directive=(
        "Câu cực ngắn, sắc lạnh như đao. Mỗi câu một dòng (One-sentence paragraphs). "
        "Tuyệt đối cấm gộp các câu ngắn thành câu ghép dài. Bảo toàn phép điệp từ tạo nhịp."
    ),
)

CUTTLEFISH_PROFILE = AuthorDNAProfile(
    author_id="CUTTLEFISH",
    author_name="Mực Thích Lặn Nước",
    target_avg_sentence_words=(14.0, 26.0),
    min_single_sentence_para_ratio=0.20,
    signature_particles=("khẽ", "dường như", "không khỏi", "thầm"),
    stylistic_directive=(
        "Cú pháp tầng bậc chuẩn mực kiểu tiểu thuyết Anh thế kỷ 19. Bề ngoài lịch thiệp quý phái "
        "nhưng độc thoại nội tâm (phun tào) sắc sảo, hài hước ngầm (dry lampooning)."
    ),
)


@dataclass
class StylometricAuditReport:
    passed: bool
    avg_sentence_words: float
    single_sentence_para_ratio: float
    violations: List[str]
    enforced_rewrite: str


class StylometricCritic:
    """
    Bộ Kiểm định & Tái cấu trúc Văn phong theo DNA Tác giả (Author Voice Imprinting Engine).
    """

    def audit_and_imprint(
        self, draft_vi: str, profile: AuthorDNAProfile
    ) -> StylometricAuditReport:
        rewritten = draft_vi
        violations: List[str] = []

        # Nếu là hồ sơ Cổ Long, tự động tách các câu ghép rườm rà thành các đoạn đơn câu sắc lạnh
        if profile.author_id == "GU_LONG":
            rewritten = self._imprint_gu_long_staccato(rewritten)

        paragraphs = [p.strip() for p in rewritten.splitlines() if p.strip()]
        sentences = [
            s.strip()
            for p in paragraphs
            for s in re.split(r"[.!?。！？]+", p)
            if s.strip()
        ]

        avg_words = (
            sum(len(s.split()) for s in sentences) / float(len(sentences))
            if sentences
            else 0.0
        )

        single_sent_paras = sum(
            1
            for p in paragraphs
            if len([s for s in re.split(r"[.!?。！？]+", p) if s.strip()]) <= 1
        )
        single_para_ratio = (
            single_sent_paras / float(len(paragraphs)) if paragraphs else 0.0
        )

        min_w, max_w = profile.target_avg_sentence_words
        if not (min_w <= avg_words <= max_w):
            violations.append(
                f"Độ dài câu trung bình ({avg_words:.1f} từ) nằm ngoài biên độ DNA ({min_w}-{max_w})."
            )

        if single_para_ratio < profile.min_single_sentence_para_ratio:
            violations.append(
                f"Tỷ lệ dòng đơn ({single_para_ratio:.2f}) thấp hơn chuẩn DNA ({profile.min_single_sentence_para_ratio})."
            )

        return StylometricAuditReport(
            passed=(len(violations) == 0),
            avg_sentence_words=avg_words,
            single_sentence_para_ratio=single_para_ratio,
            violations=violations,
            enforced_rewrite=rewritten,
        )

    def _imprint_gu_long_staccato(self, text: str) -> str:
        """
        Tách các câu ghép nối bằng 'nhưng mà', 'bởi vì', 'sau đó' thành các câu ngắn độc lập
        và xuống dòng theo đúng nhịp văn Cổ Long.
        """
        compact = re.sub(r"\s*,\s*(?:nhưng mà|nhưng|rồi sau đó|tiếp đó)\s+", ".\n", text)
        lines: List[str] = []
        for raw_line in compact.splitlines():
            parts = [p.strip() for p in re.split(r"\.(?=\s|$)", raw_line) if p.strip()]
            for p in parts:
                lines.append(f"{p}.")
        return "\n".join(lines)
