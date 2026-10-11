# Repository and design reset

Owner request began 11 October 2026; completion crossed midnight into 12 October IST. The clarified deliverables are fresh PRD, TRD, architecture diagram and sequenced TODO. Runtime repairs remain the subsequent implementation sequence.

## Current documents

- [PRD](../../../docs/PRD.md)
- [TRD](../../../docs/TRD.md)
- [Architecture diagram](../../../docs/ARCHITECTURE.md)
- [Sequenced TODO](../../../TODO.md)

## Cleanup and retention

[Removal manifest](removal_manifest.json) records 4,297 removed tracked/untracked active files. Old Word specifications, competing architecture experiments, duplicate generated reports, retired full-manual Claude code, obsolete review attempts, stale workflows and redundant handoffs were removed. Legacy prototype retrieval tests and their provisional index were removed together.

The source PDF/manifest, current ingestion/retrieval/generation/UI dependencies, deployed Qdrant and billing-guard infrastructure, required source approvals, current failure evidence and packaging inputs remain. All 64 v8 frozen files and 187 signed approval outputs retain their exact bytes. Some old modules are necessary compatibility imports; they do not select a retired answer method.

[Local cleanup](local_cleanup.json) records active-file removal. Old generated build directories were removed. Protected temporary dependency folders were moved into the ignored recovery area rather than left in the active tree; [the cache receipt](quarantined_caches.json) records their locations. The selected immutable development snapshot remains at `build/index-bge-final`. Only it and recovery material remain under `build/`.

The obsolete uncommitted exact-answer-cache additions in two compatibility modules were restored to the pre-reset committed version. Their bytes remain in the recovery snapshot. No current frozen runtime object or source authority was changed.

## Recovery

[Recovery receipt](recovery_receipt.json) records verified SHA-256 hashes for the complete pre-reset Git bundle and non-ignored file snapshot. They are local-only at `build/recovery/reset_20261011/`, preserving all branch tips and uncommitted work. Backups are ignored by Git and excluded from Docker build contexts. Historical tracked files also remain in Git history; no history rewrite is needed for the reset.

Original baseline: `997a21e22625ec5b972a66f38df898e2f41315bb`. Historical links inside unchanged evidence reports refer to that snapshot. The new Markdown specifications provide current navigation.

## Checks and operating boundary

The repository checker verifies current navigation, the PDF checksum, both pinned manifests, 64 runtime bindings and 187 approved outputs. Provider-free CI checks source approval, admission, provider adapters, fake managed state and UI streaming. Index-dependent semantic-composer tests and real quality/deployment remain separate gates. [Validation](validation.json) and [remote consolidation](remote_receipt.json) record completion. [Hosted CI](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38165030392) passed 17 approval and 86 synthetic contract tests, 103 total, without providers. The index-dependent composer suite is outside this hosted CI scope; local attempts were blocked by filesystem-inaccessible Flask installs and are not counted as passes.

The real v8 run still released zero technical answers and answered 0/4 answerable or partial questions. This cleanup does not repair source admission, token packing, Qdrant serving, conditional scheduling or durable worker lifetime. TODO records those next actions.

GitHub and local main now share the clean reset. Both superseded branches and PRs are closed. [Fifteen retired workflows](retired_workflows.json) were disabled; only current versioned ingestion and provider-free CI remain active. Required source history includes one original judge result retained for scoped quality provenance. The independent organization monitor has checked the new baseline and updated its existing references without restoring superseded files.

No provider call, model activation, source-display change, service deployment or GCP billing change was made by this reset.
