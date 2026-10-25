# Verifier-free template release (30 questions)

**Label: local candidate diagnostic with Claude Code Sonnet subagents as the generator. Not deployed, not the Haiku pipeline, no human signoff, not answer-quality acceptance.** The design follows the owner decisions in [owner_decision_v1.json](owner_decision_v1.json) and [owner_decision_v2.json](owner_decision_v2.json). The design documents now describe this path; deployed v10.14 still drafts and verifies until a new serving version ships.

## Design under test (gate v2)

- **One generator call.** The generator fills the agreed template:
  - `answer`, `policy` and `watchouts` are cited sections.
  - `disclaimers` may cite.
  - `watchout_review` holds an explicit decision for every listed warning.

  Empty sections may be left out. `route` and `coverage` are always present, and they record the other decisions: a route other than AMBIGUOUS means no clarification was needed, and COMPLETE coverage means no limit had to be disclosed. There is no semantic verifier and no correction round. The policy text is `ANSWER_POLICY` in [candidate/answer_release.py](candidate/answer_release.py).
- **Watchout candidates.** These are the admitted objects that the parser placed under a WARNING or CAUTION heading (`section_path` in the index's `parents.jsonl`). There is no authored list. The model chooses which watchouts to show. The gate checks only that every candidate was decided, that each INCLUDED one is cited in `watchouts`, and that each NOT_APPLICABLE one has a reason.
- **Deterministic gate.** If any of these checks fails, the turn is a SYSTEM_ERROR:
  - Schema and per-section caps (answer 6, policy 3, watchouts 5, disclaimers 3).
  - Every cited item cites only admitted evidence.
  - Every number in a cited item appears in the cited object or in the rider's question.
  - Every page reference belongs to a cited object.
  - An uncited disclaimer may not state a measurement or a page.
  - Route rules: PARTIAL needs a disclaimer, and AMBIGUOUS needs a clarification question.
  - The watchout review check described above.
- **Not in the manual.**
  - When nothing is admitted, no model call is made.
  - When the model routes UNSUPPORTED, the rider sees any cited clarifying facts, then the fixed fallback and the manifest support route (`mailto:support@royalenfield.com`). Model-written disclaimers are not shown.
- **Tests.** [candidate/test_answer_release.py](candidate/test_answer_release.py): 7 pass with zero provider calls.

## Method

1. The same 30 questions, the same blind aliases ([alias_mapping](../20261024_sonnet_generation_v1/alias_mapping.json)) and the same v5-admitted evidence as the [stage replay](../20261023_stage_replay_v1/README.md). The inputs are in [inputs/](inputs/).
2. 30 isolated Sonnet subagents, one fresh session per question, followed [ANSWER_INSTRUCTIONS_v1.md](ANSWER_INSTRUCTIONS_v1.md). No subagent saw canonical answers, gold or case IDs. Their outputs are in [drafts/](drafts/).
   - Two subagents wrote their file through a shell command rather than the Write tool.
   - The drafts were not regenerated for gate v2.
3. [run_gate.py](run_gate.py) rebuilds each payload with the v5 authority, asserts that the shown evidence and candidates match it, and runs the gate:
   - [gate_results_v1.json](gate_results_v1.json) comes from the v1 gate at commit `f95f22d`;
   - [gate_results_v2.json](gate_results_v2.json) comes from the current gate.
4. [score_release.py](score_release.py) records the main agent's judgment ([scored_v1.json](scored_v1.json), [scored_v2.json](scored_v2.json)):
   - every cited item was read against the text of each object it cites;
   - each released answer was compared with the approved package's canonical answer.

## Results

| Group | v1 gate | v2 gate (same drafts) | Before: Sonnet draft + verify ([run](../20261024_sonnet_generation_v1/README.md)) |
|---|---|---|---|
| Golden (10) | 9 released, all correct. GEN011 failed: empty field omitted. | **10 released, all correct** | 7 released, 3 not |
| Partial (10) | 10 released; EXP040 weaker than canonical | **9 released, all correct.** EXP040 failed closed: uncited disclaimer refers to "page 116". | 8 released, 2 not |
| No-answer (10) | 10 abstentions in model wording | **10 fixed fallbacks with the support route**. 3 cited clarifying facts first (N01, N07, N08). 3 made no model call (N03, N09, N10). | 7 abstentions, 3 SYSTEM_ERROR |

- **Faithfulness.** All 54 cited items shown under v2 (56 under v1) are stated by the objects they cite. No invented number, repair or page reached a released answer.
- **Internal wording.** Riders see it in 2 of 29 answers (GEN030, EXP027), down from 13. The fixed fallback removed the rest.
- **Calls.** v2 makes 27 provider calls for 30 questions; draft-then-verify made two per question, plus a correction when one was needed. Latency was not measured, because subagent timings are not API timings.
- **Watchouts.** Each case had between 0 and 27 candidates. The model included 9 across 6 cases and gave a reason for every exclusion. Candidates are broad because admitted closure is broad (USB had 23).

## Why the remaining problems happen

- **Internal wording.**
  - The generator input labels evidence as "admitted", lists `source_gaps` as "retrieved but NOT citable", and carries `reviewed_source_context`.
  - The policy forbids claiming the manual lacks something ("a failed search does not prove the manual lacks it").
  - When the model must state a limit, it therefore describes exactly what it saw, in the vocabulary it was given.
  - Production's draft policy asks for the same "honest limited-evidence explanation". There the verifier always replaced UNSUPPORTED text with the fixed fallback, which hid the wording.
- **GEN030, display languages.**
  - The answer lists all six languages, but marks itself PARTIAL. Its disclaimer says other retrieved passages could not be used, so the list may be incomplete.
  - The three source gaps were unrelated (dark theme on p41, a navigation note on p57, the 24-hour clock on p60). The model saw only their IDs and could not tell.
  - The three menu-navigation sentences come from the same page 50–51 list as the languages. Admission returns the whole reviewed list, and the policy does not say to leave out unasked steps.
- **EXP040.** The v1 instructions did not tell the model that a disclaimer mentioning a page must cite. The v2 policy does, and the gate now enforces it.
- **What the gate cannot catch.** A non-numeric factual claim in an uncited disclaimer (for example, "the manual says use the first notch") passes. This is the residual risk of having no semantic verifier.
