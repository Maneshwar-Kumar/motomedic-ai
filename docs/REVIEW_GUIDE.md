# Review guide

This guide is for someone reviewing MotoMedic for the first time. It says what to read, in what order, what each claim rests on, and how to check it yourself. None of these checks needs an account, key or paid call.

## 1. What the system is (10 minutes)

1. [README](../README.md): what MotoMedic does, the answer path in six steps, and the repository map.
2. [Architecture](ARCHITECTURE.md): what runs where, and one rider turn step by step.
3. [Status](STATUS.md): what is built, frozen, tested, measured and not yet done.

## 2. What the model sees and returns (20 minutes)

| Question | Read |
| --- | --- |
| How is the manual split and searched? | [section_index.py](../cloud/grounded_generation/section_index.py) and [section_retrieval.py](../cloud/grounded_generation/section_retrieval.py) |
| What text reaches the model? | [section_assembly.py](../cloud/grounded_generation/section_assembly.py). A real example input is [Q01](../evals/20261025_answer_release_v3/inputs/Q01.txt). |
| What is the model told, and what must it return? | `SYSTEM_PROMPT` and `answer_schema` in [template_answer.py](../cloud/grounded_generation/template_answer.py) |
| What does the gate reject? | `gate()` in [template_answer.py](../cloud/grounded_generation/template_answer.py), with examples in [test_section_answer.py](../cloud/grounded_generation/test_section_answer.py) |
| How is the one paid call bounded? | [haiku_answer.py](../cloud/grounded_generation/haiku_answer.py) and [whole_turn_admission.py](../cloud/grounded_generation/whole_turn_admission.py) |
| How does one turn run end to end? | [section_questions.py](../cloud/grounded_generation/section_questions.py), then the worker in [durable_dispatch.py](../cloud/arm_a/durable_dispatch.py) and the API in [rider_api.py](../cloud/arm_a/rider_api.py) |

## 3. Why it is built this way (15 minutes)

- [Decision log](DECISIONS.md): every owner decision, in order, with its record.
- [Evaluations](../evals/README.md): five runs on the same 30 questions, in the order the design changed, then the [held-out test](../evals/20261025_heldout_v1/README.md) on 33 new questions. The [section answer path v3](../evals/20261025_answer_release_v3/README.md) is the evidence for the current design.

## 4. Check the claims yourself

| Claim | Check |
| --- | --- |
| The repository is laid out as documented and every link resolves. | `python tools/check_repository_structure.py` |
| The serving code is exactly what release v11.3 froze. | `python tools/serving_release.py verify` |
| The current answer path meets the answer-quality bar, and no prompt, model or index change has slipped past it. | `python tools/regression.py check` ([regression gate](../evals/regression/README.md)) |
| The offline tests are reproducible from `main`. | [reproduce_offline.py](../tools/reproduce_offline.py), or the [reproduce-offline workflow](../.github/workflows/reproduce-offline.yml) on GitHub |
| Logs carry no rider text. | [test_telemetry.py](../cloud/common/test_telemetry.py) and the [privacy policy](PRIVACY.md) |
| The code behaves as specified: retrieval, assembly, gate, the paid call's validation and ledger, the API → worker → saved stream → UI path. | The provider-free suite in [SETUP](SETUP.md), also run by [CI](../.github/workflows/ci.yml) |
| The serving modules reproduce the v3 run's 30 model inputs and 90 gate outcomes on the previous index (on the current index only GEN004 differs, by its added luggage warnings). | [serving_parity.py](../evals/20261025_answer_release_v3/serving_parity.py) (needs the index; [SETUP](SETUP.md) shows how to rebuild it) |
| A new question goes through the real path. | [EXPERIMENTS](EXPERIMENTS.md): real retrieval and gate here, with a Claude Code Haiku subagent as the generator |

## 5. How to weigh the evidence

- **The evaluations are local and agent-scored.** Claude Code subagents generated the answers, and the main agent compared them with the canonical answers of an earlier review package. None of it is hosted, human or independent factual acceptance. The 30 questions are development cases. The 33 held-out questions were new when run, with a blind agent judge, and are now spent.
- **The gate checks form, not meaning.** It proves that structure, citations, numbers, page references and warning decisions passed; a released answer can still be wrong in meaning.
- **Tests use synthetic data.** They run on a synthetic index, a fake model transport and an in-memory store, so they prove behavior, not answer quality or latency.
- **The hosted service is not running this release.** Hosted latency, cost and prompt-cache use are unmeasured.

## 6. History

[archive/](../archive/README.md) keeps earlier designs and their evidence:
- the draft-then-verify runtime;
- the review packages;
- frozen manifests v8–v10.14;
- hosted run receipts and retired code.

The current path does not use any of it.
