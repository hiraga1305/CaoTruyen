# Native Repository Review — Zh→Vi Translation Pipeline

**Prepared by:** novel-research subagent  
**Date (UTC):** 2026-10-13  
**Scope:** Review of five pinned repositories listed in `repositories.json` for use in a Chinese-to-Vietnamese novel translation pipeline.

---

## 1. Source Material

### 1.1 Pinned Repositories (from `repositories.json`)

| # | Repo | Commit (short) | License |
|---|------|---------------|---------|
| 1 | `chi-vi/hanlp_mt` | `fa19f40` | *none stated* |
| 2 | `chi-vi/ltp-dep-to-con` | `cc852ec` | *none stated* |
| 3 | `chi-vi/ltp-onnx` | `455e0b5` | MIT |
| 4 | `hankcs/HanLP` | `281e8ef` | Apache-2.0 (code); CC BY-NC-SA 4.0 (multilingual models); research/teaching only (Chinese models) |
| 5 | `HIT-SCIR/ltp` | `1f042d4` | Free for academic; **commercial use requires a paid license** |

All five have status `VERIFIED_ONLINE` per `repositories.json`.

### 1.2 URLs Fetched (5 URL budget)

| # | URL | Result |
|---|-----|--------|
| 1 | https://github.com/chi-vi/hanlp_mt *(README snapshot used instead)* | — |
| 2 | https://github.com/chi-vi/ltp-dep-to-con *(README snapshot used instead)* | — |
| 3 | https://github.com/chi-vi/ltp-onnx *(README snapshot used instead)* | — |
| 4 | https://bachngocsach.cc/forum/threads/5069/ | **Login-gated** — only JS scaffold returned; no thread content accessible to unauthenticated HTTP request |
| 5 | https://bachngocsach.cc/forum/threads/32905/ | **Login-gated** — same as above |

> [!NOTE]
> The BNS (Bạch Ngọc Sách) forum requires an authenticated session to view thread content. The raw HTML responses confirmed the site identity ("Chào mừng bạn đến với diễn đàn Bạch Ngọc Sách") but contained no readable post text. Therefore **no BNS-specific editorial requirements could be extracted** from these URLs in this review cycle. Any BNS guidelines cited elsewhere in this pipeline must come from authorised local copies or authenticated sessions, and must be clearly distinguished from BNS's *official* requirements vs. our project's stricter editorial interpretation.

---

## 2. Repository Capability Profiles

### 2.1 `chi-vi/hanlp_mt` — *Zh2Vi Hybrid Machine Translator* (Crystal)

**Language:** Crystal  
**Role in pipeline:** Core translation engine (the "brain")

**Capabilities:**
- Implements a three-stage hybrid translation pipeline:
  1. **Input Analysis** — ingests HanLP MTL output: TOK, POS, NER, CON (constituency), DEP (dependency) layers simultaneously.
  2. **Translation Strategy** — phrase-level matching via constituency (CON) tree + UTT (Unified Translation Tagset) labels; falls back to dependency-guided (DEP/DRT) grammar reordering and word-level selection.
  3. **Lexical Selection** — tiered lookup: DepDict (dependency-relation context, priorities: RES > OBJ > AGT) → POS Dict → Sino-Vietnamese (Hán-Việt) fallback.
- Handles idioms and fixed phrases as atomic CON-tree blocks (highest priority).
- Supports special Chinese grammatical constructions (ba 把, bei 被, de 的 structures).
- Word order reordering based on grammar rules applied to DEP labels (e.g., ATT modifier inversion for Vietnamese SVO order).
- Dictionary files: `pos-dict.jsonl` (UTT-tagged single words and phrases) and `dep-dict.jsonl` (DRT-tagged contextual pairs).

