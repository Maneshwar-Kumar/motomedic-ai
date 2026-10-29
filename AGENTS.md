# MotoMedic project instructions

## Current contract

Read [README](README.md), [PRD](docs/PRD.md), [TRD](docs/TRD.md), [architecture](docs/ARCHITECTURE.md), [status](docs/STATUS.md), [decision log](docs/DECISIONS.md) and [TODO](docs/TODO.md) before changing behavior, and follow [CONTRIBUTING](CONTRIBUTING.md). The owner's decisions of 24–25 October 2026 define the answer path:
- [v3](evals/20261025_answer_release_v3/owner_decision_v3.json): the design;
- [v4](evals/20261025_answer_release_v3/owner_decision_v4.json): Haiku at effort high accepted for integration;
- [v5](releases/owner_decision_v5.json): token ceiling removed, local Claude Code experiments, repository layout.

There is **no review layer**. Every parsed object of the manual can be cited, and no authored catalog, canonical wording, answer scope or StepDefinition gates a question.

Ordinary Q&A accepts arbitrary manual-supported questions, including concise partial answers and checklists. Keep SUPPORTED, AMBIGUOUS, UNSUPPORTED, SAFETY_STOP and SYSTEM_ERROR distinct; malformed output, outage, quota and integrity failures are SYSTEM_ERROR. The fixed messages are in the PRD. Reported success is not a verified repair. Never invent repairs, page numbers, hidden faults or OEM diagnostic order.

## Source

The sole source is [source/royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf](source/royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf), 149 pages, SHA-256 `CF221A29E2F9CD5AF6E80A99774A697C814E8EDA661C27D72E519D8A7E80DA89`, edition RAM00818/A, 4 November 2025. It is an owner's manual. The owner approved Himalayan + BS6 selection; do not invent model-year or manual-edition rider questions. The support route is the manifest-bound `mailto:support@royalenfield.com` ([source manifest](source/source_manifest.json)), with its recorded market-fit limitation. Docling's page 103 gap stays flagged.

The 161-case package and the other review packages are in [archive/](archive/README.md) as golden-answer data, not as a gate. Do not label agent inspection as human signoff.

## Answer path

Index `index_f768fbb216836c003701079e` is built offline from the cached Docling parse of the base index `index_a3282c4d98cf54595e4ba168`, which was produced by [ingest/](ingest/README.md). In the index:
- WARNING, CAUTION and NOTE boxes join the section they follow;
- page-break continuations stay in one section;
- the search text carries the real heading;
- a subsection Docling split from its parent inherits the parent's WARNING/CAUTION boxes.

It has 154 sections and 532 chunks embedded with BGE-M3. Requests never reparse or re-embed the manual, and a source, parser, sectioning or embedding change creates a new index.

A turn runs in five steps:
1. **Retrieval.** Dense search (BGE-M3) and BM25 are fused with reciprocal rank fusion, keeping only the top 5 chunks. When the dense and BM25 top-3 sections differ, the cross-encoder orders those 5; it never adds a chunk. When its best score over the 5 is below the relevance floor (−9.0), the turn gets the fixed fallback with no model call.
2. **Model input.** The whole section of each chunk is sent as plain text with short labels. No parser JSON, server-added warning text or source-gap IDs are added.
3. **Generation.** One `claude-haiku-5-5` call (effort `high`, thinking disabled, system prompt cached for 5 minutes) fills the answer template. There is no verifier, correction round, retry or fallback model.
4. **Gate.** The deterministic gate releases or fails closed. It rejects internal labels in rider text, rewords meta phrases about "the sections supplied", and leaves out policy, watchout or disclaimer sentences that only repeat an earlier section. When nothing is retrieved, the fixed fallback and support route are sent with no model call.
5. **Delivery.** The released view is saved before any byte streams, and recovery reads the same saved view.

Code is in [cloud/grounded_generation/](cloud/grounded_generation/), with the worker and API wiring in [cloud/arm_a/](cloud/arm_a/) and shared types in [cloud/common/](cloud/common/). The gate checks structure, citations, numbers and warning decisions, not meaning. The 30 v3 questions are development cases. The [33 held-out questions](evals/20261025_heldout_v1/README.md) have now been seen, so a new quality claim needs new questions; neither set may enrich prompts or retrieval tuning.

## Experiments

Run experiments locally with [tools/local_answer.py](tools/local_answer.py) or the `/motomedic-answer` skill ([docs/EXPERIMENTS.md](docs/EXPERIMENTS.md)). These use the real retrieval, assembly and gate on the pinned index, with a Claude Code Haiku subagent at effort high as the generator. They make no API call and use no ledger. Label results as local Claude Code runs, and put evaluation runs under `evals/<date>_<name>/`.

## Release, operations and spending

The current release is [serving manifest v11.2](releases/serving_manifest_v11_2.json). Never alter a frozen manifest to make a check pass; a changed serving input needs a new frozen version. Manifests v8–v10.14 are history in `archive/`; their bindings were last verified in their original layout at commit `7c412369f055b4d0ee747501e6b026f5987d1564`.

There is no token ceiling. The 100-attempt allocation (72 used) and the shared Haiku USD1 ledger still bind; do not reset or refund them. Nothing in the repository authorizes deployment, public opening, provider spending, billing changes or GCP changes. Each needs the owner's explicit scope.

The hosted stack is offline while billing is disabled. The budget is INR3,120 with an INR2,960 billing-disconnect guard; delayed reporting prevents an exact instantaneous cap. Never restart stopped billing without owner authorization. Keep provider credentials, rider data and raw rider media out of Git and routine telemetry.

## Repository discipline

Keep `main` as the baseline. Temporary branches use `codex/` and are removed after checked integration. Historical files stay in [archive/](archive/README.md) and Git; do not restore draft-then-verify, the review gate or other retired designs into the active tree.

Run `python tools/check_repository_structure.py` after navigation or layout changes, and the provider-free tests listed in [CI](.github/workflows/ci.yml) after runtime changes. On Windows, keep each file's line endings (`git ls-files --eol`); the release hashes exact bytes.
