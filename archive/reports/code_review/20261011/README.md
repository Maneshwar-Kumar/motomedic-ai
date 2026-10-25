# MotoMedic code and DevOps review

Review date: 11 October 2026. The current architecture is substantially implemented on the reviewed-controller branch, but the repository does not yet demonstrate a coherent, accepted release of that architecture. Integration defects affect multi-turn retrieval, provider admission, conditional retrieval scheduling and operation recovery. Deployment tools and GitHub's default branch describe older generations.

This review covers the workspace, GitHub branches, current PRD/TRD and owner decisions, source authority, serving code, UI boundary, hosted validation records and DevOps. It adds review artifacts only. It makes no runtime, source-approval, deployment, billing or provider-spending changes. Cloud configuration files are recorded snapshots; current live GCP configuration was not queried.

## Folder and GitHub comparison

| State | Commit | Tracked files | What it contains |
| --- | --- | ---: | --- |
| GitHub default `main` | `d46f856cd04ab7b173591526a9fb21e235559506` | 61 | Older candidate retrieval implementation and planning documents; lacks the current controller, rider UI, source approvals and draft/verify/stream runtime |
| GitHub `codex/rider-ui-20261011` | `aed6f4ce5399aee4a16e4d4f7ef7b7ba1f16ab71` | 585 | Earlier rider interface and controller generation; lacks current open Q&A and Claude evidence fallback |
| GitHub `codex/reviewed-evidence-controller` and local HEAD | `09faf7dfe1865dda0a2155bb06f67fdc4fdfdbbd` | 4,567 | Current TRD v0.6 documents, approvals, open Q&A, verifier, buffered delivery and fallback adapter |

GitHub directly confirmed these branch heads. The reviewed-controller branch is 83 commits ahead of main. The two feature branches have diverged: reviewed-controller is 56 commits ahead and seven behind the rider branch. This is not evidence that all seven rider commits need copying; their final behavior must be compared individually because the reviewed branch already includes substantial UI changes.

The workspace additionally has tracked modifications to Arm A composer/questions, UI contracts and navigation, plus untracked public-edge, testing, deployment-preparation and report files. These local changes cannot be reproduced from a GitHub checkout. Untracked files may be deliberate work in progress; they are not assumed to be approved dependencies. The checked v8 runtime freeze's 64 bound files all match the workspace. That freeze does not bind every file in the folder.

Recommended repository action: consolidate reviewed changes through a PR into an agreed integration/default branch, reconcile the remaining rider-branch commits by behavior, and publish a single release manifest. Do not stage all local files, move frozen approvals, or copy historical artifacts into active runtime indiscriminately.

## Governing requirements and actual path

The reviewed local Concept, PRD, TRD and To Build documents incorporate the TRD v0.6 owner decision. [The current architecture decision](../../../docs/architecture/DRAFT_VERIFY_STREAM_DECISION_20261011.md) supersedes exact-answer-only wording, question/action catalogues, universal StepDefinitions and the no-online-verifier alternative for ordinary manual Q&A. The frozen 161-case v3 source approvals remain valid within their exact scopes. They are not blanket approval of new generated answers, every source object or public deployment.

The current serving path is `cloud/arm_a/app.py:load_production` → `rider_api.py` → `open_questions.py` → hybrid retrieval → `source_authority.py` → `verified_qa.py` draft and separate verifier → final binding checks → Firestore commit → `delivery.py` → rider SSE client. The historical `arm_a` folder name obscures this migration: production now selects the open verified composer, while the old exact composer remains for earlier fixtures.

Claude support is present. `fallback_provider.py` and `claude_provider.py` implement one availability fallback per call against retrieved evidence; production enables it only with `MOTOMEDIC_CLAUDE_FALLBACK_ENABLED=true` and a server-side secret. It is not the retired full-owner-manual Claude architecture. Quota, schema, source-integrity and semantic rejection do not select a second provider. Successful adapter execution does not establish answer acceptance or deployed activation.

## Prioritized findings

P1 means address before claiming a reliable end-to-end release. P2 means a concrete functional or operational gap that should be resolved in the next integration version. These priorities are review judgments, not claims that the defects have caused an incident.

### R1 P1 Whole-turn provider admission is incompatible with draft and verification

