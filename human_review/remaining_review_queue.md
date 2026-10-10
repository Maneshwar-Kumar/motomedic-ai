# MotoMedic remaining review queue

Created during the 9–10 October 2026 review session; current review date 10 October 2026. Owned by the remaining-review chat. This queue records outstanding decisions and scoped conversational acceptance; it is not a source approval ledger or a release authorization.

## Current position

All eleven original examples have conversational acceptance, including the later record8 gauge-refresh prerequisite and record11's source-limited cooling wording. Original history remains in `record_id_verification.md`; reusable lessons remain in `subagent_feedback.md`. Record11 closure did not accept page75 starting additions. On10October the owner separately accepted recovery timing (R001); post-start cautions (R002) remain open. No room-temperature, overnight, numerical cooling endpoint or safe-restart threshold has been established.

Actual `registry/review_decisions.json` contains zero decisions. Actual `registry/candidate_registry.json` is `candidate-steps-v2`: 11 DRAFT steps, 14 DRAFT rules, 11 DRAFT dependency manifests and 6 DRAFT procedure records. All 11 dependency scopes are incomplete; all 6 procedure boundaries are unchecked. Its 48 claims lack `response_role`; 11 are DRAFT_PARAPHRASE and 37 are ENGINEERING_SOURCE_EXCERPT. These unchanged candidate texts do not incorporate all accepted conversational changes.

Manual SHA-256 verified in this chat: `cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89`. Selected index remains `index_a3282c4d98cf54595e4ba168`. No index rebuild is needed merely to review wording.

## Queue and closure rules

Current owner preference (10October): collect the review items in REVIEW_FOR_COMMENTS.md for annotations and feedback at its end. Keep decisions independently scoped by ID; do not require another one-item chat response before document review. Use plain rider-facing language after original-page inspection. Keep a compact setup checklist; follow up on only the condition the rider flags. Preserve uncertain, observed-normal, action-unresolved and customer-reported-resolved outcomes separately. Keep contradictory observations and separately unresolved symptoms open. Do not infer diagnoses, OEM order or automatic repeated actions. Explain a source limit and use the verified support route when the supporting guidance cannot supply a safe next step.

Conversational acceptance closes only the presented wording/branch scope. Independent technical/source checks, complete source objects, procedure boundaries, warning/prerequisite/figure/table dependencies, applicability, display rights and formal content-bound approval remain separate. Agent visual inspection is recorded as agent inspection, never manufactured human signoff. Do not turn missing source review into a rider question.

After each acceptance, append the owner's exact response, the exact accepted revision and exclusions to this file's history. Preserve the original history. Coordinate any additive update to the shared feedback guide/history with its owning coordinator; do not overwrite concurrent edits. Do not change the formal ledger on the basis of a conversational yes. Formal review requires the exact target digest/version, reviewer identity, actual checked source spans, independent original-page review and complete checks under `registry_workflow.py`.

## Ordered outstanding items

### R001 Starter recovery addition to records4 and7

Status: CONVERSATIONALLY ACCEPTED on10October2026. Scope: recovery timing only; formal source/dependency approval remains open. Existing five-second maximum and compact setup remain accepted historically.

Original PDF72–75, printed70–73, were rendered from the exact PDF and inspected in full in this chat. Review assets: `remaining_review_assets/original-072.png` through `original-075.png`. These are engineering review assets, not approved public displays.

PDF73 says hold until the engine starts, maximum five seconds. PDF74 says release after five seconds without starting and wait about five seconds before another attempt. PDF75 adds 15–20 seconds for battery recovery after three successive cranking attempts. Treat the latter as the additional wait for that documented condition; it is neither a requirement to make three attempts nor authority for an automatic retry loop. The page75 instruction to hold until starting stays constrained by PDF73/74's maximum and release instructions.

Exact accepted conversational addendum:

> Hold the starter until the engine starts, for a maximum of 5 seconds. If it has not started within 5 seconds, release it and wait about 5 seconds. If you have already made three successive cranking attempts, wait 15–20 seconds for the battery to recover.

