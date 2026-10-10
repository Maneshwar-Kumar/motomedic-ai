# Cached full-manual Claude experiment

Private engineering experiment requested by the owner. Both arms use the same
immutable owner's manual converted by Microsoft MarkItDown, the same cheapest
supported Claude model, and the same cached full-Markdown source.

- Arm A: deterministic controller retains typed eligibility, warnings, attempt
  history, claim checks and stopping rules.
- Arm B: Claude manages dialogue, eligibility and stopping through instructions;
  external evaluation observes the original output without correcting it.
- No production architecture, source approval or deployment is changed.
- No end-user PDF, excerpt or image delivery is authorized.

## Hosted conversion

`.github/workflows/convert-manual-markitdown.yml` runs conversion on GitHub Actions
and saves a private artifact. It does not use an LLM, any API key, GCP or embeddings.
The converter verifies the approved PDF checksum and preserves all physical page
boundaries. The manifest records page extraction coverage and tool versions.
Figures, table layout and warning scope require separate checks; successful text
extraction is not full evidence approval.

## Eight-case evaluation scope

Use current approved object bindings, not the older D-series draft schedule:

| Record | Purpose |
| --- | --- |
| GEN003 | Direct mirror lookup |
| lookup_oil_grade | Specification and warning |
| lookup_tyre_pressure | Table values, units and warnings |
| GEN004 | Missing accessory payload specification |
| EXP040 | Conflicting rear suspension source statements |
| EXP047 | Atomic no-start clarification |
| EXP048 | ABS safety handling and prompt injection |
| EXP003 | Three-turn clarification, action and unresolved-feedback flow |

Seven initial responses and three EXP003 responses give ten rider-visible turns
per arm per pass. Provider requests are counted separately: deterministic routes
may need no model call and composition/verification may require multiple calls.
The version 3 source approvals and newer scoped runtime approval govern their
exact objects only. New Claude runtime objects require fresh agent verification.
Golden expectations are evaluator-only and must not enter either model prompt.

## Zero-based budget

No arbitrary spending target or reserve. Before paid execution, count the exact
prefix, each changing input and each output ceiling with the selected tokenizer.
Budget cache writes, cache reads, uncached input, output and retries individually.
The account's $4 credit is a maximum, not the desired spend. Record hosted compute
and existing Codex usage separately from Claude credits. No paid conversion,
Claude supervisor or Claude judge is required by this preparation.

Compare accuracy against exact required claims, warnings, citations, routes and
typed outcomes, with source adjudication for disputed results. Measure cold/warm
time to first token and time to complete rider-visible response. Eight regression
cases establish a smoke comparison, not release-level or held-out accuracy.

## Secrets

Paid execution needs `ANTHROPIC_API_KEY` in the hosted runner's secret store.
Never put keys in this directory, model prompts, logs or committed files.
No provider requests have been made by the conversion workflow.
