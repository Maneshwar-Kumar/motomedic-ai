# MotoMedic AI

## Retired design choices

On 11 October 2026, the owner rejected the cached full-owner-manual Claude
architecture after its eight-case experiment. Its source conversion, code, raw
results and disabled workflows are preserved in
[outdated_design_choices/claude_full_manual](../../outdated_design_choices/claude_full_manual).
See the [decision and metric comparison](../../outdated_design_choices/claude_full_manual/DECISION.md).
Continue with the versioned Docling/BGE M3 hybrid-retrieval architecture and
deterministic state, evidence and citation gates. The archived Claude experiment
is not an active build option and must not be rerun without owner authorization.

Owner-manual-grounded motorcycle troubleshooting prototype. The sole source is the supplied 149-page Royal Enfield New Himalayan 450 owner's manual, checksum `CF221A29E2F9CD5AF6E80A99774A697C814E8EDA661C27D72E519D8A7E80DA89`.

## Online index build

Run **Versioned owner manual ingestion** in GitHub Actions. It verifies the PDF checksum, parses layout with Docling, retains the structured document and figure crops, creates section parents and token-bounded children, and builds pretrained embeddings, a Qdrant vector store, BM25 postings and a provenance graph. It then loads a pretrained cross-encoder and compares retrieval with and without reranking on 27 draft reference cards.

The run artifact contains `manifest.json` with source/model revisions, dependency versions, chunk settings and file checksums, and `ingestion_qa.json` with extraction gaps. Changes to source, parser, chunker or embedding model create a new index. Document embeddings are reused; requests compute a query embedding and conditional cross-encoder pair scores. Retrieval policy changes version assembly without re-embedding the document.

The hosted build uses Qdrant's open source embedded storage without a Qdrant account. A dedicated server receives the same vectors. The authorized GCP project is `motomedic-ai-20261009`; the Qdrant service name is `motomedic-qdrant`.

```bash
pip install -r requirements-ingest.txt
python online_retrieve.py --index build/index --query "engine will not start" --rerank-mode conditional
```

## Evidence boundary

The extracted objects are unreviewed candidates. Section parents preserve context; procedure parents, prerequisite edges and mandatory warning links require source review. Seven existing topic links retain provisional agent-check status. Relevance and topic links cannot establish an OEM procedure order. Retrieval returns `may_generate_procedural_advice: false` pending applicability, evidence and claim gates.

The 37 dialogue cases and exact cache are provisional. Retrieval scores on the older 27 cards are in-sample diagnostics. Edition, variant, display rights and the support route remain open.

## Controller choice

Use the TRD's deterministic controller for state, eligibility, prerequisites, safety stops and non-repeat behavior. A decision model may interpret free-form feedback or rank already eligible choices, subject to confidence checks and clarification. OpenAI Decisions API and TypeSafe AI Jev are possible interpretation adapters; neither has been benchmarked here. Compare typed-outcome errors, next-step correctness, ambiguity handling, latency and cost on independently reviewed cases before selecting one.

## GCP spending controls

The account bills in INR. A non-recurring lifetime budget starts 9 October 2026: INR800, alerts at INR400/640/800, automated billing disconnection at INR640 to leave headroom below the authorized US$10. Billing data is delayed; this cannot guarantee an instantaneous cap. The guard is restricted to this project. The private Qdrant service scales to zero, permits at most one instance, and uses a 30-second request timeout.

Check the guard in simulation before enabling live shutdown. Re-enabling billing after an actual budget stop requires owner authorization. See `cloud/deployment_status.json` for deployed resources and verification results.

See [INDEX_README.md](../architecture/LOCAL_INDEX_BASELINE.md) for the local baseline and [AGENTS.md](../../AGENTS.md) for the project contracts.

## Current hosted result

