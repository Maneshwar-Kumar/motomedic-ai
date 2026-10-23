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

The [latest model scope](../reports/public_evaluator/20261012/owner_model_scope_v3.json) selects only Haiku `claude-haiku-5-5`. Since the owner's 24 October decision it makes one generation call per turn, released by a deterministic gate; the deployed v10.14 code still drafts and verifies until a new version ships. Complete native counting, the five-minute policy/evidence cache and the shared existing USD1 ledger remain required. Rider questions are limited to 100 words; complete applicable evidence is preserved without the former assembled cap. Native windows, throughput and lifetime budgets are separate controls. A dedicated private task worker generates while the private API streams saved answers. Only the signed-cookie/proof frontend may open publicly after current acceptance. API `/v1/health` and gateway `/health` remain external readiness routes. [Current status](../docs/STATUS.md) preserves useful-answer, cache, recovery, rollback and browser gates, together with historical failures.

The 11 October reset did not authorize operational changes. The later [public-evaluator scope](../reports/public_evaluator/20261012/owner_scope_v1.json), [credential approval](../reports/public_evaluator/20261012/owner_credential_scope_v1.json) and model scope authorize their exact deployment/validation/role changes. They preserve INR2,700/INR2,540 guards, disabled inference billing, existing provider allocations, disabled availability fallback and source-display restrictions. Use exact manifests, locked dependencies, image/provenance bindings and compatible revisions/rollback. Existing 100 attempts/999,200 reserved tokens and Haiku USD1 remain permanent; larger requests may exhaust capacity sooner than the historical twelve-turn ceiling. Unused/uncertain reservations are retained.
