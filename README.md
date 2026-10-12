# MotoMedic AI

**Current work: Haiku-only v10.13 repair.** V10.12 passed software, hosted build, counts and rollback checks, but its live answer review failed: one incorrect claim-to-object citation and one invalid draft. UI remains private. V10.13 will preserve complete literal evidence/history, constrain original source IDs and strengthen exact-object verification. Read [model scope3](reports/public_evaluator/20261012/owner_model_scope_v3.json).

A manual-grounded question-answering assistant for the Royal Enfield New Himalayan 450. The selected source is the supplied **owner's manual**. The runtime privately drafts from retrieved evidence, separately verifies the finalized answer, saves it, then streams that exact verified text.

The owner stopped this build for a fresh-chat handoff. Start with the [handoff summary](reports/handoff/20261012/SUMMARY.md) and [ordered continuation TODO](reports/handoff/20261012/TODO.md). The saved work is unfinished; the UI is private and the Haiku-only migration remains pending.

## Read these four documents

| Document | Purpose |
| --- | --- |
| [PRD](docs/PRD.md) | Product scope, rider behavior and acceptance criteria. |
| [TRD](docs/TRD.md) | Component, evidence, retrieval, provider and delivery contracts. |
| [Architecture diagram](docs/ARCHITECTURE.md) | Versioned ingestion and the online answer pipeline. |
| [TODO](TODO.md) | Ordered delivery steps, paired concurrent work and completion evidence. |

These Markdown documents are the current design baseline. Superseded Word drafts, experiments and handoffs remain in Git history.

## What is present

| Area | Location |
| --- | --- |
| Hosted ingestion and hybrid retrieval | online_ingest.py, online_retrieve.py, retrieval_policy.py |
| Drafting, separate verification and delivery | cloud/grounded_generation/ |
| API, durable state and compatibility dependencies | cloud/arm_a/ and retained root modules |
| Rider interface | [rider_ui/README.md](rider_ui/README.md) |
| Qdrant, infrastructure and billing guard | [cloud/README.md](cloud/README.md) |
| Manual identity and display restrictions | [source_manifest.json](source_manifest.json) |
| Exact source approval authority | [human_review/agent_release_161/README.md](human_review/agent_release_161/README.md) |
| Retained evidence and cleanup receipt | [reports/README.md](reports/README.md) |

Some compatibility modules implement earlier methods because current imports and exact approval bindings still need them. Their presence does not select those methods for ordinary Q&A. Future changes follow the fresh TRD; remove a dependency only after replacing and verifying its consumers.

## Current acceptance

The selected index `index_a3282c4d98cf54595e4ba168` has 532 BGE M3 chunks, 277 parents and BM25. Runtime retrieval uses authenticated Qdrant concurrently with BM25, RRF and conditional reranking. Accepted answers require separate model verification and exact saved-buffer streaming.

The owner selected Haiku only for drafting and separate finalized-response verification. Frozen v10.11 and the failed v10.12 live run remain history. The v10.13 repair preserves complete literal evidence and history and binds citations to admitted source objects. UI remains private until current acceptance passes. [Current status](docs/STATUS.md) preserves results and failures.

Haiku policy/evidence-prefix caching is required; primary caching optimization, photo and voice are deferred. The availability fallback and whole-manual Claude route remain disabled. Existing source-display restrictions and spending guards stay in force.

## Clone, fork and review

The repository and manual are public by the owner's latest review instruction. Start with [reviewer guide](docs/REVIEWER.md), [setup](docs/SETUP.md) and [architecture](docs/ARCHITECTURE.md). The current Haiku repair is on `codex/public-evaluator` in [PR #4](https://github.com/Maneshwar-Kumar/motomedic-ai/pull/4); main remains the baseline until accepted integration. [CI workflow](.github/workflows/ci.yml) and [runs](https://github.com/Maneshwar-Kumar/motomedic-ai/actions) are public. Public preview and service inspection do not establish answer-quality acceptance.

## Working checks

```sh
python tools/check_repository_structure.py
python human_review/agent_release_161/approval_consumer.py
```

[CONTRIBUTING.md](CONTRIBUTING.md) explains placement and checks. [AGENTS.md](AGENTS.md) records the working constraints. Builds, ingestion and real-provider evaluation run in the hosted environment. Existing source, access, provider, budget and deployment permissions continue to apply.
