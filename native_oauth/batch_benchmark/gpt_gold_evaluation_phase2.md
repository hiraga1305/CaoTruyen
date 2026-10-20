# GPT blind evaluation, phase2 — 2026-10-13

All104 generated targets were reviewed untouched against full original Chinese and the frozen gold. Model labels, route code, native workspaces and peer style judgments were not opened. No candidate was edited and no replacement translation lines are supplied.

Evaluation hash: `d2c143ead597d9a74217ef302fc890c04137ca435ec323f4999193aed14b87c3`. The source corpus hash stays `3d8b75e3eb8ed2dcd0348e8c8f5ce93f14b34a17103488843767071737f5975e`.

## Scope and counts

| Group | Evidence role | Target paragraphs | Gold PASS / FAIL / AMBIGUOUS | Confirmed semantic error paragraphs | Literary error paragraphs |
|---|---|---:|---|---:|---:|
| V2-X | Diagnostic retest, previously inspected targets | 52 | 23 / 1 / 1 | 1 | 6 |
| V2-R | First translation of reserved synthetic scene102 | 4 | 4 / 0 / 0 | 0 | 1 |
| CTRL-Y | Imperfect single-worker control, extra combined context | 48 | 22 / 0 / 0 | 0 | 5 |

There are25 obligations for V2-X, four for V2-R and22 for CTRL-Y:51 case judgments. Prior synthetic source paragraphs are not counted as generated outputs. The JSON contains every104 source/target row with separate semantics, actors, relation type, numeric amount, unit and style results.

## Did generation repair the previous financial failures?

The old added action “quỵt nợ” is absent from the new V2-X paragraph c0004p0047. The fresh target says “đi vay các khoản vay nhỏ ... lấy khoản vay này đắp khoản vay khác”, preserving taking loans and servicing loans without adding deliberate evasion. This is a generation result, not an edited old candidate. Native provenance verification is root’s responsibility; this evaluator received the untouched-output blind bundle.

At c0002p0055, “vay tiêu dùng vi mô” restores the small scale through “vi mô”, but still narrows 小贷 to a consumer-loan subtype not explicitly supplied. This is a remaining minor category qualifier, with correct lender/borrower, duration and broad action. It is not a catastrophic financial inversion.

The fresh c0002p0057 has a new domain ambiguity: 上线 becomes “cấp trên”. The source identifies an upstream loan promoter and subsequently a classmate. The target still mentions loan promotion and preserves classmate context; it does not expressly say employment. Therefore a claimed new boss relationship would be too strong. This review marks the relationship obligation AMBIGUOUS, rather than a proved major false relationship. A production relation ledger should bind the domain, not merely retain the two person names.

## Reserved first-generated synthetic scene

All four frozen obligations pass: brother500 versus sister20,000, the female phone respondent, the next-day2,000 loan after a tonight-only refusal, and all300 units at least900g. No wrong actors, amounts, inequality or permanent-refusal state was found.

Paragraph c0102p0003 retains a clumsy deictic phrase “lời từ chối tối qua ... tối nay”. The Chinese source itself uses the corresponding 昨晚/今晚 form, and the target explicitly states no permanent commitment, so it is an editorial clarity issue rather than a proved time inversion.

“Kiện thuốc” remains packaging AMBIGUOUS: 件 counts the goods and source does not specify whether each medicine unit is packaged. The prior evaluator qualification still applies. It is not counted as a confirmed scale error. Only four synthetic paragraphs were first generated; this cannot establish unseen real-novel quality.

## What survived and what remains weak

The new diagnostic and control outputs preserve debt ownership,700,000, the original versus current protagonist, conditional teacher risk, offers refused, the older sister, and the two500 transfers crossing1,000. Narration now consistently uses cậu in the authentic candidates; no cậu/hắn drift was found in these phase2 spans.

Natural Vietnamese remains weak in both. Examples include “ánh mắt ... ngưng lại”, “không/chẳng cho là đúng nói” and “thằng nhóc cậu”. CTRL-Y also retains “những học sinh ... nối liền không dứt” and the awkward credit verb “quẹt các khoản vay nhỏ”. These are literary failures; “quẹt” does not prove deliberate debt evasion. The diagnostic has six flagged literary paragraphs and the control five. Single-reviewer style counts are editorial judgments, not certified Bạch Ngọc Sách scores.

## What this supports for the system

- Generic financial action rules prevented the old explicit default claim in the fresh diagnostic, but term subtype inference still needs discipline. Keep source granularity and typed action evidence.
- Bind each relation to its source domain: classmate, loan promoter, relative or employment superior. A generic higher-level label is insufficient for automatic confidence.
- Narrator register improved in the diagnostic. Keep that immutable across workers, with documented contextual address overrides.
- Parser trees and correct entity states do not guarantee fluent Vietnamese. Evaluate literary coherence on whole source chunks; regenerate failed chunks through a stronger generic contract rather than patching flagged lines.
- Add fresh authentic targets with pronoun ellipsis, aliases and delayed reveals that require earlier source, then compare equal-context sequential and parallel runs.

V2-X is a diagnostic retest, because phase1 findings informed design. CTRL-Y received combined original capsules with extra cross-scene/future context; it is not an equal-context causal control. Its zero confirmed semantic errors cannot prove that single-worker scheduling is superior or that parallelism caused the diagnostic’s qualifier/ambiguity. No evidence here warrants a ten-thousand-chapter reliability claim.
