# Hosting and spending controls

| Area | Entry point |
| --- | --- |
| Recorded deployed resources | [deployment_status.json](deployment_status.json) |
| Backend live smoke results | [live_smoke.json](live_smoke.json) |
| Qdrant restoration service | [qdrant](qdrant/) |
| Project billing guard | [budget_guard](budget_guard/) |
| Vector export and smoke utilities | [export_qdrant.py](export_qdrant.py), [smoke_test.py](smoke_test.py) |

Deployment records are snapshots; check actual settings read-only before proposing changes. Qdrant restores immutable stored vectors on startup; it does not ingest/embed the PDF per rider request. The recorded service is authenticated and scales to zero.

The project limit is US$10 with an INR800 lifetime budget and INR640 automated billing stop. Reporting delay prevents an instantaneous cap. Do not re-enable stopped billing without owner authorization. The [warm-instance investigation handoff](../TRD_UI_FOLLOWUP_HANDOFF.md) authorizes research, not settings or billing changes.


## Arm A preparation

The [private initial-answer package](arm_a/README.md) is a separate work area. Its [preparation receipt](../reports/arm_a/implementation_receipt_v1.json) currently records implementation tested with deployment pending. See the [local handover](../MotoMedic_ArmA_Production_20261011/README.md). The package has a bounded initial-lookup scope; it is not yet the complete rider UI API. The organization monitor does not authorize IAM or resource changes.


For subsequent rollout and retention evidence, use the [Arm A integration run guide](../reports/arm_a/integration_v1/README.md). The earlier preparation receipt remains a dated historical snapshot; it is not the latest deployment status.
