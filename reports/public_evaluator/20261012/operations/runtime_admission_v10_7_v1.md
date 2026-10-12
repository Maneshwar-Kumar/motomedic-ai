# Synthetic v10.7 retrieval and phased admission verification

This is an engineering receipt for local provider-free checks. It establishes no
new live answer acceptance, deployment, public access, provider spending or
billing state. The failed v10.6 count-only run remains preserved.

The retrieval scheduler now finalizes the conditional rank decision before
admitting source anchors. Matching parent rankings and absent approved anchors
skip reranking; observed disagreement with approved anchors permits one rerank.
Every final selected anchor retains its complete applicable approved dependency
closure. Immutable retained hit skeletons preserve extraction/review gaps from
dropped candidates without admitting their reviewed siblings. Already loaded,
validated closure evidence no longer fabricates a recovery attempt. Explicit
topic shifts and self-contained questions search their own wording; deictic and
elliptic follow-ups expand actual prior rider questions. Composer still binds the
complete actual saved history.

Retrieval versions are `authenticated-open-hybrid-rank-disagreement-v5`,
`ordered-distinct-parent-rank-disagreement-v3`, and
`open-reviewed-anchor-authority-v4`. The index, source approvals, dependency
closure bound and mandatory warning/condition/unit obligations are unchanged.
The two retrieval/source-authority suites passed 46 synthetic checks. These
fixtures demonstrate removal of discarded-anchor dependencies and preservation
of the selected anchor's warning dependency; actual revised native counts still
require the hosted count-only job.

Serving admission now atomically reserves an initial three-slot pair: the
selected draft, its distinct verifier, and the allowed Gemma rejection retry.
Before the one permitted correction, `reserve_correction` atomically reserves
three more slots for the same operation, model roles, source binding and durable
deadline. The corrective request, rejected response binding and verdict have
separate hashes. Exhausted or uncertain correction admission ends as
`SYSTEM_ERROR`; it cannot send an unfunded correction, replay the reservation or
release rejected text. Explicit full-turn compatibility requires an explicit
flag and is separate from the production phased path.

The existing non-expiring allocation identities and prior charges are retained:
100 attempted slots and 999,200 total forecast tokens globally, and USD1 for
Haiku. No unused or uncertain slot is refunded. Confirmed unused reservations
can be sealed only for future pacing. Phase, nonce, native envelope and plan hash
mutations block permits, later reservation and pacing sealing. The initial
Haiku count headroom and known verifier prefix participate in immutable role
identity. Large evidence inputs use the model's native window; the actual
Gemma complete input additionally obeys the observed 16,000 input-token minute
quota. The conservative 61-second permit spacing remains in force.

Funding a future verifier does not establish that an unknown finalized response
will fit its actual account quota. Its unavoidable full-source/history prefix
is checked before drafting; its complete finalized request is counted again
before transmission. An oversized final verifier request fails privately as
`SYSTEM_ERROR`. Haiku native counter estimates have an explicitly reserved
initial headroom of at most 512 tokens, with actual returned usage checked
against the reserved ceiling.

Allocation version remains `whole-turn-capacity-v1`; native plan version is
`whole-turn-model-native-envelope-v1`; pacing version is
`whole-turn-sealed-unused-pacing-v3-variable-model`. The API is:

```python
admission.begin_turn(operation_identity, plan=initial_three_slot_forecast)
admission.for_model(pinned_model)(actual_input_tokens + 1800, 'generation')
admission.reserve_correction(operation_identity, plan=correction_three_slot_forecast)
admission.end_turn()
```

The admission suite passed 47 synthetic tests. Combined admission, router,
Gemma and Haiku adapter suites passed 92 tests. This includes the real router's
forecast objects through the real transactional admission guard for both model
role selections and both phases. Independent source inspection found no paid
call path that precedes its funded pair: complete finalized Gemma requests are
counted and quota-checked before permits; central Haiku checks the prepaid cost
envelope and does not reserve its monetary budget again. Each corrective body
is counted and hash-bound before its fresh reservation.

The combined index-free admission, role-router, adapter, paired/routed Composer,
lossless context codec and cross-session admission identity suites passed 118
synthetic tests. Hosted native-count and semantic acceptance remain separate
checks. Public opening still requires actual accepted outputs and the owned
operation boundary, rollback and restored readiness receipts.
