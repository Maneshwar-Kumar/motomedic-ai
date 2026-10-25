# Sonnet generation diagnostic (30 questions)

**Label: generation-stage diagnostic run with Claude Code Sonnet subagents. It is not the deployed Haiku pipeline and not answer-quality acceptance.** It answers one question: given the evidence the reviewed gate admits, does a stronger generator produce correct, verified answers? The owner asked for Sonnet so the run would avoid the exhausted shared Haiku ledger.

## Method

1. **Inputs.** For each question, the exact payload the candidate v5 gate admits was rebuilt. It holds the evidence objects with content, reviewed context and provenance, plus server-required displays and source gaps.
   - The admitted IDs match [replay_v5.json](../20261023_stage_replay_v1/replay_v5.json) for all 30 questions, and the hosted v10.15 traces for all 30.
   - Questions were blinded as Q01–Q30 ([alias_mapping.json](alias_mapping.json)).
   - No subagent saw canonical answers, gold or case IDs.
2. **Draft.** 30 isolated Sonnet subagents, one fresh session per question, each received the production `DRAFT_POLICY` verbatim ([DRAFT_INSTRUCTIONS.md](DRAFT_INSTRUCTIONS.md)).
3. **Server finalization.** [finalize.py](finalize.py) runs the production `validate_draft`, the numeric-citation guard and the v5 `select()`, then appends the mandatory displays. Drafts that fail validation are SYSTEM_ERROR, as in production.
4. **Verify.** 24 separate Sonnet subagents received the production `VERIFY_POLICY` verbatim ([VERIFY_INSTRUCTIONS.md](VERIFY_INSTRUCTIONS.md)) and judged the finalized response.
   - A release decision shows the answer.
   - Otherwise the rider sees the fixed fallback.
   - No correction round was run.
5. **Scoring.** The main agent compared released answers with the approved package's canonical answers ([compiled.json](compiled.json)). This is an agent judgment, not human review.

## Results

| Group | Released, correct | Released, wrong | Not released | Why not released |
|---|---|---|---|---|
| Golden (10) | **7** | 0 | 3 | GEN011 and GEN044: numeric-guard false positives. GEN017: verifier rejected a 17-claim draft padded with unsupported extras. |
| Partial (10) | **8** (EXP038's limit not disclosed) | 0 | 2 | GEN004: UNSUPPORTED draft carried a cited fact, so rejected. EXP037: verifier rejected a padded draft. |
| No-answer (10) | 7 correct abstentions (1 explained, 6 fixed fallback) | **0 hallucinated answers; 0 traps taken** | 3 SYSTEM_ERROR | N01, N07, N08: ideal UNSUPPORTED drafts carrying a cited clarifying fact, rejected by the validator |

The traps were all defused explicitly:
- **N01:** "110 km/h is an accessory speed limit, not a top speed."
- **N07:** "8 Ah is capacity, not CCA."
- **N08:** "11.5:1 is a compression ratio, not a test pressure."

### Same questions with deployed Haiku (private v10.15 candidate)

Of 12 Haiku-generated questions, 5 were released correct, 2 got UNSUPPORTED (GEN022 as a fallback, N03 as a correct abstention) and 5 got SYSTEM_ERROR. The errors were 3 verifier-inconsistent, 1 incomplete or refused, and 1 numeric-guard rejection. Sonnet released correct answers for GEN014, GEN022 and GEN035, which Haiku did not. Both models fail GEN044 on the same numeric guard.

## What blocks answers now (ranked)

1. **Numeric citation guard too strict.**
   - It rejects numbers echoed from the rider's question (GEN044's "300 km") and simple derived values (GEN011's "20 mm lower").
   - Fix: exempt question-echo numbers, and either drop derived arithmetic or mark it explicitly.
2. **The UNSUPPORTED route forbids cited facts.**
   - Four ideal answers (N01, N07, N08, GEN004) became SYSTEM_ERROR.
   - GEN004's approved canonical answer is exactly such an answer: UNSUPPORTED, pointing to the fitting instructions.
   - Fix: allow cited clarifying FACT claims under UNSUPPORTED, or route them as SUPPORTED with PARTIAL coverage.
3. **Over-generation.** Drafts with many claims (GEN017 had 17, EXP037 had 19) pick up unsupported extras and get rejected. Fix: tighten "answer only the question" and cap the claim count.
4. **Verifier reliability with Haiku.** 4 of 11 failures came from the verifier itself. All 24 Sonnet verdicts were well-formed and consistent. Changing models is an owner policy decision.
5. **Display noise.** Mandatory displays add unrelated text, such as the fuel-pump warnings in the E20 answer. Revisit the scope of displays from the earlier fuel refinement.
