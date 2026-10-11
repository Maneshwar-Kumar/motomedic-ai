# MotoMedic UI prerequisites continuation

The owner requested this work in a new Service Agent chat and intends to clear the previous chat. Continue from this file without asking the owner to repeat context.

## Owner decisions recorded 11 October 2026

Keep A and B as the app methodologies. A uses streaming delivery. C is excluded from the current UI because the clock case failed in both passes and successful paced cases took excessive time. These decisions are recorded in `03_TRD.docx` v0.5 section 14 and `03_TRD_Architecture_Decision_Note.docx`. The note includes the options considered and clearly separates tested alternatives from untested hypotheses. A removes the separate online semantic verifier only for selecting exact reviewed wording; source, approval, eligibility, dependency, warning, prerequisite, citation and session-save gates remain mandatory. B keeps its semantic verifier. Streaming A emits a complete approved unit after gates and save, never raw model fragments or partial cautions. No C fallback is selected.

## Two tasks requested for the new chat

1. Test post facto whether the output already delivered by A would have passed the removed verification step. Audit all three cases against their exact original cited source and required reviewed meaning. Keep initial and repeat provenance, use exact output hashes to identify duplicates, and report per-claim support, completeness, unsupported additions and citations. Do not regenerate composition. Do not infer acceptance from invalid schema, provider failure or a missing output. Use the same Gemma 26B model for this bounded hosted audit; create fresh exact engineering protocol/review/approval and budget proof for the new verifier-only run, following existing safeguards. The old v4 run authorization is exhausted. Reuse identical initial/repeat verifier results only with explicit exact payload identity; normally three unique A output bundles need three verifier calls, but confirm this from the saved artifacts first. No model substitution or schema relaxation. The owner authorized the check; no generic human-review blocker is appropriate for the exact approved scopes. Changed runtime audit objects still need exact versioned engineering review. The engineering review requirement permits independent agent review if needed under AGENTS.md.
2. Investigate current warm/minimum instance pricing and startup CPU boost. Read current official Cloud Run pricing, actual us-central1 service settings, billing mode and CPU/memory. Calculate zero versus one minimum instance under explicit idle/traffic assumptions, distinguish gross cost from account-dependent free tier, show daily/monthly USD and INR using a checked exchange-rate assumption, and assess the INR800 lifetime budget/INR640 stop. Read the current CPU boost setting and explain startup billed CPU versus normal CPU, proposed cold-start experiment, expected tradeoffs and uncertainty. Distinguish Qdrant restoration from the future query-model/API service. Package pinned model assets and reuse loaded models as candidate improvements. Research authorizes no deployment, instance setting, CPU setting or billing mutation. Do not re-enable stopped billing. Return a concrete recommendation before any setting change.

These are prerequisites for UI wiring. Coordinate with the existing rider UI changes in the shared workspace; do not overwrite another chat's edits. Do not deploy or wire C. Do not treat A's post facto audit as a broad corpus release or general vision approval.

## Exact evidence and current state

Private repository `Maneshwar-Kumar/motomedic-ai`, branch `codex/reviewed-evidence-controller`. Workspace `C:\Users\kumar maneshwar\OneDrive - The Boston Consulting Group, Inc\Desktop\Service Agent`. Hosted operation is required; no local provider secrets or model calls.

Latest real run: https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38122505406
Reviewed runtime commit: `e910c86d2fb8a0a2f955bbea4fa4cbedbe64d82d`.
Results commit: `adea3d6`.
Model: `gemma-4-26b-a4b-it`, minimal thinking, max output 400, no fallback.
Cases: GEN003 mirrors, EXP003 signal cancellation, GEN026 phone-connected/disconnected clock settings. Exact prompts are in architecture_benchmark.SAMPLES.

Evidence files:
- `reports/architecture_run_38122505406/architecture_comparison.json` raw report; SHA256 `bfd7603c1dccb84d99613c8de647de9475da4f9675d75ccdfb583c915583ac83`.
- `reports/architecture_run_38122505406/hosted_job.json`.
- `reports/architecture_owner_measurement_summary_v4.json` all 18 client timing rows.
- `reports/architecture_timing_analysis_v4.json` recomputed timing math.
- `reports/architecture_result_independent_audit_v4.json`; final SHA256 `bc4c75a293550a196cf6edef32d3960f7eb3a0718fec73dc6b1f49bc9c7b1dec`.
- `reports/architecture_benchmark_review_v4.json`, `reports/architecture_benchmark_approval_v4.json`, `reports/architecture_budget_preflight_v4.json` explain the previous exact protocol; they do not authorize more calls.
- `GEMMA26B_ARCHITECTURE_RERUN_HANDOFF.md` preserves the v3 and v4 history.