**Limits:**
- Output quality is bounded by dictionary coverage; new vocabulary or rare idioms will silently fall through to Hán-Việt pronunciation, not a semantic translation.
- The CON-tree matching ("phrase matching") **is pattern lookup**, not a genuine parse of Vietnamese semantics — a phrase that spans a CON node will be translated as a block only if it appears verbatim in the dictionary. Novel or uncommon phrasings will be processed at the dependency level instead.
- SRL (Semantic Role Labelling) is **not consumed** — it is available in HanLP output but `hanlp_mt` does not appear to use SRL tags for disambiguation. This is a known gap for long complex sentences with multiple predicate arguments.
- No stated license; redistribution or commercial use requires clarification with the `chi-vi` maintainer.
- Requires pre-parsed input from HanLP MTL; cannot operate standalone on raw text.

---

### 2.2 `chi-vi/ltp-dep-to-con` — *LTP DEP→CON Tree Builder* (Crystal)

**Language:** Crystal  
**Role in pipeline:** Adapter — converts LTP4 flat dependency parse to a traversable tree object compatible with the `hanlp_mt` translator's DEP-based reordering logic.

**Capabilities:**
- Takes flat LTP4 token list `{id, word, pos, ner, head, deprel}` and builds a linked tree of `Node` objects.
- Each node retains all LTP tags (POS, NER, DEP relation label).
- Provides `visual_index` float field for non-destructive reordering without altering the underlying tree structure — allows `ATT` modifiers to be placed after their head for Vietnamese order.
- Exposes `vietnamese_meanings` property on nodes (hook for dictionary lookup integration).
- `flatten` method produces a linear word sequence from any subtree (useful for outputting translated segments).
- Standard Crystal shard; installs via `shards install`.

**Limits:**
- Constructs a **dependency tree**, not a true constituency tree (CON). The `hanlp_mt` pipeline uses CON from HanLP natively; this shard is a bridge specifically for pipelines using LTP instead of HanLP as the NLP backend.
- `visual_index`-based reordering is a positional heuristic — it does not enforce grammatical correctness of the reordered output; grammar rules must be implemented by the caller.
- No stated license.
- Only covers LTP4 output schema (CWS, POS, NER, DEP); does not provide SDP (semantic dependency) or SRL.

---

### 2.3 `chi-vi/ltp-onnx` — *LTP ONNX Runtime Parser* (Rust)

**Language:** Rust (+ Python export scripts)  
**Role in pipeline:** High-performance Chinese NLP inference layer — alternative to calling LTP via Python

**Capabilities:**
- Runs LTP models (tiny/small/base/base2) via ONNX Runtime in Rust, yielding:
  - **CWS** (Chinese Word Segmentation)
  - **POS** (Part-of-Speech tagging)
  - **DEP** (Dependency Parsing with Eisner decoding)
- CPU inference (default) and GPU/CUDA inference (`LtpParser::new_with_gpu`).
- FP16 quantisation pipeline (Python scripts): exports PyTorch LTP model → ONNX → FP16-quantised `.onnx` with fused LayerNorm/Attention/GeLU blocks, significantly reducing memory footprint.
- Accepts both raw text (`parse_raw_text`) and pre-segmented text (`parse_cws_text`).
- Benchmarking scripts available to compare Rust-ONNX vs Python-PyTorch throughput.
- License: **MIT** — permissive; suitable for any use including commercial.

**Limits:**
- Only outputs CWS + POS + DEP; **does not produce NER, SRL, CON, or SDP**. For the `hanlp_mt` pipeline (which relies on CON and NER), this shard alone is insufficient; it would need to be paired with `ltp-dep-to-con` and a separate NER source.
- ONNX Runtime dependency must be installed as a system library; GPU support additionally requires CUDA + cuDNN configured on the host.
- The FP16 quantisation introduces approximation error (measurable as MAE vs base model); the `verify_quantized.py` script validates this is within acceptable range, but accuracy loss is real.
- The Python export/quantisation scripts (convert-ltp.py, quantize.py) require Python + `torch ltp onnx onnxruntime onnxruntime-tools` — this is a **build-time** dependency, not a runtime dependency.
- Dependency tree output (head indices + labels) reflects statistical model predictions; these are **not guaranteed semantic truth** — parsing errors propagate into translation reordering errors downstream.

---

