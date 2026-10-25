# Pre-promotion operational inventory

Read-only metadata inspection on 12 October 2026 (local); final billing/ledger check around `2026-10-11T20:16:42Z`. This is a pre-promotion snapshot, not a deployment or quality-acceptance receipt. No service, IAM, queue, API, secret, provider or billing changes were executed by this inventory. Secret payloads and rider documents were not read. Human IAM members and unrelated project metadata are omitted.

## Billing and provider capacity

Authoritative `gcloud billing projects describe` reads returned:

| Project | Project number | Billing enabled |
| --- | --- | --- |
| `motomedic-ai-20261009` | `279945185781` | `true` |
| `motomedic-inference-20261009` | `528777303044` | **`false`** |

The existing budget guard remains `motomedic-budget-guard-00003-qax`: `SIMULATE=false`, `BUDGET_INR=2700`, `STOP_INR=2540`, display name `MotoMedic lifetime INR2700`. Its existing runtime identity has project billing-manager/browser/event-receiver permissions. This configuration is not an instantaneous cost report. **Keep the stopped inference project's billing disabled.**

Only these two global Firestore ledger documents were requested, with a whitelist of quota fields; both returned HTTP 404:

| Document in `arm_a_usage` | Existing configured non-recurring limit | Read result |
| --- | --- | --- |
| `grounded-primary-nonrecurring-v1` | 100 attempts / 999,200 reserved tokens | Absent; the current code will initialize its first reservation at zero |
| `owner-haiku-fallback-20261011-validation-v1` | USD 1.00 maximum reservation | Absent; the current code will initialize its first reservation at zero |

Before subsequent reservations, this gives 100 primary attempt slots, enough for at most 12 eight-attempt primary turns (96 slots). An authorized fallback turn reserves 12 slots instead. Reservations survive uncertain transport and are never refunded or reopened automatically. An absent new ledger does not erase historical provider charges or authorize replay of prior calls.

## Existing services and identities

All four services are in `us-central1`, with ingress `all` and IAM protection at this snapshot. None of the inspected backend, Qdrant or UI policies grants `allUsers` or `allAuthenticatedUsers`.

| Service | Ready revision | Identity | CPU / memory | Request settings |
| --- | --- | --- | --- | --- |
| `motomedic-arm-a` | `motomedic-arm-a-00003-gs2` | `motomedic-arm-a@motomedic-ai-20261009.iam.gserviceaccount.com` | 2 / 8 GiB | min/max 1, concurrency 1, timeout 180 s, startup boost |
| `motomedic-qdrant` | `motomedic-qdrant-00003-cjb` | `motomedic-qdrant@motomedic-ai-20261009.iam.gserviceaccount.com` | 1 / 512 MiB | min/max 1, concurrency 8, timeout 30 s, startup boost |
| `motomedic-rider-ui` | `motomedic-rider-ui-00001-wg9` | `motomedic-rider-ui@motomedic-ai-20261009.iam.gserviceaccount.com` | 1 / 512 MiB | concurrency 4, timeout 300 s, startup boost; no recorded minimum |
| `motomedic-budget-guard` | `motomedic-budget-guard-00003-qax` | `motomedic-budget-guard@motomedic-ai-20261009.iam.gserviceaccount.com` | 0.1666 / 256 MiB | max 1 revision setting, concurrency 1, timeout 60 s |

Observed deployed images:

```text
backend: us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/arm-a@sha256:9d92653a7984cea1a21f132752d961dbd1eb79140380d6d30773ea5ae3cf0969
qdrant:  us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/qdrant@sha256:e2ad5afa1977a66c6a7185d93810dc5cf73318cde7122dfe3327b34bb343be37
ui:      us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/rider-ui@sha256:1776769d01193a1c2522fb745e5adcd10063756fa6e3d0c1da96cff8d06ba202
```

The backend service grants `roles/run.invoker` to the UI identity. Qdrant has no service-account invoker binding and the backend has no project-level invoker role. The backend has project `roles/datastore.user`. The UI has no datastore role. The index bucket grants `roles/storage.objectViewer` to Qdrant only; the backend has no inherited project storage grant. No task-specific service account existed among the seven inspected accounts. Existing default compute/App Engine editor roles were observed; this inventory does not propose expanding or changing them.

## Tasks, Firestore and secrets

Cloud Tasks API `cloudtasks.googleapis.com` is **disabled**. Queue listing returned `SERVICE_DISABLED`; the enable prompt was not accepted. No functioning queue inventory can be asserted while the API is disabled.

