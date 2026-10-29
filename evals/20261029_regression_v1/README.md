# Regression baseline v1 (29 October 2026, local)

**Label:** local Claude Code subagent run, deterministic score. Not hosted, API or human acceptance.

This is the first run of the [regression set](../regression/README.md). It sets the bar that the current serving path (manifest v11.3, the v11.2 answer path) is held to. [receipt.json](receipt.json) binds it to that path's answer identity:
- index `index_f768fbb216836c003701079e`;
- retrieval `section-top5-hybrid-v2`;
- assembly `section-plain-text-v2`;
- `claude-haiku-5-5` at effort high, with the current system prompt hash.

## How it ran

- **Setup.** A new Python 3.12.14 environment installed from [tools/requirements-experiments.txt](../../tools/requirements-experiments.txt), the published section index and BGE-M3 at its pinned revision. The receipt records the package versions.
- **Turns.** [tools/regression.py](../../tools/regression.py) prepared 63 turns. N07 fell below the relevance floor and got the fixed fallback with no model call. The other 62 turns each had one isolated Claude Code Haiku subagent at effort high write the draft, and the three follow-ups were prepared from their first turn's released text.
- **Scoring.** The gate (`template-answer-v5`) released each draft, and the set's checks scored the released text.

## Result

| Total | Result | Bar |
| --- | --- | --- |
| Cases passed | 48 of 63 (development 26 of 30, held-out 22 of 33) | at least 46 |
| SYSTEM_ERROR turns | 3 (N03, N08, N09) | at most 4 |
| Forbidden matches | 1 (H05: a false "the manual does not say" claim) | at most 1 |
| Required warnings shown | 20 of 24 | at least 19 |
| Reference pages reached | 80 of 111 | at least 80 |

The held-out half agrees with the [25 October run](../20261025_heldout_v1/README.md): 22 cases passed against 21, and only H24 changed. Its failures are the same retrieval and omission gaps described there.

## What it found

**A regression from the quality round.** The v3 drafts of the 30 development questions all pass these checks; this run passes 26 of them. Three of the four lost cases share one failure. On a not-in-the-manual question, the model writes "The manual does not give X" as an uncited answer item, so the gate fails the turn closed as SYSTEM_ERROR (N03, N08, N09; H24 did the same on 25 October). The v3 drafts of these questions wrote no such sentence: they gave only cited facts, or nothing, and left the limit to the fixed fallback. The likely cause is the v4 prompt rule that asks for limits to be phrased as "the manual does not give". It prompts a limit sentence, and on an UNSUPPORTED route the model files it as an uncited answer item. The fourth lost case, EXP040, gave only one of the two notch settings the manual states.

Two fixes are possible, and the [TODO](../../docs/TODO.md) lists them:
- **Prompt.** Send limit sentences to `disclaimers`. This needs a new regression run.
- **Gate.** Treat an uncited answer item on an UNSUPPORTED route as a suppressed disclaimer. CI checks this from this run, with no model call.

## Files

- **[runs/](runs/):** for each turn, the question, retrieval, model input, schema, instructions, draft and release.
- **[receipt.json](receipt.json):** answer identity, generator, environment, per-case results and totals.
