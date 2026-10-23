# Stage-by-stage answer-path replay (30 questions)

**Label: local, provider-free diagnostic. Not hosted acceptance and not answer-quality acceptance.** Zero Haiku calls, zero cloud spend. Run on 23 October 2026.

## Question

For each question, does the chunk that contains the answer survive each stage, and is it the evidence that is sent to generation?

1. Retrieval: dense (BGE-M3/Qdrant) top-20, BM25 top-20, and their RRF fusion top-20.
2. Ranking cut: the initial primary top-5.
3. Reranking, where the conditional gate fires: does the cross-encoder keep the answer chunk?
4. Final chunk set handed to source admission.
5. Source admission: which evidence objects the generator actually receives.

## Setup and fidelity

- **Code:** frozen v10.14 backend snapshot at [build/serving-v10_14/backend](../../../build/serving-v10_14/backend), source commit `67fc3171`, imported unchanged. [stage_replay.py](stage_replay.py) subclasses the serving retriever only to record what each stage returns. Every decision (RRF, rerank gate, anchor preservation, admission) is made by the frozen code.
- **Index:** local `build/index-bge-final`. `verify_index` passed against the v10.14 release lock (all 212 pinned file hashes). The query model is BGE-M3 at revision `5617a9f6`, with weight SHA-256 `b5e0ce34…` matching the pinned LFS object. The reranker is the index's pinned `ms-marco-MiniLM-L6-v2`.
- **Dense substitution:** the hosted stack is down. The budget guard disabled billing on 22 Oct at 11:50 UTC (delayed INR 2,547.79 against INR 2,540). Dense search therefore uses exact cosine over the index's own stored `embeddings.npy`.
- **Fidelity control:** "When is the service due for my bike?" was replayed and compared to hosted job `4133435e`. All 8 recorded points match:
  - final 6 chunk IDs
  - 3 admitted evidence IDs
  - dense top-3 parent sections
  - BM25 top-3 parent sections
  - rerank fired
  - preserved anchor chunk
  - final action
  - 16 gaps

  The local replay reproduces production retrieval for that question.
- **Cases:** [cases.json](cases.json).
  - Golden (10) and partial (10) come from the approved 161-case package. Gold is the claims' `manual_evidence_ids`. EXP027 has none, so I used brake-pad pages found by text search (my derivation).
  - No-answer (10) were written for this run. Each was checked absent by full-text search of all 149 parsed pages, including flagged page 103. A candidate about axle torque was dropped because page 103 lists a 70 Nm wheel-spindle torque.
- **Not measured:** generation. No answers were drafted or verified, so answer correctness is not measured. These 30 cases are now development cases, not held-out evidence.

## Result in one line

**v10.14 as deployed:** retrieval and reranking deliver the answer chunk in 20/20 answerable questions. The loss happens at source admission: the generator receives the full gold evidence for only 8/20 (plus 1 partial), because the serving gate admits only reviewed objects, 199 of 1,691.

