# Hosted 161-case question wiring validation

Completed all 161 records. Strict recorded checks passed 102/161; 59 records failed at least one check.

Source-backed initial questions: 61/92 passed. The other 69 records require trusted policy or failure events; raw question text matched 41/69 expected routes, but these are not injected-failure results.

## Method

The hosted job used the exact deployed backend image and release bindings, real hybrid retrieval, the Arm A question adapter, controller and display gates. Each record began with only the selected Himalayan BS6 manual confirmed. Seven-second pauses followed each completed case (observed minimum 7.000208 seconds). No retries or Gemma/provider calls occurred.

This validates the question core. It does not measure production HTTP, Firestore, browser streaming, Gemma reliability, complete adaptive dialogues or held-out accuracy. The approved corpus was used during development. No deployment or runtime tuning was made during this run.

## Source-backed results

| Expected route | Cases | Passed | Actual routes |
|---|---:|---:|---|
| AMBIGUOUS | 22 | 12 | {"AMBIGUOUS": 12, "UNSUPPORTED": 10} |
| SAFETY_STOP | 11 | 9 | {"SAFETY_STOP": 9, "SYSTEM_ERROR": 1, "UNSUPPORTED": 1} |
| SUPPORTED | 59 | 40 | {"SUPPORTED": 40, "SYSTEM_ERROR": 13, "UNSUPPORTED": 6} |

Source-backed technical responses with a wrong selected record: 0. Technical responses failing wording, citation, evidence or display checks: 0.

The four no-start records share the same input text but encode different intended branches. No case ID or hidden branch facts were supplied to the question core. Their individual mismatches remain in the results.

## Gate diagnosis

Bound metadata shows 18 failing source records contain approved policy-only caveats with no OEM evidence IDs. The current composer requires an OEM evidence ID on every claim and rejects such claims. Policy references must remain distinct from manual citations; addressing this needs an explicit runtime contract change, not fabricated citations. The runner did not capture response reason codes, so this static finding is not claimed as the sole cause of every failure. See `static_gate_diagnosis.json`.

## Recorded failures

