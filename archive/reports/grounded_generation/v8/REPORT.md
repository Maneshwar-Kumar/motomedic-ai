# Draft, verify, stream v8 and Haiku fallback

The pipeline and rider UI connection are implemented and committed on `codex/reviewed-evidence-controller`. Software boundary checks pass. Real-provider answer coverage failed; this version is not accepted for live technical-answer release. No deployment or GCP billing change was made.

The owner decision is recorded in [the pipeline decision](../../../docs/architecture/DRAFT_VERIFY_STREAM_DECISION_20261011.md), with [the separately authorized Haiku fallback](../../../docs/architecture/HAIKU_EVIDENCE_FALLBACK_20261011.md). Ordinary Q&A uses applicable assembled evidence rather than authored answer or step allowlists. Source approvals, history, safety, citations, conditions, warnings, exact versions and display restrictions remain enforced.

The drafting model produces a private proposed response. A separate verifier returns the strict RELEASE_COMPLETE, RELEASE_PARTIAL or SHOW_FALLBACK decision, question coverage, per-claim support, omissions, conflicts and eligibility, bound to the exact response, evidence, history and runtime. Application code performs the final checks and durably commits before it streams the saved buffer. A partial limitation and mandatory warnings are present before verification. One corrective revision is permitted. Rider-resolvable clarification and verified safety stops retain their separate routes and precedence. Operational failures remain SYSTEM_ERROR.

The UI uses this backend path for questions and follow-ups, shows operational progress, checks operation and response bindings before displaying accepted chunks, and recovers the same saved response after disconnection. Fixed fallback/error messages have no technical-answer label or answer chunks. Haiku configuration and secrets are confined to the backend; the UI has no model selector. See [the connection handover](ui_wiring/CONNECTION_HANDOVER.md), [API contract](../../../../rider_ui/API_CONTRACT.md) and [full-path software tests](../../../cloud/grounded_generation/test_ui_fallback_wiring.py).

## Software evidence

[Verifier/controller review](verified_qa_review.json) records 21 passing tests; [Claude adapter and cost guard](claude_adapter_review.json) records 13. The final [UI/provider wiring receipt](ui_wiring/validation.json) records 69 passing tests against all 64 final freeze hashes: 60 UI, 6 backend delivery and 3 full-path adapter tests. It exercises the actual composer, fallback and Claude schema/count/reservation adapter, transactional store contract, authenticated API, strict UI client, streaming and recovery with synthetic transport and zero paid calls. Earlier [UI/delivery receipts](ui_streaming/REPORT.md) remain preserved and are explicitly superseded for current runtime hashes. Together, these suites record 103 passing runtime/UI tests.

These tests cover complete and partial release, limitations written before verification, relevant but non-answering drafts, unsuccessful correction, schema/provider/quota/integrity failures, safety/clarification precedence, rejected-content isolation, durable commit, idempotency and accepted/streamed/recovered equality. They are software evidence, not factual or deployed-service acceptance.

All 64 serving objects in [the freeze](runtime_freeze.json) matched both Git HEAD and checkout before paid validation. The fallback-enabled runtime lock is `cb3ae7b2ece4086b50c5bd2c6d23f3a149e779ebb3ed16a877ef2d91bb1a8d78`; the primary-only lock differs intentionally. Exact original source approvals and the existing immutable BGE M3/BM25 index remain unchanged. No reparse or re-embedding was performed.

## Real Haiku execution and independent review

[GitHub run 38160944967](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38160944967) completed on commit `09faf7d`. The workflow's success means the validation ran and saved its results. [Independent original-page review](original_source_review/run_38160944967.md) records **FAILED_ANSWERABLE_AND_PARTIAL_COVERAGE**.

The [unaltered provider artifact](run_38160944967/claude-fallback-result.json) has SHA-256 `51dfb305db78ba0b176d15dc5f62d989e1e7225588d36ab1c257289ab19638b9`. [Independent execution recount](execution_review.json) binds the artifact, runtime and dataset and checks exact neutral wording and delivery hashes.

