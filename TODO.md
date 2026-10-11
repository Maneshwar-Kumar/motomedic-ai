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

The 12 October v10 public evaluator supersedes v9.1 as the current candidate. Current revision v10.4 repairs external readiness routes and awaits freeze/build acceptance; immutable v10.3 preserves its 525 direct inputs, successful image/cache receipts and failed health preflight. It implements authenticated Qdrant/BM25 retrieval, distinct-parent rank-disagreement reranking, Gemma drafting, a different cached Haiku verifier, follow-ups, dedicated-worker durable processing and a public signed-cookie/proof gateway. [Current status](docs/STATUS.md) separates code from acceptance. The [exact public-evaluator scope](reports/public_evaluator/20261012/owner_scope_v1.json) and [credential approval](reports/public_evaluator/20261012/owner_credential_scope_v1.json) authorize necessary deployment, identity/secret setup and bounded hosted validation; billing, allocations, fallback and source-display restrictions stay unchanged.

The v9.1 [build receipt](reports/build/20261012/README.md) preserves its 341 inputs, hosted backend/UI builds and 198 provider-free CI checks. Those results do not validate changed v10 inputs. V10.3 hosted builds and actual cache creation/read succeeded; its [health preflight failed](reports/public_evaluator/20261012/reserved_health_path_failure_v1.json) before questions or providers. V10.4 builds, fresh quality, public-browser operations and rollback remain pending. Implementation notes below do not check off their joint live exit gates.

### 6. Establish one immutable serving baseline

- [x] **6a — Source and index:** validate manual checksum, scoped approvals, parser/chunk/index versions, evidence IDs and mandatory dependencies. Use durable GCS artifacts with generation/hash checks rather than expiring Actions artifacts. Exit recorded in [hosted source validation](reports/build/20261012/hosted_source_validation_v9_1.json): exact generation/SHA, all 212 original index hashes, original scoped source reload and 36 synthetic checks. Page 103 and unapproved context gaps remain explicitly flagged maintainer work.
- [ ] **6b — Runtime and CI:** v10.4 readiness-route repair awaits freeze/build; immutable v10.3 retains 525 inputs and successful hosted image bindings. Provider-free PR checks, dependency locks and strict build/promotion binders are implemented. Complete current hosted image/provenance checks and exact compatible backend/UI/worker rollback. Exit: reproducible build receipt, CI rejection of altered bindings and rollback receipt for the same release.

**Concurrency:** 6a and 6b run together after step 5 and join before step 7. Reuse unchanged immutable artifacts; do not reparse or re-embed per rider request.

### 7. Repair retrieval and operation state

- [ ] **7a — Hybrid retrieval:** code connects authenticated Qdrant dense search and concurrent BM25, filters source/index, retains follow-up topic, uses RRF and bounded dependency recovery, and conditionally reranks observed ordered distinct-parent rank disagreement. Complete hosted direct/follow-up/RPC acceptance. Exit: applicable evidence is retrieved; matching/missing ranks and source-review gaps cause no false rerank or rider question.
- [ ] **7b — Durable state:** code implements owned sessions, optional typed outcomes, deduplication, named tasks, fenced leases, terminal reconciliation and exact saved-response recovery. Deploy a dedicated private worker separate from API/SSE capacity. Exit: hosted duplicates/disconnects do not repeat paid calls or strand `RUNNING` work.

**Concurrency:** 7a and 7b run together after step 6. Keep `ACTION_COMPLETED_UNRESOLVED` distinct from observed normality. StepDefinitions and authored question IDs are not general Q&A prerequisites.

### 8. Admit complete evidence within the budget

- [ ] Accept the implemented compact approved-anchor/dependency assembler against hosted source-reviewed cases. Preserve conditions, warnings, units, table headers, references and server page metadata at reviewed scopes; exclude unapproved parent bodies.
- [ ] Verify complete native-counted Gemma and Haiku requests on the hosted account, including policy/schema, question, relevant history and evidence. Overflow is `SYSTEM_ERROR`; never silently discard mandatory context.
- [ ] Verify implemented persistent whole-turn pacing/monetary admission on the hosted store. The existing 100-slot allocation admits at most 12 conservative eight-slot turns from a fresh ledger, shared with validation; it never resets or refunds unused/uncertain slots. V10.3 seals only its own never-consumed future pacing slots at turn end so they do not delay the next question; all allocation/event charges remain. Consumed/uncertain slots and sealing outages stay active. Haiku uses the unchanged USD1 guard; fallback remains disabled.

**Depends on:** 7a and 7b. **Exit:** separately versioned repairs for the recorded v8 brake-fluid, bore/stroke, USB and low-fuel failures, with independently checked complete evidence and bounded prompts. Quota failure is never described as missing manual information.

### 9. Integrate drafting, verification and saved delivery

- [ ] **9a — Answer path:** validate implemented Gemma drafts against the distinct Haiku verifier over actual question/history/evidence. Finalize warnings, limitations, citations and service wording before verification. Bind both model contracts and exact response/evidence/history/runtime identities; permit one correction plus fresh verification. Exit requires independently adjudicated useful complete/partial/follow-up answers.
- [ ] **9b — Delivery and provider path:** validate implemented progress, saved accepted-buffer streaming, recovery and ownership on deployed v10. [Hosted exact-schema cache proof](reports/public_evaluator/20261012/cache_probe_capability_v2.json) records 6,113 five-minute policy/evidence cache-write then cache-read tokens; question/history/answer remain dynamic, with no padding or answer caching. The joint delivery gate remains open. Fixed fallback/errors carry no technical chunks. Selecting Haiku as verifier does not activate the separate disabled availability fallback.

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