### 2.4 `hankcs/HanLP` — *Han Language Processing* (Python/Java/Go)

**Language:** Python (primary), with RESTful clients in Go, Java  
**Role in pipeline:** Primary Chinese NLP backend for `hanlp_mt`; produces the 5-layer MTL output (TOK/POS/NER/CON/DEP)

**Capabilities (native/MTL API):**
- Multi-task learning model produces in one pass: TOK (fine/coarse), POS (CTB/PKU/863/UD), NER (PKU/MSRA/OntoNotes), DEP (SD/UD/PMT), CON (CTB constituency), SRL (Chinese Proposition Bank), SDP (CSDP/DM/PAS/PSD), AMR, coreference.
- 130-language support (multilingual models); dedicated Chinese models (simplified/traditional).
- Both RESTful API (cloud, minimal local setup) and native API (local GPU/CPU inference, Python 3.6–3.10, Windows/Linux/macOS).
- Native API model sizes: small, base, ernie — balancing speed vs accuracy.
- Custom dictionary support (trie-based, three rule modes: force/merge/correct) — critical for proper noun handling in novel translation.
- Sentence-level input; includes sentence splitting utilities.
- Output: unified JSON `Document` format.
- License (code): **Apache-2.0** — permissive.

**Limits:**
- **Chinese model license**: "仅供研究与教学使用" — **research and teaching use only**. Commercial deployment of Chinese-specific models requires explicit negotiation.
- **Multilingual model license**: CC BY-NC-SA 4.0 — **non-commercial**.
- RESTful API (cloud): anonymous users have low quota; requires free API key registration for production use.
- Native API: requires significant compute resources; GPU strongly recommended for acceptable throughput on large corpora.
- SRL output in the `hanlp_mt` design is **not consumed** — SRL labels (ARG0, ARG1, ARGM-TMP, etc.) are available in the Document output but the current `zh2vi` integration does not use them for lexical disambiguation. This means argument-structure ambiguities (e.g., patient vs. agent in passive constructions) are resolved only via DEP labels, not SRL.
- MTL vs single-task accuracy trade-off: per the EMNLP 2021 paper, MTL speed is better but single-task models score higher on individual tasks. For novel translation quality, consider whether CON/DEP accuracy is sufficient from MTL.
- Python 3.6–3.10 only (Python 3.11+ not listed as supported in the pinned README).

---

### 2.5 `HIT-SCIR/ltp` — *Language Technology Platform 4* (Python + Rust)

**Language:** Python (deep learning), Rust (perceptron legacy)  
**Role in pipeline:** Alternative Chinese NLP backend (to HanLP) — provides CWS, POS, NER, SRL, DEP, SDP

**Capabilities:**
- **Deep learning pipeline** (PyTorch, 6 tasks): CWS, POS, NER, SRL, DEP, SDP — all in one model pass.
- **Legacy perceptron models** (Rust, CWS/POS/NER only): extremely fast (16-thread: ~21,581 sentences/sec), accuracy comparable to LTP v3.
- Models on HuggingFace Hub: tiny / small / base / base1 / base2 (various accuracy/speed trade-offs).
- Custom vocabulary via `add_word` / `add_words` API.
- Pipeline API for task scheduling; SDP and SDPG can share computation.
- Rust and C/C++ bindings available for deep learning models (via `libltp`).
- Python installation via pip; model download automatic from HuggingFace.

**Limits:**
- **License for commercial use: PAID** — academic/research use is free, but enterprise/commercial deployment requires a fee and formal agreement with HIT-SCIR (email: car@ir.hit.edu.cn). This is a **blocking constraint** if the pipeline is deployed commercially.
- Does **not natively output CON (constituency trees)**; produces DEP and SDP only. This is why `ltp-dep-to-con` exists — to reconstruct a pseudo-CON-style structure from LTP DEP output for the `hanlp_mt` translator.
- The `ltp-dep-to-con` adapter produces a dependency tree traversal object, **not a true CTB-style constituency tree** — the phrase-level CON matching in `hanlp_mt` (which expects e.g. `(IP (NP ...) (VP ...))` strings) would not work identically with LTP-derived structures without additional adaptation.
- HuggingFace model downloads may be slow or blocked in some network environments (mirrors available at hf-mirror.com).
- Rust legacy model: only CWS/POS/NER (no DEP/SRL/SDP) — insufficient alone for `hanlp_mt`.

