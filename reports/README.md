# Results and validation records

Reports are evidence snapshots. A passing report applies to its named source, runtime, scope and run; it does not establish a public release or a newer runtime's approval.

| Question | Start with |
| --- | --- |
| What happened in the latest architecture comparison? | [Run 38122505406](architecture_run_38122505406/), [timing analysis v4](architecture_timing_analysis_v4.json), [independent audit v4](architecture_result_independent_audit_v4.json) |
| Which source approval applies? | [161-case v3 root validation](../human_review/agent_release_161/root_validation_v3.json) |
| How did the bounded grounded text exit perform? | [Step 2 grounded exit v2](step2_grounded_exit_v2.json) |
| What does the rider UI look like? | [UI reports](rider_ui/) |
| Were the TRD and decision note rendered? | [TRD v0.5 render](trd_v05_render/) |
| What changed in folder organization? | [Organization records](repository_organization/) |

Existing flat versioned records remain in place because review and handoff files refer to them. For new work, use `reports/<work-area>/<version-or-run>/`, with a README linking inputs, raw results, review and interpretation. Keep failed runs; do not overwrite them with successful reruns. Never include secrets or raw rider media in routine reports.


The completed 30-case A/B comparison has an owner-requested [local handover README](../MotoMedic_AB30_20261011/README.md), [accuracy/speed/spend readout](../MotoMedic_AB30_20261011/ACCURACY_SPEED_SPEND.md) and [Arm A latency analysis](../MotoMedic_AB30_20261011/ARM_A_LATENCY.md). Its export and file manifest retain their original paths and bytes; copies of protocol/review records in that bundle are intentional handover packaging.


Arm A service preparation records are grouped in [reports/arm_a](arm_a/); start with the [implementation receipt](arm_a/implementation_receipt_v1.json) and [package guide](../cloud/arm_a/README.md). The current receipt distinguishes software checks from deployment and live HTTP acceptance.


Subsequent Arm A rollout, test and retention evidence is grouped under [integration_v1](arm_a/integration_v1/README.md). Read its dated records alongside the earlier preparation receipt; a completed rollout record does not widen source or rider-interface approval scopes.
