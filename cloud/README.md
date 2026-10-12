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

Qdrant reloads immutable stored vectors; it does not parse or embed the manual on cold start. Recorded minimum-instance/startup settings remain historical configuration, not new changes. Frozen v10.6 native-count traces prove authenticated Qdrant concurrent with BM25 and conditional distinct-parent rank-disagreement reranking; [private readiness](../reports/public_evaluator/20261012/private_readiness_v10_6.json) passed with zero provider calls. Useful-answer quality and the changed candidate's acceptance remain pending.

The recorded lifetime allocation is INR2,700, with alerts at INR1,350/2,160/2,700 and billing disconnection at INR2,540. Treat receipts as snapshots, retain the guard and verify current state before operational changes. Never restart stopped billing without owner authorization.

The [latest model scope](../reports/public_evaluator/20261012/owner_model_scope_v1.json) limits rider questions to 100 words and permits complete applicable evidence above the former prompt cap. New v10.7 routes smaller complete draft requests to Gemma draft/Haiku verify and larger ones to Haiku draft/Gemma verify; the 8,192-token threshold routes without rejecting evidence. Haiku's selected role caches policy/source prefix for five minutes. Native windows and [actual Gemma throughput](../reports/public_evaluator/20261012/provider_quota_summary_v1.json) remain separate controls. Saved responses stream through a private API while a dedicated private task worker owns generation. Only the signed-cookie/proof frontend is intended for public access; all staging remains private. V10.6 CI/images/private readiness and actual retrievalv4 traces passed, but its old native-count limits failed with zero generation/reservations; no paid Q&A was submitted. Approved v10.7 retrieval/history/role repairs await final tests/freeze/builds/counts. Semantic projection is unimplemented. V10.3 cache proof, v10.4 private shell and six SYSTEM_ERROR cases remain unchanged. API `/v1/health` and gateway `/health` remain external readiness routes. [Current status](../docs/STATUS.md) preserves quality/public/rollback gates and the [v8 failure](../reports/grounded_generation/v8/REPORT.md).

The 11 October reset did not authorize operational changes. The later [public-evaluator scope](../reports/public_evaluator/20261012/owner_scope_v1.json), [credential approval](../reports/public_evaluator/20261012/owner_credential_scope_v1.json) and model scope authorize their exact deployment/validation/role changes. They preserve INR2,700/INR2,540 guards, disabled inference billing, existing provider allocations, disabled availability fallback and source-display restrictions. Use exact manifests, locked dependencies, image/provenance bindings and compatible revisions/rollback. Existing 100 attempts/999,200 reserved tokens and Haiku USD1 remain permanent; larger requests may exhaust capacity sooner than the historical twelve-turn ceiling. Unused/uncertain reservations are retained.