**Location:** [admission.py lines 27–30](../../../cloud/grounded_generation/admission.py), [provider.py reservation loop](../../../cloud/grounded_generation/provider.py), [Claude validation reservations](../../../tools/validate_claude_fallback.py).

The production admission function hard-rejects when conservative reservations exceed 10,000 tokens in a rolling minute. Each generation attempt reserves its input plus 1,800 output tokens. A legal 4,000-token draft call followed immediately by a legal 4,000-token verifier call requires 11,600 reserved tokens, so the verifier is rejected after the draft has already been paid for. Corrections and provider fallback add further attempts. Claude currently shares the same admission ledger.

An offline reproduction using the existing admission fixture accepts `5800` tokens for drafting, then rejects another `5800` with `PROVIDER_DAILY_OR_RATE_LIMIT`. The real v8 Haiku run reserved 12,034, 12,015 and 12,731 tokens for its three executed pairs. Its evaluation-only scheduler waited approximately 54–58 seconds before several calls; production does not schedule those waits.

**Improve:** account for the complete operation before starting it and schedule its bounded calls within the existing authorized quota. Measure full draft/verify/correction/fallback attempts under the actual production admission implementation. Preserve spend and quota guards; any quota change is a separate decision. Report queue time and true first verified answer latency.

### R2 P1 Retrieval loses the topic of short follow-up answers

**Location:** [open_questions.py lines 58–59 and 93–99](../../../cloud/grounded_generation/open_questions.py).

Retrieval receives only the newest query. Conversation history and typed outcomes reach drafting and verification after retrieval has finished. For “What tyre pressure should I use?” → “Solo or pillion?” → “solo”, a focused offline reproduction confirms that the retriever receives exactly `solo`. The drafter sees the original topic, but it cannot legitimately supply the missing manual evidence from model knowledge. Similar problems affect “still happens”, “yes” and references to an earlier component.

**Improve:** resolve the relevant conversation topic before retrieval and/or retain prior immutable evidence/topic bindings for a clarification. Keep the actual rider question separately for verification; source authority and scope checks still apply. Add end-to-end cases with elliptical replies, topic changes, corrections and unresolved attempted actions.

### R3 P1 Operation recovery depends on a surviving in-process worker

**Location:** [delivery.py lines 70–105](../../../../cloud/grounded_generation/delivery.py), [rider_api.py streaming work and recovery](../../../../cloud/arm_a/rider_api.py), [store.py operation state](../../../../cloud/arm_a/store.py).

