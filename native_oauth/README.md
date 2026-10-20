# Antigravity OAuth novel workflow

Workspace-owned artifacts and custom native agents. Authentication uses agy's
cached account profile; subprocesses clear GEMINI_API_KEY and never read or copy
OAuth token storage. Original chapters remain untouched. No publishing to BNS.

Source -> real Chinese parser -> Antigravity genre-aware draft -> two independent
GPT/Codex reviews -> editing -> GPT re-review -> source-bound publication.

Current batch route: [BATCH_WORKFLOW.md](BATCH_WORKFLOW.md) and [batch pilot](BATCH_RESULT_20261013.md).
The single-chapter approved pilot remains documented in [WORKFLOW.md](WORKFLOW.md).
Verified pilot and limitations: [AUDIT_RESULT_20261013.md](AUDIT_RESULT_20261013.md).
Default native execution stops at DRAFT_READY_FOR_CODEX; native reviewers are an
explicit historical experiment and are not the user's chosen final review path.

Native definitions are in ../.agents/agents. Runtime evidence is in runs/.
Research/source references are retained in research/.
