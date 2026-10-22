# Antigravity OAuth novel workflow

Antigravity owns crawling, translation, independent native review, repair, approval and publication. No external approval application is required.

See [ANTIGRAVITY_WORKFLOW.md](ANTIGRAVITY_WORKFLOW.md) for commands and limits.

- `pipeline_native.py`: source/parser package -> native draft -> isolated native semantic/literary reviews -> bounded regeneration -> publication evidence. `--draft-only` stops before review; `--resume-draft` validates original runtime provenance.
- Book runners / `chapter_runner.py`: verified scene drafts with ownership and source overlap.
- `review_book_chapter.py`: adapt book drafts to source-bound review envelopes, review natively, then promote to `book_*/approved/` in dependency order.
- `batch_run.py`: source-frozen experimental drafts; no automatic publication claim.
- `run_agy.py` / `native_evidence.py`: completed runtime/model/session provenance.

Native profiles are in `../.agents/agents`; each review receives an isolated workspace. SessionMonitor reports stages directly in Antigravity. Historical evidence is retained for investigation, not used as current approval policy.
