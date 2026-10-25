# Setup: clone, test and rebuild

Everything here runs without a model call, a cloud account or a key. To ask new questions with Claude Code as the generator, see [EXPERIMENTS](EXPERIMENTS.md).

## Get the source

```sh
git clone https://github.com/Maneshwar-Kumar/motomedic-ai.git
cd motomedic-ai
git rev-parse HEAD
```

The [manual](../source/royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf) must hash to `cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89`.

## Run the provider-free checks

The [CI workflow](../.github/workflows/ci.yml) is the authoritative list. It runs on Ubuntu 24.04 with Python 3.12, and the dependency lock is for Linux, amd64 and Python 3.12. On other systems (Windows, newer Python), any environment with Flask 3.1, NumPy and Streamlit 1.65 runs the same tests unlocked.

```sh
python3.12 -m venv .venv && . .venv/bin/activate
python tools/check_repository_structure.py
python tools/serving_release.py verify --committed-revision "$(git rev-parse HEAD)"
python -m pip install --require-hashes -r rider_ui/requirements-linux-amd64-py312.lock.txt
python -m pip install Flask==3.1.2
python -m unittest -v \
  cloud.grounded_generation.test_section_answer cloud.grounded_generation.test_section_wiring \
  cloud.grounded_generation.test_whole_turn_admission \
  cloud.arm_a.test_store cloud.arm_a.test_durable_operations cloud.arm_a.test_health \
  cloud.arm_a.test_public_inspection_auth cloud.arm_a.test_production_policy cloud.arm_a.test_public_admission \
  tools.test_serving_release tools.test_check_installed_serving_release tools.test_local_answer cloud.budget_guard.test_policy
python -m unittest discover -s rider_ui/tests -p 'test_*.py' -v
```

The tests use:
- a synthetic section index ([test_section_fixture.py](../cloud/grounded_generation/test_section_fixture.py));
- a fake Anthropic transport and a fake ledger;
- an in-memory Firestore double.

They exercise the full API → worker → saved stream → UI parser path. They do not test live Qdrant or Firestore, paid Haiku behavior, factual answers or latency.

## Rebuild the section index

The section index is derived from the cached Docling parse inside the public base-index snapshot. Nothing is re-parsed.

1. **Download and check the snapshot.** It is 181,153,632 bytes, SHA-256 `4248b6f21bede82375a2aceda2205ad8abb63a061abf18c30e9686cd82bba6bc`. Treat it as untrusted data and extract it into its own empty directory.

   ```sh
   mkdir -p build/downloads build/index-snapshot
   curl --fail --location --output build/downloads/index_snapshot.tar.gz \
     'https://github.com/Maneshwar-Kumar/motomedic-ai/releases/download/index-a3282c4d98cf54595e4ba168/index_snapshot.tar.gz'
   sha256sum build/downloads/index_snapshot.tar.gz
   tar -xzf build/downloads/index_snapshot.tar.gz -C build/index-snapshot
   ```

2. **Get BGE-M3.** Use `BAAI/bge-m3` at revision `5617a9f61b028005a4858fdac845db406aefb181`, with `sentence-transformers` and a CPU build of PyTorch. The model directory must hold `pytorch_model.bin`, SHA-256 `b5e0ce3470abf5ef3831aa1bd5553b486803e83251590ab7ff35a117cf6aad38`. [EXPERIMENTS](EXPERIMENTS.md#setup) gives the download call. The index ID includes the weights hash, so a re-saved or converted model gives a different ID.
3. **Build with the script that produced the frozen index,** so the build-code hash in the ID matches. Set `PYTHONPATH=ingest` so it finds `online_ingest.py`:

   ```sh
   PYTHONPATH=ingest python evals/20261025_answer_release_v3/candidate/section_index.py build/index-snapshot build/index-v3-sections <bge_m3_dir>
   ```

4. **Compare with the frozen identity:**

   ```sh
   python -c "import json; from cloud.grounded_generation import section_index as si; m = json.load(open('releases/serving_manifest_v11_1.json')); print(si.verify('build/index-v3-sections', m['index'])['index_id'])"
   ```

The sectioning is deterministic, but two things can change the file hashes:
- **Embedding bytes.** They can differ across CPUs and library versions.
- **Line endings.** The frozen index was built on Windows, so its `chunks.jsonl`, `sections.jsonl` and `manifest.json` end lines with CRLF. A Linux rebuild writes LF, so those files hash differently even when the content is identical; compare them with line endings normalized.

A rebuild whose bytes differ is a different artifact. Inspect it, but it needs its own frozen release before serving. Serving reads either line ending.

With NumPy installed, `python evals/20261025_answer_release_v3/serving_parity.py` reruns the [parity check](../evals/20261025_answer_release_v3/serving_parity.json). It checks that the serving modules reproduce the v3 run's model inputs and gate outcomes on the real index.

## Hosted reproduction with your own credentials

A hosted run needs:
- your own Google Cloud project and workload identities;
- Firestore;
- a Cloud Tasks queue with an exact worker identity;
- Cloud Run services for the UI, API and worker;
- an Anthropic key in a managed secret;
- your own explicitly authorized ledger allocation.

The backend image needs the section index at `build/section-index`. [check_installed_serving_release.py](../tools/check_installed_serving_release.py) verifies that index during the image build. The image also needs the BGE-M3 query model at `build/index/embedding_model`; startup checks that its identity matches the index.

Dense search runs over the image's pinned vectors, or over a hosted Qdrant collection exported with [export_qdrant.py](../cloud/export_qdrant.py) when `MOTOMEDIC_QDRANT_URL` is set. [app.py](../cloud/arm_a/app.py) shows the production wiring.

Pointing a fork at other infrastructure needs configuration changes, a fresh frozen manifest and its own validation. Never reuse or reset this deployment's charged ledger, and never put a key in source, browser settings, traces or screenshots.
