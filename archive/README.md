# Archive

This folder holds history: the designs, evidence and code that led to the current answer path. **Nothing here is used by the current runtime, tests or release.** Read it to understand how decisions were reached; read [docs/](../docs/REVIEW_GUIDE.md) for the system as it is.

| Folder | What it holds |
| --- | --- |
| [reports/](reports/README.md) | Receipts and reports from 11–23 October 2026: the reset, v8–v10.15 builds, hosted runs, public-review checks, operations, code review and frozen serving manifests v9–v10.14. Highlights: the [reset](reports/reset/20261011/README.md), the [v8 failed run](reports/grounded_generation/v8/REPORT.md) and the [v10.14 status](reports/public_evaluator/20261012/serving_manifest_v10_14.json). |
| [human_review/](human_review/) | The review packages, including the 161-case package (`agent_release_161`). Its canonical answers are the golden answers the evaluations score against. It is no longer a gate. |
| [grounding_bindings/](grounding_bindings/README.md), [registry/](registry/) | Source-binding and acceptance-scenario records of the reviewed controller |
| [legacy_root/](legacy_root/) | Retired root modules and their tests: the reviewed controller, the approved registry, the Gemini transport, the constrained generator, the earlier retrieval and registry code, and golden dialogues. It also holds the originals of the session types now in `cloud/common/`. |
| [legacy_cloud/](legacy_cloud/) | A retrieval-only smoke test of the original Qdrant service and its results |

## Paths

On 25 October 2026 the repository was reorganized for external review:
- `reports/` became `archive/reports/`, except `reports/evals/` (now `evals/`) and the v11 manifest (now `releases/`);
- `human_review/`, `grounding_bindings/` and `registry/` moved under `archive/`;
- retired root files went to `archive/legacy_root/`;
- the manual and source manifest went to `source/`;
- the ingestion job went to `ingest/`.

Markdown links inside the archive were rewritten to the new locations. JSON receipts keep the paths they recorded at the time, which are relative to the old layout.

## Verifying history

Before the move, `tools/check_repository_structure.py` verified the old bindings:
- the v8 frozen runtime copies;
- the v9–v10.14 manifest digests;
- the 187 outputs of the 161-case approval package.

To repeat that check in the original layout:

```sh
git switch --detach 7c412369f055b4d0ee747501e6b026f5987d1564
python tools/check_repository_structure.py
```

The files here keep the same bytes; only their location changed.
