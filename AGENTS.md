# MotoMedic project instructions

## Current contract

Read [PRD](docs/PRD.md), [TRD](docs/TRD.md), [architecture](docs/ARCHITECTURE.md), [status](docs/STATUS.md) and [TODO](TODO.md) before changing behavior, and follow [CONTRIBUTING](CONTRIBUTING.md). The owner's decisions of 24–25 October 2026 define the answer path: [owner_decision_v3.json](reports/evals/20261025_answer_release_v3/owner_decision_v3.json) sets the design, and [owner_decision_v4.json](reports/evals/20261025_answer_release_v3/owner_decision_v4.json) accepts Haiku at effort high for integration. There is **no review layer**: every parsed object of the manual can be cited, and no authored catalog, canonical wording, answer scope or StepDefinition gates a question.

Ordinary Q&A accepts arbitrary manual-supported questions, including concise partial answers and checklists. Keep SUPPORTED, AMBIGUOUS, UNSUPPORTED, SAFETY_STOP and SYSTEM_ERROR distinct. Malformed output, outage, quota and integrity failures are SYSTEM_ERROR. The fixed messages are in the PRD. Reported success is not a verified repair. Never invent repairs, page numbers, hidden faults or OEM diagnostic order.

## Source

The sole source is the 149-page `royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf`, SHA-256 `CF221A29E2F9CD5AF6E80A99774A697C814E8EDA661C27D72E519D8A7E80DA89`, edition RAM00818/A, 4 November 2025. It is an owner's manual. The owner approved Himalayan + BS6 selection; do not invent model-year or manual-edition rider questions. The support route is the manifest-bound `mailto:support@royalenfield.com`, with its recorded market-fit limitation. Docling's page 103 gap stays flagged.

The [161-case package](human_review/agent_release_161/README.md) and other review packages are retained as golden-answer data, not as a gate. Do not label agent inspection as human signoff.

## Answer path

Index `index_a609ca61c635641e0a22dc48` is built offline from the cached Docling parse of `index_a3282c4d98cf54595e4ba168`. WARNING, CAUTION and NOTE boxes join the section they follow, page-break continuations stay in one section, and the search text carries the real heading. It holds 154 sections and 532 chunks, embedded with BGE-M3. Requests never reparse or re-embed the manual. A source, parser, chunking or embedding change creates a new index.

A turn runs as follows:
1. Dense search (BGE-M3 query vector) and BM25 run, and reciprocal rank fusion keeps only the top 5 chunks. When the dense and BM25 top-3 sections differ, the pinned cross-encoder orders those 5; it never adds a chunk.
2. The model receives the whole section of each chunk as plain text with short labels. There is no parser JSON, no server-added warning text and no source-gap IDs.
3. One `claude-haiku-5-5` call fills the answer template. It runs at effort `high` with thinking disabled and the system prompt cached for 5 minutes. There is no verifier, correction round, retry or fallback model.
4. The deterministic gate releases the answer or fails closed. When nothing is retrieved, the fixed fallback and support route are sent with no model call.
5. The released view is saved durably before any byte streams. Recovery reads the same saved view.

Code is in [cloud/grounded_generation/](cloud/grounded_generation/); the worker and API wiring is in [cloud/arm_a/](cloud/arm_a/). The gate checks structure, citations, numbers and warning decisions, not meaning, so a released answer is not independent factual proof. The 30 evaluation questions are now development cases; held-out cases cannot enrich prompts or retrieval tuning.

## Release, operations and spending

The current release is [serving manifest v11](reports/public_evaluator/20261025/serving_manifest_v11.json). Never alter frozen bindings to make a check pass; a changed serving input needs a new frozen version. Earlier v8–v10 manifests are history.

Nothing in the repository authorizes deployment, public opening, extra provider spending, Haiku-ledger changes, billing changes or GCP changes. Each needs the owner's explicit scope. The hosted stack is offline while billing is disabled, and the new index is not uploaded to hosted Qdrant. Never restart stopped billing without owner authorization. Keep the existing shared Haiku USD1 ledger, 100-attempt and token ceilings, and the INR2,700 lifetime budget with its INR2,540 billing-disconnect guard; delayed reporting prevents an exact instantaneous cap. Keep provider credentials, rider data and raw rider media out of Git and routine telemetry. Builds and real-provider runs are hosted; label local checks as local.

## Repository discipline

Keep `main` as the baseline; current work is on `codex/public-evaluator`. Temporary branches use `codex/` and are removed after checked integration. Historical files are recoverable from Git; do not restore draft-then-verify, the review gate or other competing designs into the active tree. Root-level Python modules outside the serving import graph are historical tooling.

Run `python tools/check_repository_structure.py` after navigation or layout changes, and the provider-free tests listed in [CI](.github/workflows/ci.yml) after runtime changes. New reports belong under `reports/<work-area>/<version-or-run>/`; evaluations under `reports/evals/<run>/`.
