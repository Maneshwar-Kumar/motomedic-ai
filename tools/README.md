# Tools

None of these tools calls a model provider or writes to the cloud.

| Tool | What it does |
| --- | --- |
| [check_repository_structure.py](check_repository_structure.py) | Checks the top-level layout, that every local link in the reader-facing documents resolves, the manual's SHA-256 and the current serving manifest. Run it after layout or doc changes. |
| [serving_release.py](serving_release.py) | `freeze --index <dir>` writes a new serving manifest that binds every serving input and the section index identity. `verify [--committed-revision <sha>]` checks the current one, optionally against committed blobs. |
| [check_installed_serving_release.py](check_installed_serving_release.py) | The release policy, plus the check a built image runs on its installed bytes and section index |
| [local_answer.py](local_answer.py) | Local experiments: `prepare` runs the real retrieval and assembly, a Claude Code subagent writes the draft, then `release` runs the real gate ([EXPERIMENTS](../docs/EXPERIMENTS.md)) |
| [resolve_container_base.py](resolve_container_base.py) | Resolves a public Docker Hub image tag to an immutable digest for hosted builds; it makes anonymous registry reads only |
| [provision_evaluator_secret_hosted.py](provision_evaluator_secret_hosted.py) | A hosted-only bridge that adds the existing GitHub model key as a new version of the managed secret. It runs only from its workflow, under owner scope. |

Tests for these tools are `test_*.py` in this folder; [CI](../.github/workflows/ci.yml) runs them.