The current default is BGE M3 with a 1,024-token chunk budget. It has 532 search chunks and 277 section parents. Conditional reranking is implemented; pending source/applicability review skips it on current candidate bundles. See [HOSTED_INDEX_DECISION.md](../architecture/HOSTED_INDEX_DECISION.md) and [index_benchmark.json](../../index_benchmark.json) for measured baseline results and remaining misses. See [cloud/deployment_status.json](../../cloud/deployment_status.json) for immutable storage, authentication and spending controls.

This is the retrieval backend. The Streamlit rider UI, integrated controller and gated generative answering are later build phases.

## Conditional retrieval policy

TRD v0.4 and `retrieval_policy.py` define the normal path: hybrid retrieve, initial assembly, source/applicability checks, one exact-dependency recovery if needed, one optional rerank for uncertain ordering, reassembly, then controller and answer gates. Complete reviewed evidence with clear ordering skips the cross-encoder. Missing review, unsupported requests, safety stops and system errors have separate routes. Current bundles always retain `may_generate_procedural_advice: false`.

The trusted registry/controller supplies `dependency_manifest`, `step_id`, confirmed `applicability_status` and optional terminal `gate_status`/`gate_evidence_ids` to `Retriever.search`. These are internal service inputs and must not be accepted from rider text, uploads or model output. `retrieval_action` is a scheduling result, not a final answer verdict; `CONTINUE_GATES` still requires controller eligibility and final claim checks. `RANKING_UNRESOLVED` withholds a release decision and returns to the controller for clarification or abstention.

Default experimental bounds: fused pool 20, recovery pool 40, at most one recovery and one cross-encoder attempt, at most 100 scored passage windows and 256 mandatory evidence IDs. Rank uncertainty compares distinct parent sections using dense/BM25 overlap and relative RRF margins. The thresholds are `PROVISIONAL_UNCALIBRATED`; independent reviewed calibration and held-out evaluation are required before release activation. The full rider query is preserved; queries over the current cross-encoder's 128-token limit skip it with an explicit reason.

Bundles record policy/configuration, trigger signals, decision history, recovery evidence IDs, attempt/pair counts, skip reasons and stage timing. Failures raise `RetrievalSystemError` with status `SYSTEM_ERROR` and telemetry. No failed reranker is retried or silently converted into an unsupported-source claim. Mandatory reviewed evidence survives changed ranking. Model loading occurs only when scheduled and is reused in the process.

Use `--rerank-mode off` and `--rerank-mode always` only for diagnostic comparisons (`--rerank` remains an always-mode alias). Run `python -m unittest test_conditional_retrieval test_online_assembly` for failure and assembly checks. The **Verify retrieval policy and TRD** GitHub workflow reuses the immutable hosted BGE artifact and renders the TRD without rebuilding its embeddings. `tools/render_docx.py` is the supplied documents skill renderer, vendored for hosted visual verification; it uses the runner's `/usr/bin/soffice`, not a desktop Office installation.

## Reviewed controller integration

The TRD v0.4 registry, review workflow and deterministic service boundary are implemented in [CONTROLLER_INTEGRATION.md](../../CONTROLLER_INTEGRATION.md). Run the private **Verify reviewed evidence controller** GitHub workflow to reuse the existing BGE snapshot, execute state/retrieval/budget regressions and verify five direct plus three multi-turn draft gates. No new document embeddings or GCP deployment are required.

All eleven imported step/lookup records and the exact cache remain blocked pending independent original-page review and human sign-off. Passing synthetic controller tests is not source approval or release acceptance. `ReviewedService` integrates the trusted registry with `online_retrieve.py`; the legacy scripted controller remains an engineering prototype.

The owner accepts Himalayan + BS6 confirmation and restricts PDF/excerpt display to engineering. End-user source display is denied. The manifest records the visually checked RAM00818/A edition, 4 November 2025, and the verified, owner-requested Royal Enfield support email. Public UI, production session storage, semantic-verifier calibration and release review are pending.