Existing compact checklist retained: neutral and neutral lamp; ignition ON; right-hand kill switch RUN; adequate fuel and no continuously blinking final bar; clutch pulled in and held; side stand fully retracted. Existing prolonged-holding/battery-below-10-V caution and source-supported service routes remain. An unresolved attempt is recorded as ACTION_COMPLETED_UNRESOLVED and follows the accepted eligible-check/service policy, without automatic repetition or inferred battery health.

Owner accepted this recovery-timing addition for records4/7 with "although, the above is fine." This does not accept R002, source objects, dependency completeness, registry roles or runtime release.

### R002 Post-start scope on the continuation page

Status: OPEN; present after R001. PDF75/printed73 was visually inspected here. It says do not accelerate as soon as the engine starts, especially cold; idle for at least120seconds for oil circulation/lubrication and temperature rise; accelerate only when idle rpm has stabilized and is consistent; nonadherence can seriously damage engine internals. Inspect and attach the neutral/moving-bike gear-shift caution, clutch instruction, riding warning and other continuation content according to the actual procedure boundary. Do not indiscriminately append every page sentence to a narrow lookup.

Concrete next review: propose the smallest complete post-start wording for cards that actually guide starting/riding, with conditions and warning. Keep unrelated damaged-acceleration-cable/module replacement out of a routine starting answer unless that documented condition applies. Do not infer a hot-engine restart threshold, cooling completion criterion, road test, obligation to repeat starting or permission to ride from this page. Record11 cooling acceptance remains separate.

### R003 Reconcile schematic display permission with the manifest

Status: OPEN policy reconciliation, not a request to repeat already-granted permission. `source_manifest.json` prohibits end-user PDF/excerpts/figure crops under engineering-only-v1. Accepted history explicitly permits inline fuse-location PDF111 and switch-identification PDF28 schematics. Record10 also accepts matching stand/indicator schematic assistance using PDF25/58/59. Precisely reconcile the allowed assets and context, including record10 scope, before runtime display. Preserve prohibition for unrelated material and separate OEM redistribution rights; owner permission does not manufacture an OEM licence. Engineering page review remains permitted. Do not silently enable all crops or public PDF hosting.

### R004 Independent source metadata and market-fit review

Status: OPEN formal source review. Current manifest already records owner-confirmed Himalayan+BS6 selection; model year is unknown and not required by that policy, and rider edition selection is not required. Edition RAM00818/A, 4November2025 and English are recorded as agent observations pending independent approval. OEM portal URL is verified; exact original download URL remains unknown. India support email/route is verified as of9October2026, with source-market fit still pending. Do not re-open accepted selection policy as a seven-field rider questionnaire or describe the route as wholly unverified.

Concrete reviewer packet: original cover/publication pages1/4/149, exact file checksum and supporting model description page3; applicability and market/source provenance; source-target digest and actual checked spans. Scope any remaining rights/storage/display question to the current engineering-only policy and approved schematic exceptions. Planning documents still contain older broad unresolved metadata/rights wording and PDF-opening UX; reconcile explicitly with the later manifest and accepted scoped permissions.

### R005 Original-page technical checks for the eleven accepted examples

Status: OPEN independent human review. Conversational acceptance is already closed; do not re-present unchanged wording as though rejected. The following is the concrete technical/source scope to reconcile into review packets, not a claim that all evidence on these pages is approved or mandatory for every branch.

