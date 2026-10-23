# Verifier-free template release (30 questions)

**Label: local candidate diagnostic with Claude Code Sonnet subagents as the generator. Not deployed, not the Haiku pipeline, no human signoff, not answer-quality acceptance.** The design follows the owner decision in [owner_decision_v1.json](owner_decision_v1.json). PRD FR-06/FR-07, the TRD, ARCHITECTURE and AGENTS still describe draft-then-verify, so they must be reconciled before this design can be adopted.

## Design under test

- **One generator call.** The generator fills the agreed template:
  - `answer`, `policy` and `watchouts` are cited sections.
  - `disclaimers` are uncited.
  - `watchout_review` holds an explicit decision for every listed warning.

  There is no semantic verifier and no correction round. The policy text is `ANSWER_POLICY` in [candidate/answer_release.py](candidate/answer_release.py); the generator's instructions are in [ANSWER_INSTRUCTIONS.md](ANSWER_INSTRUCTIONS.md).
- **Watchout candidates.** These are the admitted objects that the parser placed under a WARNING or CAUTION heading (`section_path` in the index's `parents.jsonl`). There is no authored list. The model chooses which watchouts to show. The gate checks only that every candidate was decided, that each INCLUDED one is cited in `watchouts`, and that each NOT_APPLICABLE one has a reason.
- **Deterministic gate.** If any of these checks fails, the turn is a SYSTEM_ERROR:
  - Schema and per-section caps (answer 6, policy 3, watchouts 5, disclaimers 3).
  - Every cited item is non-empty and cites only admitted evidence.
  - Every number in a cited item appears in the cited object or in the rider's question.
  - Route rules: PARTIAL and UNSUPPORTED need a disclaimer, and AMBIGUOUS needs a clarification question.
  - The watchout review check described above.

  Tests: [candidate/test_answer_release.py](candidate/test_answer_release.py), 5 pass with zero provider calls.

## Method

1. The same 30 questions, the same blind aliases ([alias_mapping](../20261024_sonnet_generation_v1/alias_mapping.json)) and the same v5-admitted evidence as the [stage replay](../20261023_stage_replay_v1/README.md). The inputs are in [inputs/](inputs/).
2. 30 isolated Sonnet subagents, one fresh session per question. No subagent saw canonical answers, gold or case IDs. Their outputs are in [drafts/](drafts/). Two subagents wrote their file through a shell command rather than the Write tool; the gate treats every file the same way.
3. [run_gate.py](run_gate.py) rebuilds each payload with the v5 authority and asserts that the shown evidence and candidates match it, then runs the gate. Output: [gate_results.json](gate_results.json).
4. [score_release.py](score_release.py) records the main agent's judgment ([scored.json](scored.json)):
   - every cited item was read against the text of each object it cites;
   - each released answer was compared with the approved package's canonical answer.

## Results

| Group | Released | Matches canonical | Not released | Before: Sonnet draft + verify ([run](../20261024_sonnet_generation_v1/README.md)) |
|---|---|---|---|---|
| Golden (10) | 9 | 9 | 1: GEN011, the draft omitted the empty `clarification_question` field | 7 released, 3 not |
| Partial (10) | 10 | 9 (EXP040 weaker) | 0 | 8 released, 2 not |
| No-answer (10) | 10 abstentions | 10; all three traps defused with a cited fact | 0 | 7 abstentions, 3 SYSTEM_ERROR |

- **Faithfulness.** All 56 cited answer, policy and watchout items are stated by the objects they cite. No invented number, repair or page reached a released answer.
- **Previously blocked, now released:**
  - GEN044 ("300 km" is exempt because the rider said it).
  - GEN017 and EXP037 (no server-appended warning padding).
  - GEN004, N01, N07 and N08 (UNSUPPORTED may carry cited facts).
- **Watchouts.** Each case had between 0 and 27 candidates. The model included 9 across 6 cases and gave a reason for every exclusion. Candidates are broad because admitted closure is broad; for example, USB had 23 candidates, mostly fuse and fuel cautions. That costs tokens, not correctness.
- **Calls.** Each turn makes one provider call; before, each turn made a draft call and a verify call, plus a correction when one was needed. Latency was not measured, because subagent timings are not API timings.

## Problems found (not fixed here)

1. **Internal wording reaches riders in 13 of 29 released answers.**
   - Examples: "the admitted manual evidence does not state…" and "passages retrieved".
   - N10 tells the rider that "source context was not fully reviewed".
   - GEN030 marks a complete six-language answer PARTIAL with a disclaimer of this kind.
2. **Disclaimers are not checked.** They are uncited, and the number check skips them. EXP040's disclaimer cites pages and a setting; it is accurate here, but nothing would have stopped an inaccurate one.
3. **Conflicts are under-hedged.** EXP040 discloses the conflict between pages 116 and 117 but leans to the 3rd notch and marks coverage COMPLETE. The canonical answer says the setting cannot be verified and the rider should confirm with authorised service.
4. **UNSUPPORTED drops the PRD fixed fallback and support route.** The rider sees model-written disclaimers instead.
5. **Schema slips fail closed** (GEN011). A strict output schema on the API call would prevent this class of failure.
6. **Length.** EXP044 runs to 9 items (1,483 characters) and GEN030 adds unasked navigation steps. The caps hold, but they are loose.
