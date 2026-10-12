# Reviewer access

The [repository](https://github.com/Maneshwar-Kumar/motomedic-ai) and supplied manual are public. Frozen v10.13 source [3b7da1692187736295fee7345e9b3e932d02b216](https://github.com/Maneshwar-Kumar/motomedic-ai/commit/3b7da1692187736295fee7345e9b3e932d02b216) passed [provider-free CI](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38233548200). The immutable-index release, public paused UI preview and anonymous API/worker/Qdrant inspection are available. The owner [waived independent manual answer review](../reports/public_evaluator/20261012/public_review/owner_functional_acceptance_scope_v1.json) for the present functional demo. Answer submission stays paused until the functional probe; no independent factual-quality acceptance is claimed. The approved 2,000,000-token ceiling was [applied atomically](../reports/public_evaluator/20261012/haiku_v10_13_helpers/operator_v2/hosted_runs/57f78b4b-1385-428b-8b90-fa31f134230b/application_receipt.json) without charge/counter reset.

Start with the [architecture](ARCHITECTURE.md), [actual results and failures](STATUS.md) and [clone/fork setup](SETUP.md). The [owner's public-review instruction](../reports/public_evaluator/20261012/public_review/owner_public_review_scope_v1.json) supersedes prior network/manual-display restrictions for this review while preserving credentials, charges and application authorization.

## Repository, manual, index and pipeline

| Resource | Link and scope |
| --- | --- |
| Public repository | [Maneshwar-Kumar/motomedic-ai](https://github.com/Maneshwar-Kumar/motomedic-ai), available to clone/fork. Current work is on `codex/public-evaluator`; `main` remains preserved. |
| Change under review | [Draft PR #4](https://github.com/Maneshwar-Kumar/motomedic-ai/pull/4). Check its actual head and CI before treating any receipt as current. |
| Supplied manual | [149-page Himalayan BS6 owner's manual](../royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf), SHA-256 `cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89`. Historical source/approval manifest bytes remain unchanged. |
| Immutable index export | [Release index-a3282c4d98cf54595e4ba168](https://github.com/Maneshwar-Kumar/motomedic-ai/releases/tag/index-a3282c4d98cf54595e4ba168), with [index_snapshot.tar.gz](https://github.com/Maneshwar-Kumar/motomedic-ai/releases/download/index-a3282c4d98cf54595e4ba168/index_snapshot.tar.gz). The uploaded asset and GitHub digest are recorded in the [publication readback](../reports/public_evaluator/20261012/public_review/index_release_readback_v1.json). SHA-256 `4248b6f21bede82375a2aceda2205ad8abb63a061abf18c30e9686cd82bba6bc`; use [SETUP](SETUP.md) to verify it. |
| Complete CI definition | [Provider-free contract checks](../.github/workflows/ci.yml), including runtime, source, store, admission, delivery and UI tests. |
| Public pipeline page | [Actions workflow](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/workflows/ci.yml). |
| Frozen v10.13 CI | [Run 38233548200: success](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38233548200), for the exact source commit above. |
| Historical CI | [v10.12 run 38223614708](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38223614708). Its live answer review subsequently failed; this is not v10.13 quality evidence. |

The frozen [v10.13 manifest](../reports/public_evaluator/20261012/serving_manifest_v10_13.json) has SHA-256 `3d1d01d09c1929a8c1e52e698a3b4ca9b48c14a14954b82f7d6c795ab6bf031c` and binds 561 input files. Public index export copies the existing immutable bytes; it does not create a new index or approve new answers.

## Anonymous service inspection

The anonymous [API](../reports/public_evaluator/20261012/haiku_v10_13_helpers/public_core_inspection_v3/anonymous_motomedic-arm-a.json), [worker](../reports/public_evaluator/20261012/haiku_v10_13_helpers/public_core_inspection_v3/anonymous_motomedic-answer-worker.json) and [Qdrant](../reports/public_evaluator/20261012/haiku_v10_13_helpers/public_core_inspection_v3/anonymous_motomedic-qdrant.json) readbacks passed. No Google account or platform IAM grant is needed for these read-only routes. The [public browser](../reports/public_evaluator/20261012/public_review/browser_preview_v1/public/receipt.json) passed the paused UI shell; answering remains pending. A read-only cold-start health timeout was retried without any paid-call replay.

| Service | URL | Read-only purpose |
| --- | --- | --- |
| Rider UI | [MotoMedic preview](https://motomedic-rider-ui-279945185781.us-central1.run.app) | Anonymous browser entry with answering paused. `/health` checks gateway readiness. |
| API | [API health](https://motomedic-arm-a-279945185781.us-central1.run.app/v1/health) | Anonymous GET reports source/index/runtime/model/dispatch identities. |
| Worker | [Worker health](https://motomedic-answer-worker-279945185781.us-central1.run.app/v1/health) | Anonymous GET reports the worker's runtime/model identities and readiness. |
| Qdrant | [Qdrant health](https://motomedic-qdrant-279945185781.us-central1.run.app/health), [query endpoint](https://motomedic-qdrant-279945185781.us-central1.run.app/query) | Health reports immutable source/index and point count. Query requires POST with a 1,024-value numeric vector, exact source/index IDs and a limit from 1 to 20. No native dashboard or `/collections` management route is exposed. |

PowerShell health checks need no token:

```powershell
Invoke-RestMethod -Uri 'https://motomedic-arm-a-279945185781.us-central1.run.app/v1/health'
Invoke-RestMethod -Uri 'https://motomedic-answer-worker-279945185781.us-central1.run.app/v1/health'
Invoke-RestMethod -Uri 'https://motomedic-qdrant-279945185781.us-central1.run.app/health'
```

Opening a browser link to `/query` performs GET and does not run a vector query. Query search is read-only and does not call Haiku. It is separate from full RAG answer acceptance.

## Authentication behind public inspection

Every API/worker route except anonymous GET `/v1/health` retains cryptographic Google signature validation, exact service audience and an allowlisted verified service-account email before application authorization. A personal Google login, arbitrary signed identity, forged JWT, visitor cookie or Cloud Tasks header alone cannot authorize these requests. See the frozen [inspection-auth implementation](../cloud/arm_a/public_inspection_auth.py) and [route guard](../cloud/arm_a/app.py).

The UI calls the API with its managed identity and the owned signed visitor capability. Visitor issuance requires the exact UI identity; worker execution requires the exact Tasks caller/audience. Session/operation recovery remains owner-bound. The public preview does not grant job submission, paid generation, rider-state or private-draft access.

Production service identities use audience-bound tokens as documented by [Google Cloud developer authentication](https://docs.cloud.google.com/run/docs/authenticating/developers) and [identity-token tooling](https://docs.cloud.google.com/sdk/gcloud/reference/auth/print-identity-token). Credentials and signing secrets stay server-side. A Qdrant management key, if separately supplied for another environment, stays private; this wrapper exposes only read-only health/query and does not expose a management key.

## Assess the evidence

For the present demo, inspect functional evidence that questions reach the deployed agent, real retrieval runs and answers return through separate finalized-response verification. The owner explicitly waived independent manual answer comparison; do not treat the functional receipt or a model verdict as independent factual acceptance. Immutable source/context approval and runtime source/binding checks remain required. Current role-specific cache creation/read tokens must come from hosted usage; a configured cache or prior-model receipt is insufficient.

For delivery, compare finalized, saved, streamed and recovered answer hashes, disconnect recovery, completed replay and wrong-owner rejection. Check exact image/revision/configuration and candidate/rollback/restore health. Native-count receipts, provider-free tests and successful container builds each establish narrower facts; they do not establish factual correctness or public answer acceptance.

All historical reservations remain charged. The shared Haiku USD1, 100 attempts, INR2,700 lifetime and INR2,540 disconnect guard remain in force. A new cookie, session, fork, service revision or day cannot refill this deployment's allocation. The exact measured owner-approved 2,000,000-token grant is now applied; it changes only that ceiling and preserves all historical usage. Reviewer access does not restart billing, reset budgets or create another allocation.
