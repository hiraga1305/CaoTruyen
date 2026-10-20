# GPT blinded route evaluation — 2026-10-13

This review inspected all 208 untouched targets: four anonymous groups, each with 48 authentic paragraphs from chapters2–4 and four generated synthetic final-scene paragraphs. The eight preceding synthetic paragraphs were read-only Chinese context, not generated targets. No mapping, native worker workspace or route result file was opened. No candidate was edited and no replacement translation is provided.

The frozen source corpus hash remains `3d8b75e3eb8ed2dcd0348e8c8f5ce93f14b34a17103488843767071737f5975e`. The evaluation hash is `e7c4f2416b4b802e2b39edd61bc228447c2656916c46307638d037f4af0a28be`. The JSON report contains every source/target row and all25 evaluated obligations per group.

## Results

| Anonymous group | Obligations PASS /25 | Confirmed semantic error paragraphs /52 | Critical / major / minor | Style error paragraphs /52 | Unsettled unit interpretation |
|---|---:|---:|---|---:|---:|
| V1-A | 24 | 2 | 0 / 0 / 2 | 8 | 1 |
| V1-B | 23 | 3 | 0 / 1 / 2 | 6 | 1 |
| V1-C | 25 | 0 | 0 / 0 / 0 | 7 | 1 |
| V1-D | 25 | 0 | 0 / 0 / 0 | 7 | 1 |

The obligations and full-paragraph review measure different things. A correct ownership obligation can pass while packaging remains ambiguous. Style flags include editorial judgments and must not be presented as certified Bạch Ngọc Sách scores. There is no measured statistical confidence or model superiority in this small single-run experiment.

## Confirmed semantic findings

| Group | Paragraph | Source evidence | Target evidence | Failure class |
|---|---|---|---|---|
| V1-A | c0002p0055 | 小贷 | khoản vay tiêu dùng | Small-loan category becomes consumer-loan category; minor scope change. |
| V1-A | c0002p0057 | 小贷 | khoản vay tiêu dùng | Small-loan category becomes consumer-loan category; minor scope change. |
| V1-B | c0002p0055 | 小贷 | khoản vay tiêu dùng | Small-loan category becomes consumer-loan category; minor scope change. |
| V1-B | c0002p0057 | 小贷 | khoản vay tiêu dùng | Small-loan category becomes consumer-loan category; minor scope change. |
| V1-B | c0004p0047 | 最后硬着头皮撸小贷也要修仙，一路以贷养贷到现在 | bấm bụng quỵt nợ vay khoản vay nhỏ cũng phải tu tiên | Adds deliberate debt evasion not asserted by the source; major action change. |

The repeated category substitution is one systematic failure class producing two paragraph defects in each of V1-A and V1-B. It is not four independent discoveries. V1-B adds a separate unsupported action. These findings support a generic financial relation contract; they do not justify handcrafted replacements for the benchmark lines.

## What continuity actually survived

All groups preserve Zhang’s700,000 debt, the original-versus-current identity, Zhou’s offered loan and Zhang’s refusal, reported school violence rather than confirmed narration, the older sister as caller, the sister’s500 versus Bai’s previous500 and a balance exceeding1,000. The synthetic final scene preserves sister20,000 repaid, brother500 still unpaid and rent2,000 still recorded. No wrong actor, number amount or invented kinship was found in these selected outputs.

This does not prove that shared context caused the correct results. Many target paragraphs explicitly name their actors and quantities; even a worker without earlier source can translate them correctly. The next unseen extension should contain elliptical targets and aliases whose resolution truly depends on earlier source, with original context ablation.

## Ambiguous unit: qualify the gold rather than inventing a failure

All groups say “ba trăm kiện” for 三百件. The frozen synthetic gold originally treated these as individual non-package units. The original Chinese only specifies300 medicine entities and each net weight of at least900g; it does not fix their packaging. 件 is a generic counter for individual entities, as described by the [Ministry of Education dictionary](https://dict.revised.moe.edu.tw/dictView.jsp?ID=5808&la=0&powerMode=0). Therefore “kiện” is an unproved packaging interpretation, not a demonstrated scaling error. It is AMBIGUOUS and excluded from confirmed semantic counts. The corpus hash stays frozen; this qualification is explicit in the evaluator report.

For a decisive unit test, future unseen source should specify bottles, loose units, boxes or crates, rather than expect the evaluator to infer an unstated container. A production unit resolver should retain source uncertainty.

## Literary route weaknesses

Every group retains some literal Vietnamese. Examples include “ánh mắt ... ngưng lại”, an objectless “chẳng cho là đúng/không cho là đúng”, tangled family/credit clauses and stacked peer address such as “thằng nhóc cậu”. V1-A has “những học sinh ... vẫn nối liền không dứt”; V1-B has “gương mặt lạnh tanh như bài tây”. These preserve broad scene meaning but fail natural prose.

V1-C switches narration from cậu to hắn inside the continuing chapter3 scene; V1-D uses hắn in chapter2 then cậu in chapters3–4. The referent remains Zhang, so these are voice consistency defects rather than fabricated wrong characters. Peer tao/mày versus tôi/cậu cannot by itself be marked semantically wrong; the supplied friendship permits multiple address choices.

## Route improvements to evaluate on fresh candidates

- Bind a source-grounded financial relation lexicon distinguishing small loans, applying for credit, overdue status and intentional debt evasion. Treat these as separate typed actions with actor and evidence; a loan being overdue does not license adding intentional evasion.
- Give every worker an immutable narrative register and a versioned relationship address profile. Allow explicit scene overrides instead of each worker independently choosing a narrator pronoun.
- Keep unit and packaging uncertainty in the source state; require positive evidence before specializing a generic counter.
- Use the semantic tree to support source interpretation and a separate chunk-level literary criterion for fluent Vietnamese. If a chunk fails, regenerate that whole chunk from Chinese under a stronger generic contract. Preserve the failed candidate and report the fresh run separately.
- Expand genuine heldout context-dependent targets before claiming that parallel workers retain a ten-thousand-chapter story arc. Once these results inform the route, reruns here are regression checks rather than unseen evidence.

This report remains anonymous. Root can reveal the mapping only after the report hash is locked.
