# Contributing to MotoMedic

Read [the human starting guide](docs/START_HERE.md), [folder contract](docs/REPOSITORY_ORGANIZATION.md) and [AGENTS.md](AGENTS.md) before changing behavior.

## Where to work

Keep new code, documents and results in their work area's folder. New reports belong in `reports/<work-area>/<version-or-run>/`; include a short README identifying the question, inputs/version, result and limitations. Existing root modules, tests, Word documents and handoffs are compatibility paths. Do not silently relocate them or edit frozen approval bundles.

## Concurrent work

Inspect `git status` and relevant chats before shared edits. Use `codex/` branches and reviewable diffs. Do not switch the shared checkout beneath another active chat, stage everything, reset others' edits or move another chat's active inputs. Stage only owned files. Read-only polling does not authorize messaging other chats.

## Review and validation

Run `python tools/check_repository_structure.py` after navigation or layout changes. Run the relevant existing subsystem checks for behavior changes; preserve manual checksums, evidence IDs, warnings, applicability, typed outcomes and five response states. Changed exact runtime/source objects require updated scoped review bindings. Preserve the owner-delegated v3 authority; do not invent human signoff.

Keep provider calls and ingestion hosted and versioned. Organization changes do not authorize deployment, provider spending, billing mutation or public manual redistribution. Do not commit credentials, raw rider media, environment files or temporary artifacts. No new license is assigned to the OEM manual or project through this organization work.
