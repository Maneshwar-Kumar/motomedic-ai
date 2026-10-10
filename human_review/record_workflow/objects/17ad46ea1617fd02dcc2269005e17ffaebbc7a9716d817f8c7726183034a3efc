# MotoMedic reusable record loop

This folder coordinates engineering candidates. It preserves question, answer, conversation, source feedback, revisions and final judgment as exact content objects and a hash-chained event history. It makes no model calls and writes only its own folder and `human_review/record_catalogue.md`. It does not change source registries, cache, deployment, billing, indices or the Gemma integration.

The accepted feedback guide is the authoring objective and the independent review rubric: concise relevant answers; accessible observations and label discovery; exact specifications; compact conditional prerequisites; complete relevant warnings; supported schematics with scoped display permission; typed outcomes, corrections and non-repeat; separate contradictory/open observations; specific source-limit explanations and authorised-service stops. No invented thresholds, diagnosis or OEM ordering. Consult the original pages independently; retrieval output and agent consensus cannot authorize instructions.

## Current 50-record job: read-only import

Run from the project directory:

```powershell
python human_review/record_workflow/workflow.py sync
python human_review/record_workflow/workflow.py verify
```

`sync` reads EXP001–EXP050 drafts/reviews/judgments progressively. It never authors or edits their owned files. It verifies the actual original PDF checksum, snapshots the four planning documents, source manifest, feedback guide, original feedback history, coordination plan and this workflow code, then freezes stable record files and available source inspection images. A changing or incomplete file is reported and skipped until the next run. Repeated captures with identical inputs reuse the same snapshot. Catalogue exports are materialized views; previous content is retained by digest and event, even when those views are refreshed.

`inventory.json` includes every expected ID, every captured version/hash, review/judge bindings, latest state and explicit pending/block reasons. `work_items.json` assigns the next author/reviewer/judge task or maintenance/human review, with exact hashes and remaining revision budget. These are a queue for the existing coordinator, not automatic dispatch or a duplicate author job. The catalogue embeds readable current draft Q&A, source limits, complete latest feedback and judgments, historical corrections when current reviews are pending, and links to immutable prior versions. It preserves the original eleven IDs with their source history and scoped conversational acceptance. Each new record declares **Generated based on feedback from the first 11 cases**.

An imported PASS requires the newest draft hash, a matching independent review hash and the original manual checksum in the decision records. Only the first draft/review hash in a provenance-wrapper file binds the newest version; nested historical hashes cannot bless it. A changed version invalidates its older judgment. Reviews missing source-checksum binding remain explicitly blocked; do not silently fill that field or claim formal source approval. Legacy human-readable review attestations are retained as agent claims, not independently authenticated attestations by this importer. Exact source IDs, dependency/rule approvals and runtime claim gates are still required separately.

The conservative bound is v1 plus three revision cycles (v2–v4), including origin-only revisions. A v4 judgment requiring further work becomes `BLOCKED_HUMAN_REVIEW`; versions beyond v4 are blocked. `SOURCE_GAP` stops automatic revision and carries its actual reason to the human source-review queue. A sound source-limit abstention may pass agent review; that does not mean a supported technical action passed. See each card's expected route and reason, not merely its verdict.

`recorded_judge_counts` and `recorded_agent_batch_complete` preserve actual latest judge closure separately from workflow audit holds. `agent_loop_complete` is the stricter workflow gate: true only when all fifty latest versions have bound reviewer/manual decisions and exact agent passes or explicit terminal source/human blocks. A missing reviewer checksum can hold that gate even though the judge recorded a pass. `complete_inventory` only means fifty drafts are present; it is not loop completion. Every entry remains a tuning/regression draft; none is a held-out evaluation result or public instruction. Subsequent native GEN records append to the same catalogue when `sync` runs, preserving their immutable submissions and role history.

## Reusable author → reviewer → judge flow

