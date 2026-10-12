# Working on MotoMedic

Start with [README](README.md), [PRD](docs/PRD.md), [TRD](docs/TRD.md), [architecture](docs/ARCHITECTURE.md) and [TODO](TODO.md). Keep one current specification. Reconcile it whenever a decision changes it.

Public answering is enabled by the [later direct owner instruction](reports/public_evaluator/20261012/public_review/owner_public_answer_enablement_scope_v1.json), before full six-case acceptance. [Routed UI health](reports/public_evaluator/20261012/haiku_v10_13_helpers/functional_ui_promotion_v2/enabled_health.json) passed for `motomedic-rider-ui-v10-13-functional-enabled`. The [anonymous browser](reports/public_evaluator/20261012/public_review/browser_enabled_v1/receipt.json) observed a 97-character SUPPORTED answer in 71.06 seconds with enabled input and all four progress stages; it did not capture incremental chunk rendering or session/operation identity. The separate [private direct audit](reports/public_evaluator/20261012/haiku_v10_13_runtime/direct_delivery_a77d_v1.json) proves exact-finalized verification and identical saved/stream/recovery. USB returned `PROVIDER_INCOMPLETE_OR_REFUSED` without a retained exact stop reason, four cases remain unrun and positive cache reads are unproven. Broader functional acceptance and merge remain pending; independent manual answer review was waived.

## Placement

- Current product and technical documentation: docs/.
- Answer pipeline: cloud/grounded_generation/; API/store compatibility: cloud/arm_a/.
- Rider presentation/client: rider_ui/.
- Maintenance and evaluation commands: tools/.
- New execution evidence: reports/<work-area>/<version-or-run>/.
- Exact source approvals: existing human_review/, grounding_bindings/ and pinned source-context paths. Preserve required bytes and paths.
- Generated environments, caches, index copies and temporary output: ignored build/ or tmp/. Keep credentials and raw rider media out of Git.

Retained root Python modules are compatibility dependencies. Replace consumers and create new versioned review bindings before moving or changing frozen objects.

## Change and verification

Keep the current public evaluator work on `codex/public-evaluator` and main as the preserved baseline until checked integration. Use short-lived codex/<change> branches for later work and focused commits. Do not restore superseded experiment branches or planning documents as the active design.

Run provider-free hosted CI and relevant contract tests. Source/content changes still require immutable index loading, exact approval validation and newly scoped source review. The [latest owner instruction](reports/public_evaluator/20261012/public_review/owner_functional_acceptance_scope_v1.json) waives independent manual answer review for the present functional demo; it does not waive immutable source admission or separate verification of the exact finalized response. Prove that the hosted agent retrieves and answers, with actual delivery/cache/operation evidence, without claiming independent factual acceptance. Real-provider work requires its recorded scope and persistent spending ledger; routine CI must not spend provider credits.

Before promotion, bind the source commit, runtime inputs, index generation/hash, exact source approvals, model/prompt policy and image digest. Record compatible backend/UI/worker revisions, rollback and the exact current functional acceptance scope. A successful build alone proves neither that the agent answers nor that its answers are factually correct. Preserve failed historical adjudications.

The [public-review permission](reports/public_evaluator/20261012/public_review/owner_public_review_scope_v1.json) authorizes the public existing repository/manual, paused UI preview and anonymous API/worker health plus read-only Qdrant. The [separate index-release approval](reports/public_evaluator/20261012/public_review/owner_index_release_scope_v1.json) authorizes the exact existing evidence/figure/vector/BM25 archive. Historical source/display manifests keep their bytes; source-content approval is unchanged. All other API/worker routes retain verified Google signatures, exact audiences, allowlisted verified service identities and existing visitor/Tasks/owner bindings. Keep keys, signing secrets, rider records and private drafts out of Git and public inspection.

The existing shared Haiku USD1, 100 attempts, INR2,700 lifetime and INR2,540 disconnect guard remain unchanged. The owner separately approved only a 2,000,000-token legacy ceiling; actual application/readback is tracked in [status](docs/STATUS.md), without refund/reset or another allocation. Never restart stopped billing implicitly. No optional refinement, photo, voice or compaction follows from the functional-demo scope.

## Recovering the reset

Older tracked files remain available in Git history. The ignored local recovery bundle also preserves pre-reset branch tips and uncommitted files. See [the reset receipt](reports/reset/20261011/README.md) before restoring anything. Restore only necessary objects into a new reviewed version.
