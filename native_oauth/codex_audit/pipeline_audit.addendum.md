# Current Codex gate re-audit and fixture correction addendum

Date: 2026-10-13. Reviewer: independent Codex GPT subagent `/root/gpt_pipeline_audit`. This addendum supersedes the initial report wherever it discusses the now-revised default review route, parser version interpretation, and the causes of interrupted native experiments. No peer GPT review files were read. No implementation edits, external API calls, agy runs, credential access, or account configuration reads were performed.

## Verified current behavior

`pipeline_native.py` now stops at `DRAFT_READY_FOR_CODEX` by default. Native reviewer/auditor execution requires explicit `--native-review-experiment`. An offline mocked invocation of the actual `main` called the translator stage exactly once, emitted the Codex-ready state/protocol, and did not publish or call a native reviewer. This resolves OAUTH-01 for the normal route. The opt-in historical experiment remains distinct.

The shared gate now accepts `review_policy.mode=codex_gpt_sessions`, requiring two distinct expected session identities, matching review session identities, `identity_basis=codex_subagent`, `codex/gpt-` reviewer model strings and a `native/` candidate. Same inherited GPT model across two sessions is allowed. The default remains `distinct_models`, preserving the strict API policy. Review policy is included in the cache digest, report and published evidence; sourced continuity revalidates using that saved policy.

`codex_gate.py` evaluates the two reviews and checks the second review's five explicit literary-inspection flags before its CLI publish path. Its session identifiers are coordinator attestations from the actual delegated tasks, not model-generated proof of their own isolation. The tool does not cryptographically authenticate arbitrary JSON identity strings; the trusted coordinator must pass the real dispatched session/task identifiers.

`run_agy.py` now copies existing runtime directory files to a uniquely named sibling `.history.*` directory before replacing event/diagnostic/runtime files, when prior `events.jsonl` exists. This prevents that ordinary rerun path from silently overwriting its earlier runtime evidence. The supervisor reports that temporary scoped permission grants were removed after testing; this audit did not read private/global settings to independently verify that cleanup. Native `always-proceed` flags still belong only to the native experiment/translation subprocess route.

## Corrected interpretation of parser provenance

An actual offline call of the revised `load_parser()` succeeded, including local model hash checks and strict model loading. It returned:

```json
{"engine":"HIT-SCIR LTP","ltp_module_version":"4.2.13","ltp_distribution_version":"4.2.14","model":"LTP/small","revision":"dea87bf0da3c5d054bbd426a78d7fa9efd347799","torch":"2.14.0+cpu","transformers":"4.57.6","weights_format":"safetensors","compatibility":["validated deterministic position_ids buffer omitted because runtime does not persist it"]}
```

The initial audit correctly detected that distribution metadata is 4.2.14, but calling the old 4.2.13 engine label simply wrong was too strong: the installed module itself exposes `__version__=4.2.13`. The old provenance concealed a module/distribution version discrepancy. The new code reports both and resolves that ambiguity for future output. The earlier Transformers-5-specific output note was inaccurate for this runtime; the revised compatibility output correctly names the actual missing-buffer condition. The existing saved prediction artifacts retain their historical provenance text, rather than being silently regenerated or relabeled. No parser accuracy claim follows from loading or these version checks.

## Current offline tests and remaining gate gap

All 31 focused tests in `tests.test_native_pipeline` and `tests.test_semantic_gate` passed, in 0.078 s. Additional in-memory/temporary-directory checks exercised the actual gate/publisher with explicitly synthetic review assertions, not literary-quality claims:

| Check | Result |
|---|---|
| Same GPT model, two expected distinct Codex task paths | PASS |
| Same reviews under the strict default model policy | BLOCKED |
| Duplicate actual review session | BLOCKED |
| Native identity basis substituted for Codex identity | BLOCKED |
| Non-GPT reviewer model | BLOCKED |
| Stale candidate hashes after a negation edit | BLOCKED |
| API candidate under the Codex-native policy | BLOCKED |
| Published evidence retains review policy | Verified |
| Continuity restores and uses that policy | Verified |
| Default native driver calls only translator, stops before release | Verified |

**Remaining concrete release-path gap at this inspected snapshot:** direct `semantic_gate.evaluate(..., review_policy=codex_gpt_sessions)` returns PASS when neither review contains `literary_checks`; direct `semantic_gate.publish` consequently creates a TXT in a temporary directory. The five-flag check currently exists only in `codex_gate.main`. Thus the intended CLI path is guarded, but the shared publishing function and continuity revalidation can accept a Codex-policy bundle without literary inspection flags. Enforce the Codex literary requirement inside the shared validator/publisher, keeping the API default unchanged, and add a direct-publish regression for missing/false flags. This was a real offline reproduction, not an inferred hypothetical defect; no actual novel was released by this test.

