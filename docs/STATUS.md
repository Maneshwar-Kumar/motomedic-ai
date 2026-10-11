# Implementation status

Candidate v9, 12 October 2026. The fresh [TRD](TRD.md) defines the target. The [build receipt](../reports/build/20261012/README.md) separates implementation checks from hosted acceptance.

| Component | Implemented candidate | Remaining gate |
| --- | --- | --- |
| Ingestion/index | Reuses the unchanged 532-chunk, 277-parent BGE M3/BM25 index. Generation/hash-bound GCS loading fails closed. | Authenticated object-generation receipt and hosted reload. Page 103 stays flagged. |
| Dense serving | Authenticated private Qdrant query runs concurrently with BM25; source/index membership is checked before RRF. | Live identity, model availability and Qdrant readiness. |
| Hybrid scheduling | Reviewed object closure, one bounded recovery and conditional reranking for ordinary Q&A; review gaps skip reranking. | Measured direct/follow-up evidence recall and calibrated ranking. |
| Source assembly | Independently complete reviewed anchors survive unreviewed siblings. Compact tables preserve headers, spans, units, null/absence and warnings. Four fuel objects have new exact agent source-context review. | Exact model counts and useful complete/partial answers within existing bounds. No whole-parent approval. |
| Generation/verification | Private drafting, finalized warnings/limitations/citations, separate strict verification and at most one correction. | Fresh real-provider quality and independent original-page adjudication. |
| Provider admission | Complete-request native counting, persistent whole-turn reservations and paced attempts; fallback has native counting and prepaid maximum cost. | Hosted store/quota/deadline behavior. Claude stays disabled. |
| History | Prior rider topic retained for short references; optional typed outcomes remain distinct from conversational text. | Live follow-up quality. Unresolved attempts never imply normality or verified repair. |
| Operations/delivery | Named authenticated Cloud Tasks, owned Firestore work, leases/deadlines, deduplication and terminal reconciliation. SSE reads committed buffers and exact recovery bindings. | Managed identity/IAM, deployed disconnect recovery and cold/warm latency. |
| Safety | Separate proof/precedence adapter for exact coordinator-approved initial safety scopes. Generated safety still requires the separate verifier. | All 11 current finite steps lack a manual-backed typed hazard predicate; they stay inactive. New scoped relationships and hosted recovery need separate review. |
| DevOps | Provider-free PR/main CI, immutable input inventory, image provenance checks and coordinated rollback preparation. All 64 v8 runtime bytes are preserved separately. | Hosted image build, exact image digests and compatible accepted revisions. |

The retained [v8 report](../reports/grounded_generation/v8/REPORT.md) records 103 runtime/UI software tests plus five packaging integrity tests. Its real Haiku run released zero technical answers and answered 0 of 4 clearly answerable/partially answerable turns. Three exceeded the 8,192-token input bound before drafting. These are failed quality results.

The existing machine GCP login was found after an elevated metadata check. Read-only capture verified snapshot generation `1791537775184836` and its full recorded SHA; the inherited backend image exists. No login or billing configuration was changed. GitHub still lacks the managed workload-identity variables for its optional read-only artifact workflow; machine credentials can submit the hosted build. [The build receipt](../reports/build/20261012/README.md) records subsequent image results separately from hosted answer acceptance. Provider use, deployment, public opening, fallback activation and billing changes remain separate gates. [TODO](../TODO.md) keeps those exits open.
