# Current work

Snapshot: 11 October 2026. Chat progress changes independently of this file; the organization monitor polls relevant chats and the folder.

| Chat | Work area | Durable entry point |
| --- | --- | --- |
| UI for MotoMedic | `rider_ui/`, `reports/rider_ui/`, Word TODO register | [UI README](../rider_ui/README.md), [API contract](../rider_ui/API_CONTRACT.md) |
| Waits are pretty high. why? | TRD v0.5, architecture decision note, hosted document renders | [TRD](../03_TRD.docx), [decision note](../03_TRD_Architecture_Decision_Note.docx) |
| MotoMedic A verification and warm instance costs | Existing A-output audit and read-only hosting cost investigation | [Continuation handoff](../TRD_UI_FOLLOWUP_HANDOFF.md) |
| Organize repository for humans | Navigation, contribution rules and folder checks | [Organization decision](REPOSITORY_ORGANIZATION.md) |

Other durable historical handoffs: [implementation progress](../IMPLEMENTATION_PROGRESS.md), [previous handoff](../NEXT_CHAT_HANDOFF.txt), [receipt](../NEXT_CHAT_HANDOFF_RECEIPT.json), [Gemma controller](../GEMMA_CONTROLLER_HANDOFF.md), [architecture rerun](../GEMMA26B_ARCHITECTURE_RERUN_HANDOFF.md).

Concurrent contributors should keep outputs inside their work area's folder, inspect current changes before editing shared files and stage only their own files. Do not rename or relocate an active chat's inputs while it is running.

Organization monitor: **Keep MotoMedic organized**, every 30 minutes while this work settles. It inspects folder placement and relevant chat snapshots, repairs safe navigation drift and reports protected-path conflicts. It pauses after the other chats finish and two clean checks.

## Monitoring update, 11 October 2026, 14:45 IST

The table above preserves the initial work snapshot; chat titles and task scope may change afterward.

- **UI for MotoMedic** completed its latest turn. Its durable [UI outcome and continuation](../rider_ui/CHAT_OUTCOME_20261011.md) now records decisions, checks and remaining integration work. Use that record and [TODO.md](../TODO.md) to resume the UI work.
- The A/B audit and hosting continuation is active. Its scope has moved beyond the original read-only investigation; this organization monitor does not change resources, billing or run authorization. New audit results are discoverable in [reports/a_semantic_audit_run_38126896735](../reports/a_semantic_audit_run_38126896735/).
- The earlier architecture-document chat was unavailable to polling in this pass. Its durable TRD, decision note and handoff remain linked above; unavailability is not proof of completion.

## Monitoring update, 11 October 2026, 15:12 IST

The active 30-case A/B evaluation now has a [local handover folder](../MotoMedic_AB30_20261011/README.md) and [run status](../MotoMedic_AB30_20261011/RUN_STATUS.json). Its README currently says preparation is complete and measured results remain pending. This is an owner-requested local export; retain its active paths.

The structure check flags `ab30_benchmark.py` and `test_ab30_benchmark.py` as new root files. They are referenced by `.github/workflows/ab30-benchmark.yml` and exact `reports/ab30_v2_review.json` bindings. They have not been relocated or added to the allowlist. Resolve their placement through a coordinated versioned migration after the active evaluation, preserving workflow commands and scoped review bindings.


## Monitoring update, 11 October 2026, 15:42 IST

The 30-case comparison and latest analysis turn are complete. The local export records COMPLETE_WITH_RECORDED_FAILURES; its previous preparation status above is historical. Start with the [completed comparison README](../MotoMedic_AB30_20261011/README.md), [accuracy, speed and spend report](../MotoMedic_AB30_20261011/ACCURACY_SPEED_SPEND.md), [recorded Arm A selection](../MotoMedic_AB30_20261011/ARM_A_SELECTION.md), [Arm A latency analysis](../MotoMedic_AB30_20261011/ARM_A_LATENCY.md), and [all delivered outputs](../MotoMedic_AB30_20261011/ALL_OUTPUTS.md).

The visible UI and evaluation chats are idle. The two benchmark root-path warnings remain unresolved: completed work still has exact review and workflow path consumers, so completion alone does not permit relocation. No allowlist change or release/runtime approval follows from this navigation update.


## Monitoring update, 11 October 2026, 16:12 IST

The Arm A continuation is active again. Its new [private initial-answer package guide](../cloud/arm_a/README.md), [local production handover](../MotoMedic_ArmA_Production_20261011/README.md) and [implementation receipt](../reports/arm_a/implementation_receipt_v1.json) are now available. The receipt records IMPLEMENTED_NOT_DEPLOYED_IAM_APPROVAL_PENDING and an initial-only 30-lookup scope. These are preparation records, not proof of the full rider UI API or live deployment. Leave the approval request in its owning chat.

The new runtime and evidence work is grouped under cloud/arm_a/ and reports/arm_a/. The local production handover stays in its active, version-bound location. The two previously flagged benchmark root paths remain unchanged.


## Monitoring update, 11 October 2026, 17:12 IST

The visible Arm A continuation and UI chats are idle. New rollout and retention evidence is grouped in the [Arm A integration run guide](../reports/arm_a/integration_v1/README.md). That guide and its dated records supersede the earlier preparation-only snapshot for rollout status. The latest continuation reports completed dedicated-namespace retention work; use its records for exact scope and remaining acceptance limits. This organization pass does not certify the rollout or alter resources.

The integration run keeps its own README, reviews, test logs and deployment records together. The two previously reported benchmark root-path conflicts remain unchanged and require coordinated migration; no automatic allowlist exception was added.

## Owner decision: draft, verify, stream (11 October 2026)

The current open manual Q&A method is [draft, verify, stream](../docs/architecture/DRAFT_VERIFY_STREAM_DECISION_20261011.md). It supersedes exact-answer-only, catalogue/action allowlists and the no-online-verifier amendment. Implementation and test status are recorded in [the integration report](../reports/grounded_generation/draft_verify_stream_v1/README.md). Existing source restrictions, model and spending/deployment authorizations still apply. No public release follows from the decision.

