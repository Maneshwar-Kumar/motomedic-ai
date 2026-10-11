# MotoMedic AI

A manual-grounded question-answering assistant for the Royal Enfield New Himalayan 450. The selected source is the supplied **owner's manual**. The runtime privately drafts from retrieved evidence, separately verifies the finalized answer, saves it, then streams that exact verified text.

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

The candidate index exists: index_a3282c4d98cf54595e4ba168, with 532 BGE M3 search chunks, 277 parents and BM25. The current answer runtime still bypasses Qdrant for dense search, misses conditional retrieval scheduling for ordinary Q&A, can exceed input limits, and needs durable worker completion.

The last real Haiku validation released **zero technical answers** and answered **0 of 4** clearly answerable or partially answerable turns. Passing software checks establish boundaries, not answer coverage or deployed release acceptance. [Current status](docs/STATUS.md) and the [v8 report](reports/grounded_generation/v8/REPORT.md) explain the remaining work.

Claude is an optional retrieved-evidence availability fallback, disabled by default. The full-manual Claude alternative is retired. Prompt caching has no demonstrated support for the current exact primary configuration. Photo and voice follow text acceptance.

## Working checks

```sh
python tools/check_repository_structure.py
python human_review/agent_release_161/approval_consumer.py
```

[CONTRIBUTING.md](CONTRIBUTING.md) explains placement and checks. [AGENTS.md](AGENTS.md) records the working constraints. Builds, ingestion and real-provider evaluation run in the hosted environment. Existing source, access, provider, budget and deployment permissions continue to apply.