| Record | Original source scope from accepted history | Remaining technical reconciliation |
| --- | --- | --- |
| 1 lookup_oil_grade | PDF21/printed19 | Exact10W40/API SN/JASO MA2/semi-synthetic and full material caution; accepted removed metadata sentence; no oil-changing or capacity instruction. |
| 2 lookup_tyre_pressure | PDF90/88 and18/16 | Exact pressure/units/headers, warning scope, named front/rear CEAT specs, rim requirements and separate replacement branches; no invented tube/tubeless model mapping. Current registry cites90 only. |
| 3 lookup_fan_fuse | PDF112/110 | F3/red/10A mini-blade; full conditional replacement warnings and mandatory post-failure service inspection even if operation resumes. |
| 4 lookup_starter_duration | PDF72–75/70–73 and121/119 | Compact prerequisites, exact starter limits/recovery, scoped post-start context, battery caution; source-backed unresolved/MIL branches. R001/R002 are newly pending. |
| 5 lookup_usb_charging | PDF65/63 | Relevant engine-running answer, cap/warranty scope, cable/cap branches and conditional>2.5A warning; no cap-cause or warranty eligibility diagnosis. |
| 6 a_fuse | PDF111–112/109–110 and121/119 | Discovery/access, exact sticker/location/colour mapping, scoped inline schematic; uncertainty goes to service; persistent replacement failure stops; retain inspection after reported success. |
| 7 a_switches_on | PDF28/26,72–75/70–73 and121/119 | Switch figure/ON-OFF legend, compact setup, battery caution on ending checks and pending R001/R002; no assumed EFI health. Current registry omits28/75. |
| 8 a_refuel | PDF8/6,27/25,28/26,63/61,73/71,121/119 | Full refuelling safety/cap scope; accepted side-stand-retracted+ignitionON refresh prerequisite; preserve blinking/adequate-fuel discrepancy, no repeated fuel addition or gauge diagnosis. Current registry omits63. |
| 9 a_reconnect | PDF121/119; inspected identification figures23–25/21–23 | Accepted source-limited service routing replaces incomplete guided reconnection; establish supporting evidence audit scope rather than claim exhaustive absence. No continuation after failed fuse replacement. |
| 10 a_raise_stand | PDF122/120,74/72,121/119,25/23,58–59/56–57 | Actual stand and indicator observation pair; matching display legend/location; retain discrepancy and unresolved service stop; no bypass or diagnosed switch fault. Figures absent from current proposed dependency set. |
| 11 a_cool_engine | PDF122/120,121/119; display context37–38/35–36 if used | Accepted switchOFF/allowcool source limit; no temperature/time/room-temperature/overnight clearance; display examples cannot authorize a hot/not-hot threshold. |

For each packet, compare original full pages and relevant continuation/cross-reference pages independently from retrieval. Record actual condition, warning, number/unit/model, stopping and claim support checks. New dependencies invalidate incomplete prior assumptions; they do not invalidate historical conversational acceptance.

### R006 Complete evidence objects and procedure boundaries

Status: OPEN, maintainer/source reviewer work. Six concrete procedure records have boundaries_checked=false. Eleven dependency manifests have scope_review_complete=false. Review each linked action/condition/prerequisite/warning/table/figure/legend and original provenance, not merely page coverage. Establish required scope and actual order before marking fields complete. A section parent is not automatically a verified procedure. Source objects, procedure targets and dependency targets have their own formal checks.

Specific extraction gap: `source_review_notes.json` flags original PDF103/printed101: Docling omitted a page with text, diagram and warning; whole-page fallback is candidate context, with typed procedure/warning associations unapproved. Review when a dependent chain case is selected; it does not authorize invented chain adjustment. Do not rebuild the selected index merely to make unchecked objects appear reviewed.

### R007 Content-bound wording, roles, rules and citations

Status: OPEN authoring then independent approval. Reconcile accepted versions into reviewable drafts under generator-chat ownership. Split compound draft claims into the required ACTION/FACT/WARNING/PREREQUISITE roles, preserving exact reviewed wording and order, complete citations and warnings. There must be exactly one ACTION for an action step, none for a lookup. Current engineering excerpts cannot become public answers; end-user wording requires reviewed paraphrase classification. Number, unit, model and supported scope must remain exact.

Review all14 applicability predicates/questions, including actual rider-resolvable observations and separate product-policy behavior. Unknown remains unknown. For each approved claim retain immutable evidence IDs, original PDF/printed mapping and checked support. Missing figure verification blocks image-dependent claims. Finalize authoring first: editing wording, roles, evidence, rules or dependencies after signoff invalidates the digest.

### R008 Formal ledger completion

Status: OPEN, zero formal decisions. After R004–R007 prepare exact packets for source, evidence, procedure, step, rule and dependency targets via `registry_workflow.py`. Every approval requires actual independent original-page review, human signoff, reviewer identity, checked source spans, notes and complete target-kind checks. Author cannot approve their own record. Never populate signatures/checklists automatically from the original conversational yes responses. Record a source-limit/service case honestly rather than approve an incomplete repair action.

### R009 Accepted policy conflicts still awaiting implementation

