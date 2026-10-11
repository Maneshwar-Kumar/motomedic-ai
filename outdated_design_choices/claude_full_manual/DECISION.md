# Rejected: cached full-owner-manual context with Claude

**Status: OUTDATED / REJECTED. Decision date: 11 October 2026 (Asia/Calcutta).**
The owner instructed us to stop pursuing this architecture because the observed
handling quality was too low. Preserve the experiment; do not tune it, rerun paid
calls or restore its workflows without a new owner instruction. This decision
supersedes the historical experiment report's suggestion to retain it as a candidate.

## Design that was tested

Convert the complete 149-page Royal Enfield Himalayan BS6 owner's manual with
Microsoft MarkItDown, put the full Markdown into Claude's context, and reuse it
through five-minute prompt caching instead of retrieving small evidence bundles.
Use the cheapest supported Claude model accessible to the owner's account,
selected by free model discovery and token counting: **Claude Haiku 5.5**.

Two arms used the same frozen Markdown and shared grounding policy:

- **A:** existing deterministic controller, typed state, approved authored wording,
  constrained composition and semantic verification over Markdown page contexts.
- **B:** Claude manages intent, dialogue, state, answer selection and stopping.

Eight existing regression cases were replayed twice. Each arm produced 20 rider
turns; the experiment made 28 inference calls. Repeat turns do not create 40
independent cases. These are smoke results, not held-out release accuracy.

## Observed metrics

| Measurement | Cached manual + controller (A) | Cached manual, Claude managed (B) |
| --- | ---: | ---: |
| Complete golden handling under original strict rubric | 9/20 = **45%** | 5/20 = **25%** |
| Expected response-route agreement | 13/20 = 65% | 11/20 = 55% |
| All emitted technical clauses and conditions supported | 20/20, includes abstentions | 13/20 = 65% |
| Source-safe handling under original review | 20/20, includes abstentions | 12/20 = 60% |
| All physical citations supported, per technical output | 5/5 = 100% | 7/20 = **35%** |
| Required warnings/conditions complete, per applicable output | 5/5 | 7/10 |
| Scripted adaptive turns completely handled | 6/6 | 0/6 |
| Repeated completed unresolved actions / unresolved inferred normal | 0 / 0 | 0 / 0 |
| Warm complete response with model calls, median | 6.17 s, n=3 | 6.16 s, n=19 |
| All complete responses with model calls, median | 7.10 s, n=4 | 6.17 s, n=20 |
| Estimated Claude inference cost | $0.01761245 | $0.03511945 |

Total token-based cost was **$0.0527319**. There were **26 cache hits and two cache
writes**. The all-cache-miss preflight upper bound was $0.2772935. Caching reduced
cost by 75.4% against pricing the same observed token usage without caching, but
there was no uncached latency control. A speed advantage was not established.
Arm A's 16 zero-model-call responses had median 0.0054 s; many were abstentions,
so this must not be presented as fast generated-answer performance.

### Scoring correction preserved from the owner

The owner accepted a concise manual-backed checklist as a valid response format.
The original experiment instead selected atomic no-start case EXP047, with the
expected question "Are the lights dim or is the horn weak?" Its strict handling
rubric also required that dialogue route. Therefore **45% and 25% are original
golden-contract compliance scores, not percentages of factually correct answers**.
Several steps in one response are not inherently inaccurate. No checklist-aware
rescoring was conducted; do not invent an adjusted accuracy score.

The independent citation errors, missing conditions/citations, conversion gaps
and unstable next-step selection remain distinct observations. Citation counts
are per-output, not per-claim precision. A's 5/5 citation score covers only the
technical outputs it released and does not compensate for low answerable coverage.

## Why the tested choice was rejected

1. **Having the entire manual in context did not ensure correct grounding.** B
   sometimes used printed page labels as physical PDF page numbers. Its repeat
   mirror answer cited PDF page 11 instead of physical page 13. Only 7/20 technical
   outputs had fully supported physical citations.
2. **Conversion lost necessary structure.** MarkItDown retained all 149 page
   markers but left page 103 empty and damaged oil, suspension and troubleshooting
   table associations. A appropriately withheld several answers, reducing coverage.
   The original PDF still contained relevant evidence; this was not proof of
   absent OEM guidance.
3. **Verification and dialogue were unreliable.** A's first mirror answer was
   rejected by a model verifier even though its distance caution was supported;
   the same repeat passed. B's final turn-signal response escalated in one pass
   and introduced a hazard-light branch in the other. Both remembered the failed
   action; the issue was different next-step selection, not loss of attempt history.
