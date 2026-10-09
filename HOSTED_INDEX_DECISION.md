# Hosted index decision and diagnostic

The current prototype uses BGE M3, 1,024-token chunk budgets, dense cosine retrieval plus BM25 with reciprocal rank fusion, bounded graph expansion, and full section context. The pretrained cross-encoder is available and disabled by default: on this draft set it reduces cited-page coverage and adds latency. Model weights are reused; each request computes a query vector and, when enabled, new cross-encoder pair scores.

| Embedding | Retrieval mode | All cited pages assembled | Warm retrieval p95 on GitHub CPU |
| --- | --- | --- | --- |
| MiniLM | hybrid_only | 21/27 | 0.02 s |
| MiniLM | cross_encoder | 22/27 | 1.22 s |
| BGE M3 | hybrid_only | 23/27 | 0.39 s |
| BGE M3 | cross_encoder | 22/27 | 3.00 s |

These 27 cards are draft, in-sample probes. Page presence does not establish complete procedure evidence, source applicability or supported claims. The timing excludes model loading, the hosted API, generation and final verification. No held-out or end-to-end release score is claimed.

BGE M3 yields 532 search chunks, 277 section parents, 1,691 evidence objects, 23 tables, 188 figure crops and one full-page fallback image. The lightweight graph has 2,649 nodes and 3,393 structural/provisional topic edges. All 149 pages are represented. Page 103 required a whole-page fallback because Docling omitted its contents; it remains flagged for layout and dependency review. Nine oversized source chunks use retrieval windows while preserving their complete text for assembly.

The remaining page misses are G009 (PDF 102), G010 (122), G015 (21) and G021 (70). Improve source dependencies and compare on independently reviewed cases before enabling technical answers. Section parents are context objects; `parent_procedure_id` is still null until procedure boundaries and warning/prerequisite scope are reviewed. Resolve every evidence ID together with its index version and source checksum.

The choice is provisional. Reconsider the embedding model if reviewed evidence recall, warm latency, memory or cost worsen. Reconsider reranking if it improves required-evidence recall without violating latency and cost limits. Original manual checksum, parsed document, model revisions, actual dependency versions, configurations, index artifacts and pipeline versions are recorded in each snapshot.

The selected snapshot and Qdrant vectors are held privately in GCP; source and code are stored in the private GitHub repository. The service serves immutable vectors and rejects anonymous requests, mismatched source/index IDs and invalid vectors. Cold starts restore existing vectors from Cloud Storage. Live service verification is recorded in `cloud/live_smoke.json`.

TRD v0.3 dependency fields are now returned alongside the actual typed evidence objects. Missing/unreviewed dependency sets remain insufficient, and source-review gaps are explicitly not rider-resolvable. Registry authoring, independent approval and the integrated eligibility controller remain later work. This schema update reuses the existing document vectors.
