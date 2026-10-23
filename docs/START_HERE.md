# Start here

**24 October 2026: the separate verifier has been removed from the design.** One Haiku generation call fills the answer template, and a deterministic release gate releases it. Deployed v10.14 still drafts and verifies, and the hosted stack is offline while billing is disabled. Read [STATUS](STATUS.md) and the [evaluations](../reports/evals/README.md) first. The paragraphs below are the earlier v10.13 handoff, kept for history.

**Earlier work: Haiku-only v10.13 repair.** V10.12 passed software, hosted build, counts and rollback checks, but its live answer review failed: one incorrect claim-to-object citation and one invalid draft. UI remains private. V10.13 will preserve complete literal evidence/history, constrain original source IDs and strengthen exact-object verification. Read [model scope3](../reports/public_evaluator/20261012/owner_model_scope_v3.json).

Read the preserved [handoff summary](../reports/handoff/20261012/SUMMARY.md) and [ordered continuation TODO](../reports/handoff/20261012/TODO.md) for history. V10.11 remains superseded and unbuilt. V10.12 failed live citation and draft validation. The v10.13 repair requires fresh hosted counts, source review and delivery acceptance; UI remains private until acceptance.

Read [PRD](PRD.md), [TRD](TRD.md), [architecture](ARCHITECTURE.md), [root TODO](../TODO.md), [AGENTS](../AGENTS.md) and [CONTRIBUTING](../CONTRIBUTING.md). [STATUS](STATUS.md) separates implementation, checks and acceptance; [reports](../reports/README.md) preserve exact evidence and failures.

Latest owner selection: **Haiku only**, `claude-haiku-5-5`, with one generation call per turn and the deterministic release gate. This supersedes different-model identity and the separate verifier; factual acceptance still needs independent original-source review. Do not continue Google access probes. Preserve 100-word inputs, complete evidence/history, private hybrid retrieval, conditional reranking, Haiku prefix caching, durable saved streaming and shared spending guards.

V10.10 CI/images/private readiness/native counts/private shell passed, but its evaluator launcher failed before questions. The served cloud remains that private release. V10.11 is only a preserved549-input snapshot with unfinished tests/helpers and no live quality acceptance. No source-review, workflow or metadata success creates a public-release claim.
