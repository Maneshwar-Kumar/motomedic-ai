# Cached full-manual Claude experiment

**OUTDATED / REJECTED BY OWNER — 11 October 2026.** This directory preserves a
historical experiment, not an active architecture candidate. Start with
[DECISION.md](DECISION.md) for the rejection, metrics and original-architecture
comparison. Raw results and source bindings remain unchanged. Workflow files were
moved out of `.github/workflows` into `workflows/*.yml.disabled`; do not run the
archived scripts or restore those workflows without fresh owner authorization.

The descriptions below record the experiment as it was executed. Original
`experiments/claude_full_manual` paths in evidence are historical provenance.

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

## Runtime comparison limits

Arm A integrates the existing reviewed controller and exact registry. Its composer
retains approved authored wording and the benchmark selects the case intent; its
semantic verifier receives only page contexts from the common raw Markdown.
Arm B receives literal rider messages and manages the dialogue independently.
This compares the complete architectures, so differences cannot be attributed
solely to the presence of a controller.

The frozen conversion has an empty page 103 and damaged table associations.
Arm A blocks oil-grade, suspension-conflict and no-start cases on conversion
review; the existing evidence gate also blocks the tyre-pressure case. These are
safe abstentions but lose answerable coverage against the original-PDF goldens.
They do not establish that the original manual lacks the relevant content.

The fixed EXP003 follow-ups are replayed even if Arm B chooses a different first
response. Report source safety and conformity to that scripted dialogue
separately. Two passes of eight existing cases are a regression smoke experiment.
Provider TTFT is separate from complete JSON response timing, and deterministic
zero-call timing is separate from model-generated response timing.