**After the scoped v2 source-structure review (candidate v5, not deployed):** the answer evidence reaches the generator in **20/20**. See [After the fix](#after-the-fix-candidate-v5).

## Your three checks (20 answerable questions)

| Check | Result |
|---|---|
| 1. Retrieval contains the answer chunk | **20/20** in RRF top-20. Dense top-20: 19/20 (GEN041 missed; BM25 found it at #5). BM25 top-20: 18/20. Initial top-5: 19/20. |
| 2. Reranker, where used, keeps the answer chunk | Fired in 17/20. **Dropped gold 0/17.** Gold ranked #1 after rerank in 14/17. Rerank rescued GEN041 (RRF #10, outside top-5, to #4) and raised EXP037 (#4 to #1), EXP044 (#4 to #2), GEN022 (#3 to #2) and GEN030 (#2 to #1). Skipped in 3 (GEN004, EXP027, EXP040) because the initial top-5 held no reviewed evidence; gold was already in the top-5 there. |
| 3. The answer chunk is what goes to generation | Answer chunk in the final chunk set: **20/20**. Gold evidence actually admitted to the generator: **8/20 fully** (GEN007, 011, 012, 017, 022, 025, 044, 047), **1 partly** (GEN014), **0 in 11/20**. |

By group, gold reaching the generator:
- **Golden:** 7 full, 1 partial, 2 none (GEN030, GEN035).
- **Partial:** 1 full (GEN047), 9 none.

## Where each answer ends up

Rank = first position of a chunk containing gold evidence (page-based for EXP027); – = not in that list.

| Case | Question | Dense | BM25 | RRF | Top-5 | Rerank | Final set | Gold admitted | Where it ends |
|---|---|---|---|---|---|---|---|---|---|
| CTRL | When is the service due for my bike? | 10 | 7 | 2 | 2 | fired, dropped (kept by anchor rule) | #6 of 6 | 3/3 | ✅ all gold admitted |
| GEN007 | Does this manual allow E20 fuel? | 1 | 1 | 1 | 1 | fired, #1 | #1 of 5 | 1/1 | ✅ all gold admitted |
| GEN011 | Are the standard and low seats the same adjustable height? | 1 | 1 | 1 | 1 | fired, #1 | #1 of 6 | 3/3 | ✅ all gold admitted |
| GEN012 | What spark-plug gap is specified? | 1 | 1 | 1 | 1 | fired, #1 | #1 of 5 | 1/1 | ✅ all gold admitted |
| GEN014 | Are the left and right fork oil quantities identical? | 1 | 1 | 1 | 1 | fired, #1 | #1 of 5 | 2/3 | 🟡 qualifier missing |
| GEN017 | What output rating is listed for the USB port? | 1 | 1 | 1 | 1 | fired, #1 | #1 of 7 | 3/3 | ✅ all gold admitted |
| GEN022 | Why will the ignition key not come out while it is ON? | 1 | 11 | 3 | 3 | fired, #2 | #2 of 6 | 3/3 | ✅ all gold admitted |
| GEN025 | Which riding mode combinations are listed? | 1 | 1 | 1 | 1 | fired, #1 | #1 of 5 | 4/4 | ✅ all gold admitted |
| GEN030 | Which display languages are listed? | 1 | – | 2 | 2 | fired, #1 | #1 of 6 | 0/6 | ❌ blocked at admission |
| GEN035 | Why does the compass not work with navigation inactive? | 1 | 1 | 1 | 1 | fired, #1 | #1 of 5 | 0/1 | ❌ blocked at admission |
| GEN044 | At 300 km, does this manual allow full throttle? | 1 | 1 | 1 | 1 | fired, #1 | #1 of 5 | 5/5 | ✅ all gold admitted |
| GEN004 | How many kilograms can I put in the panniers and top box? | 1 | 1 | 1 | 1 | skipped | #1 of 5 | 0/1 | ❌ blocked at admission |
| GEN041 | The general warning symbol is on. Which exact part has failed? | – | 5 | 10 | – | fired, #4 | #4 of 7 | 0/1 | ❌ blocked at admission |
| GEN047 | It says Champion: what exact spark-plug part number…? | 1 | 1 | 1 | 1 | fired, #1 | #1 of 5 | 2/2 | ✅ all gold admitted |
| GEN048 | Will the app work with my new phone OS released this week? | 1 | 1 | 1 | 1 | fired, #1 | #1 of 6 | 0/2 | ❌ blocked at admission |
| EXP027 | When do the brake pads need replacement? | 1 | 1 | 1 | 1 | skipped | #1 of 5 | page no | ❌ blocked at admission |
| EXP034 | How do I check the battery voltage? | 1 | 1 | 1 | 1 | fired, #1 | #1 of 8 | 0/1 | ❌ blocked at admission |
| EXP037 | The number-plate light stopped working. Which bulb…? | 4 | – | 4 | 4 | fired, #1 | #1 of 6 | 0/2 | ❌ blocked at admission |
| EXP038 | Which direction can the headlamp beam be adjusted? | 1 | 1 | 1 | 1 | fired, #1 | #1 of 5 | 0/1 | ❌ blocked at admission |
| EXP040 | What rear-suspension notch should I use riding solo? | 1 | 10 | 3 | 3 | skipped | #3 of 5 | 0/2 | ❌ blocked at admission |
| EXP044 | My bike has been stored for over a month. Can I just restart it? | 2 | 17 | 4 | 4 | fired, #2 | #2 of 7 | 0/2 | ❌ blocked at admission |

## No-answer questions: what the generator would receive

| Case | Question (trap) | Top dense | Rerank | Generator receives |
|---|---|---|---|---|
| N01 | Top speed? (trap: 110 km/h accessory limit, p14) | 0.617 | fired | 28 approved non-answer objects. The p14 110 km/h chunk was retrieved but **not** admitted (unreviewed). |
| N02 | 0–100 km/h time? | 0.584 | fired | 23 approved non-answer objects (starting/running-in) |
| N03 | Mileage in km/l? (trap: km/l display unit) | 0.572 | skipped | nothing, so the route is forced to UNSUPPORTED |
| N04 | Cruise control? | 0.573 | fired | 23 approved non-answer objects |
| N05 | Water-crossing depth? | 0.513 | fired | 4 objects (salt-water washing, brake fluid) |
| N06 | High-altitude advice? | 0.543 | fired | 35 approved non-answer objects |
| N07 | Battery CCA? (trap: 12 V 8 Ah VRLA) | 0.497 | fired | 44 objects, **including the trap "12 V – 8 Ah VRLA battery" and other 12 V ratings** |
| N08 | Compression-test pressure? (trap: compression ratio) | 0.602 | fired | 16 objects, **including the trap "Compression ratio 11.5:1"** |
| N09 | Throttle free play? (trap: clutch/chain free play) | 0.612 | skipped | nothing, so the route is forced to UNSUPPORTED |
| N10 | Bluetooth intercom pairing? | 0.501 | skipped | nothing, so the route is forced to UNSUPPORTED |

- **3/10** reach UNSUPPORTED deterministically. That happens only because their nearest chunks are unreviewed, not because absence was detected.
- **7/10** depend entirely on the Haiku draft and verifier to abstain, and 2 of those carry a plausible-looking trap fact.
- **Scores do not separate answerable from unanswerable.**
  - Top dense: no-answer 0.50–0.62 sits inside the answerable range of 0.47–0.78.
  - Top cross-encoder: no-answer max is 0.93, while answerable gold scored as low as −6.1.

## Findings, ranked by impact

1. **Review coverage at admission is the main bottleneck, not retrieval.**
   - The serving source authority admits only evidence in its complete-context set: 199 of 1,691 objects, listed in [complete_context_ids.json](complete_context_ids.json).
   - The approved 161-case package cites 203 indexed manual evidence objects. Only 105 of them are admittable at serving.
   - **59 of the 100 package cases that cite manual evidence have at least one gold object the generator can never receive.**
   - In this sample, that alone accounts for all 11 lost answers. Fixing it is a scoped source-context review of the missing objects (a maintainer task with a new review version), not a retrieval or prompt change.
2. **Qualifier and context objects that are not linked to their facts are not retrieved.**
   - GEN014 admits the two fork-oil values, but the reviewed note "The above values are approximate…" sits in its own chunk and is in no top-20 list.
   - Only an approved dependency link would bring it in.
3. **The reranker is weak on this manual, and the anchor rule masks it.**
   - In the control, the cross-encoder pushed the Service Reminder chunk out of its top-10. It survived only through the v10.14 preserved-anchor rule.
   - The cross-encoder scored gold chunks strongly negative for GEN014 (−6.1), GEN030 (−5.5) and GEN041 (−6.0).
   - It never cost a gold chunk here, but it is a general web-QA model (`trained_for_this_manual: false`).
4. **Rerank is skipped exactly when it might help most.**
   - When the initial top-5 has no reviewed evidence, the gate returns `SOURCE_REVIEW_REQUIRED` and never looks at reviewed evidence at RRF ranks 6–20.
   - Reviewed evidence existed at those ranks in 6/6 skip cases. None of it was gold here, so this cost nothing in this sample.
5. **Abstention is unmeasured.** No-answer safety rests on the generator in 7/10 cases. Measuring it requires a generation-stage run of about 60 Haiku calls, estimated at about USD 0.03 from the recorded per-call costs.

## After the fix (candidate v5)

Finding 1 was addressed with a scoped source-structure review: [structural_review_v2](../../grounded_generation/structural_review_v2/README.md). It covers 79 exact objects in 25 sections, plus their warning, note and caution context. It took four independent review rounds, approval is recorded with no open findings, and no human signoff is claimed.

The candidate loader [serving_source_authority_v5.py](../../grounded_generation/structural_review_v2/candidate/serving_source_authority_v5.py) subclasses v4 and raises the admittable set from 199 to 277 objects. The same 31 questions were replayed through the unchanged frozen v10.14 retrieval code, with v5 as the admission gate. Results are in [replay_v5.json](replay_v5.json) and [scored_v5.json](scored_v5.json).

| Check (20 answerable) | v10.14 (v4 gate) | Candidate v5 gate |
|---|---|---|
| 1. Retrieval contains the answer chunk (RRF top-20) | 20/20 | 20/20 (retrieval unchanged) |
| 2. Reranker fired / kept answer chunk / ranked it #1 | 17 / 17 / 14 | 20 / 20 / 16. Rerank now also runs for GEN004, EXP027 and EXP040, because their initial top-5 now holds reviewed evidence. Not #1: GEN022 #2, GEN041 #4, EXP040 #2, EXP044 #2. |
| 3a. Answer chunk in the final set sent onward | 20/20 | 20/20 |
| 3b. Answer evidence admitted to the generator | 8 full, 1 partial, 11 none | **20/20 full**, including GEN014's "values are approximate" note and the p117 suspension table with its merged-cell FACT display |
| Fidelity control vs hosted job `4133435e` | 8/8 match | 8/8 match |

Side effects on the no-answer questions:
- **N01 (top speed)** now also receives the p14 "Do not exceed 110 km/h on an accessory-equipped motorcycle" line, as 15 more objects. That is a stronger trap for the abstention step.
- **N04, N05 and N08** each gain 4 related objects.
- **N03, N09 and N10** still receive nothing, so the route is forced to UNSUPPORTED.

Abstention still depends on the Haiku draft and verifier, and it remains unmeasured.

Limits:
- **Local diagnostic only.** v5 is not wired into production and is not deployed. Promotion needs a new serving manifest, hosted CI and build, a hosted verifier probe of the merged-cell FACT display, and owner authorization. Hosted billing is currently disabled.
- **Generation not run.** Answer correctness is not measured.
- **Development cases.** These 30 cases chose the reviewed sections, so they are not held-out evidence for the fix. Coverage of the other approved-package cases improves only where they share these sections.

## Files

| File | Contents |
|---|---|
| [replay_v5.json](replay_v5.json), [scored_v5.json](scored_v5.json) | Same replay and scoring with the candidate v5 admission gate (`stage_replay.py … v5`) |
| [cases.json](cases.json) | 31 cases (30 plus control), gold IDs/pages, absence checks |
| [stage_replay.py](stage_replay.py) | Recording harness over the frozen v10.14 code |
| [score_stages.py](score_stages.py) | Per-stage scoring and fidelity comparison |
| [replay.json](replay.json) | Raw per-stage lists: dense/BM25/RRF top-20, top-5, rerank top-10 with scores, final hits, admitted IDs, gaps |
| [scored.json](scored.json) | Per-case ranks, admission counts, verdicts, control fidelity |
| [complete_context_ids.json](complete_context_ids.json) | The 199 serving-admittable evidence IDs |

To reproduce (Python with torch 2.14.1+cpu and sentence-transformers 6.1.0, plus BGE-M3 at the pinned revision):

```sh
python stage_replay.py build/serving-v10_14/backend build/index-bge-final <bge_m3_dir> cases.json replay.json
python score_stages.py replay.json cases.json scored.json
```
