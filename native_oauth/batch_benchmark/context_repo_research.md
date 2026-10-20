# Context research and route constraints — 2026-10-13

## What the repositories actually provide

The local folder contains repositories cloned from the verified Chivi organization, but it does not establish a release or executable specifically named **Chivi v3**. `clone_chivi.py` clones the organization's repositories; a folder name or conversational label is not a version attestation. No claim of running Chivi v3 is justified here.

| Component | Verified revision / evidence | Useful role | Limit |
|---|---|---|---|
| [chi-vi/hanlp_mt](https://github.com/chi-vi/hanlp_mt) | Local HEAD `fa19f40534377b5142b4f4cf96b946a2b9796fe1`, matches previous online manifest; inspected `src/zh2vi/translator.cr` | Sentence TOK/POS/NER/CON/DEP, dictionary selection and grammar rules | Inspected translator takes one parse plus dictionaries. No chapter chronology, identity ledger or crosschapter speaker state in this interface. Not executed in this pilot. |
| [chi-vi/ltp-dep-to-con](https://github.com/chi-vi/ltp-dep-to-con) | Local HEAD `cc852ecb163ae56efe7046b1cda66aa1ade22f65`, matches previous online manifest; inspected `tree_builder.cr` | Constructs traversable nodes from dependency heads, permits reordering | Tree construction does not infer character identity across chapters. A DEP-derived tree is not a native learned CON prediction. Not executed in this pilot. |
| [HIT-SCIR/ltp](https://github.com/HIT-SCIR/ltp) | Existing model `LTP/small` revision `dea87bf0da3c5d054bbd426a78d7fa9efd347799`; inspected actual `native_oauth/parse_source.py` | Executed CWS/POS/NER/SRL/DEP/SDP assists sentence boundaries, names, predicates and arguments | Predictions are fallible; no coreference task, chapter memory, style certification or semantic proof. Each paragraph is parsed separately. |
| [Stanford CoreNLP coreference](https://stanfordnlp.github.io/CoreNLP/coref.html) | Official documentation directly lists deterministic and neural Chinese support | Possible candidate for linking names/pronouns inside a bounded document | Not installed or run; published general-corpus scores are not novel performance. Must benchmark alias changes, dialogue, ellipsis and fantasy names before use. |

[HanLP](https://github.com/hankcs/HanLP) remains a candidate for broader NLP tasks, but its repository description is not proof that a particular Chinese coreference model is present or executed locally. This review does not rank it as superior to the existing parser. Syntax, NER and coreference address different problems; none alone supplies a trusted ten-thousand-chapter story state.

## Evidence for context-aware translation

[Voita et al. 2019](https://aclanthology.org/P19-1116/) identifies context errors involving deixis, ellipsis and lexical cohesion and explains why ordinary translation metrics can miss them. This supports explicit checks for speaker/referent, omissions and repeated entity terminology rather than a single fluency score.

[Hu et al. 2025](https://aclanthology.org/2025.findings-emnlp.1289/) studies segmented multi-turn translation, including supplying the source document before translation, and reports gains over independent segments in its evaluated models. It supports testing a sequential scene baseline alongside independent workers. It does **not** establish Gemini 3.8 low/medium performance on Chinese–Vietnamese serialized fiction.

[Maruf and Haffari 2018](https://aclanthology.org/P18-1118/) explicitly models source and target document memory. The practical distinction is useful: source facts must establish story truth, while previously accepted Vietnamese choices can establish editorial consistency. An erroneous draft must not become a source fact merely because it occurred earlier.

[Wang et al. 2025, SEGALE](https://aclanthology.org/2025.emnlp-main.1645/) evaluates long documents including under-/over-translation and finds that advertised context length does not ensure effective translation over that length. The paper does not validate this pipeline; it motivates bounded scenes and coverage checks instead of feeding an entire novel to one prompt.

## Antigravity native subagents: exact routing matters

The [official custom-subagent documentation](https://antigravity.google/docs/subagents?tab=cli) specifies isolated conversation contexts: a child does not inherit the parent's conversation history. It documents Markdown model tiers `inherit`, `flash` and `pro`. Shared disk access is not shared narrative understanding. Each child therefore needs an explicit, versioned context packet.

[Issue #1150](https://github.com/google-antigravity/antigravity-cli/issues/1150), opened 2026-10-03, reports exact model IDs failing custom-agent registration on CLI 2.1.x/macOS. This is a reporter's observation, not a reproduced Windows result. [Issue #577](https://github.com/google-antigravity/antigravity-cli/issues/577), opened 2026-07-10, similarly requests cross-model child routing. These issues corroborate a routing hazard, but runtime evidence must decide what the installed CLI actually does.

Run separate parent cohorts with `--model gemini-3.8-flash-low` and `--model gemini-3.8-flash-medium`; use `model: inherit` for their native child workers. Record installed CLI version, requested parent model, observed parent model, child conversation IDs and observed child model. If observed child metadata cannot substantiate the route, label exact-tier verification **unknown**; do not substitute a model's self-description. Do not mix tiers within one tree and assume YAML guarantees the result.

For exact-tier attribution, independent CLI custom-worker sessions launched with `--agent novel-batch-worker --model <exact-id>` are a valid fan-out experiment if each session's runtime initialization attests its model. They are parallel worker-agent sessions, not evidence of nested `invoke_subagent` execution. Test nested children separately when their metadata can attest the actual route; keep topology labels separate in results.

## Proposed scalable prevention strategy (architecture inference, not a proven result)

1. **Source preparation before translation.** Hash original chapter/paragraph spans; parse once; extract source-linked entities, aliases, relations, speaker/referent cues, quantities, negation, time, and ongoing scene state. Ambiguous links stay unresolved. Sequentially reconcile these deltas for a bounded arc, with evidence IDs and effective chapter ranges. Facts coming from future chapters may help lexical resolution only if explicitly permitted; they must not be revealed in earlier prose.
2. **Versioned editorial memory.** Keep names, terminology, genre register, narrator voice and context-conditioned forms of address separate from source facts. A glossary entry has provenance and scope. Vietnamese rendering is not permitted to alter numeric magnitude/currency or manufacture a new relation. Every worker reads the same immutable memory snapshot; workers propose deltas and never mutate the shared ledger concurrently.
3. **Parallelize complete scenes with overlap.** Let each worker own a scene/block, carry enough original Chinese before/after for dangling dialogue and referents, and retrieve evidence for relevant entities. Adjacent workers receive the same boundary contract. Translate sequentially inside strongly connected dialogue; cross-book or independent-scene parallelism is safer than arbitrary paragraph fan-out. Overlap is read-only context and must not be duplicated in output.
4. **Check boundaries as well as sentences.** Verify coverage, canonical names, quantities and speaker/referrer consistency inside a block and across adjacent blocks/chapters. A fluent paragraph can still contradict the previous scene. Include hidden continuity probes and evaluate style separately from semantic preservation.
5. **Failure changes the route.** Classify a failure as missing context, memory conflict, wrong segmentation, parser ambiguity, model-capacity issue, or editorial-policy drift. Update the context extraction/retrieval/segmentation policy or scoped glossary, increment its version, identify all dependent blocks, and automatically retranslate those complete scenes from Chinese. A broader context window or sequential medium fallback is selected by policy. Do not splice human-corrected sentences into an otherwise unverified batch.
6. **Avoid error propagation.** Draft output never establishes story truth. Memory revisions invalidate every dependent cached artifact. Re-run coverage, semantic and boundary checks before publication. Unresolved blocks go to quarantine after a bounded number of attempts, with reason codes; do not publish a partial mixture as complete. GPT audits of representative and adversarial samples test the route, rather than manually editing every chapter.

## Minimal experiment needed before broad deployment

Compare same-source low independent, low with context packets, and medium with context packets; include a sequential source-primed scene baseline. Evaluate untouched generated candidates, not hand-edited outputs. Lock tests spanning dialogue turns, aliases, mother–child/formal-address transitions, ambiguous pronouns, loan units, negation and scene changes. Distinguish authentic neighboring chapters from authored stress fixtures.

Measure source coverage, factual errors, speaker/referent errors, name/term drift, cross-boundary contradictions, style violations, calls/tokens, rerun rate and unresolved quarantine rate. Repeat beyond the small pilot before any 10,000-chapter claim. A zero-error small sample is insufficient: independence, long-range recurrence and held-out books/genres remain untested. Source-derived memory packets and context contracts are hypotheses whose improvement must be measured against the no-memory baseline.

## Review status

Only online primary documentation/papers/repositories and local source were inspected in this research task. No installer, native model call, API generation, Chivi converter execution, or CoreNLP/HanLP execution was performed by this reviewer. The root agent owns actual runtime experiments and implementation verification.

## Independent initial architecture read

Read `native_oauth/batch_contract.py` during implementation. Its hashes, source quote validation, cutoff-filtered ledger references, read-only Chinese neighbors, rejection of stale worker state and exact output ownership prevent several forms of provenance and coordination corruption. `DRAFT_MERGED_UNREVIEWED` correctly does not imply semantic approval.

The initial implementation still splits by a maximum paragraph count rather than detected scenes. Retrieval uses literal source keys and recent entries, not crosschapter coreference; a paragraph containing only a pronoun can miss a distant antecedent. Ledger facts are supplied to the builder, not automatically extracted by this module. Glossary mappings remain editorial choices, with no entry-level provenance or temporal scope in the initial schema. `commit_block` explicitly relies on the caller to validate external acceptance evidence; its integrity checks are not semantic validation.

Therefore contract tests can substantiate coordination invariants but not long-range continuity. Benchmark implicit referents and dialogue crossings explicitly, and make source-backed fact extraction, scene splitting, dependency retrieval and externally validated gate evidence concrete before broad rollout. Failure should trigger broader scene regeneration or sequential medium execution with revised context; manually edited sentences are not evidence that the automated route improved.

## Independent initial runner read

Read `batch_experiment.py` and `run_agy.py`. The runner compares the stream's initialization model to the requested exact ID and requires a successful native result plus complete owned-segment IDs. It unsets API-key environment routing, does not read credentials, and does not mutate global permission settings. Per-run CLI tool approval is scoped by the launcher to a workspace under `native_oauth`. Experimental candidates remain explicitly unreviewed and there is no automatic publication call. The two-worker wave limit and timeout provide a bounded pilot, while the stated token limit is a between-wave stop, not a hard in-flight cap.

Initial issues sent to the implementing agent before further runs:

- Reusing a job workspace leaves an old `candidate.json`. A subsequent successful native run that never writes a fresh file could accept and misattribute that old candidate. Archive previous candidate files before launching or use unique run directories; bind the accepted result to this invocation.
- Transport/runtime parsing exceptions outside the validation handler can abort the scheduler without a final blocked report. Convert these failures into explicit worker results and mark unscheduled jobs.
- Missing usage currently contributes zero to the budget total. An unmeasured wave should be marked unknown and stop further scheduling if usage is needed to enforce the declared pilot cap.
- `completed_jobs` initially counts attempted results, including blocked jobs. Report successful drafts, attempted jobs and unscheduled jobs separately so completeness is assessable.

This is a source review of the initial implementation, not a claim that these issues remain after the implementing agent's changes. Final code and runtime artifacts require a later read.

## Source-prepass and scene-contract follow-up

The subsequently added `batch_source_prepass.py` provides an automatic original-Chinese quote index keyed by glossary hits, predicted NER spans and relationship cues. Its NER interpretation matches the existing LTP output shape (`type`, entity text, token offsets). The quotes remain evidence and parser predictions remain advisory. This is a useful retrieval prepass; it is not yet entity linking, pronoun coreference, speaker attribution, timeline inference or a trusted story fact graph. Report this distinction explicitly when presenting the benchmark.

The glossary merge initially uses last-value-wins across packages. Conflicting translations for the same Chinese key should stop state creation or require a scoped explicit decision; silent overwrite can generate the very interchapter terminology drift being studied. Also check that source-package and analysis counts agree before zipped iteration, so missing analyses produce a clear provenance error.

`batch_contract.py` now accepts supplied `scene_end_ids` and adds contiguous experimental scene contracts. This enables safe ownership based on known boundaries, with the existing coverage and budget checks. It does not automatically discover scene boundaries; the fallback remains paragraph-count segmentation. A trial using selected contiguous spans must state whether it includes complete scenes or partial excerpts, and a partial-scene PASS is not a whole-chapter continuity result.

## Runner and prepass fixes re-read

The implementing agent's next revision rejects any job workspace containing a prior candidate or runtime event file, catches execution errors into blocked worker results, stops scheduling after unknown usage, and reports successful jobs separately from attempts. The prepass now rejects conflicting glossary values and missing analysis packages. These specific initial blockers are resolved by source inspection. Small remaining reporting limitations do not change the unreviewed-output status: preparation failure lacks a per-job identifier in its synthetic result, and the console's historical `completed_jobs` key still counts results rather than successes.

I also read the experiment design document for scope and leakage controls. It distinguishes development chapter 1, authentic heldout excerpts and synthetic tests, and does not count manual edits as route improvement. Consequently a later candidate review by this reviewer can be blinded to route/model labels and independent of peer judgments, but cannot be described as ignorant of the design's source-hazard themes. `locked_cases.json` and other reviewers' gold judgments were not read.

## Durable source retrieval backing store implemented

Added `native_oauth/story_store.py`, a SQLite database per novel. Original paragraphs are keyed by source ID and `(chapter, ordinal)`, with package/text hashes; literal mention quotes have an indexed `(key, chapter, ordinal)` lookup. Chapters are indexed transactionally with WAL, optimistic `expected_revision`, immutable hash-chained revisions, and idempotent resume. Changed indexed source, conflicting canonical terminology, input containing target draft fields, and quotes absent from the Chinese original are rejected. This provides storage and retrieval infrastructure for a long novel without placing all historical source quotes in a worker prompt or scanning them all for every request.

Retrieval returns only evidence strictly before the first owned source paragraph, filters rows by a frozen revision, verifies original-source and quote hashes, and caps requested keys, candidates per key, recent paragraphs, intermediate quote pool, final evidence count and final serialized character count including the capsule hash. Recent paragraphs can assist implicit pronouns but are explicitly **not coreference resolution**. A later index revision cannot silently change an earlier worker's snapshot. No translation draft or synthetic PASS receipt is admitted as a story fact.

Public API:

```python
from native_oauth.story_store import StoryStore
with StoryStore('native_oauth/my_book.sqlite3', book_id='piaotia-16014') as store:
    receipt = store.index_package(package, ledger_entries=entries_for_this_chapter,
                                  expected_revision=store.revision)
    capsule = store.retrieve_capsule(owned_ids, keys, revision=receipt['revision'],
                                     pronoun_recent=4, max_entries=32, max_chars=12000)
```

`ledger_entries` are source-quote entries for that single package, such as output from the source prepass filtered to its chapter. Capsule `evidence` rows contain source IDs, original quotations, quote/text/package hashes, and a retrieval reason. The `glossary` field is editorial policy. Callers still must decide scene ownership, relevant source keys, genre/voice policy and acceptance gates; this store never emits semantic approval.

CLI examples (from workspace root):

```powershell
python -X utf8 native_oauth/story_store.py --db native_oauth/my_book.sqlite3 --book-id piaotia-16014 index --source native_oauth/batch_benchmark/source_chapter_0002.json --expected-revision 0
python -X utf8 native_oauth/story_store.py --db native_oauth/my_book.sqlite3 --book-id piaotia-16014 retrieve --owned c0002p0053 c0002p0054 --key 张羽 --revision 1 --recent 4 --out native_oauth/capsule.json
python -X utf8 native_oauth/story_store.py --db native_oauth/my_book.sqlite3 --book-id piaotia-16014 check
```

Nine focused storage tests passed with `python -X utf8 -m unittest tests.test_story_store -v`: persistence/idempotence, concurrent-connection optimistic revision conflict, rollback on changed source/glossary, future filtering, old-snapshot immutability after a new mention index, quote/source tampering detection, target/invented-evidence rejection, character cap including hash, and verification that the actual lookup query uses its index. This is integrity evidence, not a measured 10,000-chapter throughput or translation-quality benchmark. Literal retrieval still needs a stronger entity/coreference planner for genuinely ambiguous long-range references.

## Generic long-return retrieval revision

The retrieval policy now defaults to `retain_first_anchor=True`: an indexed earliest prior source mention per requested key is retained alongside up to three recent prior mentions, followed by the bounded recent-source fallback. This prevents a recent-only cache from discarding an early family/introduction quote merely because the name occurred several more times. It preserves original evidence, not an inferred entity identity; the first mention is not guaranteed to contain the decisive relationship, and capsule budgets can still omit evidence explicitly. Cutoff/snapshot filtering, quote hashes and storage caps remain in force. Use `retain_first_anchor=False` or CLI `--latest-only` to measure the previous policy as a baseline.

Two additional focused tests exercise the long-return failure class: a latest-only query loses the original sister relationship while the default retains that quote and the latest event under the same sufficient budget; a later identity-confirmation quote cannot enter an earlier capsule. The focused storage suite now has eleven passing tests. This is a generic retrieval change, not a target-text patch or proof of resolved coreference.

## Later-block resume support

Added `StoryStore.get_source_package(chapter, revision=None)`. It loads only the requested indexed chapter, verifies the snapshot and introduction-revision hashes, package seal, paragraph coverage and source hashes, then returns a fresh copy. A later-block adapter can use this original predecessor source to build its state pool while planning ownership only for the new block. It does not return an approved translation or establish that the previous chapter passed a quality gate. Publication remains the caller's separately verified responsibility.

The two new resume tests check old-snapshot visibility, independence of caller mutations, rejection of future chapters at an older snapshot, and detection of a tampered/resealed package that disagrees with its immutable introduction revision. The focused storage suite now has thirteen passing tests.
