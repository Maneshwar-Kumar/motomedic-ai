# Rider interface

The selected v10 frontend provides a public evaluator gateway around Streamlit. Signed cookies and a browser proof challenge lead to a private IAM-authenticated backend; provider keys stay server-side. The backend owns Qdrant/BM25 retrieval, conditional ranking, private Gemma drafting, distinct cached Haiku verification and durable response storage. The client displays truthful progress and exact saved text, with follow-up and recovery binding checks.

Current product and technical requirements: [PRD](../docs/PRD.md), [TRD](../docs/TRD.md), [architecture](../docs/ARCHITECTURE.md) and [TODO](../TODO.md).

## Connection

Backend configuration stays server-side: `MOTOMEDIC_RIDER_API_URL`, `MOTOMEDIC_RIDER_AUTH=cloud_run` and managed visitor-signing secret. Direct public mode uses `MOTOMEDIC_RIDER_ACCESS=public_gateway` and `MOTOMEDIC_EDGE_POLICY=gcp-public-cloud-run-cookie-v2`, with the exact configured Cloud Run host. Only the gateway listens publicly; Streamlit is loopback. Private visitor reservation requires the exact UI service identity and persistent proof/issuance quotas. No trusted client-IP claim or UI datastore grant is required. Provider keys never belong in browser fields. Engineering loopback must remain disabled in deployment; availability fallback stays disabled.

The UI, private API and dedicated worker must have compatible v10 policy, image, operation and response bindings. Production rejects v9/older JSON/SSE views before display or continuation. [Current status](../docs/STATUS.md) defines remaining hosted acceptance; [the v8 handover](../reports/grounded_generation/v8/ui_wiring/CONNECTION_HANDOVER.md) is historical only. The [owner scope](../reports/public_evaluator/20261012/owner_scope_v1.json) and [credential approval](../reports/public_evaluator/20261012/owner_credential_scope_v1.json) authorize this exact evaluator without changing source rights, budgets or billing.

Photo and voice remain disabled pending scoped evaluation. Display only supported paraphrases and authorized evidence/page metadata; never serve the PDF, excerpts or figure crops.

## Checks and release

Provider-free CI covers the client, stream decoder and progress/recovery behavior using software doubles. Real browser-to-hosted retrieval, supported/partial answering, Firestore persistence, worker lifetime and disconnect recovery remain release gates.

V10.3 hosted images and actual verifier cache reads succeeded, but its external `/healthz` preflight failed before questions/provider work. Current candidate v10.4 exposes gateway `/health` and authenticated API `/v1/health`; internal `/healthz` aliases remain. Complete its new exact-manifest builds, compatible UI/API/worker revisions, source-reviewed quality, persistent controls and exact rollback. Public-browser challenge/WebSocket, useful direct/partial answers, streamed follow-ups and disconnect recovery remain pending. The existing 100-slot provider allocation allows at most 12 eight-slot turns from a fresh ledger including validation; reservations persist without refund/reset, and Haiku retains its USD1 guard. The evaluator has bounded remaining capacity. [Current status](../docs/STATUS.md) preserves failed preflight and quality baselines separately.
