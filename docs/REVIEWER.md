# Reviewer guide

The [repository](https://github.com/Maneshwar-Kumar/motomedic-ai) and the supplied manual are public. Work is on `codex/public-evaluator`, in [PR #4](https://github.com/Maneshwar-Kumar/motomedic-ai/pull/4); `main` is the baseline. The answer path is frozen as [serving manifest v11](../reports/public_evaluator/20261025/serving_manifest_v11.json) and is **not deployed**. The hosted services are offline while billing is disabled, so review the code, tests and evaluations rather than a live URL.

## What to read

| Question | Where |
| --- | --- |
| What does a turn do? | [Architecture](ARCHITECTURE.md), then [section_questions.py](../cloud/grounded_generation/section_questions.py) |
| What exactly does the model see and return? | [section_assembly.py](../cloud/grounded_generation/section_assembly.py) and `SYSTEM_PROMPT` and `answer_schema` in [template_answer.py](../cloud/grounded_generation/template_answer.py). An example input is [Q01](../reports/evals/20261025_answer_release_v3/inputs/Q01.txt). |
| What does the gate reject? | `gate()` in [template_answer.py](../cloud/grounded_generation/template_answer.py) and its tests in [test_section_answer.py](../cloud/grounded_generation/test_section_answer.py) |
| How is the paid call bounded? | [haiku_answer.py](../cloud/grounded_generation/haiku_answer.py) and [whole_turn_admission.py](../cloud/grounded_generation/whole_turn_admission.py) |
| Why this design? | [Section answer path v3](../reports/evals/20261025_answer_release_v3/README.md) and the [owner decision](../reports/evals/20261025_answer_release_v3/owner_decision_v3.json) |
| What is frozen? | [Serving manifest v11](../reports/public_evaluator/20261025/serving_manifest_v11.json) and [serving_release.py](../tools/serving_release.py) |

## Checks you can run

The [setup guide](SETUP.md) lists the commands:
- the provider-free tests;
- the frozen-input check;
- rebuilding the section index from the public snapshot's cached parse;
- the real-index [parity check](../reports/evals/20261025_answer_release_v3/serving_parity.py).

None of them makes a model call. The [CI workflow](../.github/workflows/ci.yml) is the authoritative test list.

## How to weigh the evidence

The v3 evaluation is local and agent-scored. Isolated Claude Code subagents were the generators, and the main agent judged their answers against the package's canonical answers. It is not hosted, human or independent factual acceptance, and its 30 questions are now development cases. A gate release proves that structure, citations, numbers and warning decisions passed, not that the meaning is right. Hosted acceptance needs a real-model run of new held-out questions on the frozen runtime; see [TODO](../TODO.md).

Credentials, rider records and private model outputs are never in the repository. Reviewing does not restart billing, reset any ledger or create an allocation.
