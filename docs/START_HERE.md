# Start here

[README](../README.md) is the entry point. Read [PRD](PRD.md), [TRD](TRD.md), [architecture](ARCHITECTURE.md) and [TODO](../TODO.md), in that order.

The Markdown specifications are current. [STATUS](STATUS.md) separates implementation from acceptance gaps. [Reports](../reports/README.md) identify retained immutable evidence and the cleanup receipt.

The selected v10 public evaluator reuses the owner's immutable hosted index and exact source approvals. Authenticated Qdrant and concurrent BM25 feed conditional rank-disagreement reranking and complete reviewed evidence. Gemma drafts privately; distinct Claude Haiku verifies the exact finalized answer with five-minute policy/evidence-prefix caching. A dedicated private task worker saves before exact streaming, follow-ups and recovery through the public signed-cookie/proof frontend.

Code is implemented. V10.3 hosted images and actual verifier cache-write/read proof succeeded; its reserved `/healthz` preflight failed before any question/provider work. Current candidate v10.4 exposes API `/v1/health` and gateway `/health` and awaits new builds, fresh source-reviewed quality, rollback and live browser acceptance. The [evaluator scope](../reports/public_evaluator/20261012/owner_scope_v1.json) and [credential approval](../reports/public_evaluator/20261012/owner_credential_scope_v1.json) authorize this work under unchanged budgets, disabled inference billing, source-display restrictions and disabled availability fallback. Historical failures and successful build/cache receipts remain preserved; they do not close live quality gates.
