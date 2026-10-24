# Current implementation status

The section-template answer path is the only answer path in the repository. It is tested without a provider and frozen, but **not deployed**. The owner's decisions are recorded in [owner_decision_v3.json](../reports/evals/20261025_answer_release_v3/owner_decision_v3.json) (the design) and [owner_decision_v4.json](../reports/evals/20261025_answer_release_v3/owner_decision_v4.json) (accepting the high-effort arm for integration). Deploying, uploading the index to hosted Qdrant, spending on the provider or changing billing each needs a new owner scope.

## Repository state (25 October 2026)

| Item | State |
| --- | --- |
| Answer path | Pipeline:<br>- [section index](../cloud/grounded_generation/section_index.py) `index_a609ca61c635641e0a22dc48`;<br>- [top-5 retrieval](../cloud/grounded_generation/section_retrieval.py);<br>- [plain-text sections](../cloud/grounded_generation/section_assembly.py);<br>- [one Haiku call](../cloud/grounded_generation/haiku_answer.py) at effort high;<br>- the [deterministic gate](../cloud/grounded_generation/template_answer.py), wired in [section_questions.py](../cloud/grounded_generation/section_questions.py).<br><br>Draft-then-verify, the review gate and the availability fallback are deleted. |
| Frozen release | [Serving manifest v11](../reports/public_evaluator/20261025/serving_manifest_v11.json) binds 123 inputs: code, UI, workflows, the manual, the source manifest, the owner decision and the evaluation. It pins the section index identity. It authorizes no deployment and makes no provider calls. |
| Provider-free tests | 149 backend and 77 UI tests passed locally (Windows, Python 3.14, scratch virtual environment). They cover the index, retrieval, assembly, gate, Haiku call (fake transport and ledger), questions, API → worker → saved stream → UI parser wiring, durable operations, admission and release tooling. GitHub CI runs the same list on Python 3.12. |
| Real-index parity | [serving_parity.json](../reports/evals/20261025_answer_release_v3/serving_parity.json): on the real index, the serving modules reproduce all 30 model inputs byte for byte and all 90 gate outcomes of the v3 run. A real-index turn released a cited answer with no model call (fake generator). |
| Section index files | Built locally at `build/index-v3-sections` (ignored by Git). The image must hold them at `build/section-index`, and startup verifies every file hash. They are not published as a release asset and not uploaded to hosted Qdrant. [SETUP](SETUP.md) shows how to rebuild them from the public snapshot. |

## Evaluation (local, agent-scored; not hosted or human acceptance)

[Section answer path v3](../reports/evals/20261025_answer_release_v3/README.md), 30 questions, isolated Claude Code subagents as generators. All 19 answerable questions had every gold object inside the sections sent. Median model input was 5,261 characters.

| Arm | Released | Correct | Unfaithful cited items | Internal wording |
| --- | --- | --- | --- | --- |
| Haiku, default effort | 24 | 24 | 0 of 62 | 1 |
| **Haiku, high effort** | **30** | **30** | 0 of 65 | 2 |
| Sonnet | 29 | 28 | 0 of 44 | 1 |

The integration bar was no unfaithful cited statement and at least 27/30 correct, for the default-effort Haiku arm. That arm missed it: it had six structural gate failures and no factual errors. The integration was first stopped and reverted (`2c35869`). The owner then accepted the high-effort arm (30/30, 0 unfaithful) as meeting the bar and had the integration merged ([owner_decision_v4.json](../reports/evals/20261025_answer_release_v3/owner_decision_v4.json)). The runtime therefore uses effort `high`. Its hosted latency and cost are not measured.

## Hosted state

| Item | Recorded state |
| --- | --- |
| Billing and services | The budget guard disabled billing on `motomedic-ai-20261009` on 22 October (delayed INR2,547.79 against INR2,540). For the owner-authorized private test of 23 October, billing was re-linked, the budget raised to INR3,120 and the guard to INR2,960, then billing was disabled again. The hosted services do not serve. Their revisions predate this design; do not route traffic to them. |
| Candidate tags | Revisions tagged `v15cand` (minimum 0 instances, 0% traffic) are still in the service templates. Restore the templates or remove the tags before any `--to-latest` routing. |
| Shared Haiku ledger | 72/100 attempts, 1,949,856/2,000,000 tokens, USD0.2577/1 after the private test. A single-call turn reserves its counted input plus 2,312 tokens. That is estimated at 5,000–7,000 tokens for the evaluation inputs, but not measured on the API. The 50,144 remaining tokens therefore cover only a few questions. |
| Hosted Qdrant | Holds the earlier index `index_a3282c4d98cf54595e4ba168`. Without `MOTOMEDIC_QDRANT_URL`, the runtime uses exact search over the pinned section-index vectors in the image. |

## Known limits

- **What the gate cannot see.** It checks structure, citations, numbers and warning decisions, not meaning. A non-numeric claim in an uncited disclaimer is not caught.
- **Wording and length.** Both Haiku arms often restate a fact in both `answer` and `policy`. "Sections supplied" wording appeared in 2 of 30 Haiku-high answers. These are candidates for deterministic checks; the [TODO](../TODO.md) lists them.
- **Warnings that are not sent.** A warning printed in another section reaches the model only if that section is retrieved.
- **The no-retrieval path.** It never fires in practice, because dense search always returns 5 chunks. Abstention comes from the model routing UNSUPPORTED.
- **The 30 questions.** They are now development cases and cannot serve as held-out evidence.
- **Source facts.** The source remains the 149-page RAM00818/A manual, SHA `cf221a29…7e80da89`. Docling's page 103 parse gap stays flagged.
