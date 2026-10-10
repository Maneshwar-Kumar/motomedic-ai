# Expanded grounding/controller refinement — 10 October 2026

The 100-record prerequisite is verified, and an isolated controller candidate plus an offline 161-record comparison are complete. Technical-answer and live Gemma evaluation remain blocked by actual source approval. No shared controller/provider files or runtime defaults were changed.

## Verified inputs

Completion manifest SHA-256: `4c332d1441417fe25caeadc3b0a83768f32622fd777f7cc9815ed3dca7111590`. Catalogue SHA-256: `4ecb7515e9bd67a703174bfb78d9780c1f08c0486521922bc50fc6751a255cd1`.

The verifier independently checked all 100 final author/reviewer/judge files, exact hashes, current versions against 353 immutable ledger events, all stored object hashes, distinct role identities, manual/context bindings, original-page-check coverage, judge-closure audit bindings and referenced blocker cards. It also checked the original PDF checksum, all 50 current EXP artifact hashes and the catalogue's 161-ID coverage. Hash/role checks establish artifact identity and recorded independent-role claims; they do not authenticate reviewer identity or prove source truth. The batch has no human/source approval.

The dataset contains the original eleven, 50 EXP candidates and 100 GEN candidates. The new batch includes 50 manual-scope records and 50 labelled engineering policy/state/failure scenarios. All material is tuning/regression; there is no held-out accuracy result. Original recovery timing R001 is accepted conversationally; R002 post-start context remains pending.

## Concrete isolated changes

`controller_candidate.py` delegates technical selection, evidence and semantic gates to the existing controller. Its owner-policy clarification asks whether the bike is Himalayan BS6 without requiring rider edition selection. `IssueController` stores separate immutable diagnostic sessions per reported issue; customer resolution closes only the selected issue, preserving others. Recurrence with the same symptom explicitly reopens that issue while retaining attempts and repeat restrictions. A known reviewed safety stop in any open issue takes precedence over selected-issue closure and a reported component outage. Unknown, draft or unreviewed stops cannot gain authority from this wrapper. Invalid, duplicate and stale issue state is rejected.

These are an engineering candidate in this chat's owned folder. They are not installed into ReviewedService, persistent storage, the generator chat's pipeline or a public UI. Explicit issue selection and recurrence events still need trusted application integration; no language model infers them here. The synthetic baseline/revised examples in `focused_comparison.json` cover GEN052, GEN058 and GEN099 policy themes, not their complete real-rider dialogues or OEM claim support.

## Actual comparison results

| Arm | Records tested | Source holds respected | Live provider calls |
| --- | ---: | ---: | ---: |
| Deterministic controller | 161 | 161 | 0 |
| Current selected Gemma pipeline, gated | 161 | 161 | 0 |
| Isolated revised controller + selected Gemma pipeline, gated | 161 | 161 | 0 |

Each record's frozen content was loaded and its query sent through the actual unapproved reconciled registry. All three arms returned UNSUPPORTED without technical claims, suggested actions or pending steps. Per-case expected *candidate-content* routes are retained separately from the correct *current-runtime source-hold* route. Synthetic candidate SYSTEM_ERROR/SAFETY_STOP/AMBIGUOUS labels are not injected as though they were observed production failures. These comparisons measure source-hold behavior only: they do not measure intent matching, complete dialogue execution, source-backed next-step correctness, citation entailment, answerable coverage or Gemma semantic accuracy. The same registry symptom superset is deliberately used because missing source approval stops selection; it must not be used for future intent/branch scoring.

77 offline protocol tests passed, including eight new isolated tests. Existing fictional suites cover typed eligibility/corrections/non-repeat, unresolved versus normal, source/applicability holds, missing dependency/warning/role context, altered numbers/units/claims/citations, stale/draft exact cache, injection attempts, retrieval failures, bounded recovery/reranking and Gemini outages/malformed responses. Scripted provider and semantic doubles establish software behavior only. Photo uncertainty, vision decoding, speech and actual service-link transport cases remain authored policy scenarios rather than measured end-to-end modality behavior. Figure-dependent generation remains blocked by the text-only semantic adapter.

## Remaining source and integration work

Both registry ledgers contain zero formal decisions. All eleven reconciled steps have authoring holds. The new GEN source references do not supply runtime-approved immutable evidence IDs. Agent passes cannot establish claim/evidence/dependency/rule approval, figure associations, variant fit, prerequisite scope or permission to display source material. Source warnings, units/roles and supporting page references are retained for review in the corpus report; this work has not independently adjudicated their truth or fabricated approved bindings.

The separate review blocker `../blockers/REFINEMENT_CORPUS_v1_source_approval_human_review.md` records the exact batch and outstanding decision. Existing 21 blocker cards remain unchanged, including scoped rights/source limits and legacy binding holds. Review source objects, exact claim spans, warnings/prerequisites, tables/figures, procedure boundaries, predicates, stopping branches and rights before real technical-answer scoring. Integrate the proposed per-issue state only with versioned session persistence and trusted typed input, and run complete approved multi-turn fixtures afterward. The original generator chat retains its shared-code and grounding-fixture ownership.

Live baseline/revised Gemma inference was not attempted: no eligible fully source-approved case exists. There is therefore no measured live timing/token/semantic verdict comparison and no verifier false-acceptance/refusal calibration. After actual approvals, use the same approved fixtures for deterministic/current/revised comparisons, with bounded existing-authorized calls, no automatic retries, redacted version/usage/error telemetry and distinct provider versus support failures. Keep an unseen set separate from this expanded corpus.

## Reproduction and files

From the project directory, using the bundled Python runtime:

```powershell
python human_review/grounding_refinement/verify_batch.py
python human_review/grounding_refinement/run_protocol_tests.py
python human_review/grounding_refinement/evaluate_corpus.py
```

`verified_gate.json` records the gate; `corpus_results.json` contains all per-case inputs and three arm results, exact registry/runtime/code locks and limits; `protocol_results.json` and `protocol_test_log.txt` record the 77 tests; `focused_comparison.json` records three actual fictional baseline/revised differences. No live provider calls, index rebuilds, deployments, billing changes, source promotions or cache enablement occurred. Release stays closed.