4. **Extra instructions need their own evidence and conditions.** Some B responses
   added starting or oil-level procedures with incomplete conditions or citations.
   This concern is separate from the owner's acceptance of checklist formatting.
5. **Cheap caching did not meet the quality objective.** The generated warm medians
   were about 6.2 s and complete handling remained low in this smoke suite. Low
   cost alone was insufficient to adopt the tested configuration.

This rejects this project's tested full-manual Claude configuration. It does not
claim that every full-context system or every Claude model necessarily fails.

## Contrast with the original architecture

Retain the TRD v0.4 architecture: versioned **Docling** ingestion, typed source
objects and parent/child chunks, **BGE M3 + BM25** hybrid retrieval, bounded reviewed
dependency recovery/conditional reranking, deterministic typed session state and
eligibility, then deterministic and semantic claim/citation gates. Reuse the
immutable manual/index; do not substitute a cached Markdown prefix for evidence.

The repository contains the following original-architecture measurements:

| Original measurement | Recorded number | What it establishes |
| --- | ---: | --- |
| BGE M3 hybrid assembled every cited page | **23/27 = 85.2%** | Draft in-sample retrieval page coverage; not final-answer accuracy |
| BGE M3 hybrid warm retrieval p95 | **0.390 s** | Retrieval on hosted-build CPU; excludes model loading, API, generation and final validation |
| BGE M3 with always-on cross-encoder | **22/27 = 81.5%; 2.997 s retrieval p95** | Historical ablation; conditional reranking remains the TRD policy |
| Frozen 161-case source/authored-answer judge: initial grounding | **159/161 = 98.8% PASS** | Historical static review, not runtime performance; two initial issues and later scoped hazard corrections are preserved |
| Same frozen judge: overall quality | **149/161 = 92.5% PASS**, 12 REVISE; mean **4.553/5** | Authored/source quality review, not a matched eight-case model accuracy score |
| Audited original-index runtime comparison, Gemma 26B, three cases × three variants | **8/9 SUPPORTED**, 1 SYSTEM_ERROR | Nine runtime cells; supported status is not independent accuracy and failure is retained |
| Runtime component-selection variant | **3/3 SUPPORTED; 9.44 s** median completion | Three samples, including conservative admission waits |
| Runtime short-generation variant | **3/3 SUPPORTED; 19.93 s** median completion | Three samples, including conservative admission waits |
| Runtime verified-stream-block variant | **2/3 SUPPORTED; 49.89 s** median of successful completions | Failed cell excluded from completion median and separately recorded at 50.11 s |

The runtime sample was GEN003, EXP003 and GEN026, run **38080802638**. It reused
the original index and used Gemma `gemma-4-26b-a4b-it`, not Claude. Provider cost
for the original runtime is not verified; do not label it free or invent a cost.
Startup (42.38 s) and pretrial cooldown (60 s) are excluded from those turn timings.
Conservative provider admission waits are included, so these latency numbers
cannot isolate architectural compute speed or establish superiority.

**These are not matched denominators, sources, models or scoring methods.** Do not
write "original 98.8% accuracy versus Claude 25% accuracy", compare 0.390 s retrieval
with 6.16 s full-response time, or claim production acceptance. All 161 scoped
content approvals are approval decisions, not a 100% runtime accuracy metric.
The owner chose to retain the original architecture despite these measurement
limits and stop spending effort on the cached full-manual alternative.

## Evidence and archive

- [Raw Claude run](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38083290522), execution commit `638ef4f428ac457fa858829c528e1af9725a6b80`.
- [Frozen outputs](experiment_results.json), [independent source adjudication](output_adjudication.json), [timing/cost metrics](comparison_metrics.json), [token ledger](request_ledger.json).
- [Original retrieval diagnostic](../../index_benchmark.json) and [index decision](../../HOSTED_INDEX_DECISION.md).
- [Original frozen 161-case judge](../../human_review/llm_judge_161/results.json).
- [Original runtime result](../../reports/architecture_run_38080802638/architecture_comparison.json), [independent audit](../../reports/architecture_result_independent_audit_v3.json), [timing analysis](../../reports/architecture_timing_analysis_v3.json).
- [Machine-readable decision and evidence hashes](decision_record.json).

All raw Claude outputs, evaluator bindings and converted-manual bytes are retained.
Paths inside historical JSON and workflow commands describe the original execution
location. The archived `.yml.disabled` files are provenance, not active jobs. No
Claude calls, deployment, billing or credential changes were made to archive this
choice. Existing unrelated architecture work is preserved.