Status: CONVERSATIONALLY RESOLVED, implementation/source signoff OPEN. Candidate finding FUSE_UNRESOLVED_ROUTE records legacy D024/D035 continuing to connection checks despite PDF121's persistent-problem service stop. Owner's accepted record6/9 route stops; review and revalidate affected actual golden branches before runtime/cache use. Do not ask owner to decide the already accepted stop again.

Other concrete drift: current a_reconnect still instructs reconnection despite accepted source-limit referral; oil caution is softened; USB lookup still includes removed irrelevant capabilities; current tyre record lacks accepted18 context; switch/refuel/stand records miss later source additions. These are author reconciliation items with exact accepted history, not new conversational acceptance or new diagnosis.

### R010 Separate generated-case human-review queue

Status: FUTURE REVIEW, never implicitly accepted. EXP001–EXP050 are explicitly generated based on feedback from the first eleven cases. Author/reviewer/judge versions are live in `agent_expansion/{drafts,reviews,judgments}` and the originating coordinator owns them. Version counts are transient and not acceptance counts. PASS_AGENT_REVIEW only resolves an agent loop. Before adding each to this human queue, obtain the coordinator's finalized exact version/digest and unresolved findings; review individually. Do not duplicate the batch or alter owned files.

Reusable loop and additive unified catalogue are owned by chat01a121e5-6e8c-7721-93df-22b7eb088fa4. Original eleven IDs/history remain distinct from generated cases. No generated case is a held-out evaluation case merely because it is new.

### R011 Provider and semantic calibration release gates

Status: OPEN technical release evaluation, owned by generator chat01a12078-1849-7160-ac38-d816307ac3ca. `GENERATOR_INTEGRATION.md` describes a constrained generator and optional OpenAI candidate; later `GEMMA_OBSERVABILITY.md` selects Gemini API/gemma-4-31b-it in the separate unbilled inference project. Do not silently substitute models or treat the earlier credential/allocation paragraph as the latest account state. At inspected snapshot, grounded bounded Gemini composer/verifier integration remains pending; smoke success is not grounding or release approval.

After reviewed registry/source inputs exist, evaluate deterministic controller first and the same cases through composer plus separate semantic verifier. Independently adjudicate supported claims, unsupported additions, altered numbers/units, omitted warnings, wrong citations and figure-dependent cases. Synthetic verdicts establish protocol tests only. Report false acceptance/refusal, answerable coverage, component failure class, real usage/cost, TTFO and warm/cold latency separately. HTTP500/timeouts remain SYSTEM_ERROR. Tiny timing probes do not establish reliability or p95.

### R012 Reviewed datasets, retrieval calibration and public-demo gates

Status: OPEN release work, not an immediate owner wording decision. Existing37 dialogue/lookup cases and exact cache remain provisional; 27 reference cards are in-sample probes, not independently reviewed goldens. Select at least25 independently reviewed release cases with supported, unsupported, safety, follow-up, table/figure and available photo coverage. Version expected evidence/outcomes; split tuning/regression from genuinely held-out cases. Calibrate conditional-retrieval thresholds and compare off/always/conditional on the same reviewed held-out cases. Revalidate exact caches against source/variant/path/policy/review/runtime changes.

Existing hosted engineering controller/generator regressions do not mean the rider UI is deployed or real source generation is approved. Public UI, managed sessions, upload/rate/per-day spend controls, redacted eligibility/TTFO traces and independent logged-out text/photo/abstention/error smoke tests remain pending in inspected integration documents. Complete a versioned release report and reproducible demo/runbook/rollback handover before release. No deployment, billing, secret retrieval, provider calls, index rebuild or formal approval write is authorized by this queue.

## Sources inspected for this queue

AGENTS.md; authoritative03_TRD.docx v0.4;01_Concept_Architecture.docx,02_PRD.docx and04_To_Build_Evaluation_Decisions.docx v0.3; source_manifest.json; record_id_verification.md; subagent_feedback.md; multi_agent_expansion_plan.md; agent_expansion/COORDINATION.md and author SUMMARY.md; actual registry/candidate_registry.json and review_decisions.json; registry_workflow.py; source_review_notes.json; GENERATOR_INTEGRATION.md; GEMMA_OBSERVABILITY.md. The three referenced chat histories were read for ownership and context. Planning documents precede later scoped source/acceptance updates; do not label their old pending wording as a newly required rider selector.

