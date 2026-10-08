# Owner-manual retrieval and evidence assembly

## Decision for the current prototype

Use the supplied Royal Enfield New Himalayan 450 owner's manual only, locked to SHA-256 `CF221A29E2F9CD5AF6E80A99774A697C814E8EDA661C27D72E519D8A7E80DA89`. Keep the existing 153 page-linked chunks and local 96-dimensional LSA vectors as the offline baseline. Rank with dense cosine similarity and BM25, fuse with reciprocal rank fusion, optionally reorder the first ten candidates using local query-term coverage, then attach full source pages and one-hop agent-checked topic links. Store vectors in a local NumPy array for this small corpus; a vector database is an operational option when scale or hosting needs justify it.

## Online build direction

On 2026-10-09 the project owner specified that the build and operating environment must be online and that the TRD governs the approach. The local NumPy index and scripts above are provisional diagnostics, not the intended deployment. The hosted system should provide the source registry, versioned index and evidence store, retrieval service, session controller, answer gate, Streamlit UI, tests and telemetry online. The TRD calls PDF parsing and embedding an offline ingestion pipeline in the sense of work performed before a rider request. Keep the manual private until display and hosting rights are confirmed.

The owner subsequently agreed that the manual should be embedded once per version. The intended online execution is therefore a versioned cloud ingestion job followed by reuse of its immutable index for rider turns. Query embeddings and optional cross-encoder scores are computed for each new rider query; document embeddings are rebuilt only when the manual checksum or indexed pipeline version changes. The owner states that the manual is publicly available; display and hosting terms remain a separately tracked manifest field.

The second pass is a cheap lexical reranker, **not** a cross-encoder. A cross-encoder remains a candidate experiment. The seven links in `reviewed_graph_links.json` are useful navigation context, not verified OEM prerequisite or next-step instructions. The automatically inferred same-section edges are excluded from evidence expansion.

## Boundary before generative answering

The bundle from `retrieve_evidence.py` is candidate evidence. It reports unconfirmed edition and variant fit and unverified procedure, warning, table, figure and prerequisite coverage. It sets `may_generate_procedural_advice` to false. A later claim verifier and rider-facing answerer must not treat retrieved text or scores as approval to advise. The diagnostic controller must choose a documented eligible step from reviewed evidence before generation; an LLM may only phrase that choice and cite immutable source IDs.

## Evidence and reversal triggers

Structural validation passes for 149 pages, 153 chunks and the source checksum. On 27 in-sample draft reference cards, retrieval plus checked-link expansion contains every cited page in 23 cases. G006, G009, G012 and G027 still miss required pages. The same 23 cases are complete with and without the local reranker, so there is no measured reason yet to prefer it. These cards are not independently reviewed or held out; no answer-quality claim follows from this result.

Next compare pretrained embeddings, no rerank and a cross-encoder on independently reviewed cases. Replace the local baseline only if complete evidence recall improves without unacceptable latency or cost. Add typed parent procedures and mandatory warning/table/figure dependencies after visual page review; until then, keep procedural generation blocked. Confirm edition, variant, source rights and OEM service route before a public demo.
