# MotoMedic execution plan

Fresh baseline: 11 October 2026. Follow [PRD](docs/PRD.md), [TRD](docs/TRD.md) and the [architecture diagram](docs/ARCHITECTURE.md). Check an item only after recording its result. Parallel work is explicitly paired as `a` and `b`; each pair joins before the next numbered step.

The first two hours are a repository and design reset. The owner clarified the deliverables as fresh PRD, TRD, architecture diagram and step sequence. Runtime replacement and live answer acceptance are subsequent gates.

## First two hours

| Step | Time from start | Work | Depends on | Exit evidence |
| --- | --- | --- | --- | --- |
| 1 | 0–20 min | Inventory local changes, remote/default branches, dependencies, exact source approvals and other active work. Save recoverable dirty/untracked work and branch tips. | None | Snapshot path/hash, inventory and cleanup retention rules. |
| 2a | 20–55 min | Write fresh PRD: manual-only open Q&A, useful complete/partial answers, separate verification, fallback/error messages and measurable acceptance. | 1 | Reviewable `docs/PRD.md` separating evidence from requirements. |
| 2b | 20–55 min | Write fresh TRD: versions, Qdrant/BM25 concurrency, reranking, complete evidence, provider capacity, verification and durable streaming. | 1; runs with 2a | Reviewable `docs/TRD.md` with data/API/failure contracts. |
| 3a | 55–80 min | Produce the diagram and ordered checklist; reconcile PRD/TRD terminology and decisions. | 2a and 2b | Diagram and sequence agree with the fresh contracts. |
| 3b | 55–80 min | Remove obsolete active files and unsupported branches using the retention inventory; preserve manual/source approvals and current failure evidence. | 1; runs with 3a | Cleanup diff and retention receipt; recovery preserved. |
| 4a | 80–105 min | Validate links, retained dependencies, baseline checks and absence of active retired-architecture references. | 3a and 3b | Passed checks and explicit remaining runtime limitations. |
| 4b | 80–105 min | Prepare one coherent GitHub default-branch update with exact inputs and recovery information. | 3a and 3b; runs with 4a | Reviewable commit/diff and verified remote tips. |
| 5 | 105–120 min | Publish authorized cleanup/design changes, remove obsolete remote branches, verify local/remote equality and hand over implementation steps. | 4a and 4b | Commit URL, branch receipt and explained remaining changes. |

- [x] Step 1: recovery and retention evidence recorded.
- [x] Step 2a: fresh PRD completed and reconciled.
- [x] Step 2b: fresh TRD completed and reconciled.
- [x] Step 3a: diagram and sequence validated against fresh contracts.
- [x] Step 3b: local active-tree cleanup completed with recovery preserved.
- [x] Step 4a: links, dependency closure and appropriate checks passed or limitations recorded.
- [x] Step 4b: GitHub update prepared against verified branch tips.
- [x] Step 5: GitHub cleanup and final comparison recorded.

Reset completed: 4,297 active files removed, the two superseded branches removed locally and remotely, main consolidated, exact bindings retained, and 103 hosted provider-free checks passed. See [cleanup and validation receipt](reports/reset/20261011/README.md). Runtime implementation steps below remain open.

Timeboxes are estimates, not a promise of a deployable agent in two hours. This reset does not authorize provider spending, live-service changes, billing changes or public access. Check existing permissions against each exact subsequent action.

## Implementation sequence after the reset

Current candidate v10.10 addresses a real native-count blocker with reversible JSON formatting only. The v10.8 follow-up's complete-source verifier prefix counted 17,318 tokens against Google's 16,000 input TPM; the hosted check made no generation or reservation and retained the ledgers. V10.9 CI, images and private API/worker/UI readiness passed after the startup fix, but its unchanged prompt representation cannot resolve that count failure. Preserve both versions. The new codec must retain every source/history value and relationship, pass exact roundtrip checks, then receive fresh hosted counts and useful-answer acceptance before public opening.

Current candidate v10.9 corrects only the startup cache-label/routing guard after8backend/worker failed before index/models/providers. Preserve8CI/build/deployment/count/source receipts; model/source/index/budget behavior is unchanged. New9freeze/build and exactprivate readiness precede useful-answer/rollback/public gates; uploaded8source_v5 is preserved and9uses source_v6/grant_v6.

Current candidate v10.8 repairs only CI test selection after v10.7's missing original-index fixtures; serving behavior is unchanged. Preserve the7freeze/build/failure receipts and do not deploy7images. OrdinaryCI selects explicit index-free paired/routed/projection classes; full original-index checks and live source-reviewed acceptance remain required. New8freeze/builds/native counts/quality/rollback/public gates are pending.