The default `codex.review.protocol.txt` uses the generic semantic review protocol. The coordinator must supplement it with session/model identity and the literary flag contract for the literary session, as the final gate requires these fields. Native wall timeout and the per-lookup eight-id cap remain; the earlier missing hard native token-budget finding is unchanged. Neither issue proves the already supplied artifacts wrong, but both matter before more native runs.

## Both final synthetic fixture comparisons

`genre_fixture_audit.final.json` contains all eight **exact original Chinese source paragraphs**, the original Vietnamese targets, final targets, paragraph verdicts/reasons, changed flags, and explicit before/after differences. It was rechecked against the actual files. The original native draft files were not changed by this audit.

- Tiên hiệp: all four targets are unchanged and remain semantically PASS at synthetic-fixture scope. Minor style notes from the original audit remain optional.
- Hiện đại: only paragraphs 3 and 4 change in `modern_fixture.gpt_edited.json`. Paragraph 3 now says `Cô chưa nhận lời, chỉ nói cần suy nghĩ thêm hai ngày.`, preserving pending assent and the two-day interval. Paragraph 4 now uses `ít nhất 900 sản phẩm, chứ không phải hơn 900 sản phẩm`, preserving `>=900` versus `>900` and correcting the unsupported package/bale unit. All four final paragraphs PASS this direct source comparison.

These remain two self-authored four-paragraph regression fixtures. This re-audit does not establish crawled-novel quality and does not replace the separate two-session final reviews of the full 192-paragraph chapter. Those reviews are delegated elsewhere and were not inspected here.

## Interruptions and quota: causal correction

The supervisor confirms the Gemini reviewer/auditor experiments were interrupted when the user clarified that final review must run in Codex. Their stored `NO_RESULT` manifests therefore represent cancelled/incomplete experiments, not demonstrated Gemini quota exhaustion. Empty diagnostics and absence of quota error text do not independently prove the cancellation reason; the causal attribution comes from the supervisor's execution context. The incomplete runs still cannot act as completed reviews.

The supervisor also reports an earlier native Opus quota `ERROR` visible in controller console output, later overwritten by the earlier research controller run. The historical `quota_after_pilot.json` snapshot shows zero Claude/GPT five-hour remaining quota and supports that prior Opus-specific explanation. The snapshot alone does not prove every cancelled invocation failed from quota, nor does it establish current quota. No fresh quota query was made. The new runtime-history copying reduces future evidence loss but cannot recover the overwritten earlier event.

## Re-audited source snapshot

| File | SHA-256 |
|---|---|
| `semantic_gate.py` | `9844dcbabe70e8a4e12a41f7f1a8e63a29c7e9ed0e044734efd0e0f3130489d6` |
| `native_oauth/codex_gate.py` | `d98f3c84c72a31736212421eb50877f66b06dd778e7dbb2bd7a2d49589ac8baa` |
| `native_oauth/pipeline_native.py` | `809d1bb3b10ac08fbc6791909391ec075f8d2c0019c6ba8dab0a966ad1e14d20` |
| `native_oauth/run_agy.py` | `9ae6c2c759edd85256c287086606e2f5c58300984653cb9a9f6a0bbabdda4304` |
| `native_oauth/parse_source.py` | `afc08ce45c49e7b9b34ae0a254bcb141d2e50afb50e00e60826b24337cfcb45a` |

Any later parent fix to the shared literary enforcement needs a new targeted check; the pass/fail findings above apply to these exact source hashes.

## Final targeted confirmation: shared literary bypass resolved

The parent applied the shared-validator correction and requested this bounded follow-up. The current `semantic_gate.evaluate` Codex policy now selects `policy.literary_session` (or the second required session by default) and requires exactly all five `LITERARY_CHECKS` fields, each literally `true`. Missing or false flags add `require_explicit_literary_review_dimensions` and block approval. Direct `publish` calls this same validator, so the CLI wrapper is no longer the sole enforcement point. The native pipeline imports the shared constant.

Two targeted regressions passed on the current code: `test_direct_codex_publication_cannot_bypass_literary_review` proves empty and false literary flag sets raise before TXT publication; `test_codex_policy_requires_isolated_sessions_and_preserves_default` proves properly flagged independent same-GPT sessions still pass the Codex policy, duplicate sessions block, and the strict default still rejects same-model reviews.

The earlier bypass reproduction occurred before this parent correction. Because multiple agents were working concurrently, the source hash was captured after that reproduction and already corresponds to the corrected code: current `semantic_gate.py` SHA-256 is **`9844dcbabe70e8a4e12a41f7f1a8e63a29c7e9ed0e044734efd0e0f3130489d6`**. Do not associate the earlier reproduced bypass with that final hash. The "remaining concrete release-path gap" paragraph above is historical and superseded by this targeted confirmation. **This specific release blocker is resolved.**

The supervisor reports that the final 192-paragraph Codex-reviewed chapter was published and a chapter-2 continuity chain was validated. This bounded follow-up did not inspect the other GPT review files or expand into another full-chapter audit. It confirms only the shared gate correction and its focused regression checks; no API or agy call was made.
