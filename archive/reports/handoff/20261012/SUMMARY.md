# MotoMedic handoff — stopped 12 October 2026

The owner ended this build session and asked for a fresh chat to continue. The build goal is paused. This is a saved work-in-progress, **not a completed or accepted public demo**. No UI public opening occurred.

Read this summary, [ordered handoff TODO](TODO.md), then the current [PRD](../../../../docs/PRD.md), [TRD](../../../../docs/TRD.md), [architecture](../../../../docs/ARCHITECTURE.md), [root TODO](../../../../docs/TODO.md) and [project instructions](../../../../AGENTS.md). The working branch is `codex/public-evaluator`; main remains the checked baseline. [Draft PR4](https://github.com/Maneshwar-Kumar/motomedic-ai/pull/4) holds implementation work. The [publication receipt](publication_v1.json) records the pushed snapshot commit.

## Latest decision: Haiku only

After requesting this handoff, the owner said: “Scrap using Gemini. Claude Haiku is the only model we will use.” The exact [model scope3](../../public_evaluator/20261012/owner_model_scope_v3.json), SHA `65755e0a6b79f2df542c1c4b5f4f2e382a6857f7ee5ff5803d64988204e5ad0f`, supersedes scope2. **Use `claude-haiku-5-5` for drafting and verification, in separate API calls with different role policies/schemas.** The latest sole-model instruction supersedes the earlier requirement for different model identities. Do not claim same-model calls establish cross-model agreement; independent original-source review remains required.

The final steer is recorded for the next chat. No Haiku-only runtime migration, build or deployment occurred after the owner stopped this session. The frozen v10.11 Flash-Lite WIP is preserved unchanged as a superseded snapshot; **do not deploy it or continue Gemini access work**. First implement and test Haiku-only roles/admission under a new exact candidate/version. Both roles must consume the existing shared Haiku USD1 ledger; do not invent a second USD1 allocation or reset historical reservations.

Historical Google access findings remain evidence only. Two hosted probes used the existing server-side key: metadata advertised 2.5 Flash-Lite version 001/input 1,048,576/output 65,536, but both valid native-count request shapes failed HTTP 404/NOT_FOUND with Google's previous-use requirement. [Probe1](../../public_evaluator/20261012/flash_lite_access_probe_v1_result.json) and [probe2](../../public_evaluator/20261012/flash_lite_access_probe_v2_result.json) generated no answers and reserved no credits. This model-access issue no longer needs solving after the Haiku-only steer.

Gemma's former 16K restriction was input tokens per minute, not its native window. Preserve that distinction in historical explanations. Model context, throughput and lifetime budget remain separate constraints for Haiku as well.

## Saved implementation

| Area | Saved state |
| --- | --- |
| Retrieval | Authenticated private Qdrant dense retrieval concurrent with BM25, RRF, conditional reranking on ordered distinct-parent rank disagreement, bounded reviewed-dependency recovery. Actual hosted count traces exercised these paths. |
| Evidence/history | Complete applicable reviewed source context, warnings, units, headers, references and relevant typed history. Lossless shared JSON codec roundtrips preserve every value; no semantic compaction layer was introduced. |
| Answer path | Private draft, finalization, separate verifier of the exact final response, strict binding checks, durable save and exact saved-buffer stream/recovery; at most one correction/re-verification. Live useful-answer acceptance is still open. |
| Superseded runtime WIP | Frozen v10.11 Flash-Lite draft/Haiku verifier contract/router; model-aware legacy provider plus `cloud/grounded_generation/flash_lite_provider.py`; updated production wiring and native admission. Conservative Flash 250K input TPM is distinct from its 1M native input window. The active key's effective quota is not proven. |
| Permanent admission | Historical Gemma reservations remain valid and charged when adding Flash-Lite; no new allocation/reset. New primary count headroom is bounded at 512 tokens. Phased draft/verifier reservations and persistent pacing remain. |
| Cache | Haiku five-minute policy/evidence-prefix caching; question/history/final answer remain dynamic. Historical 6,113-token cache write/read proof exists; new fixed-pair actual-role usage still needs live proof. Primary cache optimization is deferred. |
| Rider UI | 100-word maximum; separate post-answer new-chat notice at 80% of smaller paired native input allowance, or notice after proven native-input overflow. Technical response text/recovery is unchanged. Nine synthetic UI tests passed. |
| Release tooling | Current bindings target v10.11; historical v10.10 manifest remains exact. Installed policy binds scope2 and the fixed pair. Local immutable snapshot [serving_manifest_v10_11.json](../../public_evaluator/20261012/serving_manifest_v10_11.json) records 549 inputs, SHA `c4f87a48fcb3645c46b74734ffd1df6b8faaa735e54d2286d6f3b099700d06f1`. It is unbuilt WIP; no v10.11 image or deployment exists. |
| Engineering helpers | Ignored local helper scripts are archived in [engineering_helpers_v1.zip](engineering_helpers_v1.zip) with an [exact manifest](engineering_helpers_manifest_v1.json). V11 clones are unfinished. Restore original `tmp/` paths after hash checks; do not execute them merely because they are archived. |

The new count-only v10.11 script **was not created**. V11 browser launcher still has `CURRENT_V10_11_MANIFEST_SHA`. Test fixtures, full helper migration, native forecasts and model-access acceptance are unfinished. The [runtime diagnostic](../../public_evaluator/20261012/operations/stopped_flash_lite_wip_v2.json) ran 120 methods: 94 passed, 4 assertion failures and 23 error entries (two entries belong to one method). These are largely unmigrated retired-role fixtures; they still must be fixed. See [handoff validation](validation_v1.json) for checks; syntax and synthetic tests are not real-provider acceptance.

The published snapshot `1c0626561a3ecc31f8447e1904be730ababc69ba` passed committed verification of all 549 frozen inputs. [Hosted provider-free CI](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/38221482493) passed navigation, source approvals and committed inventory, then failed its 264-method boundary suite with four assertion failures and 24 error entries from the unfinished role migration. The later UI workflow step was skipped; the nine local synthetic UI passes remain separate evidence. [Failed CI log](provider_free_ci_38221482493.log.txt) is preserved. The PR remains draft; main is unchanged.

## Last deployed cloud state

Project `motomedic-ai-20261009`, region `us-central1`. The last serving release is **v10.10**, still using the older Gemma/Haiku routing. Current edited local Flash-Lite code has not been deployed.

| Service | Original ready revision used by the last recorded traffic | Access |
| --- | --- | --- |
| API | `motomedic-arm-a-00011-2cf` | Private |
| Dedicated worker | `motomedic-answer-worker-00008-x7q` | Private |
| Rider UI | `motomedic-rider-ui-00011-ck8` | Private |
| Qdrant | Existing recorded private index service | Private |

Intended UI origin: `https://motomedic-rider-ui-279945185781.us-central1.run.app` — **private, not an evaluator URL to share**. External readiness paths are `/v1/health` for API/worker and `/health` for UI; `/healthz` is an internal Cloud Run probe.

V10.10 backend image is `us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/arm-a@sha256:a04a94caa5f6c485204916f1a824cc49ebfbc2e7802ef680a2c51b03091ebd48`; UI image is `us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/rider-ui@sha256:2f57d1a9da6237e795e8066e15474883f3451d2e8ed82bd5dbd4a4e2ae3d60aa`. [Exact image binding](../../public_evaluator/20261012/hosted_image_binding_v10_10.json) and [private readiness](../../public_evaluator/20261012/private_readiness_v10_10.json) retain complete identities. Runtime lock: `b59c7eac02bcf9efdf729a3e846d7c4f87f15d88336f8292af187924c7c83fbc`.

Rollback preparation submitted clones of all three services. The last read-only diagnosis showed 100% traffic on the original revisions, newer `latestCreatedRevision`, original `latestReadyRevision`, and no traffic changes. No candidate/rollback/restore routed-health proof was established. `latestReadyRevision` cannot prove a staged zero-traffic candidate ready; query that candidate's exact Revision condition/config. The v11 helper fix for this is unfinished and unvalidated as a full live workflow. Preserve [rollback operations](../../public_evaluator/20261012/operations/rollback_v10_10_candidate_operations.json) and [initial state](../../public_evaluator/20261012/operations/rollback_v10_10_initial.json).

## Successes and failures that must remain distinct

- V10.10 CI `38215228535`, backend build `586384b7-1ac2-4691-860d-e0a4770225c4`, UI build `1f26fe5a-f812-4eaa-b4fb-db9f275a4751`, all-three private readiness and private browser shell passed.
- Hosted count job `2854d315-011c-407d-9d40-6dd7aef08c67` passed: 42 native-count calls plus one metadata GET, zero generation/reservations, unchanged ledgers. Its [receipt](../../public_evaluator/20261012/hosted_runs/2854d315-011c-407d-9d40-6dd7aef08c67/count_receipt.json) SHA is `d4de3ec86f357f97eb1e2e51628f2b5a7c417c461f53738b77cc2d4e95dd09b5`. Counts/scaffold stress do not establish factual answers or unknown new finalized verifier size.
- V10.10 evaluator `b9c6b217-c03b-4ded-a2b9-d8d93af52021` failed before questions, [preflight receipt](../../public_evaluator/20261012/hosted_runs/b9c6b217-c03b-4ded-a2b9-d8d93af52021/preflight_failure.json). The compressed `runpy` wrapper missed the client's sibling-import directory. The v11 fix passed an actual isolated sibling-import/Unicode-budget roundtrip test; full client/helper migration remains open.
- V10.8 full-source follow-up verifier BASE counted 17,318 against Gemma 16K input TPM; zero generation/reservations. V10.9 repaired startup and privately passed readiness. V10.10 lossless formatting reduced that older-history BASE to 15,832, before unknown actual final answer/history. None establishes a useful live follow-up.
- Historical v10.4 six-case run returned six SYSTEM_ERROR outcomes and zero technical answers. V8 released zero technical answers and answered 0/4 answerable/partial cases. Preserve the failed baselines and never call them quality acceptance.

The fixed six engineering cases are direct bore/stroke, USB engine-running condition, deictic USB follow-up, explicit low-fuel topic shift, partial USB charging/time answer, and unsupported connecting-rod-bolt torque. [Original-page plan](../../public_evaluator/20261012/original_page_evaluator_plan_v2.json), SHA `a7dc784be633c14accdff256e57abb784a486076da07b149c6f2e04096ee5541`, and [original review procedure](../../public_evaluator/20261012/original_page_review_procedure_v1.json) govern actual independent adjudication. No new v10.11 six-case run occurred.

## Authority and operating limits

Source: 149-page `royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf`, SHA `cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89`, RAM00818/A, 4 November 2025. Himalayan+BS6 selection is approved; do not invent model-year/edition rider questions. Docling page 103 remains flagged. Rider-facing PDF/excerpts/figure crops are prohibited; engineering source use is permitted.

Delegated exact 161-case v3 source/initial-response authority is [release_manifest_v3.json](../../../human_review/agent_release_161/coordinator/release_manifest_v3.json), SHA `b8f8c7b5a9e1a299f0a90eecbf10127779b62b35fc105f0cd587de433e235298`. Do not recreate a blanket human-review blocker or claim agent inspection is human signoff. Changed scopes still require exact review. Arbitrary manual-supported Q&A and partial answers/checklists are allowed; authored catalogs/StepDefinitions are not input gates.

Immutable index: `index_a3282c4d98cf54595e4ba168`, BGE M3, 1,024-token chunk budgets, 532 chunks/277 parents/BM25. Reuse generation `1791537775184836` from the pinned GCS snapshot/reference; no request-time parsing or document re-embedding.

User approvals already recorded: credential setup (“Ok do as you wish with the credential setup”); exact deployment/checks/UI public opening (“Approve deployment, checks and public UI”); retrieved manual evidence/questions/history/proposed answers to Google Generative Language and Anthropic (“Approve these model API requests”); the superseded paid Flash-Lite choice; and the latest Haiku-only choice. The latest instruction takes precedence. Do not re-ask existing approvals. Different provider destinations, stopped billing restart, higher allocations or a model other than Haiku need applicable scope rather than assumptions.

Preserve INR2,700 lifetime/INR2,540 disconnect guard, 100 primary attempts/999200 reserved tokens and Haiku USD1. Latest confirmed primary usage before these zero-generation runs was 24 attempts/239,808 reserved tokens, remaining 76/759,392. Do not refund/reset uncertain or consumed reservations. Main billing stays enabled; `motomedic-inference-20261009` billing is disabled. The [latest saved guard](../../public_evaluator/20261012/operations/guard_readback_v10_9_20261012T065501209222Z.json) reported delayed INR185.31/stop=false, not an instantaneous cost guarantee. No billing/guard change or public opening was performed while stopping this session; existing deployed minimum instances remain configured.

Backend managed secret refs are `motomedic-gemini-serving-v1`, `motomedic-evaluator-anthropic-v1`, and `motomedic-rider-visitor-v1`, version1. No key values belong in Git or handoff documents. Real builds and provider runs must remain hosted; local tests are synthetic/provider-free. All agents and the private acceptance console have stopped; restore scripts explicitly if continuation is authorized in a new chat.