## Scoped decision history

10October2026 — Queue initialized and first item presented. All eleven original conversational acceptances from9October retained. R001 presented; no owner response yet. R002 remains separately pending. Source ledger unchanged and no source/registry/generator/expansion files edited by this chat.


10October2026 — Owner accepted R001 and requested all review material in the human_review subfolder, with comments/annotations and feedback at the document end. R002 remains open. See REVIEW_FOR_COMMENTS.md. Formal ledgers remain unchanged.

## Current engineering snapshot update 10 October 2026

A newer draft exists at registry/reconciled-accepted-eleven, version accepted-eleven-reconciliation-draft-v1. It has29 claims with ACTION/FACT/WARNING/PREREQUISITE roles, but all11 steps are DRAFT, all11 dependency scopes incomplete, all6 procedure boundaries unchecked and its ledger empty. This is separate from the unchanged older48-claim registry described above. Its recorded context predates the new R001 acceptance and must be reconciled by its owner. Reports gemma_grounding_gates_candidate_v1.json and gemma_grounding_gates_existing_v1.json record configured Gemini/gemma-4-31b-it runtime locks and zero calls because source review blocks. Current generation_providers.py includes GeminiJSONProvider. R011 therefore remains source-dependent integration/calibration and release evaluation work; the earlier observability document's statement that the transport is absent is outdated. Neither draft engineering reports nor code presence establishes real-source semantic calibration or release. Frozen copies are in review_bundle_20261010.

## Completed generated batch update 10 October 2026

JUDGE_CLOSURE_AUDIT.md records47 PASS_AGENT_REVIEW and3 SOURCE_GAP across the50 exact latest drafts, with no pending wording revisions. The three source-gap cases remain separate: EXP027v2 brake-pad replacement-threshold ambiguity; EXP032v3 extraction/dependency assembly gap despite an actual chain procedure on originalPDF103; EXP040v3 unresolved first-notch versus third-notch preload applicability. All50 remain generated DRAFT candidates requiring separate human review. The imported workflow may retain binding blocks even where the judge audit records a pass; preserve that distinction for its owning coordinator.


<!-- workflow-blocker-handoff:57b1f6b84edcd43a1187f9fed6bec26615cd17ef8ed27de2707735b3be14fa57 -->
## Coordinator append: additional workflow blockers — 10 October 2026

This is a coordinator handoff, not owner feedback or approval. Existing comments and R001 acceptance are preserved. Review these exact-version cards; each states source/audit reason, frozen hashes and required human decision.

[Complete blocker index](blockers/WORKFLOW_INDEX.md)

