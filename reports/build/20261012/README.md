# v9 text candidate implementation

12 October 2026. Baseline: `7cd58405e5e8a98abc0c272336249443d231d7ad`. The [execution sequence](../../../TODO.md) and [TRD](../../../docs/TRD.md) remain the contract. This receipt records candidate implementation; it does not approve factual answers, images or deployment.

The candidate replaces local dense similarity in the production answer path with authenticated Qdrant/BM25 concurrency and reviewed open-Q&A recovery/reranking. It preserves arbitrary manual questions, partial answers, concise checklists and optional typed outcomes. It adds complete compact evidence, pre-reserved whole-turn provider capacity, a durable Cloud Tasks worker and exact committed-buffer delivery/recovery.

Generated answers are privately drafted, finalized, separately verified and saved before streaming. Exact coordinator-approved initial safety scopes use their existing independent scope authority with distinct proof; no model verdict is fabricated. Unknown, malformed, quota, store, source-integrity and outage conditions fail closed. The evidence-only Claude availability fallback stays disabled, answer caches stay disabled and the primary stays `gemma-4-26b-a4b-it`.

The finite safety adapter requires a reviewed manual-backed typed hazard predicate. All 11 current finite safety steps have only product-policy applicability gates, so they remain inactive for this adapter. No query matching, inferred hazard link or new adaptive transition was introduced. Source-specific generated safety still passes through draft and separate verification.

## Version and source evidence

- [Historical preservation](v8_preservation.json) retains all 64 exact objects from the immutable v8 runtime freeze in `frozen_v8_runtime/`. The original v8 manifest and failed-run outputs remain unchanged.
- All 187 exact coordinator-approved output bindings remain at their original paths and bytes; their 161 initial scopes do not approve general generation or deployment.
- [Fuel proposal v3](source_context_refinement_v2/proposal_v3.json) and [independent agent review v3](source_context_refinement_v2/independent_review_v3.json) approve four exact fuel objects and their warnings/footnote, using original PDF pages 18 and 64. They authorize no parent body, new action catalog, rider-facing source display or factual model acceptance.
- Earlier proposal/review bytes remain as superseded evidence. A Windows descriptor-encoding mismatch was rejected by the loader and corrected in the new v3 package; the original source objects were unchanged.
- The existing 532-chunk, 277-parent index is reused without parsing or embedding. Page 103 remains an extraction gap.

## Checks

All local checks use synthetic providers, HTTP/store doubles or read-only original index data. No local image build or real-provider run was performed. Focused implementation results are in [retrieval/source notes](retrieval_evidence.md), [durable operations](durable_operations.md) and [release/CI](release_ci.md). Consolidated checks and hosted CI results will be recorded in this directory after the final candidate freeze.

The preserved v8 real run released zero technical answers and answered 0/4 answerable/partially answerable cases. Source reload, workflow success and synthetic tests do not establish that v9 repairs real answer coverage or meets latency targets.

## Remaining build and acceptance gates

Initial ADC capture failed `ARTIFACT_STORE_UNAVAILABLE`. An elevated check subsequently found the owner's already configured machine gcloud login. Read-only capture through that login verified [generation 1791537775184836](index_snapshot_reference.json) and the complete recorded SHA `4248b6f21bede82375a2aceda2205ad8abb63a061abf18c30e9686cd82bba6bc`. The inherited backend image exists and main-project billing is already enabled. No credential material, login configuration or billing change is written or performed by this work. GitHub still has no configured GCP workload-identity provider or read-only service-account variables.

`tools/serving_release.py prepare` requires a verified generation and matching committed blobs before it emits hosted image contexts. `tools/bind_serving_images.py` requires matching service/revision/input provenance before accepting digests or preparing rollback. Missing credentials, absent generations and mismatched provenance are rejected.

The existing login can submit the requested image build directly to hosted Cloud Build. Fresh provider quality, deployed Firestore/Qdrant/Cloud Tasks and browser recovery require their exact applicable authorization. Deployment, public opening, fallback activation, new provider spending and billing changes remain separate. No stopped billing has been restarted.

## Repeating the hosted build

Use the already installed Google Cloud CLI and the existing account; no new key is needed. Confirm `gcloud auth list` and use explicit `--project=motomedic-ai-20261009` on project commands because the machine's default project is different. Do not change the global default as a side effect.

1. Verify the committed serving manifest with `python tools/serving_release.py verify --committed-revision <full-commit>`.
2. Prepare contexts from those committed blobs with `python tools/serving_release.py prepare --committed-revision <full-commit>`; immutable generation/hash checks are mandatory.
3. Upload each canonical source archive under a new versioned GCS object, capture its generation/full SHA, and submit its generated `cloudbuild.json` to hosted Cloud Build using that exact object generation.
4. Record both successful build results and use `tools/bind_serving_images.py --mode build-only` to bind images to the exact source, archive generation, recipe and input tree. Promotion additionally requires an accepted candidate and compatible rollback; build-only receipts grant neither.

To run the separate GitHub read-only artifact workflow, configure repository variables `MOTOMEDIC_GCP_WORKLOAD_IDENTITY_PROVIDER` and `MOTOMEDIC_GCP_READONLY_SERVICE_ACCOUNT` for an existing GitHub OIDC provider/service account that can read the immutable index bucket. Machine gcloud credentials are not copied to GitHub. This setup is optional for direct Cloud Build submission; no service-account key or provider-secret access is needed by provider-free CI.
