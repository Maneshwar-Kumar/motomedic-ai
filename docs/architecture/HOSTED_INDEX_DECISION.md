# Hosted index decision and diagnostic

The current prototype uses BGE M3, 1,024-token chunk budgets, dense cosine retrieval plus BM25 with reciprocal rank fusion, bounded graph expansion, and full section context. The pretrained cross-encoder has a conditional scheduling policy under TRD v0.4. Current candidate bundles skip it because applicability and independent dependency review remain pending. The earlier always/off diagnostic showed reduced cited-page coverage and added latency when always enabled. Model weights are reused; each request computes a query vector and, when scheduled, new cross-encoder pair scores.

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

The TRD v0.3 dependency schema is returned by the recorded candidate assembly deployment; TRD v0.4 adds the authoritative eligibility and conditional scheduling contracts. Dependency fields are returned alongside the actual typed evidence objects. Missing/unreviewed dependency sets remain insufficient, and source-review gaps are explicitly not rider-resolvable. Registry authoring, independent approval and the integrated eligibility controller remain later work. This schema update reuses the existing document vectors.

## Conditional policy update 9 October 2026

The owner approved conditional reranking for uncertain candidate ordering. TRD v0.4 and the implementation distinguish that uncertainty from missing required evidence, unresolved applicability, unreviewed source dependencies, safety stops and system failures. One bounded exact-ID recovery can attach reviewed dependencies and widen the candidate pool. One cross-encoder attempt can reorder a bounded pool when rank signals indicate uncertainty. Reassembly preserves mandatory evidence; controller/claim gates remain required. Current source review gaps skip both attempts rather than reranking every insufficient bundle.

The initial trigger values are provisional and uncalibrated. No conditional-policy accuracy or TTFO improvement is claimed from the table above. Reviewed calibration and held-out off/always/conditional evaluation must record rescues, regressions, complete evidence recall, abstention, fallback rate, per-path and combined TTFO, cold starts and cost. The selected document vectors and Qdrant deployment are unchanged by this retrieval-policy update.

## Reconciliation and release boundary 9 October 2026

TRD v0.4 is the authoritative design and technical contract as of 9 October 2026. This document follows it. The approved owner manual governs motorcycle facts; source applicability, rights, independent review and release gates remain mandatory. Recorded implementation progress does not constitute release approval.

The deterministic controller evaluates approved manual-derived and versioned product-policy predicates as TRUE, FALSE or UNKNOWN using typed facts and explicit units. FALSE blocks a dependent step; UNKNOWN withholds it and permits one reviewed source-derived question only if the rider can resolve the fact. An unresolved action never becomes a normal observation. Eligibility is separate from complete evidence and final claim validation. Optional models may propose observations or rank already eligible candidates; they cannot authorize actions.

Keep final statuses SUPPORTED, AMBIGUOUS, UNSUPPORTED, SAFETY_STOP and SYSTEM_ERROR distinct. A known applicable safety stop retains its verified warning even if another component fails; otherwise a required operational failure is SYSTEM_ERROR. Rider-resolvable missing facts yield AMBIGUOUS. Established source gaps, unsupported requests and exhausted paths yield UNSUPPORTED after bounded recovery, with verified OEM support. Never ask the rider to resolve missing source warnings, table headers or review decisions. SUPPORTED requires both deterministic and semantic claim validation after controller selection.

Provisional retrieval bounds are fused pool 20, five assembled hits, recovery pool 40, rerank pool 20, 100 query/passage pairs and 256 mandatory dependency IDs. More than 256 dependencies yields SYSTEM_ERROR without truncation. Distinct-parent top-three overlap below 0.5 or relative RRF margin at most 0.05 are PROVISIONAL_UNCALIBRATED. Zero BM25 matches provide no agreement signal. Queries beyond the current cross-encoder 128-token bound skip inference with an explicit reason and retain full input. Independently reviewed calibration and held-out evaluation remain required.

Exact reviewed paths are keyed by manual checksum, confirmed variant, intent/relevant symptoms, typed outcomes, flow/controller and policy versions, with prompt and approval dependencies. Draft, stale and mismatched entries miss closed. Changes to rules, review, dependencies or policy invalidate affected cache entries and cases. Manual checksum, parser/chunker or embedding changes create a new index version; unchanged document vectors are reused for retrieval-policy changes.

The authorized private repository is Maneshwar-Kumar/motomedic-ai and the GCP project is motomedic-ai-20261009, under a US$10 project limit. The non-recurring INR800 budget starts 9 October 2026, alerts at INR400/640/800 and uses a simulation-checked live billing-disconnect guard at INR640 with retry delivery. Delayed reporting prevents an instantaneous exact cap. Do not re-enable billing after a real budget stop without owner authorization. Add per-user rate, upload and per-day spend limits before the public UI.

The updated design register and before/after record are in 04_To_Build_Evaluation_Decisions.docx. The current index and deployment are unchanged by this documentation refresh.