New jobs use `GEN` IDs, keeping this run's owned `EXP` namespace read-only. Submit UTF-8 JSON using:

```powershell
python human_review/record_workflow/workflow.py submit --input path/to/submission.json
python human_review/record_workflow/workflow.py status
```

1. The coordinator assigns one unique GEN ID and a named author, reviewer and judge. Each role must have a distinct actor identity. Give all three the current feedback guide, TRD and source manifest. This CLI validates artifact bindings and schedules states; actual source inspection and authoring are performed by the assigned agents or humans. It never invokes Gemini/Gemma or handles credentials.
2. Author submits v1 readable `question`, `answer`, `turns`, expected route, conditions/warnings, original-page references with actual printed labels, source limits, stopping rules and forbidden claims. An author payload is frozen before any reviewer sees it. `SUPPORTED` is an expected route for review, not permission to serve the answer.
3. Independent reviewer reads that frozen version and the original pages, including figures/tables/continuations, and submits specific findings and checked spans. Bind the exact author hash, context hash and manual checksum; keep source gaps separate from missing rider facts and operational failures.
4. Independent judge reads the same frozen author and review, independently checks original pages, and dispositions every reviewer finding. PASS requires a passing source/experience review with no unresolved judge findings. Contradictory verdicts cannot pass silently. Return `NEEDS_REVISION` or `SOURCE_GAP` with concrete reasons otherwise.
5. Author revises into the next version, binding the previous author and feedback-judgment hashes, recording changes and dispositions. Reviewer and judge recheck exact revised content; old decisions stay immutable. If the context changed, an explicit context-change reason may start a new version without a prior judgment. It still uses the three-revision budget and needs fresh reviewer and judge checks.
6. Stop at exact agent consensus, an explicit source gap, or exhausted budget. Keep human conversational acceptance, formal original-source/evidence/rule/dependency approval, rights/applicability and release as separate downstream decisions. This engine cannot write them.

Use the JSON contracts in `submission_examples.json` as templates. There are no actual generated technical instructions in those examples. Replace placeholder hashes with values from the prior submission response. `status` reports native roles/hashes; imported EXP statuses are in `inventory.json`.

Native payload required fields:

| Role | Additional fields |
|---|---|
| All | `record_id`, integer `version`, `role`, named `actor`, exact `manual_sha256` |
| Author | `origin_declaration`, `question`, `answer`, `turns`, `expected_route`, `conditions`, `warnings`, `source_refs`, `source_limits`, `stopping_rules`, `forbidden_claims` |
| Reviewer | `author_sha256`, `context_sha256`, `independent_original_review=true`, `original_page_checks`, `findings`, `reason`, `verdict=PASS/NEEDS_REVISION/SOURCE_GAP` |
| Judge | reviewer fields plus `review_sha256`, `feedback_disposition`, `verdict=PASS_AGENT_REVIEW/NEEDS_REVISION/SOURCE_GAP` |
| Revised author | `previous_author_sha256`, `feedback_judgment_sha256` (or explicit `context_change_reason`), `changes`, `feedback_disposition` |

Original-page checks require `pdf_page`, actual `printed_page` string and `checked_span`. Every cited author source page must be checked by both reviewer and judge. Optional evidence IDs, asset references and complete source quotes can be retained in payloads; do not fabricate reviewed IDs to fill a template. Findings use unique `id`, issue, consequence, correction and supporting source. No code executes manual/user content.

## Approval and source boundaries

The original eleven were conversationally closed. The owner accepted R001 page75 recovery timing for records4/7 on 10 October; R002 post-start scope still awaits separate acceptance. History contains superseded proposals; the current guide consolidates lessons and later scoped updates. Do not treat every historical paragraph as accepted. The original manual can state a high-level remedy without documenting enough access/procedure to guide it; name that specific gap, preserve other observations and use the verified service route when appropriate.

