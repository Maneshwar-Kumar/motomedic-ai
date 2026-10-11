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

Qdrant reloads immutable stored vectors; it does not parse or embed the manual on cold start. The latest deployment receipt records min one/max one instance and startup CPU boost. The current answer path still needs to call that Qdrant service.

The recorded lifetime allocation is INR2,700, with alerts at INR1,350/2,160/2,700 and billing disconnection at INR2,540. Treat receipts as snapshots, retain the guard and verify current state before operational changes. Never restart stopped billing without owner authorization.

The candidate draft/verify runtime has failed real answer coverage. [The v8 evidence](../reports/grounded_generation/v8/REPORT.md) and [status](../docs/STATUS.md) explain its limits. Source approval, packaging preparation and historical deployed revisions do not approve this changed pipeline for live use.

No repository reset change deploys a service, activates Claude, transfers a secret or changes billing. Current build recipes are retained compatibility inputs; the next release must use explicit approved inputs and image bindings.