---

## 3. Dependency Architecture

```
Raw Chinese text
       │
       ▼
┌──────────────────────────────────────────┐
│  NLP Backend (choose one)                │
│                                          │
│  Option A: hankcs/HanLP (Python)         │
│    → TOK + POS + NER + CON + DEP         │
│    → (SRL available but unused)          │
│                                          │
│  Option B: HIT-SCIR/ltp (Python)         │
│    → CWS + POS + NER + DEP + SRL + SDP  │
│    ↓ (no CON)                            │
│  chi-vi/ltp-dep-to-con (Crystal)         │
│    → pseudo-CON tree from DEP            │
│                                          │
│  Option C: chi-vi/ltp-onnx (Rust)        │
│    → CWS + POS + DEP only               │
│    (NER/CON missing — incomplete alone)  │
└──────────────────────────────────────────┘
       │
       ▼
chi-vi/hanlp_mt (Crystal)
  ├── POS/phrase dictionary (pos-dict.jsonl)
  ├── Dependency-context dictionary (dep-dict.jsonl)
  └── Hán-Việt fallback
       │
       ▼
Vietnamese text output
```

> [!IMPORTANT]
> The dependency tree produced by any NLP backend is a **statistical model output**, not a ground-truth semantic parse. Errors in CWS, POS, NER, or DEP labelling propagate directly into translation word-order and lexical selection errors. This is **not a regex replacement** — it is a probabilistic structured prediction that can and does make mistakes, particularly on: classical literary style (文言文 elements common in Chinese web novels), idiomatic four-character expressions (成语), character names, and ambiguous measure words.

---

## 4. Known Limits Summary

| Concern | Detail |
|---------|--------|
| **SRL not used** | `hanlp_mt` does not exploit SRL output. Argument role errors in complex sentences (passive, causative, serial verb) are not corrected by semantic role labels. |
| **CON gap with LTP** | LTP does not produce constituency trees. `ltp-dep-to-con` bridges this but the result is not equivalent to HanLP's CTB-trained CON parser. Phrase-matching accuracy will differ. |
| **License risk** | LTP (HIT-SCIR) requires paid license for commercial use. HanLP Chinese models are research/teaching only. `hanlp_mt` and `ltp-dep-to-con` have no stated license — redistribution rights are unclear. |
| **Dictionary coverage** | Translation quality is directly proportional to dictionary completeness. Uncovered words fall through to Hán-Việt phonetic rendering, which is often unsuitable for modern web novel prose. |
| **BNS guidelines not retrieved** | Both `bachngocsach.cc` thread URLs (5069 and 32905) returned only the login-gate JS scaffold. Thread content was not accessible without authentication. No BNS-specific editorial standards could be confirmed from these fetches. |
| **Model accuracy vs MTL** | HanLP MTL (multi-task) trades accuracy for speed; per the EMNLP 2021 paper, single-task models are more accurate. For high-quality translation, CON/DEP accuracy matters. |
| **Python version** | HanLP native API supports Python 3.6–3.10 (not 3.11+). LTP supports current Python via pip. |
| **Windows support** | HanLP documents Windows support; LTP is Linux-primary but pip-installable on Windows. `ltp-onnx` (Rust) requires ONNX Runtime to be available as a system DLL on Windows. |

---

## 5. Operational Feasibility Assessment

### 5.1 Using HanLP as Primary NLP Backend (Option A — Recommended)

**Feasibility: HIGH** for research/non-commercial use; **CONDITIONAL** for commercial use.

