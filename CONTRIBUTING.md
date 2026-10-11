# Working on MotoMedic

Start with [README](README.md), [PRD](docs/PRD.md), [TRD](docs/TRD.md), [architecture](docs/ARCHITECTURE.md) and [TODO](TODO.md). Keep one current specification. Reconcile it whenever a decision changes it.

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

Use a short-lived codex/<change> branch for subsequent implementation. Keep commits focused, merge the checked result into main, and delete the finished branch. Do not restore superseded experiment branches or planning documents as the active design.

Run provider-free hosted CI and relevant contract tests. Source/retrieval changes also require immutable index loading, approval validation and independent original-page checks. Real-provider evaluation requires recorded scope and a persistent spending ledger; routine CI must not spend provider credits.

Before promotion, bind the source commit, runtime inputs, index generation/hash, exact source approvals, model/prompt policy and image digest. Record compatible backend/UI revisions and rollback. A successful build alone is not answer-quality acceptance.

Current rights prohibit rider-facing PDF, excerpts and figure crops. Keep provider credentials server-side and preserve the billing guard. A repository/design change does not authorize deploying, opening public access or restarting billing.

## Recovering the reset

Older tracked files remain available in Git history. The ignored local recovery bundle also preserves pre-reset branch tips and uncommitted files. See [the reset receipt](reports/reset/20261011/README.md) before restoring anything. Restore only necessary objects into a new reviewed version.
