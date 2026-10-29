# Serving code

The answer path and its services. Read the [architecture](../docs/ARCHITECTURE.md) first.

| Folder or file | What it holds |
| --- | --- |
| [grounded_generation/](grounded_generation/) | The answer path:<br>- section index, top-5 retrieval, plain-text assembly;<br>- system prompt, schema and release gate (`template_answer.py`);<br>- the Haiku call;<br>- the turn pipeline (`section_questions.py`);<br>- the admission ledger and saved-view delivery. |
| [arm_a/](arm_a/) | The Flask app and production loader (`app.py`), the rider API, the Cloud Tasks worker, the Firestore store, visitor and edge admission, and the backend Dockerfile. The folder name is historical. |
| [common/](common/) | Session records, the provider error and the content hash, copied unchanged from retired root modules, so stored sessions and ledger hashes stay compatible. Also [telemetry.py](common/telemetry.py): allowlisted structured logs and spans with no rider text ([privacy](../docs/PRIVACY.md)). |
| [qdrant/](qdrant/) | The read-only Qdrant wrapper (`/health`, `/query`), for a hosted dense index. |
| [export_qdrant.py](export_qdrant.py) | Export an index's stored vectors as a Qdrant bundle; it reads section indexes too. |
| [budget_guard/](budget_guard/) | The Cloud Function that disables billing at the guard amount, with its policy test. |
| [deployment_status.json](deployment_status.json) | The hosted state as last recorded on 23 October: billing disabled, the INR3,120 budget with its INR2,960 guard, and the Qdrant service, which holds the base index only. Earlier configurations are kept under `history`. It is a record, not a live read-back. |

Tests sit next to their modules (`test_*.py`) and use synthetic data and doubles only. The serving image loads the section index from `build/section-index` and verifies every file hash at startup; it never parses or embeds the manual. Dense search uses the pinned vectors in the image unless `MOTOMEDIC_QDRANT_URL` points at a hosted Qdrant collection exported from the same index.

There is one `claude-haiku-5-5` call per turn, at effort high, with the system prompt cached for 5 minutes, and a deterministic gate releases the answer. There is no verifier, correction round, retry or fallback model, and no token ceiling. Each call reserves one slot in the 100-attempt allocation and the shared Haiku USD1 ledger, and unused or uncertain reservations stay charged. Nothing here authorizes deployment or billing changes.
