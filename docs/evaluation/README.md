# Evaluation and approvals

## Exact reviewed scope

Start with the [v3 release review README](../../human_review/agent_release_161/README.md), [release report](../../human_review/agent_release_161/coordinator/RELEASE_REPORT_v3.md) and [root validation](../../human_review/agent_release_161/root_validation_v3.json). These identify what was approved and what remains excluded. Preserve all exact files and bindings in place.

## Draft and historical cases

| Dataset | Purpose |
| --- | --- |
| [Atomic dialogue cases](../../golden_dialogues.md), [JSON](../../golden_dialogues.json) | Original 37 draft entry/lookup cases; not a blanket release golden set |
| [Reference answer cards](../../golden_qa.md), [JSON](../../golden_qa.json) | Earlier 27 compound retrieval probes; not atomic entry prompts |
| [Draft exact cache](../../provisional_golden_cache.json) | Draft paths that must miss closed for release |
| [Provisional diagnosis flow](../../diagnosis_flow.json) | Prototype branching counterpart |

## Results

Use the [reports guide](../../reports/README.md) to select the relevant version. Keep raw results, reviews, approval records and interpretation separate. In-sample cited-page recall, strict handling, matched answer accuracy and field repair success are different measures.

Existing `test_*.py` files remain at the root because hosted workflows and reviewed runtime bundles name them. UI tests live in `rider_ui/tests/`. Prefer the named hosted verification workflow for the subsystem you change; avoid provider runs or re-embedding for a documentation edit.


## Subsequent question-core validation

The [161-case question-core baseline](../../reports/arm_a/golden161_validation_v1/README.md) and [targeted policy-caveat candidate report](../../reports/arm_a/policy_caveats_v2/README.md) preserve distinct tested runtime versions. Read the [policy-caveat validation scope](../architecture/POLICY_CAVEAT_VALIDATION_20261011.md) for claim-policy handling and acceptance limits. Candidate evaluation is separate from installed runtime and broader browser/adaptive/vision acceptance.
