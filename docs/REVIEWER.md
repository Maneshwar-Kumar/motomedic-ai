# Reviewer access

Start with the [architecture](ARCHITECTURE.md), [current results and failures](STATUS.md) and [setup guide](SETUP.md). The owner has authorized public repository/manual access, an anonymous UI preview and anonymous read-only service inspection. Publication/readback is in progress on 12 October 2026. Answer submission is paused in the preview while v10.13 source/answer checks finish; no successful public text demonstration or v10.13 answer-quality acceptance is claimed yet.

## Repository, manual and pipeline

| Resource | Link and scope |
| --- | --- |
| Repository | [Maneshwar-Kumar/motomedic-ai](https://github.com/Maneshwar-Kumar/motomedic-ai); current work is on `codex/public-evaluator`, with `main` preserved. Public visibility is pending its credential/history scan and owner-authorized publication. |
| Change under review | [Draft PR #4](https://github.com/Maneshwar-Kumar/motomedic-ai/pull/4). Check its actual head and CI before treating any receipt as current. |
| Supplied manual | [149-page Himalayan BS6 owner's manual](../royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf), SHA-256 `cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89`. Public inspection is newly owner-authorized; historical manifest bytes remain unchanged. |
| Complete CI definition | [Provider-free contract checks](../.github/workflows/ci.yml), including runtime, source, store, admission, delivery and UI tests. |
| Public pipeline page | [Actions workflow](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/workflows/ci.yml); repository publication makes this pipeline inspectable without credentials. |
| Historical successful CI | [v10.12 run 38223614708](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38223614708). Its live answer review subsequently failed; this is not v10.13 quality evidence. |

## Service endpoints

These are the recorded service origins. A service URL alone does not establish anonymous access, the currently routed revision or answer-quality acceptance. The final publication receipt must bind anonymous readback to the exact UI image/revision and state.

| Service | URL | Access and useful check |
| --- | --- | --- |
| Rider UI | [MotoMedic preview](https://motomedic-rider-ui-279945185781.us-central1.run.app) | Intended anonymous browser entry. Public opening/readback pending; answer submission paused until current checks pass. `/health` checks gateway readiness. |
| API | [Private API health](https://motomedic-arm-a-279945185781.us-central1.run.app/v1/health) | Google Cloud IAM required. Reports source/index/runtime/model/dispatch identities. `/v1/catalogue` reports open-question capability. |
| Worker | [Private worker health](https://motomedic-answer-worker-279945185781.us-central1.run.app/v1/health) | Google Cloud IAM required. Execution additionally accepts only the exact Cloud Tasks caller and audience. |
| Qdrant | [Private Qdrant health](https://motomedic-qdrant-279945185781.us-central1.run.app/health) | Google Cloud IAM required. `/query` accepts a bounded vector and exact source/index IDs. Native `/collections` and dashboard routes are not exposed by this wrapper. |

The newly authorized public inspection route will be linked here after its implementation and anonymous readback are recorded. It should expose a fixed read-only view of service/version/health and release evidence through the public gateway while preserving raw backend/worker/Qdrant IAM. It must not relay arbitrary paths or URLs, execute tasks, expose secret payloads, display private drafts or reveal rider state. Inspection of a service is separate from paid answer generation.

## Optional authenticated engineering inspection

Anonymous reviewers need no Google account for the published repository, manual, UI preview or safe public inspection. A reviewer who also receives a scoped IAM grant may inspect raw service health with their own Google identity. An IAM grant is not assumed or created by this guide. Cloud Run invocation requires `run.routes.invoke`, provided by a service-scoped `roles/run.invoker` grant; configuration viewing is a separate permission. See [Google's Cloud Run roles](https://docs.cloud.google.com/run/docs/reference/iam/roles).

With the Google Cloud CLI installed and the exact account granted access, use PowerShell:

```powershell
gcloud auth login REVIEWER_GOOGLE_ACCOUNT
gcloud config set project motomedic-ai-20261009
$motomedicIdentityToken = gcloud auth print-identity-token
$motomedicHeaders = @{ Authorization = "Bearer $motomedicIdentityToken" }
Invoke-RestMethod -Uri 'https://motomedic-arm-a-279945185781.us-central1.run.app/v1/health' -Headers $motomedicHeaders
Invoke-RestMethod -Uri 'https://motomedic-answer-worker-279945185781.us-central1.run.app/v1/health' -Headers $motomedicHeaders
Invoke-RestMethod -Uri 'https://motomedic-qdrant-279945185781.us-central1.run.app/health' -Headers $motomedicHeaders
Remove-Variable motomedicIdentityToken, motomedicHeaders
```

Google documents user CLI identity tokens for development invocation. Production service-to-service requests use audience-bound managed service-account tokens. Keep tokens out of logs, screenshots, shell transcripts and Git. See [developer authentication](https://docs.cloud.google.com/run/docs/authenticating/developers) and [print-identity-token](https://docs.cloud.google.com/sdk/gcloud/reference/auth/print-identity-token).

IAM invocation preserves application authorization: API mutations/recovery still require the owned signed visitor capability, visitor issuance requires the exact UI identity, and `/internal/operations/run` requires exact task OIDC. The public UI uses these identities server-side. Do not bypass them to test an endpoint. A separate Qdrant management key, if privately supplied for another environment, is never committed; this deployed wrapper uses Cloud Run IAM and does not require or expose such a key.

## Assess the evidence

Review the original manual page and exact cited object for every technical claim, including units, conditions and warnings. Inspect useful direct, partial and follow-up answers independently of retrieval relevance and model-verifier success. Current role-specific cache creation/read tokens must come from hosted usage; a configured cache or prior model receipt is insufficient.

For delivery, compare finalized, saved, streamed and recovered answer hashes, disconnect recovery, completed replay and wrong-owner rejection. Check exact image/revision/configuration and candidate/rollback/restore health. Native-count receipts, provider-free tests and successful container builds each establish narrower facts; they do not establish factual correctness or public answer acceptance.

All historic reservations remain charged. The existing shared Haiku USD1, 100 attempts, INR2,700 lifetime and INR2,540 disconnect guard remain in force. A new cookie, session, fork, service revision or day cannot refill this deployment's provider allocation. The dormant token-ceiling mechanism requires separate exact measured owner approval. No reviewer action implies billing restart, budget reset or another allocation.
