# Answer-quality regression gate

CI cannot call the model, so the provider-free tests check behaviour, not answer quality. This gate fills that gap. **No prompt, model, index, retrieval or assembly change ships** (a serving freeze is refused) unless a regression run of that exact path meets the bar below. The same check runs in CI on every push.

## The set

[set_v1.json](set_v1.json) holds 63 questions:
- the 30 development questions of the [v3 run](../20261025_answer_release_v3/README.md);
- the 33 [held-out questions](../20261025_heldout_v1/README.md), including 3 follow-up pairs.

Both sets have been seen, so this set detects regressions. It is not held-out evidence.

Each case has deterministic checks on the released rider text, matched case-insensitively with dashes, quotes and spaces normalized:

| Check | Meaning |
| --- | --- |
| `routes` | The routes the answer may take |
| `require` | Groups of alternatives; every group must match. Values come from the canonical or reference answer, for example `589` and `507` for the fork oil. |
| `forbid` | Patterns that must not match: invented values on not-in-manual questions and known traps, such as a top speed or a compression pressure. |
| `warnings` | Required warnings, counted separately |
| `pages` | Reference pages that retrieval should reach, counted separately |

A case **passes** when it is released on an allowed route, every `require` group matches and no `forbid` pattern matches.

The checks were calibrated against independent judgments before any threshold was set. They agree with all 66 blind-judged held-out answers and all 90 judged v3 answers. Calibration fixed four check errors (gap "0.8 mm to 0.9 mm", "litres", "roll-over", and an over-strict H21 requirement). It never loosened a check to pass a wrong answer.

## The bar

| Total | Threshold | Baseline ([20261029_regression_v1](../20261029_regression_v1/README.md)) |
| --- | --- | --- |
| Cases passed | at least 46 | 48 of 63 |
| SYSTEM_ERROR turns | at most 4 | 3 |
| Forbidden matches | at most 1 | 1 |
| Required warnings shown | at least 19 | 20 of 24 |
| Reference pages reached | at least 80 | 80 of 111 |

Two runs of the 33 held-out questions, four days apart, differed by one case and one warning. Answers therefore get a small tolerance. Retrieval is deterministic, so it gets none. Raising the bar is the expected direction. Lowering it is a visible change to this file and needs a reason in the commit.

## How a change ships

1. **Run.** Answer the set with the changed path. Prepare every turn, write one draft per turn, release, then prepare and answer the follow-ups ([EXPERIMENTS](../../docs/EXPERIMENTS.md)):

   ```sh
   python tools/regression.py prepare --run evals/<date>_regression_<n> --model <bge_m3_dir>
   # one Claude Code Haiku subagent per prepared folder writes draft.json
   python tools/regression.py release --run evals/<date>_regression_<n>
   python tools/regression.py prepare --run evals/<date>_regression_<n> --model <bge_m3_dir> --turn 2
   # drafts for the follow-ups, then release again
   python tools/regression.py score --run evals/<date>_regression_<n>
   ```

2. **Point and freeze.** Set `CURRENT` in [tools/regression.py](../../tools/regression.py) to the new run, then freeze a new serving manifest. The freeze binds the receipt and refuses if the bar is not met.
3. **CI.** `python tools/regression.py check` runs on every push and does the following:
   - the receipt must name the current answer identity (index, retrieval constants, assembly version, generation contract and system prompt hash);
   - every saved model input and schema is rebuilt from the saved sections and must match byte for byte;
   - every saved draft is passed through the current gate and rescored with the current set;
   - the totals must meet the bar.

A **gate-only change** is checked this way without a new model run. A **prompt, model, index, retrieval or assembly change** makes the receipt stale, and CI fails until a new passing run is committed.

## Limits

- **Local generation.** The generator is a local Claude Code subagent at the runtime's model and effort, not the hosted API call.
- **Pattern checks.** The checks test the presence of facts and the absence of known traps. They do not prove faithfulness beyond what the gate checks.
- **Retrieval in CI.** Retrieval is not recomputed in CI, which has no index or BGE-M3. It is bound by index ID and retrieval constants, and [reproduce-offline](../../.github/workflows/reproduce-offline.yml) recomputes it on demand.
