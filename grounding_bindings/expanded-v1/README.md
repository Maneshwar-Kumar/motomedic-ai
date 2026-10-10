# Completed 150-record agent claim-to-evidence support review

Completed 10 October 2026 using the owner's human_review/subagent_feedback.md. All 100 GEN and 50 EXP records have an explicit agent support-review disposition. This finishes the pending agent editorial support work. It does not create independent human/source approval or authorize runtime answers.

The review covers 371 exact answer sentences, all 100 conditional branch/source-scope spans in the EXP cards, the GEN conditions/warnings/scenario context, and relevant original-page continuations. Each answer sentence now has its own selected immutable manual objects and/or versioned policy references. Tables retain headers/cells and row roles. Seventeen original full-page renders were visually inspected. Supplementary original-PDF page evidence is explicitly outside the selected index and is not runtime-approved.

## Results and corrections

The original frozen records contain 339 supported answer claims, 28 discourse sentences and four findings. At record level, 146 pass this agent review and four require correction. All four corrected candidate answers have also been written and source-mapped; the producer's frozen records and catalogue remain unchanged.

| Record | Finding | Corrected candidate |
| --- | --- | --- |
| GEN057 | Internal NOT_APPLICABLE enum exposed to the rider. | Plain-language description; retain the typed outcome internally. |
| GEN058 | Re-asks which symptom returned after the rider specified the same symptom. | Preserve the symptom, customer-reported resolution and earlier attempts; no automatic repeat. |
| EXP027 | Interprets the printed warm-to-indicator wording as a wear threshold. | State the scheduled-check requirement and unclear threshold; route assessment to service. |
| EXP024 | Interprets the printed sealer-container wording as sealed container. | Answer the mixing/specification question without filling instructions or container interpretation. |

corrected_candidates.json contains the four fixes. candidate_grounding_fixtures.json contains all150 candidate answers with those replacements, source maps, original producer hashes, accepted feedback, warnings, applicability and conditional dependencies. Every record remains source-held for runtime use. support_review.json preserves the original findings and exact source locators.

Ten integrity and fail-closed regressions passed: record/claim coverage, immutable inputs, exact character offsets including CRLF, citation existence, source-text integrity, policy/OEM separation, preserved holds, correction coverage and blocked runtime promotion. These tests do not measure semantic-verifier accuracy. The semantic work here is the explicit agent editorial adjudication, not a model benchmark. This chat authored the earlier bundles and reviewed them; it is not an independent reviewer identity.

## Preserved limits

The first50 historical inventory remains35 agent passes,12 checksum-attestation holds and3 source gaps. Twelve fresh content-bound agent attestations are available in legacy_attestation_remediation.json. They bind exact final drafts, manual checksum and completed review digest. They do not rewrite old attestations, authenticate another actor or clear producer-owned holds. The missing agent paperwork here is completed without requiring new owner annotations.

EXP027's original threshold ambiguity, EXP032's flagged indexed page103/procedure boundary and EXP040's first-notch/third-notch conflict remain preserved. EXP032 and EXP040 correctly abstain; their source gaps do not make their abstention answers unsupported. Original page103 text was readable despite a PDF decompression warning; the indexed omission and procedural approval are not silently repaired. EXP024's container wording remains a clarification requirement for any future filling instruction; its corrected lookup avoids that interpretation. Page118 washing prose uses separately identified original-PDF candidate evidence. Page117's merged32psi cell was visually checked across both tyre columns and loading rows.

No source ledger, active registry, exact cache, shared controller/provider, deployment or billing setting was changed. Provider calls and token spend were zero. Formal source, applicability, warning/prerequisite, figure/procedure and scoped display-rights decisions still govern live eligibility. Complete dialogue accuracy, Gemma quality and independent verifier calibration remain unmeasured. These feedback-tuned records are regression material, not a held-out set.

## Files and reproduction

- support_review.json:150 original-record adjudications and371 claim-specific source maps, hashes, branch context and findings.
- reviewed_sources.json:immutable index objects, versioned policy/owner-feedback objects and original-PDF supplements; private engineering material.
- corrected_candidates.json:four corrected answers and source maps.
- candidate_grounding_fixtures.json:150-record source-gated candidate evaluation package.
- legacy_attestation_remediation.json:twelve new agent attestations; historical holds retained.
- support_validation.json:ten passing integrity regressions and measurement limits.
- first50_audit.json, claim_bindings.json, bound_sources.json, validation.json:earlier audit/authoring evidence, retained as history. Their NOT_EVALUATED status describes that earlier stage; current status is in status.json and support_review.json.

Run from the workspace root:

```text
python grounding_bindings/expanded-v1/review_support.py
python grounding_bindings/expanded-v1/test_support_review.py
```

Revalidate affected decisions when producer/manual/index/policy/accepted-feedback hashes change. Do not regenerate unchanged completed work on every heartbeat. Only eligible source-approved cases may enter bounded live Gemma evaluation.
