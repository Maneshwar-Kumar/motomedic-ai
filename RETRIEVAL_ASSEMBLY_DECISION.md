# Owner-manual retrieval and evidence assembly

Updated 9 October 2026. TRD v0.4 is authoritative for design and technical contracts; source_manifest.json governs unresolved manual fit and rights.

## Historical local baseline

Use the supplied Royal Enfield New Himalayan 450 owner's manual only, locked to SHA-256 `CF221A29E2F9CD5AF6E80A99774A697C814E8EDA661C27D72E519D8A7E80DA89`. Keep the existing 153 page-linked chunks and local 96-dimensional LSA vectors as the offline baseline. Rank with dense cosine similarity and BM25, fuse with reciprocal rank fusion, optionally reorder the first ten candidates using local query-term coverage, then attach full source pages and one-hop agent-checked topic links. Store vectors in a local NumPy array for this small corpus; a vector database is an operational option when scale or hosting needs justify it.

## Adopted hosted build direction

On 2026-10-09 the project owner specified that the build and operating environment must be online and that the TRD governs the approach. The local NumPy index and scripts above are provisional diagnostics, not the intended deployment. The hosted system should provide the source registry, versioned index and evidence store, retrieval service, session controller, answer gate, Streamlit UI, tests and telemetry online. TRD v0.4 calls this versioned hosted ingestion performed ahead of rider requests. Keep the manual private until display and hosting rights are confirmed.

The owner subsequently agreed that the manual should be embedded once per version. The intended online execution is therefore a versioned cloud ingestion job followed by reuse of its immutable index for rider turns. Query embeddings and optional cross-encoder scores are computed for each new rider query; document embeddings are rebuilt only when the manual checksum or indexed pipeline version changes. The owner states that the manual is publicly available; display and hosting terms remain a separately tracked manifest field.

The second pass is a cheap lexical reranker, **not** a cross-encoder. This describes the local baseline only. The hosted implementation now has the TRD v0.4 conditional cross-encoder scheduling contract; current unreviewed bundles skip it. The seven links in `reviewed_graph_links.json` are useful navigation context, not verified OEM prerequisite or next-step instructions. The automatically inferred same-section edges are excluded from evidence expansion.

## Boundary before generative answering

The bundle from `retrieve_evidence.py` is candidate evidence. It reports unconfirmed edition and variant fit and unverified procedure, warning, table, figure and prerequisite coverage. It sets `may_generate_procedural_advice` to false. A later claim verifier and rider-facing answerer must not treat retrieved text or scores as approval to advise. The diagnostic controller must choose a documented eligible step from reviewed evidence before generation; an LLM may only phrase that choice and cite immutable source IDs.

## Evidence and reversal triggers

Structural validation passes for 149 pages, 153 chunks and the source checksum. On 27 in-sample draft reference cards, retrieval plus checked-link expansion contains every cited page in 23 cases. G006, G009, G012 and G027 still miss required pages. The same 23 cases are complete with and without the local reranker, so there is no measured reason yet to prefer it. These cards are not independently reviewed or held out; no answer-quality claim follows from this result.

Hosted MiniLM/BGE comparisons have since completed; BGE M3 is the selected candidate. Compare off/always/conditional on independently reviewed held-out cases before a release claim. Preserve the local result as historical diagnostics. Add typed parent procedures and mandatory warning/table/figure dependencies after visual page review; until then, keep procedural generation blocked. Confirm edition, variant, source rights and OEM service route before a public demo.

## Current contracts and progress

Hosted ingestion and embedding comparisons are complete. The selected BGE M3 index index_a3282c4d98cf54595e4ba168 has 532 search chunks and 277 section parents at a 1,024-token budget. Authenticated Cloud Run Qdrant serves immutable vectors from private Cloud Storage with min zero and max one instance; cold starts restore vectors without reparsing or re-embedding. The recorded backend smoke report passes 11/11 checks. Rider UI, integrated eligibility controller and gated generator remain pending; may_generate_procedural_advice stays false.

Use dense cosine retrieval plus BM25 and RRF, initial parent/dependency assembly, source and applicability checks, at most one exact-ID recovery for approved missing dependencies, and at most one conditional cross-encoder attempt for uncertain ordering. Reassemble while retaining mandatory evidence. Missing review must not trigger reranking. Conditional is the normal policy; off and always_diagnostic are ablations. Current unreviewed bundles skip reranking and block technical generation.

The deterministic controller evaluates approved manual-derived and versioned product-policy predicates as TRUE, FALSE or UNKNOWN using typed facts and explicit units. FALSE blocks a dependent step; UNKNOWN withholds it and permits one reviewed source-derived question only if the rider can resolve the fact. An unresolved action never becomes a normal observation. Eligibility is separate from complete evidence and final claim validation. Optional models may propose observations or rank already eligible candidates; they cannot authorize actions.

Section parents are contextual candidates. Independent review must establish procedure boundaries and approve StepDefinition, ApplicabilityRule and per-step dependency manifests against the original pages. A missing, empty, stale or unapproved dependency set cannot establish sufficiency. PDF page 103 has a flagged whole-page text/image fallback after Docling omission. Confirm year, market, variant, edition, source URL, display/hosting rights and the OEM service route before public advice.

Keep final statuses SUPPORTED, AMBIGUOUS, UNSUPPORTED, SAFETY_STOP and SYSTEM_ERROR distinct. A known applicable safety stop retains its verified warning even if another component fails; otherwise a required operational failure is SYSTEM_ERROR. Rider-resolvable missing facts yield AMBIGUOUS. Established source gaps, unsupported requests and exhausted paths yield UNSUPPORTED after bounded recovery, with verified OEM support. Never ask the rider to resolve missing source warnings, table headers or review decisions. SUPPORTED requires both deterministic and semantic claim validation after controller selection.

Exact reviewed paths are keyed by manual checksum, confirmed variant, intent/relevant symptoms, typed outcomes, flow/controller and policy versions, with prompt and approval dependencies. Draft, stale and mismatched entries miss closed. Changes to rules, review, dependencies or policy invalidate affected cache entries and cases. Manual checksum, parser/chunker or embedding changes create a new index version; unchanged document vectors are reused for retrieval-policy changes.

See the reconciliation change record in 04_To_Build_Evaluation_Decisions.docx for prior and updated choices.
