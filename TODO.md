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

The 12 October v9 candidate implements the code for steps 6–9 and adds provider-free checks, source-context review and frozen release inputs. See the [implementation receipt](reports/build/20261012/README.md) and [current status](docs/STATUS.md). The existing machine GCP identity and immutable snapshot generation are verified. The step exits below stay open where hosted loading, image provenance or live quality/operations evidence is still required. Synthetic checks do not close those gates; no deployment or provider-spending permission is inferred.

### 6. Establish one immutable serving baseline

- [ ] **6a — Source and index:** validate manual checksum, scoped approvals, parser/chunk/index versions, evidence IDs and mandatory dependencies. Use durable GCS artifacts with generation/hash checks rather than expiring Actions artifacts. Exit: deterministic loading and an explicit review-gap inventory.
- [ ] **6b — Runtime and CI:** select one serving package/version manifest, add provider-free PR checks, bind container inputs and image digests to the release, and document exact rollback. Exit: reproducible build-input receipt and CI rejection of altered bindings.

**Concurrency:** 6a and 6b run together after step 5 and join before step 7. Reuse unchanged immutable artifacts; do not reparse or re-embed per rider request.

### 7. Repair retrieval and operation state

- [ ] **7a — Hybrid retrieval:** connect authenticated Qdrant dense search and concurrent BM25; filter selected manual/version before ranking; preserve history in the retrieval query; fuse with RRF; implement bounded dependency recovery and conditional reranking for ordinary Q&A. Exit: approved direct/follow-up evidence is retrieved, and source-review gaps trigger neither reranking nor rider questions.
- [ ] **7b — Durable state:** implement owned sessions, optional typed outcomes, request deduplication, operation leases, terminal reconciliation and exact saved-response recovery. Processing must survive browser disconnection. Exit: duplicates/disconnects do not repeat paid calls or leave operations indefinitely `RUNNING`.

**Concurrency:** 7a and 7b run together after step 6. Keep `ACTION_COMPLETED_UNRESOLVED` distinct from observed normality. StepDefinitions and authored question IDs are not general Q&A prerequisites.

### 8. Admit complete evidence within the budget

- [ ] Version a compact approved-anchor/dependency assembler. Preserve conditions, warnings, units, table headers, references and server page metadata at reviewed scopes; exclude unapproved parent bodies.
- [ ] Count the complete projected request with the exact provider's mechanism, including question, relevant history, evidence and schema overhead. If complete context does not fit, return `SYSTEM_ERROR`; never silently discard mandatory evidence.
- [ ] Reserve whole-turn token/rate/monetary capacity, including maximum permitted correction and authorized availability fallback. Retain uncertain reservations. Validation allocations are non-recurring across runs.

**Depends on:** 7a and 7b. **Exit:** separately versioned repairs for the recorded v8 brake-fluid, bore/stroke, USB and low-fuel failures, with independently checked complete evidence and bounded prompts. Quota failure is never described as missing manual information.

### 9. Integrate drafting, verification and saved delivery

- [ ] **9a — Answer path:** privately draft from actual question, relevant history and assembled evidence. Finalize warnings, limitations, citations and service wording before a separate verifier. Require strict question coverage, all-claim support, omissions/conflicts and exact response/evidence/history/runtime bindings. Permit one corrective draft plus re-verification.
- [ ] **9b — Delivery and provider path:** show operational progress, then stream only a durably saved accepted buffer. Keep fixed fallback/error messages outside technical-answer streaming. Bind token counts and budgets to the actual model; keep Claude disabled until serving activation is authorized, and allow it only for eligible primary availability failures. Validate UI recovery and ownership.

**Concurrency:** 9a and 9b run together after step 8. **Joint exit:** accepted/saved/streamed/recovered hashes match; no rejected tokens escape; malformed/outage/quota/integrity failures are `SYSTEM_ERROR`; unsupported, safety and ambiguity remain distinct.

### 10. Independently evaluate quality and operations

- [ ] **10a — Answer quality:** review fresh direct, partial, follow-up, table/unit, warning, unsupported and safety cases against original pages independently of serving models. Separate tuning/held-out cases. Measure question coverage, all-claim support, false acceptance/refusal, complete-evidence recall and citation support. Workflow success is not answer-quality success.
- [ ] **10b — Failure, latency and cost:** test injection, wrong selection, missing dependencies, overflow, provider/store outage, replay, concurrent turns and disconnects. Separate cold/warm timings, especially first verified answer. Record retrieval, draft, verification, correction, save and completion, provider usage, estimated cost and cost per correctly handled case.

**Concurrency:** 10a and 10b run together after step 9. **Exit:** explicit quality/operational acceptance for the same frozen runtime. Zero unsupported released technical steps is mandatory. A run releasing zero technical answers cannot establish factual-support accuracy.

### 11. Deploy an accepted text candidate

- [ ] Confirm current deployment/provider/IAM/spending authorization for the exact candidate. Preserve budget-stop behavior and never re-enable stopped billing without permission.
- [ ] Build immutable backend/UI images from the accepted manifest, bind secrets to managed identities, verify Qdrant readiness and Firestore permissions, and deploy compatible revisions with rollback recorded.
- [ ] Test a fresh authenticated browser: direct, partial, follow-up, unsupported, safety/ambiguity, operational error and disconnect/recovery. Verify deployed image/runtime/index bindings.
- [ ] Review public identity/access, abuse/rate/per-day spend controls, retention/deletion and display restrictions separately before publishing a rider URL.

**Depends on:** successful 10a and 10b plus applicable authorization. **Exit:** reproducible live acceptance, measured latency/cost, rollback and an approved access scope. Existing private retrieval deployment does not establish new-answer-pipeline acceptance.

### 12. Add optional optimizations and modalities

- [ ] **12a — Caching and tuning:** establish caching support for the exact authorized model/account. Preserve source/verification gates; measure reported cached tokens and paired latency/cost. Compare reranking thresholds and retrieval variants on held-out cases. Unsupported caching remains an explicit capability gap with no claimed savings.
- [ ] **12b — Photo, then voice:** add bounded ephemeral uploads and observation-only vision with uncertainty; exclude hidden-fault diagnosis. Reuse text evidence/verification. Add voice only with editable transcript confirmation. Verify privacy/deletion and modality quality before activation.

**Concurrency:** 12a and 12b may run together after accepted text release in step 11, under separately confirmed scope and spending. They are not prerequisites for fixing the current text-answer coverage failure.
