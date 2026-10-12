# Clone, fork and test MotoMedic

The [repository](https://github.com/Maneshwar-Kumar/motomedic-ai), supplied manual and [immutable index release](https://github.com/Maneshwar-Kumar/motomedic-ai/releases/tag/index-a3282c4d98cf54595e4ba168) are public. Frozen v10.13 source [3b7da1692187736295fee7345e9b3e932d02b216](https://github.com/Maneshwar-Kumar/motomedic-ai/commit/3b7da1692187736295fee7345e9b3e932d02b216) passed [provider-free CI](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38233548200). Current work remains on `codex/public-evaluator`, in [draft PR #4](https://github.com/Maneshwar-Kumar/motomedic-ai/pull/4); `main` is unchanged. Anonymous API/worker/Qdrant readbacks passed; public answering is now enabled and one anonymous direct browser answer passed. The owner [waived independent manual answer review](../reports/public_evaluator/20261012/public_review/owner_functional_acceptance_scope_v1.json) for this functional demo; public answering is enabled under the later owner instruction. No independent factual-quality acceptance is claimed.

Public answering is enabled by the [later direct owner instruction](../reports/public_evaluator/20261012/public_review/owner_public_answer_enablement_scope_v1.json), before full six-case acceptance. [Routed UI health](../reports/public_evaluator/20261012/haiku_v10_13_helpers/functional_ui_promotion_v2/enabled_health.json) passed for `motomedic-rider-ui-v10-13-functional-enabled`. The [anonymous browser](../reports/public_evaluator/20261012/public_review/browser_enabled_v1/receipt.json) observed a 97-character SUPPORTED answer in 71.06 seconds with enabled input and all four progress stages; it did not capture incremental chunk rendering or session/operation identity. The separate [private direct audit](../reports/public_evaluator/20261012/haiku_v10_13_runtime/direct_delivery_a77d_v1.json) proves exact-finalized verification and identical saved/stream/recovery. USB returned `PROVIDER_INCOMPLETE_OR_REFUSED` without a retained exact stop reason, four cases remain unrun and positive cache reads are unproven. Broader functional acceptance and merge remain pending; independent manual answer review was waived.

## Get the exact source

Install Git, then clone the repository or use GitHub's Fork control to make your own copy:

```sh
git clone https://github.com/Maneshwar-Kumar/motomedic-ai.git
cd motomedic-ai
git switch codex/public-evaluator
git rev-parse HEAD
```

To inspect the exact tested frozen source, use `git switch --detach 3b7da1692187736295fee7345e9b3e932d02b216`. Documentation and operational receipts may advance on the working branch without changing those frozen runtime bytes. For a fork, include the working branch or fetch it from the upstream repository; record the full commit SHA.

Read [AGENTS](../AGENTS.md), [CONTRIBUTING](../CONTRIBUTING.md), [PRD](PRD.md), [TRD](TRD.md) and [architecture](ARCHITECTURE.md). Preserve historical manifests and approval bytes. A new deployment/configuration needs a fresh scoped release; changing old bindings to make checks pass is invalid.

The supplied [manual](../royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf) must hash to `cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89`. It is the 149-page RAM00818/A, 4 November 2025 Himalayan BS6 owner's manual. The [public-review instruction](../reports/public_evaluator/20261012/public_review/owner_public_review_scope_v1.json) supersedes historical network/manual-display restrictions for this review. Source approval remains exact object/scope approval, not a guarantee for every generated answer.

## Run provider-free checks

The complete [published workflow](../.github/workflows/ci.yml) is the authoritative test list. On GitHub, enable Actions in your fork and open a pull request with the current workflow, or use `workflow_dispatch` where the workflow is available on your default branch. It runs on an Ubuntu 24.04 hosted runner with Python 3.12; no cloud account, provider key or private index access is required. Forking does not copy provider secrets.

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

## Download and load the immutable index

The [published asset](https://github.com/Maneshwar-Kumar/motomedic-ai/releases/download/index-a3282c4d98cf54595e4ba168/index_snapshot.tar.gz) is the existing byte-identical snapshot: 181,153,632 bytes, SHA-256 `4248b6f21bede82375a2aceda2205ad8abb63a061abf18c30e9686cd82bba6bc`. The [direct owner release approval](../reports/public_evaluator/20261012/public_review/owner_index_release_scope_v1.json) authorizes this export. No Google account, GCS permission or model key is needed to download it.

The snapshot contains the existing 532 chunks, 277 parents, stored 1,024-dimensional BGE M3 vectors, BM25, source objects, Qdrant data and pinned reranker files. It does not contain the BGE M3 query-embedding model or the private inherited container base. Document embeddings do not need to be recomputed.

From the repository root, after installing the synthetic dependencies above:

```sh
mkdir -p build/downloads
curl --fail --location --output build/downloads/index_snapshot.tar.gz 'https://github.com/Maneshwar-Kumar/motomedic-ai/releases/download/index-a3282c4d98cf54595e4ba168/index_snapshot.tar.gz'
python - <<'PY'
from pathlib import Path
from hashlib import sha256
import json
from cloud.serving_artifacts import extract_snapshot, restore_qdrant_lock, verify_index

archive = Path('build/downloads/index_snapshot.tar.gz')
expected_sha = '4248b6f21bede82375a2aceda2205ad8abb63a061abf18c30e9686cd82bba6bc'
if archive.stat().st_size != 181153632 or sha256(archive.read_bytes()).hexdigest() != expected_sha:
    raise SystemExit('Index archive size/hash mismatch; stop before loading')
release = json.loads(Path('reports/public_evaluator/20261012/serving_manifest_v10_13.json').read_bytes())
policy = release['index']
index = Path('build/serving-artifacts') / policy['index_id']
if not index.exists():
    extract_snapshot(archive, index)
restore_qdrant_lock(index, policy)
manifest = verify_index(index, policy)
print(json.dumps({'verified_index_id': manifest['index_id'],
                  'source_sha256': manifest['source_sha256'],
                  'counts': manifest['counts'],
                  'provider_calls': 0}))
PY
```

Extraction uses the repository's confined loader, which rejects links, traversal, duplicate members and overwrites. The lock-recovery call restores only the exact previously bound deterministic Qdrant process-lock bytes; it does not alter source/index content or exclusions. Verification checks the original manifest, every declared file, source, embedding revision, chunker and counts. An existing local index is verified again rather than trusted by its directory name.

The original GCS generation/hash references remain provenance for the hosted deployment. They are not needed for this public download and offline index inspection. A fork that changes the serving artifact location must record its own immutable location/generation/hash and fresh release bindings.

## Inspect read-only hosted retrieval

Under the passed [anonymous service readbacks](REVIEWER.md), Qdrant `GET /health` and `POST /query` need no Google token. The query contract requires:

| Field | Value |
| --- | --- |
| `vector` | 1,024 finite numeric values from the pinned BGE M3 query model, or a stored vector for an index smoke check. |
| `limit` | Integer from 1 to 20. |
| `index_id` | `index_a3282c4d98cf54595e4ba168` |
| `source_sha256` | `cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89` |

The loaded `embeddings.npy` can supply a stored vector for a read-only index smoke check. A stored-vector match tests dense lookup and immutable identities; it does not test natural-language embedding, BM25 fusion, reranking, answer quality or an LLM. Native Qdrant dashboard/management routes are not exposed.

## Reproduce full hosted RAG with your own credentials

Cloning and the public snapshot provide source, manual, approvals, vectors, BM25 and frozen manifests. They do not provide original credentials, paid capacity, the BGE M3 query model or the private inherited container base. Obtain the query model at the exact `BAAI/bge-m3` revision `5617a9f61b028005a4858fdac845db406aefb181` during your own hosted image build. The snapshot's `reranker_manifest.json` and [model packaging code](../cloud/arm_a/package_models.py) bind the reranker. Never download models or embed the document on each request.

Use your own cloud project, hosted identities, Anthropic credential and persistent allocation. The recorded Firestore project, service origins, artifact references and base-image digest currently bind the original deployment. Pointing a fork at your own infrastructure requires configuration changes, a fresh frozen manifest/image binding and independent validation.

| Prerequisite | Required setup |
| --- | --- |
| Cloud identity | Your own Google Cloud project and hosted workload identities with scoped permissions. Original credentials and service-account keys are never shared in Git. |
| Immutable artifacts and query assets | Import the verified public snapshot into your own generation/hash-bound storage. Package the pinned BGE M3 query model and reranker in your own hosted base image. Changing source/parser/chunk/embedding creates a new index and review bindings. |
| Dense retrieval | Your own source/index-bound read-only Qdrant wrapper, restored from stored vectors. Match its origin and access mode in the new configuration. |
| Persistent state | Firestore sessions, operations, fenced leases, saved answers, visitor quotas and permanent token/money ledgers. Your own deployment needs its own explicitly authorized allocation; never reset or reuse this deployment's charged ledger. |
| Dispatch | A Cloud Tasks queue and exact task-caller identity/audience for a separate worker. The current original queue has one concurrent dispatch and one delivery attempt. |
| Provider | Pinned `claude-haiku-5-5` with separate draft/verifier policies, schemas, adapters and calls. Store your API key in private managed secrets, never in source, browser settings, traces or screenshots. |
| Containers | Hosted Cloud Build and Artifact Registry; prepare complete frozen contexts using [serving_release.py](../tools/serving_release.py), not the historical raw `cloudbuild.yaml`. Replace the original private inherited base only in a newly bound own-project release. |
| Services | UI gateway/Streamlit, API and separate worker. Configure exact audiences, allowlisted verified service-account emails, task settings and visitor-signing secret. Preserve authentication for all writes, paid generation, jobs and owner-private reads. |

The [artifact loader](../cloud/serving_artifacts.py), [production wiring](../cloud/arm_a/app.py), [inspection authentication](../cloud/arm_a/public_inspection_auth.py), [dispatcher](../cloud/arm_a/durable_dispatch.py) and [Qdrant wrapper](../cloud/qdrant/boot.py) specify the actual interfaces.

Before a new hosted candidate answers publicly, prove native counts for complete evidence/history, phase admission, real retrieval/returned answers, separate exact-finalized verification, current draft/verifier cache creation and reads, saved/streamed/recovered delivery, ownership/replay, revision/rollback and browser behavior. For this present owner-authorized demo, independent manual answer review is waived; immutable source approval and runtime source checks remain binding. Preserve failed receipts. A build or a model verifier's `SUPPORTED` verdict alone is not acceptance.

The original deployment retains its historical charges, shared Haiku USD1, 100 attempts and INR2,700/INR2,540 controls. Its default legacy primary token ceiling was 999,200; the exact owner-approved [2,000,000-token grant](../reports/public_evaluator/20261012/haiku_v10_13_helpers/operator_v2/hosted_runs/57f78b4b-1385-428b-8b90-fa31f134230b/application_receipt.json) is now applied with all historical usage retained. Do not execute the dormant maintenance tool, use synthetic approval as operational evidence, reset counters or restart stopped billing while experimenting with a fork.
