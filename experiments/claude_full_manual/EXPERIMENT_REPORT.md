# Cached full-manual Claude: eight-case experiment

The hosted experiment completed using Claude Haiku 5.5: eight existing cases,
two architectures, two passes, 40 rider responses and 28 inference requests.
Estimated Claude cost from complete provider usage was **$0.0527319**. Caching
worked, but neither architecture is ready to replace the existing source gates.

Both arms consumed the same unrepaired Microsoft MarkItDown conversion of the
approved 149-page Himalayan BS6 owner's manual. Arm A used the existing reviewed
deterministic controller, typed attempt history, constrained composition and
semantic verification. Arm B managed responses and dialogue through Claude.

## Accuracy

The independent original-source adjudication is recorded in
`output_adjudication.json`. Route agreement alone was A **13/20** and B **11/20**;
these figures are not technical accuracy. Complete useful handling also requires
the expected next step, supported claims, warnings, correct physical-page
citations, and the one-question dialogue contract.

| Independent original-source review | Arm A | Arm B |
| --- | ---: | ---: |
| Complete golden handling | 9/20 (45%) | 5/20 (25%) |
| Source-safe handling | 20/20 | 12/20 |
| All physical citations supported, among technical outputs | 5/5 | 7/20 |
| Required warnings/conditions complete, among applicable outputs | 5/5 | 7/10 |
| Scripted adaptive turns completely handled | 6/6 | 0/6 |
| Repeated completed unresolved actions | 0 | 0 |

Complete handling is strict: all useful required content, route, conditions and
physical citation support must pass. Source-safe abstention can pass safety and
fail useful handling. Citation figures are per-output, not per-claim precision;
Arm A's low denominator reflects its withheld responses. The eight Arm B safety
handling failures include premature/incomplete procedures and diagnostic ordering,
and must not be described as eight independently invented dangerous repairs.
Both arms retained completed-unresolved outcomes without inferring normal health.
This is independent agent adjudication, not human inspection or release approval.

Arm A preserved the unresolved attempt in both EXP003 dialogues and escalated
without repeating the failed action or treating it as a normal inspection.
Its source and dependency gates abstained on oil grade, tyre pressure and
no-start, losing coverage against the original-PDF goldens. Generic abstentions
also omitted useful explanations for accessory payload and suspension conflict.
The first mirror answer was withheld because Claude's verifier falsely rejected
the documented distance caution; the identical repeat passed. This is a model
verification failure, not a transport failure.

Arm B answered more direct lookups with the correct core facts. However, it
sometimes cited printed labels as physical PDF pages, gave extra instructions
without their necessary conditions or citations, and replaced focused no-start
clarification with a list of checks and starting procedures. Its final turn-signal
response differed between passes. Correct core facts alone do not satisfy the
evidence and dialogue contracts.

## Speed

| Timing category | Arm A | Arm B |
| --- | ---: | ---: |
| Complete response with model calls, median | 7.10 s, n=4 | 6.17 s, n=20 |
| Warm complete response with model calls, median | 6.17 s, n=3 | 6.16 s, n=19 |
| Cold complete response | 8.20 s, n=1 | 6.22 s, n=1 |
| Response with no model call, median | 0.0054 s, n=16 | None |
| Warm provider first text token, median | 2.32 s, n=7 requests | 4.54 s, n=19 requests |

Complete-response timing includes free per-request token counting and JSON
completion. A model-generated response includes sequential composition and
verification. Provider first-token timing excludes token-counting overhead and
does not represent rider display: no partial unvalidated text was displayed.
The many fast deterministic abstentions must not be represented as fast generated
answers. One cold sample per arm cannot establish a stable cold-start estimate or
p95. No uncached latency control was run, so this experiment does not establish a
causal speed gain from prompt caching. Warm generated medians exceeded five
seconds in this run.

## Zero-based cost

The free preflight selected the cheapest supported accessible model, counted
the approximately 70,617-token source/policy prefix, enumerated 14 requests per
pass, and assigned each a 1,800-token maximum output. Unknown previous responses
were budgeted using those output limits. The all-cache-miss workload bound was
**$0.2772935**, below the owner's $4 credit ceiling; no arbitrary reserve or paid
judge was added. No inference retries were made.

| Actual inference accounting | Arm A | Arm B | Total |
| --- | ---: | ---: | ---: |
| Requests | 8 | 20 | 28 |
| Estimated USD | 0.01761245 | 0.03511945 | 0.05273190 |

There were two independent 70,610-token cache writes and 26 cache hits. All 28
streams ended normally with complete usage fields and zero unknown charges.
Input tokens totalled 23,123 uncached, 141,220 cache-write and 1,835,860 cache-read;
output tokens totalled 28,817, including provider-reported thinking tokens.

At the [published rates](https://platform.claude.com/docs/en/about-claude/pricing),
the same observed input/output usage with caching disabled would cost $0.2144288.
The observed cost was 75.4% lower than that cost counterfactual. This comparison
assumes unchanged outputs and does not measure uncached runtime. These costs are
token-based estimates, not a reconciliation of the provider billing balance.
GitHub compute and existing Codex review usage are outside the Claude-credit
ledger; no new GCP workload was launched.

## Limits and decision

MarkItDown preserved all 149 page boundaries but produced an empty page 103 and
damaged several table associations. Successful conversion did not establish
complete or faithful source evidence. Both arms used the same frozen Markdown;
it was not repaired between passes.

This is a whole-architecture regression smoke comparison. Arm A has approved
authored wording, registry metadata and scripted intent selection; Arm B handles
intent autonomously. These differences prevent attributing results solely to a
deterministic controller. The fixed follow-up script is also replayed even when
Claude chooses another initial response. Eight cases with repeat passes remain
eight cases, not 40 independent samples. No public demo, new source approval or
adaptive release approval follows from this experiment.

Keep cached full-manual Claude as an inexpensive candidate. Retain deterministic
state and citation/evidence gates. Before expanding this candidate, repair and
version the conversion associations, fix physical-page citation handling and
evaluate verifier false rejections. A clean source-equivalent ablation and held-out
cases would be needed to establish accuracy or latency superiority.

## Reproduction and evidence

- [Hosted experiment](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38083290522), execution commit `638ef4f428ac457fa858829c528e1af9725a6b80`.
- [Free preflight](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38083290534).
- [Hosted conversion](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38081614839).
- `rider_inputs.json` was supplied to the runners; `evaluator_goldens.json` was loaded only after runtime calls.
- `experiment_results.json` and `request_ledger.json` preserve the hosted outputs and token accounting.
- `comparison_metrics.json` is reproduced with `python experiments/claude_full_manual/summarize_results.py`.
- Four offline boundary tests passed locally and in the hosted run. These are software tests, not source accuracy checks.
- Source PDF SHA-256: `cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89`.
- Markdown SHA-256: `a0e33d2fc89623425f9777c4acfff6ce1dfe5426df2fe25fae84e60c212c9e29`.
