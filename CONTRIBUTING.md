# Working on MotoMedic

Start with [README](README.md), [PRD](docs/PRD.md), [TRD](docs/TRD.md), [architecture](docs/ARCHITECTURE.md), [status](docs/STATUS.md) and [TODO](TODO.md). Keep one current specification, and update it whenever a decision changes it.

## Placement

| What | Where |
| --- | --- |
| Product and technical documentation | `docs/` |
| Answer path: index, retrieval, assembly, template and gate, generation call, ledger, delivery | `cloud/grounded_generation/` |
| API, worker dispatch, store and app wiring | `cloud/arm_a/` |
| Rider UI and client | `rider_ui/` |
| Release and maintenance tools | `tools/` |
| New execution evidence | `reports/<work-area>/<version-or-run>/` |
| Evaluations | `reports/evals/<run>/` |
| Generated environments, caches, index copies and temporary output | ignored `build/` or `tmp/` |

Keep credentials and raw rider media out of Git. Root-level Python modules outside the serving import graph are historical tooling; do not add new ones.

## Change and verification

- **Branches.** Work on `codex/public-evaluator` or a short-lived `codex/<change>` branch, with focused commits. `main` stays the baseline until a checked integration. Do not restore draft-then-verify, the review gate or other retired designs; they are recoverable from Git history.
- **Tests.** After runtime changes, run the provider-free tests in [CI](.github/workflows/ci.yml). After navigation changes, run `python tools/check_repository_structure.py`.
- **Freezing.** A change to any serving input needs a new frozen manifest from [serving_release.py](tools/serving_release.py). Never edit a committed manifest to make a check pass.
- **Index.** A source, parser, sectioning or embedding change creates a new index ID; freeze it before serving.
- **Before promotion,** bind the source commit, image digest, index identity, compatible backend/UI/worker revisions and rollback. A successful build shows neither that the agent answers nor that its answers are correct.
- **Real-provider runs** need an explicit owner scope and the persistent ledger; routine CI never spends provider credits.
- **Evaluations** are labelled local, private or hosted. Held-out cases never enrich prompts or retrieval.

## Spending and access

These controls stay unchanged:
- the shared Haiku USD1 ledger;
- 100 attempts;
- the applied 2,000,000-token ceiling;
- the INR2,700 lifetime budget and the INR2,540 billing-disconnect guard.

There is no refund, reset or new allocation without the owner. Never restart stopped billing. Nothing in the repository authorizes deployment, public opening or GCP changes.
