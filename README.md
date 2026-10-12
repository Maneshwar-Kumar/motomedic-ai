# MotoMedic AI

**Current work: Haiku-only v10.13 functional demonstration.** The [public UI](https://motomedic-rider-ui-279945185781.us-central1.run.app) is visible with answering enabled. An anonymous direct SUPPORTED answer was observed; partial/follow-up, USB and cache-read checks remain incomplete. The repository, supplied manual, immutable index release and service inspection are public. Read [current status](docs/STATUS.md) for actual results and [model scope3](reports/public_evaluator/20261012/owner_model_scope_v3.json) for the sole-model decision.

A manual-grounded question-answering assistant for the Royal Enfield New Himalayan 450. The selected source is the supplied **owner's manual**. The runtime privately drafts from retrieved evidence, separately verifies the finalized answer, saves it, then streams that exact verified text.

The owner authorized continuation of the [saved handoff](reports/handoff/20261012/SUMMARY.md). The latest [functional demonstration scope](reports/public_evaluator/20261012/public_review/owner_functional_acceptance_scope_v1.json) waives independent manual answer review for this demo. Immutable source admission and the separate verification of each exact finalized answer remain required. No independent factual acceptance is claimed.

Public answering is enabled by the [later direct owner instruction](reports/public_evaluator/20261012/public_review/owner_public_answer_enablement_scope_v1.json), before full six-case acceptance. [Routed UI health](reports/public_evaluator/20261012/haiku_v10_13_helpers/functional_ui_promotion_v2/enabled_health.json) passed for `motomedic-rider-ui-v10-13-functional-enabled`. The [anonymous browser](reports/public_evaluator/20261012/public_review/browser_enabled_v1/receipt.json) observed a 97-character SUPPORTED answer in 71.06 seconds with enabled input and all four progress stages; it did not capture incremental chunk rendering or session/operation identity. The separate [private direct audit](reports/public_evaluator/20261012/haiku_v10_13_runtime/direct_delivery_a77d_v1.json) proves exact-finalized verification and identical saved/stream/recovery. USB returned `PROVIDER_INCOMPLETE_OR_REFUSED` without a retained exact stop reason, four cases remain unrun and positive cache reads are unproven. Broader functional acceptance and merge remain pending; independent manual answer review was waived.

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

The owner selected pinned Haiku for private drafting and a separate finalized-response verification call, using distinct policies and schemas. Frozen v10.11 and the failed v10.12 live run remain history. V10.13 preserves complete literal evidence/history and binds citations to admitted source objects. [Current status](docs/STATUS.md) distinguishes functional checks, software validation and factual review.

Role-specific Haiku prompt-cache creation and reads are required. Photo, voice, compaction and optional refinements remain deferred. Availability fallback and whole-manual Claude are disabled. The owner's separate public-review approval authorizes publishing the supplied manual and index; credentials, rider data, historical charges and spending guards remain protected.

## Clone, fork and review

The repository and manual are public by the owner's latest review instruction. Start with [reviewer guide](docs/REVIEWER.md), [setup](docs/SETUP.md) and [architecture](docs/ARCHITECTURE.md). The current Haiku repair is on `codex/public-evaluator` in [PR #4](https://github.com/Maneshwar-Kumar/motomedic-ai/pull/4); main remains the baseline until accepted integration. [CI workflow](.github/workflows/ci.yml) and [runs](https://github.com/Maneshwar-Kumar/motomedic-ai/actions) are public. Public preview and service inspection do not establish answer-quality acceptance.

## Working checks

```sh
python tools/check_repository_structure.py
python human_review/agent_release_161/approval_consumer.py
```

[CONTRIBUTING.md](CONTRIBUTING.md) explains placement and checks. [AGENTS.md](AGENTS.md) records the working constraints. Builds, ingestion and real-provider evaluation run in the hosted environment. Existing source, access, provider, budget and deployment permissions continue to apply.
