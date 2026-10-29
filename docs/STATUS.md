# Status

As of 29 October 2026. The section-template answer path is the only answer path, frozen as [serving manifest v11.3](../releases/serving_manifest_v11_3.json) ([decision v7](../releases/owner_decision_v7.json)). The answer path is the one of v11.2 (the quality round); v11.3 adds the answer-quality regression gate and observability. It is **not deployed**. Experiments run locally, with Claude Code as the generator ([EXPERIMENTS](EXPERIMENTS.md)). The owner's decisions are in the [decision log](DECISIONS.md).

## Built and frozen

| Item | State |
| --- | --- |
| Answer path | Five stages, wired in [section_questions.py](../cloud/grounded_generation/section_questions.py):<br>- [section index](../cloud/grounded_generation/section_index.py) `index_f768fbb216836c003701079e`;<br>- [top-5 retrieval](../cloud/grounded_generation/section_retrieval.py) with a relevance floor;<br>- [plain-text sections](../cloud/grounded_generation/section_assembly.py);<br>- [one Haiku call](../cloud/grounded_generation/haiku_answer.py) at effort high;<br>- the [deterministic gate](../cloud/grounded_generation/template_answer.py) `template-answer-v5`.<br><br>Draft-then-verify, the review gate and the availability fallback are deleted (their code is in Git history and [archive/](../archive/README.md)). |
| Quality round (25 October) | Four changes went into the path:<br>- the gate leaves out a policy, watchout or disclaimer sentence that only repeats an earlier section;<br>- internal labels in rider text fail closed, and meta phrases are reworded;<br>- a subsection split from its parent inherits the parent's warnings;<br>- a relevance floor of −9.0 skips the model call.<br><br>Haiku at default effort was retested as a comparison arm. The [measurements](../evals/20261025_quality_round_v1/README.md) and the [held-out test](../evals/20261025_heldout_v1/README.md) give the details. |
| Token ceiling | Removed from [admission](../cloud/grounded_generation/whole_turn_admission.py) on 25 October. Reserved tokens are still counted, but they no longer limit a turn. The 100-attempt allocation, the shared Haiku USD1 ledger, the rolling event limits, 61-second pacing and each call's native window still apply. |
| Regression gate | A [regression gate](../evals/regression/README.md) of 63 questions with deterministic checks. The checks agree with every judged answer: 66 of 66 held-out and 90 of 90 v3. A freeze is refused, and CI fails, unless the receipt names the current prompt, model, index, retrieval and assembly, and meets the bar. The [baseline](../evals/20261029_regression_v1/README.md) is 48 of 63 passed. |
| Observability | Allowlisted structured logs and log-based spans ([telemetry.py](../cloud/common/telemetry.py)). They record retrieval hits, gate outcomes, failure reasons, tokens, cost and timings, correlated by trace id, with no rider, answer or manual text. The [privacy and retention policy](PRIVACY.md) governs them. |
| Frozen release | [v11.3](../releases/serving_manifest_v11_3.json) binds serving code, UI, workflows, the manual and its manifest, the owner decisions v3–v7, the held-out evaluation and the regression receipt. It pins the section index identity and authorizes no deployment. The previous [v11.2](../releases/serving_manifest_v11_2.json), [v11.1](../releases/serving_manifest_v11_1.json) and [v11](../releases/serving_manifest_v11.json) are kept byte for byte. |
| Section index | Built from the cached Docling parse at `build/index-v4-sections` (not in Git):<br>- 154 sections and 532 chunks;<br>- 121 WARNING/CAUTION/NOTE boxes attached to their sections;<br>- 116 page-break continuations rejoined;<br>- 2 related-warning links;<br>- 145 of 149 pages covered, with page 103 flagged as a parse gap.<br><br>Its chunks, BM25 postings and embeddings are byte-identical to the previous index. It is published as the GitHub release asset [index-f768fbb216836c003701079e](https://github.com/Maneshwar-Kumar/motomedic-ai/releases/tag/index-f768fbb216836c003701079e) ([receipt](../releases/section_index_asset_v1.json)) and is not uploaded to hosted Qdrant, which needs billing. [SETUP](SETUP.md) shows how to download or rebuild it. |
| Tests | 157 backend, 77 UI and 18 ingest provider-free tests pass, locally and in [CI](../.github/workflows/ci.yml). They use a synthetic index, a fake model transport, a fake ledger and an in-memory Firestore. |
| Real-index checks | [Parity](../evals/20261025_answer_release_v3/serving_parity.json): on the previous index, the serving modules reproduce the v3 run's 30 model inputs and 90 gate outcomes, with no model calls. On the current index only GEN004's input differs: it now carries the luggage warnings. The held-out run [reproduces from a fresh clone of `main`](../evals/20261025_heldout_v1/README.md#reproduced-from-main), in a new Python 3.12 environment built from [tools/requirements-experiments.txt](../tools/requirements-experiments.txt). Retrieval, model inputs, schemas and prompts match on all 66 turns, and the gate on 65; the 66th is the documented post-hoc fix. The [reproduce-offline workflow](../.github/workflows/reproduce-offline.yml) repeated this on GitHub's Linux runners ([run 40848704977](https://github.com/Maneshwar-Kumar/motomedic-ai/actions/runs/40848704977), Python 3.12.15). The sections sent, model inputs, schemas and prompts match on all 66 turns, and the gate on 65. The one difference is H06's chunk order: reranker scores differ by about 0.000004 across platforms and reorder two near-tied chunks, but the same sections are sent. |

## Evaluation (local, agent-judged; not hosted or human acceptance)

The [held-out test](../evals/20261025_heldout_v1/README.md) ran 33 new questions, written by a separate subagent, through the quality-round path. A blind subagent judged the answers.

| Arm | Released | Correct | Partial | Wrong | Refused | Unfaithful cited items | Required warnings shown |
| --- | --- | --- | --- | --- | --- | --- | --- |
| **Haiku, effort high** (runtime) | 32 | **21** | 8 | 2 | 1 | 1 of 123 | 22 / 24 |
| Haiku, default effort | 33 | 21 | 9 | 2 | 1 | 0 of 129 | 20 / 24 |

On the 30 development questions ([v3](../evals/20261025_answer_release_v3/README.md)) Haiku at high effort was 30/30 correct. New questions show what that number hid:
- **Retrieval misses.** 6 shortfalls came from facts in a second place in the manual that the 5 chunks did not reach.
- **Facts left out.** About 6 came from facts that were sent but left out or misread.
- **Gate failures.** 2 came from the gate.

Default effort matched high effort on correctness and had no schema slips. The runtime stays at effort high; a change needs an owner decision.

The [regression baseline](../evals/20261029_regression_v1/README.md) of 29 October passed 48 of 63. The development half dropped from 30 to 26 against the v3 drafts. Three of the four lost cases are SYSTEM_ERROR turns of one kind: on a not-in-the-manual question, the model writes "The manual does not give X" as an uncited answer item. The likely cause is the quality round's wording rule. The fix is the first [TODO](TODO.md) item.

## Hosted state

| Item | Recorded state |
| --- | --- |
| Billing | Disabled on `motomedic-ai-20261009`. The budget is INR3,120 with an INR2,960 billing-disconnect guard, as raised for the [23 October private test](../evals/20261023_private_hosted_v5/README.md); [deployment_status.json](../cloud/deployment_status.json) records the same, with the earlier INR2,700/2,540 configuration kept as history. |
| Services | They are offline, and their revisions predate this design, so do not route traffic to them. Revisions tagged `v15cand` remain in the service templates; restore the templates or remove the tags before any `--to-latest` routing. |
| Haiku ledger | 72/100 attempts and USD0.2577/1 used after the private test. Tokens are no longer a limit, so a hosted run can make 28 more attempts. |
| Hosted Qdrant | Holds the earlier index `index_a3282c4d98cf54595e4ba168`. Without `MOTOMEDIC_QDRANT_URL`, the runtime searches the pinned section-index vectors in the image. |

## Known limits

- **Uncited limit sentences fail closed.** On not-in-the-manual questions, 3 of 10 development turns and 1 of 4 held-out turns became SYSTEM_ERROR.
- **Retrieval reaches one place.** All reference pages reached the model for only 13 of 29 answerable held-out questions. Menu paths, fluid grades and the trailer warning sit in a second section.
- **"The manual does not give X" can be false.** The model sees five chunks but speaks about the whole manual. Every wrong held-out answer (H05 in both arms, H12 and H17 in one each) is a false claim of this kind.
- **The gate checks form, not meaning.** It checks structure, citations, numbers and warning decisions. A non-numeric claim in an uncited disclaimer passes.
- **The relevance floor is inert at −9.0.** It refused nothing on the held-out questions, either rightly or wrongly. Abstention comes from the model routing UNSUPPORTED.
- **Related warnings are untested in use.** No held-out question retrieved a linked subsection without its parent.
- **Expired rider records are hidden, not deleted.** Deletion needs a Firestore TTL policy, which is a hosted step not yet applied ([privacy](PRIVACY.md)).
- **No hosted run of v11.3 exists,** and both question sets have now been seen.
