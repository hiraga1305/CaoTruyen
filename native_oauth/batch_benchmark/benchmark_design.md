# Locked batch translation experiment — 2026-10-13

The question is whether Gemini 3.8 Flash low/medium can produce coherent batch translations through separate workers when given source-derived shared context. The experiment must improve the route that generates translations. Editing a mistaken sentence after evaluation is not an experiment result.

## Freeze and split

`locked_cases.json` was created before any new Gemini output. Its canonical SHA-256 is `3d8b75e3eb8ed2dcd0348e8c8f5ce93f14b34a17103488843767071737f5975e`. Verify by serializing every top-level field except `corpus_sha256` with UTF-8, `ensure_ascii=False`, sorted keys and separators `(',', ':')`.

The full source corpus contains 580 paragraphs: chapter 1 has 192, chapter 2 has 133, chapter 3 has 125 and chapter 4 has 130. Chapter 1 is development data: its known errors already influenced the architecture and must not count as unseen improvement evidence. Sixteen selected development paragraphs cover quantitative and prose hazards.

Heldout authentic targets are sixteen paragraphs each from consecutive chapters 2–4:

- Chapter 2, paragraphs 53–68: a humorous “father” address, loan-promoter friendship, refusal, a nickname and the 700,000 debt.
- Chapter 3, paragraphs 76–91: reported school abuse, conditional risk, an offered loan refused, the original body and inherited debt.
- Chapter 4, paragraphs 39–54: unanswered parents, the older sister, separated households, loan rollover and two distinct transfers of 500.

The twelve self-authored Chinese paragraphs in scenes 101–103 are synthetic modern-fiction stress tests. They are never described as scraped stories. They test long return, sibling pronouns, units, inequalities, temporary refusal, borrowing direction and updated debt states over three scenes. There are 41 explicit source-grounded obligations overall: 8 development, 22 authentic heldout and 11 synthetic heldout. Every target paragraph also receives full semantic and literary review; the obligations are not an exhaustive quality checklist.

## Matched routes

Run the identical 60 heldout target paragraphs through each route and each model setting. Preserve the same glossary, target order, output schema and public genre style contract.

1. **Local isolated baseline:** separate workers see their selected chapter excerpt and local source only. They have no shared cross-chapter state. This is a deliberately measurable current-route baseline, not an assertion that every production pipeline currently works this way.
2. **Shared source context:** before parallel translation, build bounded snapshots from original Chinese source. Each worker receives its own immutable snapshot, relevant original quotations, consistent entity identifiers and style settings. The context source is the full original corpus, never another worker’s translation. Keep each capsule under 6,000 characters where possible. Retrieve only earlier events and the excerpt’s immediate surroundings; do not silently reveal future plot.

Gemini low and medium are separate factors. Save the actual returned model identity, native session/runtime evidence, source and contract hashes, input size, elapsed time, and usage when the CLI provides it. Logical worker separation alone does not prove actual simultaneous subagent execution; runtime evidence must establish that independently.

Prior quotations that a chapter 4 worker needs can include chapter 2 paragraphs 18 and 125–129. They establish the initial small balance and Bai’s earlier transfer. Chapter 3’s original-body references can retrieve chapter 2 paragraphs 9–10 and its own earlier introduction of Zhou. Quotations belong in a generic source retrieval result, not an answer hint named after a gold case.

## Independence and leakage

Translation workers must not receive `reviewer_cases`, categories, severity, reviewer obligations or required Vietnamese wording. Put only source packets and public contracts in the native worker workspace. A parser tree is a fallible source-analysis aid. It is neither a Vietnamese gold translation nor proof of document-wide coreference.

The GPT evaluator may read the frozen source and obligations after candidates exist. Hide low/medium and route labels when passing candidates to independent reviewers; random candidate labels and output hashes suffice. Reviewers must quote both source and candidate when claiming an error. Ambiguous sources remain ambiguous: e.g., family separation is not proof of a legal divorce, a speaker’s suspicion is not a narrator’s confirmed fact, and promises are not completed transactions.

## Measurements and interpretation

Report critical, major and minor semantic errors per 100 target paragraphs, explicit obligation pass counts, consistency failures across worker boundaries, and literary failures with evidence. Because a single paragraph can fail multiple obligations, distinguish failed obligations from erroneous paragraph counts. Format/schema failure, truncation, refused tool action, no result and completed bad translation are different outcomes.

Classify continuity errors by name/alias, pronoun or speaker, social/loan relation, numeric/unit comparison, temporal update, uncertainty or unsupported reveal. Evaluate natural Vietnamese, spelling, appropriate modern school/cultivation satire, dialogue versus inner thoughts and situated address choices. Multiple good Vietnamese phrasings can pass. Bạch Ngọc Sách orientation is an editorial rubric; no official certification is claimed.

Compare matched outputs and do not claim statistical superiority from one tiny run. Forty-eight authentic heldout paragraphs and twelve synthetic paragraphs can expose route weaknesses; they cannot establish reliability over ten thousand chapters. If a route fails, preserve its output, extract the root failure class and revise generic retrieval, contracts, scheduling or state versioning. Then rerun fresh candidates under a separately versioned contract. Do not patch failed sentences and count that as route improvement. The first results are heldout; once inspected for design, later reruns are regression evidence and require a new unseen extension for stronger claims.

## Scaling controls to test next

A coherent source plan should precede a translation wave. Parallelize independent scenes or bounded chapter windows using immutable canon snapshots. Maintain versioned entities, relations, timeline events, and quantity/loan states with source citations, while preserving uncertain or speaker-attributed claims. Publish only a complete window after source coverage and continuity checks; retry an entire failed chunk from Chinese source with a stronger generic route, instead of editing its visible mistake.

Before a ten-thousand-chapter run, extend the unseen corpus to other genres and long-range reappearances, measure throughput and native usage, add drift sampling at window boundaries and state updates, and cap retries and context size. Translation throughput and narrative coherence must be reported separately.