The 12 October v10 public evaluator supersedes v9.1. Frozen v10.6 binds 532 inputs and the pinned original index; CI/images/private readiness passed, but actual native-count preflight failed and no paid v10.6 Q&A was submitted. Approved v10.7 retrieval/history repairs and the [latest model scope](reports/public_evaluator/20261012/owner_model_scope_v1.json) are in progress: enforce a 100-word rider maximum, permit large applicable evidence, and route complete requests at the 8,192-token threshold to Gemma draft/Haiku verify or Haiku draft/Gemma verify. Final tests/freeze/builds and selected-role native counts remain pending; semantic projection is unimplemented. No frozen bytes change. Immutable v10.5's unbuilt reference failure, v10.4's six SYSTEM_ERROR cases and prior cache/image/shell evidence remain preserved. [Current status](docs/STATUS.md) separates code from acceptance. [Owner scope](reports/public_evaluator/20261012/owner_scope_v1.json) and [credential approval](reports/public_evaluator/20261012/owner_credential_scope_v1.json) authorize bounded implementation/validation; billing, allocations, availability fallback and source display remain unchanged.

The v9.1 [build receipt](reports/build/20261012/README.md) preserves its 341 inputs, hosted backend/UI builds and 198 provider-free CI checks. Those results do not validate changed v10 inputs. V10.3 hosted builds/cache, v10.4 hosted builds/private shell and v10.6 hosted builds/private readiness succeeded; preserved preflight and six-case quality failures remain open. V10.5 was never built because its reference failure was caught first. New v10.7 builds, fresh useful-answer quality, public-browser operations and current compatible rollback remain pending. Implementation notes below do not check off their joint live exit gates.

### 6. Establish one immutable serving baseline

- [x] **6a — Source and index:** validate manual checksum, scoped approvals, parser/chunk/index versions, evidence IDs and mandatory dependencies. Use durable GCS artifacts with generation/hash checks rather than expiring Actions artifacts. Exit recorded in [hosted source validation](reports/build/20261012/hosted_source_validation_v9_1.json): exact generation/SHA, all 212 original index hashes, original scoped source reload and 36 synthetic checks. Page 103 and unapproved context gaps remain explicitly flagged maintainer work.
- [ ] **6b — Runtime and CI:** v10.6 freezes 532 inputs; hosted CI and both images passed with strict source/image binding. Immutable v10.5's incomplete reference remains unbuilt. Complete compatible backend/UI/worker rollback and current release acceptance. Exit: reproducible build receipt, CI rejection of altered bindings and rollback for the same release.

**Concurrency:** 6a and 6b run together after step 5 and join before step 7. Reuse unchanged immutable artifacts; do not reparse or re-embed per rider request.

### 7. Repair retrieval and operation state

- [ ] **7a — Hybrid retrieval:** retrievalv5 connects authenticated Qdrant dense and concurrent BM25, filters source/index, retains deictic follow-up topic, uses RRF and honest bounded recovery, and conditionally reranks observed ordered distinct-parent rank disagreement. Final-ranked anchors receive their reviewed dependency closure; only validated gap obligations persist from the initial pool. A gap neither invents nor suppresses a real trigger when reviewed anchors exist. Complete hosted direct/follow-up/RPC acceptance. Exit: applicable evidence is retrieved; matching/missing ranks and source-review gaps cause no false rerank or rider question.
- [ ] **7b — Durable state:** code implements owned sessions, optional typed outcomes, deduplication, named tasks, fenced leases, terminal reconciliation and exact saved-response recovery. Deploy a dedicated private worker separate from API/SSE capacity. Exit: hosted duplicates/disconnects do not repeat paid calls or strand `RUNNING` work.

**Concurrency:** 7a and 7b run together after step 6. Keep `ACTION_COMPLETED_UNRESOLVED` distinct from observed normality. StepDefinitions and authored question IDs are not general Q&A prerequisites.

### 8. Admit complete evidence within the budget

- [ ] Accept final-ranked approved-anchor/dependency assembly against hosted source-reviewed cases. Preserve conditions, warnings, units, table headers, references, validated gap obligations and server page metadata at reviewed scopes; exclude unapproved parent bodies. Large applicable evidence is allowed; semantic projection remains unimplemented.
- [ ] Enforce the same 100-word rider-question rule in API/UI: accept 100, reject 101 before retrieval/reservation and never truncate. Arbitrary manual-supported wording remains allowed.
- [ ] Verify complete native-counted selected-role requests on the hosted account. At or below 8,192 draft tokens use Gemma draft/Haiku verify; above route to Haiku draft/Gemma verify, with complete finalized verification still counted. Pin native metadata/windows and enforce actual throughput: the [quota readback](reports/public_evaluator/20261012/provider_quota_summary_v1.json) records Gemma 16K input TPM on both existing projects but not the key's project association. Preserve [v10.6 failed native-count evidence](reports/public_evaluator/20261012/hosted_runs/cabcd939-5006-4f5e-b4ee-99dd139d2110/count_receipt.json): five useful drafts exceeded the former 8,192 cap, two synthetic verifier bodies exceeded tokens and four exceeded bytes before counting; zero generation/reservations and unchanged ledgers. New-role count preflight is not factual acceptance or a guarantee about an unknown finalized response. Native-window/quota/budget overflow remains `SYSTEM_ERROR`; never silently discard mandatory context.
- [ ] Verify phased pacing/monetary admission for both selected pairs: three initial attempts, then at most three conditional correction attempts only after fresh admission. Existing 100 attempts/999,200 reserved tokens andUSD1 stay permanent; no refund/reset. Preserve event/attempt/token charges when sealing only unused pacing permits. Bind six-case measured native forecasts and reread ledgers before each case; remaining planned initial phases plus that case's conditional envelope and three maximum measured initial envelopes must fit. Those retain one public/two human engineering envelopes, not arbitrary future affordability. Stop before provider work if insufficient. Availability fallback remains disabled.

