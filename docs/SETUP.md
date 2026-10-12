# Clone, fork and test MotoMedic

The owner has authorized publishing the existing repository and supplied manual. Public visibility is pending publication/readback; current work remains on `codex/public-evaluator` and in [draft PR #4](https://github.com/Maneshwar-Kumar/motomedic-ai/pull/4). The current UI preview is being prepared with answering paused. See [reviewer access](REVIEWER.md) for URLs and [status](STATUS.md) for actual acceptance results.

## Get the exact source

Install Git, then clone the repository or use GitHub's Fork control to make your own copy:

```sh
git clone https://github.com/Maneshwar-Kumar/motomedic-ai.git
cd motomedic-ai
git switch codex/public-evaluator
git rev-parse HEAD
```

For a fork, clone your fork's URL and select the branch containing the desired frozen release. Record the full commit SHA. Read [AGENTS](../AGENTS.md), [CONTRIBUTING](../CONTRIBUTING.md), [PRD](PRD.md), [TRD](TRD.md) and [architecture](ARCHITECTURE.md). Preserve historical manifests and approval bytes. A new deployment/configuration needs a fresh scoped release; changing old bindings to make checks pass is invalid.

The supplied [manual](../royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf) must hash to `cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89`. It is the 149-page RAM00818/A, 4 November 2025 Himalayan BS6 owner's manual. The owner now permits public inspection; historical [source_manifest.json](../source_manifest.json) retains its previous display-policy record. Source approval is exact object/scope approval, not a guarantee for every generated answer.

## Run provider-free checks

The complete [published workflow](../.github/workflows/ci.yml) is the authoritative test list. On GitHub, enable Actions in your fork and run **Provider-free contract checks** with `workflow_dispatch`, or open a pull request. It runs on an Ubuntu 24.04 hosted runner with Python 3.12; no cloud account, provider key or original private index download is required. Forking does not copy provider secrets.

For local synthetic checks, use Linux x86-64 with Python 3.12, or the equivalent WSL environment on Windows. The dependency lock below is specifically Linux/amd64/Python3.12. Use a fresh virtual environment:

```sh
python3.12 -m venv .venv
. .venv/bin/activate
python -m pip install --require-hashes -r rider_ui/requirements-linux-amd64-py312.lock.txt
python -m pip install Flask==3.1.2
python tools/check_repository_structure.py
python human_review/agent_release_161/approval_consumer.py
python -m unittest discover -s human_review/agent_release_161 -p 'test_approval_consumer.py' -v
python tools/serving_release.py verify --committed-revision "$(git rev-parse HEAD)"
```

Run the complete runtime/module test command from the CI workflow and its UI command:

```sh
python -m unittest discover -s rider_ui/tests -p 'test_*.py' -v
```

A focused admission/receipt check is:

```sh
python -m unittest cloud.grounded_generation.test_token_ceiling cloud.grounded_generation.test_whole_turn_admission cloud.grounded_generation.test_admission cloud.grounded_generation.test_claude_fallback tools.test_manage_primary_token_ceiling -v
```

These tests use in-memory provider/store/HTTP fixtures. They do not validate live Qdrant/Firestore, paid Haiku behavior, factual answers, latency or a working public release. Explicit UI loopback fixtures are engineering tests, not a production authentication mode. Keep real-provider work and production builds in the hosted environment.

## Reproduce the hosted RAG runtime

Cloning gives source, manual, approvals, frozen manifests and synthetic tests. It does **not** give credentials or the original deployment's private Cloud Storage snapshot/model assets. The existing serving index is `index_a3282c4d98cf54595e4ba168`, BGE M3 with 532 chunks, 277 parents and BM25. Active artifacts are checked by exact object generation and SHA; do not silently replace them or reparse/re-embed on each question.

To reproduce live RAG, use your own cloud project, Anthropic credential and persistent allocation, or obtain explicitly scoped access to the existing immutable artifacts. No private artifact access or free generation capacity follows from a clone. The source snapshot references, Firestore project and Qdrant origin currently bind the recorded deployment. Pointing a fork at another project requires configuration changes, a fresh frozen manifest/image binding and independent validation.

| Prerequisite | Required setup |
| --- | --- |
| Cloud identity | Your own Google Cloud project and hosted workload identities with scoped permissions. Existing source credentials and service-account keys are never shared in Git. |
| Immutable artifacts | The exact approved generation/hash-bound index and pinned query/reranker assets, through authorized artifact access/export. A different source/parser/chunk/embedding build creates a new index and review bindings. Current original artifacts remain private. |
| Dense retrieval | Your own IAM-protected Qdrant wrapper restored from the approved vector bundle; expose only source/index-bound `/query` and `/health`. No dashboard is implemented by this wrapper. |
| Persistent state | Firestore sessions, operations, fenced leases, saved answers, visitor quotas and permanent token/money ledgers. New own-project allocations must be separately authorized; never reset or reuse this deployment's charged ledger. |
| Dispatch | A private Cloud Tasks queue and exact task-caller service identity/audience for a separate worker. The current queue has one concurrent dispatch and one delivery attempt. |
| Provider | Pinned `claude-haiku-5-5` with separate draft/verifier policies, schemas, adapters and calls. Store the API key in private managed secrets, never in source, browser settings, traces or screenshots. |
| Containers | Hosted Cloud Build and Artifact Registry; prepare complete frozen contexts using [serving_release.py](../tools/serving_release.py), not the historical raw `cloudbuild.yaml`. Bind commit, input tree, manifest, source/index generations and image digests. |
| Services | UI gateway/Streamlit, private API and separate private worker. Configure exact origins, identity audiences, task settings and visitor-signing secret. Keep backend/worker/Qdrant private. |

The [artifact loader](../cloud/serving_artifacts.py), [production wiring](../cloud/arm_a/app.py), [dispatcher](../cloud/arm_a/durable_dispatch.py), [Qdrant wrapper](../cloud/qdrant/boot.py) and [UI connection](../rider_ui/README.md) specify the actual interfaces. The frozen serving manifest provides the exact original artifact references and complete inventory. Its private paths are provenance records, not publicly downloadable artifacts.

Before a new hosted candidate answers publicly, prove native counts for complete evidence/history, initial and correction admission, original-page answer/citation quality, current draft/verifier cache creation and reads, exact saved/streamed/recovered delivery, ownership/replay boundaries, actual revision configuration, rollback/restore and browser behavior. Preserve failed receipts. A build or a model verifier's `SUPPORTED` verdict alone is not acceptance.

The original deployment retains its historical charges, shared Haiku USD1, 100 attempts and INR2,700/INR2,540 controls. Its default legacy primary token ceiling is 999,200; a separately approved measured grant may change only that ceiling. Do not execute the dormant maintenance tool, create synthetic approval as operational evidence, reset counters or restart stopped billing while experimenting with a fork.