Firestore `(default)` exists in `us-central1`, native mode, pessimistic concurrency, delete protection disabled. `expires_at` TTL is ACTIVE for `arm_a_operations`, `arm_a_sessions`, `arm_a_session_versions` and `arm_a_usage`. No TTL policy was listed for the new `arm_a_session_operations` collection group. The non-expiring provider budget documents deliberately omit `expires_at`; keep them outside automatic budget resets. Existing version-subcollection TTL is independent of session-head deletion, as [Firestore TTL deletion does not delete subcollections](https://firebase.google.com/docs/firestore/ttl).

| Managed secret | Version | State | Existing access |
| --- | --- | --- | --- |
| `motomedic-rider-visitor-v1` | 1 | ENABLED | Backend and UI: secret accessor |
| `motomedic-gemini-serving-v1` | 1 | ENABLED | Backend: secret accessor; retired secret-loader: version adder |

The running backend binds only `MOTOMEDIC_VISITOR_SECRET` to visitor version 1; it has no Gemini or durable-dispatch environment binding. The running UI has `MOTOMEDIC_RIDER_AUTH`, `MOTOMEDIC_RIDER_API_URL` and the same visitor secret reference. No managed Anthropic secret exists in this main-project inventory.

The existing GitHub repository has `ANTHROPIC_API_KEY` (metadata updated `2026-10-10T20:13:50Z`) and `MOTOMEDIC_GEMINI_API_KEY` (`2026-10-09T13:29:44Z`). Names/timestamps only were read. They provide an existing hosted key route; copying a value into a managed secret and changing a scoped federation condition require their own operational receipt. The retired disabled secret-loader pool was not changed here.

## Minimum promotion changes and operational gaps

The coordinator owns subsequent deployment and IAM decisions. The following gaps are concrete consequences of the inspected resources and current runtime:

1. Enable Cloud Tasks under the newly authorized hosting scope; create one named `us-central1` queue with `maxConcurrentDispatches=1`, a bounded retry policy and dispatch deadline compatible with the 1,200-second durable deadline. Concurrent tasks would contend with the current composer pipeline lock. See [queue rate/concurrency controls](https://docs.cloud.google.com/tasks/docs/configuring-queues).
2. Give the backend queue-scoped `roles/cloudtasks.enqueuer`, and permission to act as a dedicated same-project task caller. Give only that caller `roles/run.invoker` on the private worker target. Confirm the automatically created Tasks service agent has `roles/cloudtasks.serviceAgent` and the required account-level Service Account User binding on the task caller. Exact OIDC audience must equal the worker service origin, and worker URL must end `/internal/operations/run`. See [HTTP task authentication and service-account setup](https://docs.cloud.google.com/tasks/docs/creating-http-target-tasks).
3. Bind `MOTOMEDIC_TASK_QUEUE`, `MOTOMEDIC_TASK_WORKER_URL`, `MOTOMEDIC_TASK_SERVICE_ACCOUNT`, and `MOTOMEDIC_GEMINI_API_KEY=motomedic-gemini-serving-v1:1` to the accepted backend revision. Give backend identity Qdrant-scoped invoker and exact-snapshot `storage.objects.get` access. Keep source generation/hash/inventory and the inherited local model assets pinned.
4. Use a 1,200-second worker/platform/server timeout. Preserve backend/Qdrant IAM protection and record an accepted compatible UI/backend revision pair. Ensure workers retain request capacity while browsers poll: SSE holds a request thread for up to 150 seconds, so a shared four-thread/four-concurrency service can be saturated by four browser streams before a task starts. A separate private worker service gives a clear capacity boundary; a shared service needs an explicit equivalent capacity guarantee.
5. For the coordinator's direct public Cloud Run UI mode, publish only the UI and retain its managed backend token. Browser authentication cannot use the existing private platform-subject path on an unauthenticated service. The new cookie/proof path needs backend-only visitor admission restricted to the exact UI identity; task callers must not issue visitors. Root's direct mode makes no trusted client-IP claim and requires no UI datastore role. Existing ALB-only source policy stays a separate mode. No forwarding rules/load balancer existed in the inspected main project.
6. Enforce persistent global visitor issuance (10/minute, 60/rolling day), spent-proof replay rejection and signed 24-hour cookies. Existing request limits remain 6 accepted turns/minute and 30/rolling day per visitor, 60/minute and 250/day globally, and 20/session. The non-recurring provider cap is substantially smaller than the visitor/request caps and will fail closed when exhausted. It is not reset by a new cookie, conversation, instance, revision or day. Native token-count requests happen before whole-turn capacity admission; generation capacity does not itself limit anonymous web/asset traffic.
7. Add `arm_a_session_operations.expires_at` TTL to cover the new lock records. Hosted smoke must prove Firestore transactions, wrong-owner recovery rejection, task OIDC rejection, exact committed response replay, concurrent/duplicate submission, disconnect recovery and short follow-up behavior. Software or resource metadata alone proves none of those live exits.

No billing restart, answer-cache shortcut, source-display expansion, fallback activation or additional provider allocation follows from this inventory.
