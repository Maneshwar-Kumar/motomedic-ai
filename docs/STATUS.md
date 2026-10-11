# Implementation status

Baseline before reset: commit 997a21e22625ec5b972a66f38df898e2f41315bb, 11 October 2026. The fresh [TRD](TRD.md) is the target; this status describes existing code.

| Component | Existing evidence | Remaining gate |
| --- | --- | --- |
| Ingestion/index | Hosted Docling/BGE M3, BM25, 532 chunks and 277 parents. | Complete source-context review and durable loading; retain flagged page 103. |
| Dense serving | Qdrant infrastructure exists; current answer path computes NumPy similarity. | Authenticated Qdrant request path and readiness. |
| Hybrid scheduling | Concurrency and RRF exist. | Conditional recovery/reranking for ordinary Q&A without legacy step requirements. |
| Source assembly | Exact v3 and later context approvals exist. | Useful independently complete objects and mandatory dependencies within token bounds. |
| Generation/verification | Private draft and separate strict verification exist. | Useful real complete/partial answers and measured verifier errors. |
| History | Typed state infrastructure exists. | Topic-aware short follow-ups and unresolved outcomes in ordinary Q&A. |
| Delivery | Fixtures cover saved/streamed/recovered equality. | Durable worker, terminal reconciliation and deployed browser recovery. |
| Fallback | Evidence-only Haiku adapter and serving cost guard exist. | Correct counting, whole-turn capacity and authorized activation after quality acceptance. |
| DevOps | Private infrastructure and receipts exist. | Durable inputs, exact image promotion and one current provider-free CI path. |

The retained [v8 report](../reports/grounded_generation/v8/REPORT.md) records 103 runtime/UI software tests plus five packaging integrity tests. Its real Haiku run released zero technical answers and answered 0 of 4 clearly answerable/partially answerable turns. Three exceeded the 8,192-token input bound before drafting. These are failed quality results.

This reset updates documentation, navigation, contents and branches. [TODO](../TODO.md) defines the runtime repairs and live acceptance gates.
