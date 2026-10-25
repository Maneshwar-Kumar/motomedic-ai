# Status

As of 25 October 2026. The section-template answer path is the only answer path, merged to `main` and frozen as [serving manifest v11.1](../releases/serving_manifest_v11_1.json). It is **not deployed**. Experiments run locally, with Claude Code as the generator ([EXPERIMENTS](EXPERIMENTS.md)). The owner's decisions are in the [decision log](DECISIONS.md).

## Built and frozen

| Item | State |
| --- | --- |
| Answer path | Five stages, wired in [section_questions.py](../cloud/grounded_generation/section_questions.py):<br>- [section index](../cloud/grounded_generation/section_index.py) `index_a609ca61c635641e0a22dc48`;<br>- [top-5 retrieval](../cloud/grounded_generation/section_retrieval.py);<br>- [plain-text sections](../cloud/grounded_generation/section_assembly.py);<br>- [one Haiku call](../cloud/grounded_generation/haiku_answer.py) at effort high;<br>- the [deterministic gate](../cloud/grounded_generation/template_answer.py).<br><br>Draft-then-verify, the review gate and the availability fallback are deleted (their code is in Git history and [archive/](../archive/README.md)). |
| Token ceiling | Removed from [admission](../cloud/grounded_generation/whole_turn_admission.py) on 25 October. Reserved tokens are still counted, but they no longer limit a turn. The 100-attempt allocation, the shared Haiku USD1 ledger, the rolling event limits, 61-second pacing and each call's native window still apply. |
| Frozen release | [v11.1](../releases/serving_manifest_v11_1.json) binds 81 inputs: serving code, UI, workflows, the manual and its manifest, the owner decisions and the evaluation. It pins the section index identity and authorizes no deployment. The previous [v11](../releases/serving_manifest_v11.json) is kept byte for byte. |
| Section index | Built from the cached Docling parse at `build/index-v3-sections` (not in Git):<br>- 154 sections and 532 chunks;<br>- 121 WARNING/CAUTION/NOTE boxes attached to their sections;<br>- 116 page-break continuations rejoined;<br>- 145 of 149 pages covered, with page 103 flagged as a parse gap.<br><br>It is not published as a release asset and not uploaded to hosted Qdrant; [SETUP](SETUP.md) shows how to rebuild it. |
| Tests | About 135 backend and 77 UI provider-free tests pass, locally and in [CI](../.github/workflows/ci.yml). They use a synthetic index, a fake model transport, a fake ledger and an in-memory Firestore. |
| Real-index checks | [Parity](../evals/20261025_answer_release_v3/serving_parity.json): the serving modules reproduce the v3 run's 30 model inputs and 90 gate outcomes, with no model calls. A [local Claude Code run](EXPERIMENTS.md#example-run-25-october-2026-local) of a new question released a cited SAFETY_STOP. |

## Evaluation (local, agent-scored; not hosted or human acceptance)

The [section answer path v3](../evals/20261025_answer_release_v3/README.md) ran 30 questions with isolated Claude Code subagents as generators. All 19 answerable questions had every gold object inside the sections sent. The median model input was 5,261 characters.

| Arm | Released | Correct | Unfaithful cited items | Internal wording |
| --- | --- | --- | --- | --- |
| Haiku, default effort | 24 | 24 | 0 of 62 | 1 |
| **Haiku, high effort** (runtime) | **30** | **30** | 0 of 65 | 2 |
| Sonnet | 29 | 28 | 0 of 44 | 1 |

The default-effort arm missed the 27/30 bar on structural slips. The owner accepted the high-effort arm ([v4](../evals/20261025_answer_release_v3/owner_decision_v4.json)), so the runtime uses effort high; its hosted latency and cost are unmeasured.

## Hosted state

| Item | Recorded state |
| --- | --- |
| Billing | Disabled on `motomedic-ai-20261009`. The budget is INR3,120 with an INR2,960 billing-disconnect guard, as raised for the [23 October private test](../evals/20261023_private_hosted_v5/README.md); [deployment_status.json](../cloud/deployment_status.json) still records the earlier INR2,700/2,540. |
| Services | They are offline, and their revisions predate this design, so do not route traffic to them. Revisions tagged `v15cand` remain in the service templates; restore the templates or remove the tags before any `--to-latest` routing. |
| Haiku ledger | 72/100 attempts and USD0.2577/1 used after the private test. Tokens are no longer a limit, so a hosted run can make 28 more attempts. |
| Hosted Qdrant | Holds the earlier index `index_a3282c4d98cf54595e4ba168`. Without `MOTOMEDIC_QDRANT_URL`, the runtime searches the pinned section-index vectors in the image. |

## Known limits

- **The gate checks form, not meaning.** It checks structure, citations, numbers and warning decisions. A non-numeric claim in an uncited disclaimer passes.
- **Restatement.** The same fact often appears in both `answer` and `policy` or `watchouts`, as in the local example.
- **Internal wording.** Phrases such as "sections supplied" reached 2 of 30 answers.
- **Warnings outside the retrieved sections.** A warning printed in another section reaches the model only if that section is retrieved.
- **The no-retrieval path never fires in practice,** because dense search always returns 5 chunks; abstention comes from the model routing UNSUPPORTED.
- **No held-out evidence.** The 30 questions are development cases, and no hosted run of v11.1 exists.
