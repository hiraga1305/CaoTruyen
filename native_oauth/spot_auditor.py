# -*- coding: utf-8 -*-
"""CAOTRUYEN - MODULE 3.2: SPOT-AUDIT 4B (SURGICAL MICRO-AUDIT & REPAIR)
File: native_oauth/spot_auditor.py

Functions:
1. Target Isolation: Pinpoints exact paragraph §k flagged by Quality Gate 4A.
2. Micro-Context Extraction: Extracts paragraph §k with preceding §(k-1) anchor.
3. Surgical Repair Prompt Construction: Creates zero-overhead repair directive.
4. Patch Application: Re-validates repaired paragraph §k against Gate 4A.
5. Saves token budget: Avoids re-translating entire chapters (95% token savings).
"""

from __future__ import annotations
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Callable

from native_oauth.scene_contract import SceneContract
from native_oauth.quality_gate import QualityGate4A, GateViolation, GateResult


@dataclass
class SurgicalRepairTask:
    paragraph_idx: int
    raw_source_text: str
    current_flawed_translation: str
    context_prev_translation: str
    violations: List[GateViolation]
    contract_slice: str


@dataclass
class SpotAuditReport:
    total_violations: int
    target_paragraphs: List[int]
    repaired_paragraphs: Dict[int, str]
    is_fully_healed: bool
    remaining_violations: List[GateViolation]


class SpotAuditor4B:
    """Spot-Audit 4B: Selective Surgical Repair for Flagged Paragraphs."""

    def __init__(self, gate: Optional[QualityGate4A] = None):
        self.gate = gate or QualityGate4A()

    def identify_repair_targets(
        self,
        gate_result: GateResult,
        raw_paragraphs: List[str],
        contract: SceneContract,
    ) -> List[SurgicalRepairTask]:
        """Tách các đoạn §k bị lỗi và đóng gói thành tác vụ phẫu thuật vi mô."""
        tasks: List[SurgicalRepairTask] = []
        # Group violations by paragraph
        paras_with_errors: Dict[int, List[GateViolation]] = {}
        for v in gate_result.violations:
            if v.severity == "ERROR" and v.paragraph_idx > 0:
                paras_with_errors.setdefault(v.paragraph_idx, []).append(v)

        for p_id, v_list in paras_with_errors.items():
            current_flawed = gate_result.sanitized_paragraphs.get(p_id, "")
            prev_context = gate_result.sanitized_paragraphs.get(p_id - 1, "")
            raw_src = raw_paragraphs[p_id - 1] if p_id - 1 < len(raw_paragraphs) else ""

            tasks.append(SurgicalRepairTask(
                paragraph_idx=p_id,
                raw_source_text=raw_src,
                current_flawed_translation=current_flawed,
                context_prev_translation=prev_context,
                violations=v_list,
                contract_slice=f"PACING={contract.pacing}|GENRE={contract.genre}",
            ))

        return tasks

    def format_repair_prompt(self, task: SurgicalRepairTask) -> str:
        """Tạo prompt phẫu thuật siêu ngắn gọn gửi cho Gemini 3.8 Flash (chỉ sửa 1 đoạn)."""
        error_lines = []
        for v in task.violations:
            sugg = f" (Gợi ý BNS: {v.suggestion})" if v.suggestion else ""
            error_lines.append(f"- Lỗi [{v.error_code}]: '{v.matched_snippet}'{sugg}")

        prompt = f"""[SURGICAL REPAIR DIRECTIVE - ĐOẠN §{task.paragraph_idx}]
Bạn là Biên tập viên Văn học Bạch Ngọc Sách. Đoạn dịch §{task.paragraph_idx} dưới đây đang mắc các lỗi convert/ngữ nghĩa:

{chr(10).join(error_lines)}

[NGỮ CẢNH ĐOẠN TRƯỚC §{task.paragraph_idx - 1}]:
"{task.context_prev_translation}"

[VĂN BẢN GỐC CHỮ HÁN §{task.paragraph_idx}]:
{task.raw_source_text}

[BẢN DỊCH HIỆN TẠI ĐANG LỖI]:
{task.current_flawed_translation}

YÊU CẦU:
Hãy viết lại duy nhất đoạn §{task.paragraph_idx} để sửa triệt để các lỗi trên, đảm bảo câu văn thuần Việt gãy gọn, đúng văn phong Bạch Ngọc Sách.
Chỉ xuất ra duy nhất 1 dòng bắt đầu bằng '§{task.paragraph_idx} <Nội dung đã sửa>', không in thêm bất kỳ giải thích nào.
"""
        return prompt.strip()

    def apply_deterministic_repair(
        self,
        gate_result: GateResult,
        contract: SceneContract,
    ) -> GateResult:
        """
        Sửa tự động tất định (Deterministic Healing) đối với các lỗi convert rõ ràng
        trước khi cần gọi LLM (giúp tiết kiệm 100% token cho các lỗi convert regex đơn giản).
        """
        healed_paras = dict(gate_result.sanitized_paragraphs)

        STATIC_AUTO_REPLACE = [
            (r"\bkhông cho là đúng\b", "chẳng mảy may để tâm"),
            (r"\bkhông cho là ý\b", "chẳng chút bận tâm"),
            (r"\bsắc mặt\s+(?:một\s+)?ngưng lại\b", "sắc mặt trầm xuống"),
            (r"\bánh mắt\s+(?:một\s+)?ngưng lại\b", "ánh mắt sắc lạnh"),
            (r"\bthần sắc\s+(?:một\s+)?ngưng lại\b", "thần sắc ngưng trọng"),
            (r"\bhít ngược một ngụm khí lạnh\b", "hít vào một hơi lạnh buốt"),
            (r"\bngược lại hít một ngụm khí lạnh\b", "hít vào một hơi lạnh buốt"),
            (r"\bsắc lệ nội nhẫn\b", "ngoài mạnh trong yếu"),
            (r"\bvi bất túc đạo\b", "nhỏ bé không đáng kể"),
            (r"\bthấy săn lòng vui\b", "thấy mồi ngon mà lòng khấp khởi"),
        ]

        for p_id, text in healed_paras.items():
            mod_text = text
            # Auto replace purely static convert smells safely
            for regex_pat, primary_sugg in STATIC_AUTO_REPLACE:
                if re.search(regex_pat, mod_text, re.IGNORECASE):
                    mod_text = re.sub(regex_pat, primary_sugg, mod_text, flags=re.IGNORECASE)
            healed_paras[p_id] = mod_text

        # Re-verify with Gate 4A
        reconstructed_output = "\n".join(f"§{p_id} {txt}" for p_id, txt in healed_paras.items())
        re_result = self.gate.verify_paragraphs(
            raw_worker_output=reconstructed_output,
            expected_paragraph_count=len(healed_paras),
            contract=contract,
        )
        return re_result