- [EXP001_v3_checksum_binding_human_review.md](blockers/EXP001_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `03628456be73457d601359ca88e3fbdd646ecd5dfcc96f31fb98cc6905054027`.
- [EXP002_v3_checksum_binding_human_review.md](blockers/EXP002_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `86e89d8b6861788f639a31e049b354c4ffcdefdaf4d6a4929f6fa73b7e852b76`.
- [EXP003_v3_checksum_binding_human_review.md](blockers/EXP003_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `3513391901cac0c6c8013713a9f4d0ffbef9db1f348ebf7560608530bb6a5a7a`.
- [EXP004_v3_checksum_binding_human_review.md](blockers/EXP004_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `a074642a0e7db439a2bbe04798c258b9a79ae2e79f6bbca48bea3ecb35f78be1`.
- [EXP006_v3_checksum_binding_human_review.md](blockers/EXP006_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `7ec05f4defd7033afbfe95c6a212dfdc7d3f9ffed3c4e27a979b7907b343616f`.
- [EXP007_v3_checksum_binding_human_review.md](blockers/EXP007_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `0e3ec9c6452f3a6874b0537d1aa4e77be10c419738e4737872f7f86815fa70b7`.
- [EXP008_v3_checksum_binding_human_review.md](blockers/EXP008_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `2cd5cb31823fcbd3151636f6ac2ff905c47c38df328cde0c4065186d08ef7545`.
- [EXP009_v3_checksum_binding_human_review.md](blockers/EXP009_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `7ffd937610310da1ab9a2cbf477855fb7d4a03ee81483947ffd3f88eb1f6b6f6`.
- [EXP010_v2_checksum_binding_human_review.md](blockers/EXP010_v2_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `25b71f3b0cf2e6c924382b19cd90c1fa985b070345690bbfa4239913dd38db30`.
- [EXP015_v4_checksum_binding_human_review.md](blockers/EXP015_v4_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `90025f15eaa37b517c89236474f957a15e94d433234922422b7acb94524d8f76`.
- [EXP025_v3_checksum_binding_human_review.md](blockers/EXP025_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `c27eb77a00a25cdf0fd3b0bcec1c9c10582045ac43d57562c0672e3f25c4b5d8`.
- [EXP026_v3_checksum_binding_human_review.md](blockers/EXP026_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `4ea1dc44eee5c8c3242a7ca72ad6b8f5ca3fde0f34a4f0924f5f53ee985f10b5`.
- [EXP027_v2_human_review.md](blockers/EXP027_v2_human_review.md) — Original PDF91 has ambiguous warm-to-indicator wording. No exact wear threshold is established.; card SHA-256 `f212251f621283b14bf360a980a58275173ad7f46524c33f4cbf64d38d0f0dd0`.
- [EXP032_v3_human_review.md](blockers/EXP032_v3_human_review.md) — Original PDF103 contains the procedure; the gap is approved typed evidence/dependency assembly, not absence of manual instructions.; card SHA-256 `c32b909d6eb3c38826377aaf5978797f2feea91ba0d6e506c256a0ebfdfd0a6f`.
- [EXP040_v3_human_review.md](blockers/EXP040_v3_human_review.md) — PDF116 first-notch wording and PDF117 solo third-notch table have unresolved scope/applicability.; card SHA-256 `58ab420713c3912ff93e0d955eeba06af3c6d5268cb41d14b16ccf0404cb0419`.

The current 100-case batch remains engineering-only. Its completion manifest, when present, closes the automated loop and never source/release approval.


<!-- workflow-blocker-handoff:0ea1a053bcee5a973adf018aed4d56ce1bd7adbd08da6486de64c147872e9d72 -->
## Coordinator append: additional workflow blockers — 10 October 2026

This is a coordinator handoff, not owner feedback or approval. Existing comments and R001 acceptance are preserved. Review these exact-version cards; each states source/audit reason, frozen hashes and required human decision.

[Complete blocker index](blockers/WORKFLOW_INDEX.md)

- [EXP001_v3_checksum_binding_human_review.md](blockers/EXP001_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `03628456be73457d601359ca88e3fbdd646ecd5dfcc96f31fb98cc6905054027`.
- [EXP002_v3_checksum_binding_human_review.md](blockers/EXP002_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `86e89d8b6861788f639a31e049b354c4ffcdefdaf4d6a4929f6fa73b7e852b76`.
- [EXP003_v3_checksum_binding_human_review.md](blockers/EXP003_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `3513391901cac0c6c8013713a9f4d0ffbef9db1f348ebf7560608530bb6a5a7a`.
- [EXP004_v3_checksum_binding_human_review.md](blockers/EXP004_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `a074642a0e7db439a2bbe04798c258b9a79ae2e79f6bbca48bea3ecb35f78be1`.
- [EXP006_v3_checksum_binding_human_review.md](blockers/EXP006_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `7ec05f4defd7033afbfe95c6a212dfdc7d3f9ffed3c4e27a979b7907b343616f`.
- [EXP007_v3_checksum_binding_human_review.md](blockers/EXP007_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `0e3ec9c6452f3a6874b0537d1aa4e77be10c419738e4737872f7f86815fa70b7`.
- [EXP008_v3_checksum_binding_human_review.md](blockers/EXP008_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `2cd5cb31823fcbd3151636f6ac2ff905c47c38df328cde0c4065186d08ef7545`.
- [EXP009_v3_checksum_binding_human_review.md](blockers/EXP009_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `7ffd937610310da1ab9a2cbf477855fb7d4a03ee81483947ffd3f88eb1f6b6f6`.
- [EXP010_v2_checksum_binding_human_review.md](blockers/EXP010_v2_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `25b71f3b0cf2e6c924382b19cd90c1fa985b070345690bbfa4239913dd38db30`.
- [EXP015_v4_checksum_binding_human_review.md](blockers/EXP015_v4_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `90025f15eaa37b517c89236474f957a15e94d433234922422b7acb94524d8f76`.
- [EXP025_v3_checksum_binding_human_review.md](blockers/EXP025_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `c27eb77a00a25cdf0fd3b0bcec1c9c10582045ac43d57562c0672e3f25c4b5d8`.
- [EXP026_v3_checksum_binding_human_review.md](blockers/EXP026_v3_checksum_binding_human_review.md) — Reviewer lacks explicit original manual SHA-256 binding; card SHA-256 `4ea1dc44eee5c8c3242a7ca72ad6b8f5ca3fde0f34a4f0924f5f53ee985f10b5`.
- [EXP027_v2_human_review.md](blockers/EXP027_v2_human_review.md) — Original PDF91 has ambiguous warm-to-indicator wording. No exact wear threshold is established.; card SHA-256 `f212251f621283b14bf360a980a58275173ad7f46524c33f4cbf64d38d0f0dd0`.
- [EXP032_v3_human_review.md](blockers/EXP032_v3_human_review.md) — Original PDF103 contains the procedure; the gap is approved typed evidence/dependency assembly, not absence of manual instructions.; card SHA-256 `c32b909d6eb3c38826377aaf5978797f2feea91ba0d6e506c256a0ebfdfd0a6f`.
- [EXP040_v3_human_review.md](blockers/EXP040_v3_human_review.md) — PDF116 first-notch wording and PDF117 solo third-notch table have unresolved scope/applicability.; card SHA-256 `58ab420713c3912ff93e0d955eeba06af3c6d5268cb41d14b16ccf0404cb0419`.
- [GEN004_v1_documented_scope_limit_human_review.md](blockers/GEN004_v1_documented_scope_limit_human_review.md) — The sole owner manual refers accessory payload/fitment to separate model-specific GMA instructions that are not in this approved source set. The scoped abstention can pass; an actual accessory payload limit remains unverified.; card SHA-256 `a4c6b0b0604da9fa07ab3d7a912282cf974122a022711ec8137c2db686b8fd34`.
- [GEN047_v1_documented_scope_limit_human_review.md](blockers/GEN047_v1_documented_scope_limit_human_review.md) — The owner-manual specification gives a spark-plug manufacturer/gap but does not establish the exact ordering part sought in this case. Do not derive a purchasable part from incomplete specification data.; card SHA-256 `ab560c8940ee77089dfa87cc12902d310df7cb61e3e4dc275bff765590091e4d`.
- [GEN048_v1_documented_scope_limit_human_review.md](blockers/GEN048_v1_documented_scope_limit_human_review.md) — An immutable 2025 manual cannot verify compatibility with a later OS release. Current OEM compatibility evidence would need separate source registration, applicability and rights review.; card SHA-256 `730edfc6da411e8ffa4197704e7149f8bb8dac2b7420a685afadb24a1eea6e68`.
- [GEN050_v1_documented_scope_limit_human_review.md](blockers/GEN050_v1_documented_scope_limit_human_review.md) — The manual's hot-exhaust caution supplies no elapsed-time touch-clearance threshold. Do not invent a minute count or claim safe touching from elapsed time.; card SHA-256 `91737a110a203aa65bebb10797e3bf78c36394ddf8dc4279f0115c0732fceb78`.
- [GEN097_v1_documented_scope_limit_human_review.md](blockers/GEN097_v1_documented_scope_limit_human_review.md) — Conversational schematic permission does not settle whole-manual public display/hosting rights. The restrictive source manifest and scoped permissions need explicit reconciliation before wider display.; card SHA-256 `8aea3adf16bd96c07e867f5d559575e350221e152e287291177daadfd08537db`.
- [GEN100_v1_documented_scope_limit_human_review.md](blockers/GEN100_v1_documented_scope_limit_human_review.md) — The recorded scoped-diagram display exception and the blanket restrictive manifest are not yet reconciled into an approved runtime policy. Do not silently choose the permissive source entry.; card SHA-256 `8f307b0fcf19adf077e425717d4c53c5f7367a5b2e18689335fa9b0b81da797d`.

The current 100-case batch remains engineering-only. Its completion manifest, when present, closes the automated loop and never source/release approval.