The owner's inline permissions apply only to fuse/switch schematics. The source manifest still states a broader restrictive display policy; this conflict is visible here and must be reconciled by the source-review owner before runtime use. Other figures/crops/excerpts, including expansion source images, remain engineering-only. No public display license follows from this workflow or catalogue.

The Gemma/controller/provider chat owns its code and is deliberately not integrated here. Local Python is an engineering coordinator/validation artifact, not the rider deployment architecture. `.github/workflows/verify-record-loop.yml` provides online contract tests once committed to the authorised private repository; it uses synthetic fixtures, no secrets or model calls. This work does not claim that runner has executed. Source-bound catalogue capture needs the actual engineering manual available in the authorised build workspace; this CI deliberately does not upload it. No source ingestion or embeddings occur on rider requests.

## Audit and recovery

`objects/<sha256>` holds original bytes, including Markdown decisions, JSON submissions, context and source-inspection images. `events/NNNNNN.json` is append-only with predecessor and event digests. `ledger_head.json` records the expected tail. `verify` checks every event and every object; it detects mutation, missing intermediate events, a removed tail against the recorded head and object corruption. Hashes establish content identity, not reviewer identity or truth; this is a local audit trail, not a signed external audit service. A single-writer exclusive lock prevents overlapping coordinator runs. If a process dies with `.coordinator.lock` present, first confirm no coordinator is running before removing that exact lock. An event/head write interrupted by a crash fails closed; inspect the preserved last event and pending head before reconciling the head, never silently reset the history. Run `verify` before resuming.

Source/context changes require a new native author version and fresh reviews. Existing imported snapshots preserve the source/context actually captured, not an invented historical context for earlier external agent decisions. Pending/binding failures are maintainer work, never questions asked of a rider. Test the failure boundaries with `python -m unittest discover -s human_review/record_workflow -p test_workflow.py`.

## Additional hundred-case batch

The owner requested GEN001–GEN100 on 10 October with three independent agents. `batch_100/COORDINATION.md` sets file ownership and the bound. `batch_loop.py` is the single writer to the submission ledger; agents produce canonical immutable JSON and independently inspect original pages. `pump` imports validated files and produces exact author/reviewer/judge receipts. Revisions bind prior author and judge receipts. Subsequent cases append readable Q&A, typed turns, conditions/warnings, source limits, feedback and judgments to the same unified catalogue.

This batch pins a content-addressed context before authors begin. Every role explicitly carries `batch_context_sha256`; source PDF bytes and all frozen context objects are checked on submission. This keeps a running engineering batch reproducible when a parallel human-review chat appends annotations or the coordinator adds tooling. It does not ignore a changed manual, approve new source material or authorize runtime. The live context-match indicator and frozen snapshot remain visible for later revalidation.

```powershell
python human_review/record_workflow/batch_loop.py pump
python human_review/record_workflow/batch_loop.py status
python human_review/record_workflow/batch_loop.py human-handoff
python human_review/record_workflow/workflow.py sync
```

`human_review/blockers` holds every terminal source/assembly/audit/bounded-loop issue with exact source artifact versions/hashes and the decision required. Twelve legacy reviewer-checksum holds have separate cards; frozen review files are preserved. `human-handoff` updates a dedicated blocker index and appends coordinator notes to the current human queue and comments document without overwriting annotations or claiming they are owner feedback. App messaging failure is logged as communication infrastructure failure, not missing OEM evidence.

After all 100 unique cases reach exact agent consensus or explicit source/human block, `batch_loop.py finish` checks all three actors, actual artifact hashes, current versions, source/context bindings, origin declarations, distinct intent labels, revision budget and complete terminal inventory. It writes `batch_100_completion.json` atomically and appends its immutable digest to the ledger. Missing/invalid bindings or unfinished cases prevent this gate from completing. This manifest is a dependency gate for the authorized refinement chat; it is never human/source/release approval. Only after it exists and passes verification may the coordinator send that chat the continuation.
