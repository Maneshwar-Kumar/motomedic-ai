# Working on MotoMedic

Start with the [README](README.md) and the [review guide](docs/REVIEW_GUIDE.md), then the [PRD](docs/PRD.md), [TRD](docs/TRD.md), [architecture](docs/ARCHITECTURE.md), [status](docs/STATUS.md) and [TODO](docs/TODO.md). Keep one current specification, and update it whenever a decision changes it. Record owner decisions in the [decision log](docs/DECISIONS.md).

## Placement

| What | Where |
| --- | --- |
| Product and technical documentation | `docs/` |
| The manual, its source manifest and ingestion inputs | `source/` |
| Base-index ingestion job | `ingest/` |
| Answer path: index, retrieval, assembly, template and gate, generation call, ledger, delivery | `cloud/grounded_generation/` |
| API, worker dispatch, store and app wiring | `cloud/arm_a/` |
| Shared session types, provider error and content hash | `cloud/common/` |
| Rider UI and client | `rider_ui/` |
| Release, repository and experiment tools | `tools/` |
| Evaluations | `evals/<date>_<name>/` |
| Frozen serving manifests and release-level owner decisions | `releases/` |
| History: earlier designs, review packages, receipts, retired code | `archive/` (read-only) |
| Generated environments, index copies, local answers and temporary output | ignored `build/` or `tmp/` |

Keep credentials and raw rider media out of Git. Do not add files at the repository root, and do not add to `archive/` except when retiring something.

## Change and verification

- **Branches.** Work on a short-lived `codex/<change>` branch with focused commits, and merge to `main` after CI passes. Do not restore draft-then-verify, the review gate or other retired designs.
- **Tests.** After runtime changes, run the provider-free tests in [CI](.github/workflows/ci.yml). After layout or navigation changes, run `python tools/check_repository_structure.py`.
- **Freezing.** A change to any serving input needs a new frozen manifest from [serving_release.py](tools/serving_release.py). Never edit a committed manifest to make a check pass.
- **Index.** A source, parser, sectioning or embedding change creates a new index ID; freeze it before serving.
- **Line endings.** On Windows, keep each file's committed line endings (`git ls-files --eol`); the release hashes exact bytes.
- **Experiments.** Local experiments use Claude Code as the generator ([EXPERIMENTS](docs/EXPERIMENTS.md)) and spend nothing. Hosted real-provider runs need an explicit owner scope.
- **Labelling.** Label evaluations local, private or hosted. Held-out cases never enrich prompts or retrieval.
- **Before promotion,** bind the source commit, image digest, index identity, compatible backend/UI/worker revisions and rollback. A successful build shows neither that the agent answers nor that its answers are correct.

## Spending and access

These limits remain:
- the 100-attempt allocation (72 used);
- the shared Haiku USD1 ledger;
- the INR3,120 lifetime budget with its INR2,960 billing-disconnect guard.

There is no token ceiling. There is no refund, reset or new allocation without the owner, and stopped billing is never restarted. Nothing in the repository authorizes deployment, public opening or GCP changes.
