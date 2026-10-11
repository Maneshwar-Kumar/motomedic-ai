# Exact approved policy-caveat validation

All 125 hosted software checks passed.

Targeted hosted regression: 14/14 passed, compared with 0/14 in the preserved baseline.

## Change

Technical claims retain OEM evidence, applicability, mandatory warnings, claim mappings and immutable page citations. Exact policy-only caveats can use their approved, intact PRODUCT_POLICY references. Approval is bound to the same selected record and exact wording. Policy IDs cannot become manual citations, cover mandatory manual warnings or authorize a changed technical claim. Arm A and finite approved safety wording use this allowance; the B generator remains strict.

Both runs used identical raw questions and the same immutable manual/index. Targeted pauses were seven seconds after each completed case (minimum 7.000212 seconds); no retries or model-provider calls. This is hosted real-retrieval core validation, not production HTTP, browser, Gemma or full adaptive-dialogue testing.

## Comparison

| Record | Expected | Baseline | Candidate | Passed |
|---|---|---|---|---|
| GEN012 | SUPPORTED | SYSTEM_ERROR | SUPPORTED | True |
| GEN015 | SUPPORTED | SYSTEM_ERROR | SUPPORTED | True |
| GEN025 | SUPPORTED | SYSTEM_ERROR | SUPPORTED | True |
| GEN027 | SUPPORTED | SYSTEM_ERROR | SUPPORTED | True |
| GEN029 | SUPPORTED | SYSTEM_ERROR | SUPPORTED | True |
| GEN030 | SUPPORTED | SYSTEM_ERROR | SUPPORTED | True |
| GEN032 | SUPPORTED | SYSTEM_ERROR | SUPPORTED | True |
| GEN035 | SUPPORTED | SYSTEM_ERROR | SUPPORTED | True |
| GEN039 | SUPPORTED | SYSTEM_ERROR | SUPPORTED | True |
| GEN040 | SUPPORTED | SYSTEM_ERROR | SUPPORTED | True |
| GEN042 | SAFETY_STOP | SYSTEM_ERROR | SAFETY_STOP | True |
| EXP010 | SUPPORTED | SYSTEM_ERROR | SUPPORTED | True |
| EXP024 | SUPPORTED | SYSTEM_ERROR | SUPPORTED | True |
| EXP041 | SUPPORTED | SYSTEM_ERROR | SUPPORTED | True |

## Limits and retained failures

The complete baseline source-backed result was 61/92. Only the 14 selected caveat failures were rerun. 17 other baseline source failures remain open; this targeted result is not a new full-corpus pass rate. The 69 policy/outage fixtures still need separate trusted-event injection testing. Existing quality holds and conservative question selection remain active.

The candidate is implemented and validated in a separate hosted build. The deployed service remains on the baseline image.

## Reproducible evidence

The first candidate attempt passed 123/124 checks and stopped on an outdated GEN025 rejection assertion. It is preserved in `../policy_caveats_v1/`. Version 2 retains the runtime code, preserves scope/injection checks and validates the approved caveat stream explicitly.

- `preparation.json`: exact candidate bindings, owner authorization and baseline hash.
- `build_result.json`: hosted completion receipt.
- `software_checks.json`: hosted software-check summary.
- `comparison.json`: per-record before/after checks and remaining failures.
- `partial_results.json`: complete targeted events and retrieval evidence.
- `summary.json`: paced runner summary.