| Record | Category | Expected | Actual | Failed checks |
|---|---|---|---|---|
| GEN012 | source_step | SUPPORTED | SYSTEM_ERROR | route_matches |
| GEN015 | source_step | SUPPORTED | SYSTEM_ERROR | route_matches |
| GEN021 | source_step | SAFETY_STOP | UNSUPPORTED | route_matches |
| GEN024 | source_step | SUPPORTED | UNSUPPORTED | route_matches |
| GEN025 | source_step | SUPPORTED | SYSTEM_ERROR | route_matches |
| GEN027 | source_step | SUPPORTED | SYSTEM_ERROR | route_matches |
| GEN029 | source_step | SUPPORTED | SYSTEM_ERROR | route_matches |
| GEN030 | source_step | SUPPORTED | SYSTEM_ERROR | route_matches |
| GEN032 | source_step | SUPPORTED | SYSTEM_ERROR | route_matches |
| GEN035 | source_step | SUPPORTED | SYSTEM_ERROR | route_matches |
| GEN036 | source_step | SUPPORTED | UNSUPPORTED | route_matches |
| GEN039 | source_step | SUPPORTED | SYSTEM_ERROR | route_matches |
| GEN040 | source_step | SUPPORTED | SYSTEM_ERROR | route_matches |
| GEN042 | source_step | SAFETY_STOP | SYSTEM_ERROR | route_matches |
| GEN043 | source_step | AMBIGUOUS | UNSUPPORTED | route_matches |
| GEN052 | trusted_policy_fixture | AMBIGUOUS | UNSUPPORTED | route_matches |
| GEN053 | trusted_policy_fixture | AMBIGUOUS | UNSUPPORTED | route_matches |
| GEN056 | trusted_policy_fixture | AMBIGUOUS | UNSUPPORTED | route_matches |
| GEN057 | trusted_policy_fixture | AMBIGUOUS | UNSUPPORTED | route_matches |
| GEN058 | trusted_policy_fixture | AMBIGUOUS | UNSUPPORTED | route_matches |
| GEN059 | trusted_policy_fixture | AMBIGUOUS | UNSUPPORTED | route_matches |
| GEN071 | trusted_policy_fixture | SYSTEM_ERROR | UNSUPPORTED | route_matches |
| GEN072 | trusted_policy_fixture | SYSTEM_ERROR | UNSUPPORTED | route_matches |
| GEN073 | trusted_policy_fixture | SYSTEM_ERROR | UNSUPPORTED | route_matches |
| GEN074 | trusted_policy_fixture | SYSTEM_ERROR | UNSUPPORTED | route_matches |
| GEN075 | trusted_policy_fixture | SYSTEM_ERROR | UNSUPPORTED | route_matches |
| GEN076 | trusted_policy_fixture | SYSTEM_ERROR | UNSUPPORTED | route_matches |
| GEN077 | trusted_policy_fixture | SYSTEM_ERROR | UNSUPPORTED | route_matches |
| GEN078 | trusted_policy_fixture | SYSTEM_ERROR | UNSUPPORTED | route_matches |
| GEN079 | trusted_policy_fixture | SYSTEM_ERROR | UNSUPPORTED | route_matches |
| GEN080 | trusted_policy_fixture | SYSTEM_ERROR | UNSUPPORTED | route_matches |
| GEN081 | trusted_policy_fixture | SYSTEM_ERROR | UNSUPPORTED | route_matches |
| GEN082 | trusted_policy_fixture | SYSTEM_ERROR | UNSUPPORTED | route_matches |
| GEN083 | trusted_policy_fixture | SYSTEM_ERROR | UNSUPPORTED | route_matches |
| GEN084 | trusted_policy_fixture | SYSTEM_ERROR | UNSUPPORTED | route_matches |
| GEN085 | trusted_policy_fixture | SYSTEM_ERROR | UNSUPPORTED | route_matches |
| GEN086 | trusted_policy_fixture | SAFETY_STOP | UNSUPPORTED | route_matches |
| GEN091 | trusted_policy_fixture | AMBIGUOUS | UNSUPPORTED | route_matches |
| GEN092 | trusted_policy_fixture | SUPPORTED | UNSUPPORTED | route_matches |
| GEN094 | trusted_policy_fixture | SAFETY_STOP | UNSUPPORTED | route_matches |
| GEN098 | trusted_policy_fixture | AMBIGUOUS | UNSUPPORTED | route_matches |
| GEN099 | trusted_policy_fixture | AMBIGUOUS | UNSUPPORTED | route_matches |
| EXP001 | source_step | AMBIGUOUS | UNSUPPORTED | route_matches |
| EXP005 | source_step | AMBIGUOUS | UNSUPPORTED | route_matches |
| EXP010 | source_step | SUPPORTED | SYSTEM_ERROR | route_matches |
| EXP024 | source_step | SUPPORTED | SYSTEM_ERROR | route_matches |
| EXP030 | source_step | AMBIGUOUS | UNSUPPORTED | route_matches |
| EXP041 | source_step | SUPPORTED | SYSTEM_ERROR | route_matches |
| EXP042 | source_step | SUPPORTED | UNSUPPORTED | route_matches |
| EXP049 | source_step | AMBIGUOUS | UNSUPPORTED | route_matches |
| EXP050 | trusted_policy_fixture | SYSTEM_ERROR | UNSUPPORTED | route_matches |
| lookup_tyre_pressure | source_step | SUPPORTED | UNSUPPORTED | route_matches |
| lookup_fan_fuse | source_step | SUPPORTED | UNSUPPORTED | route_matches |
| lookup_starter_duration | source_step | SUPPORTED | UNSUPPORTED | route_matches |
| a_fuse | source_step | AMBIGUOUS | UNSUPPORTED | route_matches |
| a_switches_on | source_step | AMBIGUOUS | UNSUPPORTED | route_matches |
| a_refuel | source_step | AMBIGUOUS | UNSUPPORTED | route_matches |
| a_raise_stand | source_step | AMBIGUOUS | UNSUPPORTED | route_matches |
| a_cool_engine | source_step | AMBIGUOUS | UNSUPPORTED | route_matches |

## Evidence

Cloud Build: `7e96828b-60e4-49fc-84db-af4cdf85f953`.

- `preparation.json`: pinned image, runner and approval versions.
- `build_result.json`: completed hosted build receipt.
- `summary.json`: runner totals and route confusion.
- `verified_results.json`: independent completeness, question hash, interval and subgroup audit; all failure details.
- `cases.csv`: compact per-record results.
- `partial_results.json`: full recorded events and retrieval/citation checks.
- `dataset_audit.json`: exact inputs and duplicate questions.
