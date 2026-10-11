# Hosted components

Follow the current [TRD](../docs/TRD.md) and [TODO](../TODO.md).

| Area | Location |
| --- | --- |
| Candidate Qdrant restoration service | [qdrant/](qdrant/) |
| Billing stop guard | [budget_guard/](budget_guard/) |
| Recorded deployed resources | [deployment_status.json](deployment_status.json) |
| Retrieval-only smoke results | [live_smoke.json](live_smoke.json) |
| Current candidate answer pipeline | [grounded_generation/](grounded_generation/) |
| API, store and compatibility imports | [arm_a/](arm_a/) |

Qdrant reloads immutable stored vectors; it does not parse or embed the manual on cold start. Recorded minimum-instance/startup settings remain historical configuration, not new changes. V10 code calls authenticated Qdrant concurrently with BM25 and conditionally reranks distinct-parent rank disagreement. Hosted RPC/readiness and answer-quality acceptance remain pending.

The recorded lifetime allocation is INR2,700, with alerts at INR1,350/2,160/2,700 and billing disconnection at INR2,540. Treat receipts as snapshots, retain the guard and verify current state before operational changes. Never restart stopped billing without owner authorization.

The selected v10 evaluator uses Gemma drafting and a distinct Claude Haiku verifier with five-minute policy/source-prefix caching; saved responses stream through a private API while a dedicated private task worker owns generation. Only the signed-cookie/proof frontend is public. Backend, worker and Qdrant stay IAM-protected. V10.3 hosted images and cache-write/read proof succeeded, but its reserved `/healthz` preflight failed before questions/provider work. Current candidate v10.4 uses authenticated API `/v1/health` and gateway `/health`, retaining internal probe aliases, and awaits new builds/acceptance. [Current status](../docs/STATUS.md) preserves pending quality/browser/rollback gates. [V8 evidence](../reports/grounded_generation/v8/REPORT.md) preserves zero technical releases and 0/4 answerable/partial turns; historical builds and source approvals do not prove the changed pipeline's quality.

The 11 October reset did not authorize operational changes. The later [public-evaluator scope](../reports/public_evaluator/20261012/owner_scope_v1.json) and [credential approval](../reports/public_evaluator/20261012/owner_credential_scope_v1.json) authorize necessary frontend/private-service deployment, bounded validation and hosted managed-secret/identity setup. They preserve INR2,700/INR2,540 guards, disabled inference billing, existing provider allocations, disabled availability fallback and source-display restrictions. Use exact manifests, locked dependencies, image/provenance bindings and compatible revisions/rollback. The existing 100 slots allow at most 12 conservative turns from a fresh ledger including validation; unused/uncertain reservations are retained and paid Haiku uses the unchanged USD1 guard.
