# Arm A private production package

Arm A chooses the first exact reviewed wording for every eligible claim, validates
the full source-bound envelope twice and keeps warning, applicability, dependency
and citation gates. It performs zero answer-model calls and has no benchmark
allocation limiter, sleeps or fixed inter-request delay. Hybrid BGE M3 + BM25 and
the existing conditional cross-encoder reranking remain enabled.

POST `/v1/initial-answer/stream` emits one `verified_block` SSE event containing
the complete safe answer, then a `complete` event with citation metadata and trace.
Evidence validation and durable session/operation commits precede the first
technical event. Unsupported or failed operations emit no technical block.
This deterministic path measures time to first verified text, not model-token
TTFT. Streaming cannot remove retrieval or validation latency. Live HTTP timings
must be measured after deployment; benchmark subtraction is not an observed SLO.

This private API supports the 30 frozen initial LOOKUP selections. It requires
explicit record selection and confirmed selected Himalayan BS6 applicability.
It does not implement the rider UI API-v1, free-text intent inference, photos or
adaptive feedback. GET `/v1/initial-catalogue` returns its exact capability scope.
No raw PDF, excerpt, figure or crop delivery is exposed.

Required JSON: `record_id`, `bike_variant`, `confirmed_himalayan_bs6`,
`manual_checksum`, `index_id`. Optional `query` must exactly match the selected
reviewed query after case/whitespace normalization. A unique `Idempotency-Key`
of 16–100 letters, digits, underscores or hyphens is mandatory. Repeating an
identical completed operation returns the saved response without new retrieval.
Changed payloads return 409; uncertain operations return 202 until recovery.
GET `/v1/initial-operations/{key}` is owner-bound. IAM validation at Cloud Run is
mandatory: never deploy with unauthenticated access or disabled invoker checking.

Managed Firestore transactions retain session snapshots and operations for 24h;
sessions additionally expire after 30min idle. Configure TTL on `expires_at`
for arm_a_operations, arm_a_sessions, arm_a_usage and versions collection groups.
Application expiry is immediate even if physical TTL deletion is delayed.
Admission controls reject excess usage with 429 and never pace requests: owner
6/minute and 30/24h, shared 60/minute and 250/24h. Failed admitted requests count.
These are spend controls, separate from the removed benchmark wait limiter.

Build a fresh isolated context with `python tools/prepare_arm_a_release.py
build/arm-a-release-v1`. The context verifies all frozen source bindings and
copies the existing immutable vectors; hosted image build downloads pinned query
and reranker model assets. It never reparses or re-embeds the manual.

Proposed Cloud Run: `motomedic-arm-a`, us-central1, private, dedicated identity
`motomedic-arm-a@motomedic-ai-20261009.iam.gserviceaccount.com`, CPU2, memory8Gi,
min1/max1, concurrency1, timeout180s, startup CPU boost and request-based billing.
Keep the query/reranker worker warm to reduce first verified text latency; startup
CPU boost applies during startup, not to every request. Qdrant is already min1
with CPU boost. This worker reads the immutable index locally, so Qdrant can return
to min0 after the new service passes smoke tests without losing a warm query path.
Warm instances may restart; measure cold initialization separately.

At current us-central1 list rates, 2 CPU + 8Gi idle costs approximately US$2.16/day
(before free tier, tax, build/storage/network/active-request charges). US$20 covers
less than 9.3 days of idle alone; the existing project budget stop governs total
spend and is not an exact instantaneous cap. This is a bounded prototype rollout,
not a funded month of continuous service. Source: [Cloud Run pricing](https://cloud.google.com/run/pricing).

Deployment is pending the exact `roles/datastore.user` project IAM grant for the
dedicated identity. Automatic approval review rejected that persistent grant;
no production Arm A revision is live. No Firestore service-account alternative
may be used to bypass the rejection. The database and dedicated identity exist.

Before build/deploy, verify project billing remains enabled and the existing
INR2700 lifetime budget/INR2540 stop guard remains intact. Never re-enable a
stopped billing account without owner approval. Build and query spend use the
existing additionalUS$20 authorization. Keep IAM private and credentials out of
artifacts. After deployment verify SSE first verified text/completion, scoped
withholding, idempotent replay and durable storage with authenticated requests.
Rollback by disabling traffic/deleting only the new Arm A service; retain its
versioned image, source bindings and review record for recovery. Existing Qdrant
and the billing guard are separate services.
