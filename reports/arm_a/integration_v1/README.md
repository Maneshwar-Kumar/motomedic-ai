# Arm A integration run, 11 October 2026

This run executes the owner-authorized initial private rollout, then prepares the
rider API integration. It preserves peer edits and the frozen review packages.

## Bound inputs

- Shared checkout starts at `4789b18` with peer navigation/UI edits present.
- Isolated context: `build/arm-a-release-v5`, 396 bound files / 397 total.
- Release SHA256: `66fb99d81a8c7acc4a22c620aed2c028a75765ff4bcea5e96e85ea17429991b4`.
- Source approval: owner-delegated v3, exact initial-response scopes only.
- Build: `3097a211-b468-485c-b5ce-11e47aaa9fe2`, us-central1.

## Recorded progress

The exact owner-approved `roles/datastore.user` grant succeeded for
`motomedic-arm-a@motomedic-ai-20261009.iam.gserviceaccount.com` on
`motomedic-ai-20261009`. No other IAM grant is implied.

Fresh read-only preflight confirms enabled billing, the non-recurring INR2700
budget beginning 9 October, and ready live guard revision
`motomedic-budget-guard-00003-qax`, `SIMULATE=false`, `STOP_INR=2540`.
The matching Pub/Sub function trigger has `RETRY_POLICY_RETRY`. The latest guard
notification at 10:40:13 UTC reported INR0; delayed reporting does not establish
instantaneous spend or remaining credits. No stopped billing was re-enabled.

TTL enablement requests were submitted for `expires_at` in the dedicated
`arm_a_operations`, `arm_a_sessions`, and `arm_a_usage` groups. Live activation
and actual physical deletion still require evidence. Automatic review rejected
TTL on the broad shared `versions` collection group due to irreversible deletion
outside the dedicated Arm A namespace. That group remains unchanged pending an
owner decision; no workaround was executed.

## Owner retention decision, 11 October 2026

The owner now explicitly authorized fixed 24-hour session retention and automatic
deletion confined to MotoMedic-specific collections. The exact instruction is
recorded in `owner_retention_decision_20261011.json`. Generic `versions` TTL remains
disabled. The three existing dedicated TTL policies are ACTIVE; enablement of
`arm_a_session_versions` was submitted and is asynchronous. See
`ttl_session_versions_request.json` and `ttl_live_owner_approved.json`.

The isolated `build/arm-a-auth-retention-v2` context changes snapshot storage to
`arm_a_session_versions` and preserves the session's original expiry on later
saves. It also adds sanitized authentication rejection reasons while retaining
the authentication checks. Exact independent engineering review passed, with all
14 authentication/store tests passing; see `auth_retention_review_v2.json`.
Hosted build `c545b12f-227b-4adc-a9ea-33dff255a621` runs the complete regression
suite before image publication. Successful hosted tests are required for rollout.
These receipts do not establish physical TTL deletion exactly at hour 24.

Repository structure audit found two peer-created root files outside its current
allowlist (`ab30_benchmark.py`, `test_ab30_benchmark.py`); no files were moved.

## Acceptance limits

`tools/accept_arm_a_initial.py` exercises authenticated complete-unit SSE,
durable Firestore state, exact replay/recovery, payload conflicts and scope
withholding. It hashes technical text in receipts instead of retaining it in
routine logs. A live result is required before declaring acceptance. A single
measurement cannot establish p95; cold startup classification, a second valid
owner identity, TTL deletion and the full rider/browser journey are separate
checks. No answer-model calls or provider prefix cache are part of deterministic
Arm A. Photos remain disabled until hosted text acceptance.

The initial service exposes explicit reviewed records only. It must not be
advertised as the rider API's free-text/session/feedback implementation.

## Retention rollout v3

All four dedicated TTL groups are ACTIVE in ttl_live_owner_approved.json. The v2
hosted build failed only because two test fixtures were absent; no failed image
was deployed. Preserved v3 adds those fixtures with exact bindings and retains
identical app/store bytes. Independent review: auth_retention_review_v3.json.
Hosted build 528e668a-1de3-4bce-9be8-1f1fdbfae3ba succeeded with all 68 tests;
image digest sha256:32bdd105dcee611002240ec86ab7d3f78ce1b3e882bc23f7c7d89c75082b4f96.
An image-only private rollout was submitted. Latest readiness and traffic are
recorded in retention_service_live_v3.json; physical deletion is not yet measured.
The read-only expired-record inventory found zero cleanup candidates. No generic
versions policy, manual/index deletion, or billing change was performed.
Retention rollout completed: motomedic-arm-a-00002-jh2 READY, 100% traffic on the exact v3 digest, no public invoker grant. Fixed24h session/snapshot expiry and dedicated TTL are installed. Physical deletion lag and broader end-to-end rider acceptance remain separate unverified checks.
