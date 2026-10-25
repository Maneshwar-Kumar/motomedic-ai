# Hosted components

Follow the [TRD](../docs/TRD.md), [architecture](../docs/ARCHITECTURE.md) and [TODO](../TODO.md).

| Area | Location |
| --- | --- |
| Answer path: section index, retrieval, assembly, template and gate, Haiku call, ledger, delivery | [grounded_generation/](grounded_generation/) |
| API, worker dispatch, store and production wiring | [arm_a/](arm_a/) |
| Read-only Qdrant wrapper | [qdrant/](qdrant/) |
| Qdrant export of an index's stored vectors | [export_qdrant.py](export_qdrant.py) |
| Billing stop guard | [budget_guard/](budget_guard/) |
| Recorded deployed resources | [deployment_status.json](deployment_status.json) |

The serving image loads the frozen section index from `build/section-index` and verifies every file hash at startup. It never parses or embeds the manual. Dense search runs over the index's pinned vectors in the image unless `MOTOMEDIC_QDRANT_URL` points at a hosted Qdrant collection exported from the same index. The hosted Qdrant currently holds the earlier index, not this one.

There is one `claude-haiku-5-5` call per turn, at effort high, with the system prompt cached for 5 minutes. A deterministic gate releases the answer. There is no verifier, correction round, retry or fallback model. The call reserves one slot in the existing shared ledgers (USD1, 100 attempts, the applied 2,000,000-token ceiling). Unused or uncertain reservations stay charged.

The recorded lifetime allocation is INR2,700, with alerts at INR1,350/2,160/2,700 and billing disconnection at INR2,540. Treat receipts as snapshots and verify the current state before any operational change. Nothing here authorizes deployment, billing or ledger changes; never restart stopped billing without the owner.