Streaming starts a daemon thread. Durable saving protects a completed answer, but execution before the commit is not durable. Recorded backend configuration uses request-based CPU throttling. A disconnect or request termination therefore does not guarantee continued CPU or worker lifetime. Google explicitly cautions against background threads outside request handling under this billing mode. [Cloud Run background activity guidance](https://docs.cloud.google.com/run/docs/tips/general).

There is also a definite code-level recovery gap: the worker catches every exception and emits nonterminal `OPERATION_NOT_COMMITTED`. A known session conflict or validation failure occurs after the outer HTTP handler's conflict handling has finished; it is not persisted as `FAILED`. Recovery returns `RUNNING` until the operation expires, without a lease or reconciliation path.

**Improve:** persist typed terminal worker failures, distinguish them from uncertain commits, and introduce a bounded lease/reconciliation strategy or durable task execution. Preserve operation idempotency and avoid repeating a provider call whose result is uncertain. Test process death, timeout, commit conflict and Cloud Run disconnect behavior. Changing billing alone would not make the worker durable.

### R4 P1 Cached parsing does not prove source or parser identity

**Location:** [online_ingest.py lines 89–93 and subsequent evidence construction](../../../../ingest/online_ingest.py), [ingestion workflow lines 39–54](../../../../.github/workflows/ingest-owner-manual.yml).

The supplied current PDF is SHA-checked, but a reused Docling parse is validated only by filename. The workflow accepts a prior parse run and passes its `docling_document.json` without validating that run's parse manifest. A changed PDF under the same filename, or a parse produced with different parser/options, can be accepted and its old objects stamped with the current PDF checksum. A new index ID and cached-document hash do not prove that those objects came from the current source.

**Improve:** require and verify the cached parse's original source checksum, parser version/options and document hash before reuse. Refuse an unbound cached parse. Add a same-filename/different-checksum regression and a parser-options mismatch regression. Keep versioned ingestion ahead of rider requests.

### R5 P1 CI depends permanently on an expiring index artifact

**Location:** [ingestion workflow line 68](../../../../.github/workflows/ingest-owner-manual.yml), [verify-retrieval.yml index download](../../../.github/workflows/verify-retrieval.yml), [grounded-generation.yml index download](../../../.github/workflows/grounded-generation.yml) and other controller/benchmark workflows.

The principal workflows download the immutable index from Actions run `37908240500`, whose artifact retention is seven days. GitHub's artifact API confirms expiration at **16 October 2026, 14:39 IST**. Once it expires, clean CI jobs cannot obtain their required input, even though a durable Cloud Storage snapshot exists. [GitHub artifact lifecycle documentation](https://docs.github.com/en/actions/tutorials/store-and-share-data).

**Improve:** use the durable private snapshot as the authoritative build input, locked to its object generation, index manifest and checksums. Actions artifacts should be optional transport/cache, not the permanent registry. Test a clean build without access to the original Actions artifact.

### R6 P1 Deployment does not bind the selected image to its approval

**Location:** [connect_arm_a_ui.py lines 64–72](../../../tools/connect_arm_a_ui.py).

The deployment helper checks a fixed historical local release hash, then accepts the first image from any successful supplied build under the project's registry. It does not bind that image to the reviewed context, runtime release or selected frontend/backend kind. A successful unrelated image can therefore pass the check and be deployed to the wrong service. Registry membership and successful build status are insufficient provenance.

**Improve:** verify a service-specific release manifest, approved context hash, build provenance and exact output image digest together. Deploy a candidate revision without traffic, test the matched frontend/backend release, then promote with a recorded rollback target. Retire this helper if it is historical; current instructions should make that explicit.

### R7 P2 Conditional recovery and reranking are disconnected from open Q&A

**Location:** [open_questions.py lines 58–59](../../../cloud/grounded_generation/open_questions.py), [online_retrieve.py lines 189–198](../../../../ingest/online_retrieve.py), [retrieval_policy.py lines 58–71](../../../../ingest/retrieval_policy.py).

The open path does not supply a StepDefinition/dependency manifest. The legacy scheduler marks dependency review `MISSING` and returns `SOURCE_REVIEW_REQUIRED` before ranking uncertainty can trigger reranking or recovery. SourceAuthority subsequently assembles approved source context, but does not feed that information back to scheduling. The focused reproduction reports uncertain ranking, zero recovery attempts and zero rerank attempts. Production nevertheless eagerly loads the cross-encoder.

**Improve:** provide source-based scheduling and reviewed dependency closure for open Q&A, independently of authored answers/actions. Preserve the rule that genuinely missing review does not trigger reranking. Reassemble mandatory evidence after any reordered candidates and evaluate off/conditional/always on reviewed tuning and fresh held-out cases. Do not restore universal StepDefinition admission gates.

### R8 P2 Missing-primary configuration fallback cannot complete token checks

**Location:** [provider.py lines 61–63 and 86](../../../cloud/grounded_generation/provider.py), [fallback_provider.py lines 8–23](../../../cloud/grounded_generation/fallback_provider.py), [verified_qa.py line 205](../../../cloud/grounded_generation/verified_qa.py).

`PROVIDER_UNCONFIGURED` is explicitly eligible for Claude fallback. Gemma generation detects a missing key and can fall back successfully, but Gemma token counting lacks the same configuration check. Final presentation counting then calls the primary with no key; a 401/403 or transport failure is correctly outside the fallback allowlist and prevents verification/delivery. A mocked transport reproduction exercises the real adapters: Claude drafting succeeds, then counting fails with `PROVIDER_HTTP_401`.

**Improve:** detect missing configuration consistently in both interfaces or select the appropriate bounded token counter for the provider path. Add the complete draft/finalize/verify missing-primary-secret test. Do not broaden fallback to arbitrary authentication, quota or integrity failures.

### R9 P2 Current runtime lacks an automatic provider-free integration gate

**Location:** [grounded-generation.yml lines 2–12](../../../.github/workflows/grounded-generation.yml), [verify-controller.yml push path filters](../../../.github/workflows/verify-controller.yml).

The grounded workflow's push filter is the workflow file itself on one feature branch, with commit-message gating. The controller workflow's path list omits the new backend folders. Editing only the latest backend can therefore miss the corresponding integration suite. There is no automatic PR gate for the current complete serving path. GitHub reports `main` as unprotected; ruleset inspection was unavailable, so no broader ruleset assertion is made.

**Improve:** run provider-free backend/UI, source-authority, admission, delivery, fallback and binding tests on PRs and relevant pushes. Separate software correctness, real-provider execution and independently reviewed quality acceptance. Make the relevant checks required where the repository plan supports it. Keep paid evaluations explicitly bounded and separate.

### R10 P2 Validation's non-recurring Claude allowance resets each run

**Location:** [validate_claude_fallback.py lines 37 and 49–51](../../../tools/validate_claude_fallback.py), [v8 runtime manifest](../../grounded_generation/v8/runtime_manifest.json), [production ClaudeBudget](../../../../cloud/grounded_generation/claude_budget.py).

The v8 manifest specifies a maximum non-recurring Claude allowance of US$1. The validation harness starts with a new in-memory `money` list, enforcing at most US$1 per execution. A fresh dispatch or fresh eligible push has no cumulative ledger. Production's ClaudeBudget correctly persists an allocation without expiry, but the hosted validation does not consume that ledger. No actual budget overrun was established by this review.

**Improve:** use one durable owner-allocation ledger across authorized validation runs, keyed to the allocation and model, with atomic reservation and no retention reset. GitHub job concurrency and `run_attempt == 1` do not enforce a lifetime allowance across different run IDs.

### R11 P2 Typed feedback and known safety are not fully integrated into open turns

**Location:** [open_questions.py lines 36–37 and 58–64](../../../cloud/grounded_generation/open_questions.py), [verified_qa.py saved_view](../../../cloud/grounded_generation/verified_qa.py), [rider UI capability description](../../../../rider_ui/README.md).

Open responses always return empty public/private choices and clear pending legacy bindings. Fresh sessions begin without attempts; ordinary turns do not append typed outcomes. The existing `/feedback` interface consequently cannot collect its advertised structured outcomes from a new open-Q&A answer. Evaluation directly injects some facts, which does not establish rider ingestion. Optional legacy diagnostics are allowed by the new decision, but StepDefinitions must not be reintroduced as ordinary Q&A gates.

Separately, retrieval runs before `known_safety`. A synthetic retrieval outage confirms that an already-bound safety callback is never reached. An existing known hazard can be replaced by a generic retry-only system error before source-specific safety precedence is considered.

**Improve:** implement an optional source-bound observation/attempt ledger or correct the capability claims. Resolve corrections and unresolved actions without inferring normality. Identify known bound hazard evidence independently of candidate ranking, then separately verify the finalized safety response. Source-integrity or verifier failure must still fail closed; this is not permission to release unverified safety advice.

## Completeness and coherence against the latest requirements

| Capability | Assessment |
| --- | --- |
| Immutable manual/index reuse | Implemented; cached-parse identity and permanent CI artifact retrieval need correction |
| Hybrid dense/BM25 retrieval | Implemented; open-Q&A conditional scheduling is disconnected |
| Exact source approvals and dependency assembly | Implemented for bound scopes; absent or held source context remains a legitimate coverage limit |
| Private draft and separate finalized-response verifier | Implemented; strict structured decisions and one correction are present |
| Fixed fallback versus operational error | Implemented and distinguished; source gaps remain maintainer issues |
| Final checks, save and exact buffered stream | Implemented for successful operations; worker-loss/terminal-failure recovery is incomplete |
| Multi-turn conversation | History reaches models; contextual retrieval and typed outcome ingestion need integration |
| Claude availability fallback | Implemented, disabled by default, tested with actual hosted provider; quality/deployed activation unproven |
| Photo/voice | Disabled/deferred; expected incompleteness for the text-only deployment scope, not a reason to reinstate an obsolete architecture |
| Public demo and current deployment recipe | Not established for v8 by reviewed evidence; local public-edge/preparation files are unfinished/uncommitted inputs |
| Release evaluation | Software checks exist; fresh original-page semantic acceptance and production admission/disconnect acceptance remain incomplete |

The main documentation issue is competing descriptions of the active generation. `cloud/arm_a/README.md` still describes an exact, zero-model, initial-only API and a pending historical deployment. The current serving code has moved to open drafting and verification. `tools/prepare_grounded_deployment.py` accepts only v4/v5 and explicitly packages a no-verifier architecture. The architecture guide still emphasizes historical root modules. These should be labelled historical or reconciled with one active release manifest and runbook. Preserve frozen historical bytes rather than rewriting them to appear current.

## Validation evidence

- **45 targeted local tests passed:** admission, Claude adapter/budget/fallback and both rider SSE parser suites. These use synthetic/provider-free fixtures and do not prove semantic accuracy or deployed Cloud Run behavior.
- **Focused reproductions:** production minute admission rejects the second legal reservation; short clarification retrieval receives only the short reply; open-Q&A scheduling performs no conditional recovery/reranking; missing-primary configuration can draft through Claude but fails subsequent counting; retrieval outage skips the known-safety callback.
- **Broader local attempt:** 69 tests ran, with seven failures and five errors. The bundled Python lacks Flask; successful answer fixtures then fail at delivery import, and API fixtures cannot import. The other failed assertion belongs to an untracked retired read-only overlay fixture. These results are not treated as deployed application regressions. No local dependencies were installed.
- **Frozen runtime:** all 64 files in v8's runtime freeze match the workspace.
- **GitHub run [38160944967](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38160944967):** the Haiku execution job passed software checks, frozen-byte checks and actual provider execution; the Gemma job was skipped. This is execution success, not release acceptance.

The newly available [v8 provider result](../../grounded_generation/v8/run_38160944967/claude-fallback-result.json) contains six turns: three `UNSUPPORTED`, three `SYSTEM_ERROR`, and zero accepted technical answers. Five turns were labelled expected `SUPPORTED`; none returned that route. Two had no admitted source evidence, and three failed the complete-context token bound. The unsupported repair control returned the expected fallback. Expected answers and semantic claim review remain pending independent original-page adjudication; this small run is not a whole-corpus accuracy score. Complete-context refusal protects against truncating evidence, but the observed coverage/capacity is inadequate for these test inputs.

The harness uses hosted index files and fsync files, not deployed Qdrant request latency or production Firestore. The recorded 54–58-second evaluation waits cannot be subtracted and presented as a serving SLO. Preserve the failed results, diagnose source admission and context size on reviewed tuning cases, then use fresh held-out cases for a changed runtime.

## Improvement sequence

1. Establish a canonical integration branch and version manifest linking UI/backend commits, source approval, manual checksum, index snapshot, provider policy, frozen runtime, quality record, deployment receipt and rollback revision.
2. Repair whole-operation admission, contextual retrieval, source-based conditional scheduling and optional typed state. Add focused provider-free integration regressions before further paid quality runs.
3. Correct parse reuse and durable artifact retrieval. Replace unbound deployment selection and supply a v8-compatible build/release path that cannot select the retired no-verifier method.
4. Make operation execution/recovery durable and terminal failures explicit; validate ownership, worker loss and disconnects in the actual hosted configuration.
5. Address evidence admission and context overflows by selecting relevant anchors with their entire mandatory dependency closure. Preserve exact source content and conditions; do not silently truncate mandatory evidence or relax safety/source gates to improve coverage.
6. Run fresh independent original-page evaluation and matched browser-to-hosted smoke tests. Separate harness completion, semantic acceptance, warm/cold latency and deployment acceptance.

Additional DevOps opportunities: emit redacted completion metrics for admission rejection, source gaps, verifier decisions, fallback, stuck operations, first verified answer and cost reservations; make Qdrant health verify process/backend readiness; pin base images and Actions to immutable versions and lock transitive dependencies; retain build provenance/SBOMs; and reconcile redundant retrieval services and warm-instance cost only against measured demand and existing authorization. None requires loosening source authority or replacing the selected architecture.

Good foundations to retain include private IAM and server-side secrets, immutable source bindings, distinct response states, transactional session ownership/idempotency, finalized-response verification hashes, no unchecked draft streaming, source display restrictions, conservative spending controls and the retired full-manual design remaining archived.
