# Retained evidence (archived)

This is the reports index as of the 25 October 2026 reorganization; see [archive/README.md](../README.md).

The current design is in [PRD](../../docs/PRD.md), [TRD](../../docs/TRD.md), [architecture](../../docs/ARCHITECTURE.md) and [TODO](../../docs/TODO.md).

| Record | Why retained |
| --- | --- |
| [Answer-quality evaluations](../../evals/README.md) | Stage replay, private hosted v10.15 candidate, Sonnet draft + verify, verifier-free release and the section answer path v3 that the runtime now uses (23–25 October 2026). |
| [Serving manifest v11](../../releases/serving_manifest_v11.json) | First frozen release of the section-template answer path, superseded by [v11.1](../../releases/serving_manifest_v11_1.json). |
| [Haiku continuation](public_evaluator/20261012/haiku_v10_12/continuation_scope_v1.json) | Historical v10.11–v10.13 continuation authority and verification of superseded v10.11 against its saved commit. |
| [Stopped handoff](handoff/20261012/SUMMARY.md) | Fresh-chat summary, ordered TODO, exact WIP/helper archive, access blocker and publication/validation receipts. |
| [Reset receipt](reset/20261011/README.md) | What was removed, what was preserved, recovery and validation. |
| [v9 implementation receipt](build/20261012/README.md) | Historical v9 code, frozen historical bytes and synthetic checks. |
| [v8 runtime/provider evidence](grounded_generation/v8/REPORT.md) | Exact runtime, failed real answer coverage, independent source adjudication and packaging preparation. |
| [Code review](code_review/20261011/README.md) | Concrete departures that informed the fresh specifications; dated before the reset. |
| [Source context](grounded_generation/source_context_v1/) | Pinned original-object context and source-specific safety authority. |
| [Additional source objects](grounded_generation/read_only_scopes_v1/) | Exact object approvals, not a rider-question allowlist. |
| [Structural context](grounded_generation/generic_source_v1/) | Approved required-context/dependency review. |
| [Prerequisite review](grounded_generation/prerequisite_review_v1/) | Original-source checks and retained bindings. |
| [Warm-instance/budget receipt](warm_instance_budget_20261011.json) | Existing authorized operating configuration. |

Exact retained receipts preserve their original bytes and original version meaning. Historical links or paths inside them can refer to files removed from the active tree; reconstruct that historical snapshot at commit 997a21e22625ec5b972a66f38df898e2f41315bb or the recovery bundle. They are evidence, not competing current specifications or commands to rerun paid experiments.

This folder is closed: new evaluations belong in `evals/<date>_<name>/` and new releases in `releases/`. Label synthetic checks, real provider measurements, original-page review and deployment separately. Do not convert workflow success or zero technical releases into answer accuracy.
