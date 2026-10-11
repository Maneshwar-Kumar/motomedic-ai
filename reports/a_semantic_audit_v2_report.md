# Exact A output semantic audit, 11 October 2026

All three existing A output bundles passed the removed semantic verification step in a fresh, bounded Gemma 26B verifier-only run. No answer was regenerated. Each initial/repeat pair has the same exact delivered-text hash, source, required meaning, role, verifier policy and schema; three checks therefore cover all six original deliveries.

| Existing output | Claims supported | Claims complete | Unsupported additions | Cited PDF page | Verdict |
|---|---:|---:|---|---:|---|
| GEN003 mirrors | 2/2 | 2/2 | false | 13 | VALID_ACCEPTANCE |
| EXP003 signal cancellation | 2/2 | 2/2 | false | 31 | VALID_ACCEPTANCE |
| GEN026 clock settings | 2/2 | 2/2 | false | 48 | VALID_ACCEPTANCE |

The raw outputs have supported=[true,true], complete=[true,true], and scalar unsupported_additions=false for every bundle. There were zero valid rejections, malformed schemas or operational failures in this verifier run. [Claim-level results, evidence IDs, citation mappings, exact hashes and provenance](a_semantic_audit_v2_conclusion.json) retain the complete audit trail.

## Execution and accounting

[Hosted audit run 38126896735](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38126896735) used reviewed commit 4c673c8a30a6dc9507a407f7ed0cb8a47b15867d, gemma-4-26b-a4b-it, minimal thinking and the original 400-token limit. All 48 hosted offline checks passed before provider access. Three requests returned HTTP200, with no retries, fallback, composition, ingestion or embedding. Fresh v2 engineering review, coordinator approval and read-only budget proof are retained separately.

Provider wall time was 3.034 seconds total; admission waits were 57.970 seconds and pretrial cooldown 60.000 seconds. Individual provider times were approximately 1.023, 1.004 and 1.007 seconds. Usage totalled 3257 input and 75 output tokens. Input reservations 4691/4754/3856 used conservative byte accounting; the third call waited 48.995 seconds for the rolling 12000 reservation allowance. These are experiment safeguards, not verified account quotas or app latency measurements.

The first engineering job [38126540537](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38126540537) failed an offline NumPy import before its provider step, which was skipped. It made zero calls and has no semantic verdict. Its job record and v1 review/approval remain intact. V2 pinned NumPy 2.4.6, independently confirmed in the original hosted install log; the original three verifier input hashes did not change. Combined v1/v2 usage remains three provider calls.

Budget proof confirmed main billing enabled, inference billing disabled, live stop guard ready with 10–600 second retry delivery. No billing or deployment setting changed. The provider allocation is free-only; instantaneous main-project spend and account-wide free-tier availability remain unknown.

## Meaning and limits

This establishes that these exact A outputs would pass the specified semantic check. It does not prove general A accuracy, calibrated independent judging, held-out performance, full adaptive transitions, general vision support or deployment readiness. Same Gemma model family was used for selection and this audit. Deterministic source, scope, eligibility, warnings, dependencies, citations and save-before-delivery gates remain mandatory. A may stream only complete exact reviewed units; B retains its semantic verifier, and C remains excluded from the current UI.

Original wire citation bytes were redacted: citation count and validity/closure flags remain in the old run. The audit reconstructs the exact required references from the unchanged signed registry/source; all six delivered-text hashes match. No wider citation delivery or public PDF/excerpt rights are claimed. Original benchmark, source approvals and other chats' UI/DOCX edits were preserved.

The three-call allocation is exhausted. The dedicated experimental GitHub workflow was disabled after completion to prevent another dispatch; [execution receipt](a_semantic_audit_v2_execution_receipt.json) records its disabled state. A future audit requires a fresh exact review and allocation.

The generic preflight helper retains an inherited calls_per_adapter=2 receipt field. The dedicated v2 budget, coordinator approval and actual provider adapter authorize three requests, and the run consumed exactly three; the generic receipt field is descriptive helper metadata and did not govern this audit allocation.