18 turns: nine empty-cache initial trials plus nine immediate repeats. 8/9 SUPPORTED in each pass. All A and B passed. 27 provider attempts, zero retries, 26 known HTTP200 plus one unknown status. Three repeat cache hits, all A. B/C paraphrases were unreviewed wording and not cached. C clock initial failed transport/gate at client 9.63 seconds with exact cause unretained; repeat failed at 49.16 seconds because both verifier `unsupported_additions` fields were Boolean arrays rather than required scalar Boolean. No output delivered on either failure.

The raw record redacts routine content; reconstruct A only through saved selected indices/component IDs, exact approved registry text and original run bindings. Inspect `architecture_benchmark.run_sample`, `check_texts`, `allowed_envelope`, policies and registry before building the verifier-only replay. If reconstruction is impossible, report the precise evidence gap instead of inventing an old output or silently regenerating it. Retain exact hashes and provenance in the audit artifact while avoiding unnecessary raw media or sensitive logs.

Actual localhost HTTP/SSE completion seconds for A initial mirrors/signal/clock were 2.8765, 9.5691 and 9.6868; repeats 2.0336, 1.2437 and 1.1801. Warm retrieval wall was about 1.71/0.84/0.86 seconds. Provider TTFT was around 0.61-0.66 seconds. Actual browser/public-network delivery remains unmeasured. Removing idle pacing is arithmetic only. Conservative experimental admission was 6 RPM, minimum 10 seconds between starts, 12k rolling input reservations; these are not verified account quotas. Idle wait unions exclude concurrent provider activity. No concurrency gain was demonstrated on three paired controls. Streaming TTFO superiority was not demonstrated.

Fresh-worker initialization was 63.4807 seconds including 6.8384 seconds of retrieval controls; readiness excluding controls 56.6423 seconds. Dense model/index load 38.2519, source registry 2.8816, reranker load 0.2795, query warmups about 14.4275 seconds. Pretrial cooldown 60 seconds separately. These are hosted worker costs, not Cloud Run cold-request measurements. Qdrant boot independently downloads/checksums immutable vector JSON and restores vectors; it never reparses or re-embeds the manual per request.

## Binding and budget constraints

Manual SHA256 `cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89`; index `index_a3282c4d98cf54595e4ba168`, reuse hosted immutable artifact `owner-manual-index-37908240500`. Himalayan BS6 selected scope. Exact 161 source-content/initial-response approvals: `human_review/agent_release_161/coordinator/release_manifest_v3.json` SHA256 `b8f8c7b5a9e1a299f0a90eecbf10127779b62b35fc105f0cd587de433e235298`; read README and root_validation_v3.json. No generic human-review blocker; no widening into full adaptive transitions, general vision, public source delivery or deployment. Current display policy prohibits end-user PDFs, excerpts and figure crops. No legacy human_signoff fabrication.

Main GCP project `motomedic-ai-20261009`; inference project `motomedic-inference-20261009` free-only with billing disabled. Lifetime INR800 budget, alerts INR400/640/800, live guard at INR640 with retry delivery. Main Cloud Run region us-central1. Existing Qdrant recorded min0/max1, CPU1, memory512MiB, concurrency8, timeout30 seconds; verify live read-only settings rather than assuming unchanged. Consult `cloud/deployment_status.json`, `cloud/live_smoke.json`, `cloud/qdrant/boot.py`. Provider credentials stay in hosted secrets. Confirm current billing/guard state before live verifier calls. Report all attempts/errors/pacing and bounded retries.

Official starting references: https://docs.cloud.google.com/run/pricing ; https://docs.cloud.google.com/run/docs/configuring/min-instances ; https://docs.cloud.google.com/run/docs/configuring/services/cpu . Recheck current sources and quote current prices with date, region and assumptions. No public app deployment or billing change was authorized by this handoff.
