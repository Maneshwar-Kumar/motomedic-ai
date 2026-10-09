# MotoMedic AI

Owner-manual-grounded motorcycle troubleshooting prototype. The sole source is the supplied 149-page Royal Enfield New Himalayan 450 owner's manual, checksum `CF221A29E2F9CD5AF6E80A99774A697C814E8EDA661C27D72E519D8A7E80DA89`.

## Online index build

Run **Versioned owner manual ingestion** in GitHub Actions. It verifies the PDF checksum, parses layout with Docling, retains the structured document and figure crops, creates section parents and token-bounded children, and builds pretrained embeddings, a Qdrant vector store, BM25 postings and a provenance graph. It then loads a pretrained cross-encoder and compares retrieval with and without reranking on 27 draft reference cards.

The run artifact contains `manifest.json` with source/model revisions, dependency versions, chunk settings and file checksums, and `ingestion_qa.json` with extraction gaps. Changes to source, parser, chunker or embedding model create a new index. Document embeddings are reused; requests compute a query embedding and cross-encoder pair scores.

The hosted build uses Qdrant's open source embedded storage without a Qdrant account. A dedicated server receives the same vectors. The authorized GCP project is `motomedic-ai-20261009`; the Qdrant service name is `motomedic-qdrant`.

```bash
pip install -r requirements-ingest.txt
python online_retrieve.py --index build/index --query "engine will not start" --rerank
```

## Evidence boundary

The extracted objects are unreviewed candidates. Section parents preserve context; procedure parents, prerequisite edges and mandatory warning links require source review. Seven existing topic links retain provisional agent-check status. Relevance and topic links cannot establish an OEM procedure order. Retrieval returns `may_generate_procedural_advice: false` pending applicability, evidence and claim gates.

The 37 dialogue cases and exact cache are provisional. Retrieval scores on the older 27 cards are in-sample diagnostics. Edition, variant, display rights and the support route remain open.

## Controller choice

Use the TRD's deterministic controller for state, eligibility, prerequisites, safety stops and non-repeat behavior. A decision model may interpret free-form feedback or rank already eligible choices, subject to confidence checks and clarification. OpenAI Decisions API and TypeSafe AI Jev are possible interpretation adapters; neither has been benchmarked here. Compare typed-outcome errors, next-step correctness, ambiguity handling, latency and cost on independently reviewed cases before selecting one.

## GCP spending controls

The account bills in INR. A non-recurring lifetime budget starts 9 October 2026: INR800, alerts at INR400/640/800, automated billing disconnection at INR640 to leave headroom below the authorized US$10. Billing data is delayed; this cannot guarantee an instantaneous cap. The guard is restricted to this project. Compute also receives a runtime limit and authenticated access.

Check the guard in simulation before enabling live shutdown. Re-enabling billing after an actual budget stop requires owner authorization. See `cloud/deployment_status.json` for deployed resources and verification results.

See [INDEX_README.md](INDEX_README.md) for the local baseline and [AGENTS.md](AGENTS.md) for the project contracts.