| Measurement | Result |
| --- | --- |
| Rider turns | 6, using fresh wording after freeze and known source facts |
| Actual Haiku calls | 3 drafts, 3 separate verifier decisions, 12 token counts |
| Primary outage | Synthetic Gemma HTTP 500; zero paid Gemma calls |
| Ordinary decisions | 3 SHOW_FALLBACK; no actual COMPLETE/PARTIAL release |
| Operational failures | 3 SYSTEM_ERROR before generation because complete contexts exceeded the 8,192-token limit |
| Technical answers released | 0 |
| Clearly answerable or partially answerable turns answered | 0 of 4 |
| Correct unsupported internal-repair handling | 1 |
| Neutral saved/delivered/recovered equality | 6 of 6; no technical answer chunks |
| Technical accepted/streamed/recovered equality | Unmeasured in this real run; software-tested separately |
| Reported token usage | 25,980 input and 2,017 output; zero cache tokens |
| Estimated usage cost | US$0.0036065, based on recorded prices and reported usage; not an invoice |
| Maximum cost reserved | US$0.0103152 against the non-recurring US$1 validation allocation |
| First operational progress | Median 0.000861 s, maximum 0.003031 s |
| Private processing excluding evaluation pacing | Median 3.209 s, maximum 11.637 s; all outcomes neutral |
| Completion including evaluation pacing | Median 33.176 s, maximum 119.564 s |
| Evaluation-only pacing | 278.880 s across calls; separate from production latency |
| Cold harness worker initialization | 41.209 s, measured separately |
| First verified technical answer / cost per correct technical answer | Undefined because no technical answers were released |

The brake-fluid, bore/stroke and USB questions had admitted source objects, but token estimates of 8,769, 9,249 and 18,255 exceeded the existing bound. They correctly became SYSTEM_ERROR rather than fallback or a claim that the manual lacked an answer. The low-fuel question had no admitted evidence although the original manual supports a useful partial answer. The first rear-brake question's frozen expected-answer metadata also overstated support for precise foot placement; the original diagram supports pedal identification. The reviewer records this adjudication without rewriting frozen cases.

The verifier wrongly classified honest nontechnical retrieval limitations as unsupported twice and added speculative or redundant omissions. Those drafts did not answer the technical question, so SHOW_FALLBACK still selected the appropriate handling for their empty admitted evidence. No supported technical draft reached this real verifier; technical factual-support, false-acceptance and false-refusal rates cannot be established from these outputs.

Source admission and context size need a separately versioned improvement and fresh evaluation before live release. A model change alone does not repair them. The current report does not claim successful technical coverage, public release acceptance or that an answer is absent throughout the manual.

## Preserved failure history and deployment boundary

Run [38160630087](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38160630087) failed its software checks before the provider-secret step because a changed frozen UI decoder was omitted from the pushed commit. It made no paid provider calls. Commits `6e84d56` and `09faf7d` corrected the omission and added a Git-blob/checkout check before provider access. Earlier v6 Gemma failures and the v6 fixed-copy encoding defect remain preserved in their versioned reports; v8 does not inherit their acceptance.

The existing Gemma workflow checks were preserved, with a separately guarded Haiku validation job added. The run used the hosted immutable index snapshot and fsync operation files. It did not measure live Qdrant RPC, deployed Firestore, browser access or Cloud Run work after disconnect. The GitHub key was used only by the authorized validation step; no key was exposed to riders, copied into Git, or transferred to GCP.

[The release-readiness audit](release_readiness/source_authority_audit.json) records historical service revisions, concrete backend/UI configuration, and the remaining image packaging, managed-secret activation, compatible revisions and live browser/stream/recovery acceptance steps. Existing historical deployed receipts do not establish v8 live operation. Deployment and billing changes require the owner's separate authorization and successful quality gates.

[The prepared backend/UI package](release_readiness/packaging/README.md) now supplies exact overlay manifests, Dockerfiles, build recipes and an offline reconstruction helper. Five integrity tests passed in addition to the 103 runtime/UI tests. It verifies all 64 frozen Git/workspace objects, 44 backend overlay objects and 18 explicit UI inputs. The inherited base-image filesystem is checked by the generated build recipe and remains unverified until a future authorized build. No image was built or run, and this preparation does not override the failed real-answer coverage gate.

The five planning Word documents were reconciled to TRD v0.6. [Final managed rendering](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38159695364) and [visual QA](../draft_verify_stream_v1/documents/visual_qa/) record 54 reviewed pages. Product design reconciliation and document rendering do not constitute source or model release approval.
