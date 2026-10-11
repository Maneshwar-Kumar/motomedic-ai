# Open manual Q&A: draft, verify, stream

Owner decision: 11 October 2026. This decision supersedes method restrictions in TRD v0.5, the A/B exact-answer selection, and the generic-generation amendment that omitted online verification. Historical experiments and their measured results remain evidence about those versions.

The rider may ask any question about the selected bike and immutable manual. Authored questions, fact groups, canonical wording, answer scopes and StepDefinitions are not requirements for an otherwise source-supported answer, including a documented procedure. Knowledge authority is the applicable source evidence. A concise partial answer may be useful when it explicitly states what remains unsupported.

The hosted versioned Docling/BGE M3 + BM25 index and private Qdrant infrastructure remain selected. Requests reuse the immutable index. Hybrid ranking, bounded recovery and conditional reranking identify candidate passages. Source assembly retains original evidence IDs, pages, approved object bindings and applicable warning, condition, unit, table and reference context. Unreviewed parent bodies are not authorized by a reviewed label. Missing retrieval evidence is not proof that the manual contains no answer.

The drafting model receives the actual question, relevant conversation and typed outcomes, assembled source evidence and source-only policy. It produces a complete private response. There is no preliminary evidence-assessment LLM call. All server-derived conditions, warnings, citations and service-route wording are finalized before verification.

A separate call to the current authorized model evaluates the exact proposed response, question, history, claim mapping and source passages. A strict verdict records question coverage, per-claim support, omissions, conflicts and release eligibility. Exact response/evidence/version hashes bind the verdict. High confidence is not an acceptance rule. At most one corrective draft and a new verification call may follow a correctable rejection; no rejected draft reaches the rider. Timeouts, malformed output, unavailable providers, exhausted quotas and integrity failures are SYSTEM_ERROR.

Code retains selected-manual applicability, source/version integrity, citation membership, server page metadata, strict schemas, owner-bound sessions, request/rate/token/spending limits and final delivery integrity. It does not replace semantic verification. Existing exact answer caches are disabled for this integration. Prompt caching is distinct from answer authorization; current exact model/account caching is unsupported and no savings are claimed.

Optional typed troubleshooting history remains available. ACTION_COMPLETED_UNRESOLVED is never normality. A rider reporting usefulness or success does not establish technical correctness or a verified repair. Verified source-specific safety-stop precedence remains. Ordinary Q&A is not restricted by a deterministic diagnostic branch.

The response channel opens promptly with truthful retrieval, drafting and checking stages. No drafting tokens or unchecked advice are released. Only after verification, final binding checks and durable save does the backend display the verified-answer stage and stream exact slices of the accepted buffer. It does not regenerate the answer. Operation IDs, response hashes and evidence/version bindings protect replay and complete recovery after a disconnect.

SUPPORTED, AMBIGUOUS, UNSUPPORTED, SAFETY_STOP and SYSTEM_ERROR remain distinct. Rider questions resolve only relevant rider-resolvable ambiguity; extraction or review gaps are not rider tasks. The verified OEM support route is supplied where appropriate before verification. No end-user PDF, excerpts or figure crops are authorized by the source manifest.

Validation separately measures question coverage, claim support, false acceptance and false refusal against original pages independently of the serving generator/verifier. Latency records first progress, retrieval/assembly/reranking, draft, verification, correction, final checks/save, first verified answer and completion. Progress and private tokens do not count as first-answer latency. Old targets are not claimed for this pipeline without measurement.

This decision authorizes implementation and document reconciliation within existing permissions. It is not new deployment, billing or provider-spending authorization. Public access remains closed pending recorded acceptance and the applicable deployment authorization.

Implementation and validation: [current work](../../reports/grounded_generation/draft_verify_stream_v1/README.md). Frozen prior generic version: [v5 runtime freeze](../../reports/grounded_generation/v5/runtime_freeze.json). Source manifest: [source restrictions](../../source_manifest.json).