- HanLP directly satisfies the 5-layer input requirement of `hanlp_mt` (TOK, POS, NER, CON, DEP) in a single MTL call.
- The Crystal `zh2vi` library consumes this output natively.
- Translation quality is bounded by: (a) HanLP model accuracy, (b) dictionary completeness, (c) the absence of SRL integration.
- **Commercial deployment of Chinese models is not permitted under the current license** — requires separate negotiation with 自然语义（青岛）科技.
- RESTful API (cloud) is an alternative that avoids local GPU requirements and model license complexity, subject to API key registration and quota limits.

### 5.2 Using LTP as NLP Backend (Option B)

**Feasibility: MODERATE** — requires `ltp-dep-to-con` adapter; CON fidelity is reduced.

- LTP provides CWS/POS/NER/DEP/SRL/SDP but no constituency tree.
- `ltp-dep-to-con` converts DEP output to a tree object, but this is a DEP-rooted tree, not a CTB-style phrase structure. The `hanlp_mt` phrase-matching stage (which looks up whole CON nodes like NP, VP) may not function equivalently.
- **Commercial use requires a paid license from HIT-SCIR** — a firm requirement, not a guideline.
- Speed advantage of LTP legacy (perceptron) models is significant for bulk processing, but legacy models are CWS/POS/NER only — insufficient for the full pipeline.

### 5.3 Using ltp-onnx as Inference Layer (Option C)

**Feasibility: LOW standalone** — appropriate only as a performance-optimised inference layer for CWS+POS+DEP within Option B.

- `ltp-onnx` alone cannot drive `hanlp_mt` (missing NER and CON entirely).
- As a Rust inference accelerator feeding into a larger pipeline, it offers CPU/GPU inference with FP16 quantisation.
- MIT license is the most permissive of all five repos — no commercial restriction from this component alone.

### 5.4 Overall Pipeline Recommendation

| Scenario | Recommended Stack |
|----------|------------------|
| Research / non-commercial prototype | HanLP MTL (native) → `hanlp_mt` (Crystal) |
| High throughput, non-commercial | HanLP RESTful API (cloud) → `hanlp_mt` (Crystal) |
| Commercial deployment | Clarify HanLP Chinese model license + LTP commercial license before choosing backend; obtain licenses or identify a license-permissive alternative NLP backend |
| Maximum speed (legacy, limited tasks) | LTP legacy (Rust perceptron, CWS/POS/NER only) — cannot drive full pipeline |

> [!WARNING]
> Before any production or commercial deployment: (1) confirm license status of `chi-vi/hanlp_mt` and `chi-vi/ltp-dep-to-con` with their maintainer; (2) obtain HanLP commercial rights or restrict to RESTful API with appropriate auth; (3) obtain LTP commercial license from HIT-SCIR if LTP is used. Proceeding without these clarifications creates legal exposure.

> [!NOTE]
> **Distinguishing dependency trees from semantic truth:** The DEP/CON outputs from HanLP and LTP are statistical model predictions. A head-dependency label such as `dobj` (direct object) does not guarantee the word is semantically the patient — in passive constructions, presupposition contexts, or literary inversion, the label may be structurally assigned but semantically misleading. `hanlp_mt`'s DRT-based lexical selection (DepDict) uses these labels as contextual hints, not as certified semantic facts. Translation accuracy for edge cases should be validated manually.

---

## 6. BNS Guideline Status

Both BNS (Bạch Ngọc Sách) forum URLs listed in the task (`/forum/threads/5069/` and `/forum/threads/32905/`) returned login-gated responses only. The site is a Vietnamese novel discussion/translation community forum (XenForo-based). **No specific BNS editorial requirements or translation standards were readable from these pages.** This review therefore cannot distinguish between:

- Official BNS publication requirements (e.g., chapter formatting, output encoding, glossary conventions)
- Our pipeline's own editorial interpretation (e.g., how to handle untranslated proper nouns, Hán-Việt retention policy, punctuation normalisation)

These must be established via authenticated access to the BNS forum posts or from project-internal documentation, and explicitly labelled as to their origin (BNS mandate vs. pipeline editorial policy).

---

*Report covers repository snapshots as pinned in `repositories.json`. Accuracy of this review is contingent on those snapshots reflecting the stated commit hashes.*