**Depends on:** 7a and 7b. **Exit:** separately versioned repairs for the recorded v8 brake-fluid, bore/stroke, USB and low-fuel failures, with independently checked complete evidence and bounded prompts. Quota failure is never described as missing manual information.

### 9. Integrate drafting, verification and saved delivery

- [ ] **9a — Answer path:** validate both size-selected draft/verifier pairs over actual question/history/evidence. Finalize warnings, limitations, citations and service wording before the other model verifies. Bind the route, both exact role/model contracts and response/evidence/history/runtime identities; permit one correction plus fresh verification. Exit requires independently adjudicated useful complete/partial/follow-up answers.
- [ ] **9b — Delivery and provider path:** validate implemented progress, saved accepted-buffer streaming, recovery and ownership on deployed v10. [Historical verifier cache proof](reports/public_evaluator/20261012/cache_probe_capability_v2.json) records 6,113 five-minute policy/evidence cache-write then cache-read tokens for its bound role/schema; new selected-role usage still needs evidence. Question/history/answer remain dynamic, with no padding or answer caching. The joint delivery gate remains open. Fixed fallback/errors carry no technical chunks. Selecting Haiku by request size does not activate the separate disabled availability fallback.

**Concurrency:** 9a and 9b run together after step 8. **Joint exit:** accepted/saved/streamed/recovered hashes match; no rejected tokens escape; malformed/outage/quota/integrity failures are `SYSTEM_ERROR`; unsupported, safety and ambiguity remain distinct.

### 10. Independently evaluate quality and operations

- [ ] **10a — Answer quality:** review fresh direct, partial, follow-up, table/unit, warning, unsupported and safety cases against original pages independently of serving models. Separate tuning/held-out cases. Measure question coverage, all-claim support, false acceptance/refusal, complete-evidence recall and citation support. Workflow success is not answer-quality success.
- [ ] **10b — Failure, latency and cost:** test injection, wrong selection, missing dependencies, overflow, provider/store outage, replay, concurrent turns and disconnects. Separate cold/warm timings, especially first verified answer. Record retrieval, draft, verification, correction, save and completion, provider usage, estimated cost and cost per correctly handled case.

**Concurrency:** 10a and 10b run together after step 9. **Exit:** explicit quality/operational acceptance for the same frozen runtime. Zero unsupported released technical steps is mandatory. A run releasing zero technical answers cannot establish factual-support accuracy.

### 11. Complete the authorized public text evaluator

- [x] Exact public frontend/private backend/worker, credential setup and bounded hosted validation authorization recorded in the two owner receipts above. Preserve INR2,700/INR2,540 guards, disabled inference billing, existing allocations, source display and disabled fallback.
- [ ] Build immutable v10 backend/UI images, bind managed secrets/identities, verify private Qdrant and Firestore readiness, and deploy compatible UI/backend/dedicated-worker revisions with exact rollback recorded.
- [ ] Test a fresh public browser: challenge/cookie/WebSocket access, direct and partial answer, streamed follow-up, unsupported, safety/ambiguity, operational error and disconnect/recovery. Verify deployed image/runtime/index and both model bindings.
- [ ] Verify persistent private visitor/global issuance, proof replay rejection, request/provider limits, retention/deletion and display restrictions; record the public evaluator URL and remaining limitations.

**Depends on:** successful 10a and 10b for the frozen candidate; authorization is recorded. Private deployment may be staged for hosted validation before publishing the completed evaluator. **Exit:** reproducible public-browser acceptance, measured latency/cost, rollback and the working public URL within its recorded scope. Existing private retrieval deployment does not establish v10 acceptance.

### 12. Add optional optimizations and modalities

- [ ] **12a — Optimization and tuning:** after the required v10 caching proof in step 9b, measure paired latency/cost savings without changing answer authority. Compare reranking variants on separate tuning/held-out cases. Gemma cache support remains unsupported; no unmeasured savings claim.
- [ ] **12b — Photo, then voice:** add bounded ephemeral uploads and observation-only vision with uncertainty; exclude hidden-fault diagnosis. Reuse text evidence/verification. Add voice only with editable transcript confirmation. Verify privacy/deletion and modality quality before activation.

**Concurrency:** optional optimization and modalities may run together after accepted text in step 11 under their applicable scope/spending. The owner's requested verifier caching is already a required evaluator gate in step 9b; photo/voice remain separate.
