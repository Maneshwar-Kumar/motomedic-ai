# Retrieval and source-evidence build receipt

Date: 12 October 2026. Actor: `/root/retrieval_evidence`. Label: **SYNTHETIC LOCAL, PROVIDER-FREE IMPLEMENTATION VALIDATION**. These checks establish software boundaries over the unchanged approved source/index. They do not establish factual generated-answer quality, hosted acceptance, latency, or permission to deploy.

## Implemented serving path

New version-bound modules preserve the original frozen runtime files:

- `cloud/grounded_generation/serving_baseline.py` validates the exact existing index manifest before loading models: manifest SHA-256 `665121e286a22881803ec181597e860cdec8024412dbd334b2774b509cbabfde`, index `index_a3282c4d98cf54595e4ba168`, manual SHA-256 `cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89`, 532 chunks, 277 parents, BGE M3 pinned revision/dimensions, 1,024-token chunks, 149 pages, and retained parser gap at PDF page 103.
- `serving_retrieval.py` sends the query embedding to the recorded private Qdrant endpoint using a workload identity token, concurrently with BM25. The request path has no local dense-vector similarity substitute. RRF excludes absent dense hits and zero BM25 results. Remote source/scope/chunk identities are checked against the immutable snapshot. Redirects, missing identity, malformed responses and outages fail as SYSTEM_ERROR.
- Ordinary questions use reviewed object dependencies without authored step/question matching. Assembly permits independently complete reviewed anchors inside mixed search chunks, while retaining unresolved siblings as non-rider-resolvable maintainer gaps. One bounded dependency recovery preserves the reviewed closure; conditional reranking remains bounded and cannot drop that closure. The configured assembled-hit maximum is five, remote dense candidates twenty, and expanded sparse candidates forty. Optional reranking skips overlong input without truncating the question.
- Query-only token controls remain installed. Runtime query/reranker downloads are prohibited; the production loader must supply exact pinned local assets. Answer and retrieval score cache shortcuts are disabled. Short/deictic follow-ups retain the prior rider question chain; assistant text does not become a new source fact. Original current question and full conversation still go unchanged to private drafting/verification.
- `serving_context.py` projects each complete admitted object without parser IDs, repeated coordinates, or redundant identical `orig` fields. Full table cells use field names plus positional rows, with explicit missing-field indexes. Empty, null, false, zero, spans, headers, units, captions, notes and references remain distinct. Original raw/index bytes are never changed.
- `serving_source_authority.py` binds the complete projected payload and every required warning/condition closure. Output source selection cannot discard required dependencies or display warnings.
- `serving_questions.py` wires history and new source authority. `serving_safety.py` provides a distinct exact coordinator-approved initial safety buffer and recovery validator. It binds source/record/step/dependency hashes, typed session, question/history hashes, runtime, operation and exact rendered text. It marks scoped source verification true and online semantic verification false; generated safety retains private draft/verify.

## Exact additional source/context review

The proposer inspected freshly rendered original PDF pages 18 and 64 using the PDF skill. The coordinator independently inspected the full original pages and checked immutable object/provenance/source bindings. The exact four-object fuel component scope retains the full fuel table, approximation footnote, refuel-at-earliest warning, and fuel-pump-damage warning. Unrelated tyre and USB-port material is excluded only by this separately reviewed component scope. Two warning descriptors receive additional exact source-content approval; no whole parent body, new action, adaptive transition or generated answer receives approval.

Current serving inputs:

- [proposal_v3.json](source_context_refinement_v2/proposal_v3.json), SHA-256 `405269fa7d31274a1e5c6260bbee3e762c8cf2898a5401a4f71e97e155afa1f0`.
- [independent_review_v3.json](source_context_refinement_v2/independent_review_v3.json), SHA-256 `ebfb2c39cea8d7d980a32325bc1db85448208d0e3d9dcd242eb4043f991d179d`, authority `AGENT_SOURCE_CONTEXT_REVIEW`.

The earlier approved proposal/review bytes remain unchanged as historical evidence. The v3 correction fixes Windows-default decoding in the draft proposal reader, which had introduced mojibake in an embedded descriptor. The original extracted table and frozen UTF-8 descriptor both contain valid U+00B1 (`3 L ± 0.5* L`); no raw source correction, parser repair, reparse or re-embedding occurred.

Approval is agent source/context review, not human signoff, generated-answer approval, factual acceptance, public source-display permission, or deployment permission.

## Validation

Final command used the bundled Python runtime and existing local test-only Flask dependencies (`PYTHONPATH=tmp/build-test-deps`):

```text
python -m unittest cloud.grounded_generation.test_serving_retrieval cloud.grounded_generation.test_serving_context cloud.grounded_generation.test_serving_source_authority cloud.grounded_generation.test_serving_safety tools.test_build_candidate -v
```

Result: **36 tests passed in 39.221 seconds**. Exact output: [retrieval_evidence_tests.log](retrieval_evidence_tests.log). This includes 13 synthetic retrieval tests, 5 real-source projection/baseline tests, 6 exact scoped source/context tests, 8 real-source safety-boundary tests using explicitly synthetic proof fixtures, and 4 synthetic end-to-end draft/verify/accepted-buffer integration tests.

Coverage includes authenticated RPC request/identity checks, concurrent dense/BM25 work, history chains, retrieval outage, scope mismatch, no fake zero-score candidates, open dependency recovery and conditional reranking without a StepDefinition gate, source/manifest/payload tampering, transitive mandatory closure, complete table representation, no source mutation, semantic rejection to fixed fallback, disclosed partial answers, exact final verifier buffer and exact committed-buffer replay.

All eleven current approved SAFETY_STOP records have only product-policy scope predicates. None has a reviewed manual-backed typed hazard applicability rule. The unchanged `known_safety` selector therefore activates no finite outage rescue today. Tests prove a typed ABS observation or safety-like question cannot create that missing authority. Synthetic selector substitution exercises exact source proof and wording/session/operation/runtime/source tamper rejection only; that fixture is rejected without substitution. No hazard links or successor transitions were inferred.

## Recorded v8 evidence replay and remaining gates

[evidence_projection_replay.json](evidence_projection_replay.json) replays only recorded immutable chunk IDs after implementation, with zero provider calls and no query/prompt tuning. It is evidence admission/projection regression data. It does not generate or accept held-out answers. Previous six-hit recordings differ from the new five-hit serving bound.

| Recorded case | Prior/current admitted objects | Prior/current evidence-only compact bytes |
| --- | --- | --- |
| H801 | 5 / 6 | 8,884 / 6,863 |
| H802 | 12 / 34 | 12,367 / 32,350 |
| H803 | 23 / 23 | 23,784 / 18,152 |
| H804 | 0 / 25 | 2 / 24,975 |
| H805 | 0 / 0 | 2 / 2 |

More complete evidence can increase bytes. These counts exclude policy/schema/history/final-response overhead and do not establish exact provider token fit. Authorized hosted countTokens/provider runs and the real draft/verification benchmark remain gates; complete input must fail closed rather than truncate. Live authenticated Qdrant, hosted model assets, generation-bound GCS snapshot recovery and deployed delivery were not exercised locally. Missing source-context review and PDF page 103 extraction remain maintainer gaps. The failed v8 quality and latency evidence remains intact.

This work performed no provider spending, model download/build, document ingestion, deployment, billing action, public opening, fallback activation or rider-facing source display. The source PDF, index and existing approval packages remain unchanged.
