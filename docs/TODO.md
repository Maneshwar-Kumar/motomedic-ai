# TODO

Items that touch Google Cloud, billing or provider spending need the owner's explicit approval first. See [status](STATUS.md) and the [decision log](DECISIONS.md).

## Answer quality (local, no approval needed)

1. **Measure on held-out questions.** Write 20–30 new questions the 30 development cases do not cover: follow-ups, multi-section questions, conflicts, unanswerable repairs, safety requests. Run them with [local experiments](EXPERIMENTS.md), have them scored, and record the run in `evals/`.
2. **Restatement.** Add "state each fact once; a watchout must add a warning, not repeat the answer" to the system prompt. Measure whether duplicates drop without losing warnings.
3. **Deterministic checks to consider.** Test each on the 30 development cases before enforcing it:
   - reject internal words and label patterns in rider text ("section", "supplied", `E12`);
   - a total length cap;
   - near-duplicate sentences across sections;
   - procedure steps only when the question asks how.
4. **Warning coverage.** Measure how often a relevant warning sits in a section that was not retrieved. If it matters, attach each section's general warnings (for example the page 15 loading warning) at index time.
5. **Default-effort Haiku.** The native schema already prevents misspelt or missing fields. Re-measure default effort with schema-checked drafts. If it clears the bar, it is cheaper and faster than effort high.

## Hosted (needs owner approval)

1. **A hosted run of v11.1.** It needs:
   - an image context with the section index at `build/section-index`;
   - a hosted build;
   - a private deployment at 0% traffic;
   - a real-model run of held-out questions, measuring latency, cost and prompt-cache reads.

   Choose exact in-image dense search or a new Qdrant collection ([export_qdrant.py](../cloud/export_qdrant.py)).
2. **Capacity.** 28 attempts remain in the 100-attempt allocation, and USD0.74 in the Haiku USD1 ledger. Decide whether either should change before a larger hosted run.
3. **Service templates.** Restore them or remove the `v15cand` tags before any `--to-latest` routing.
4. **Publish the section index** as a release asset, so reviewers can download it instead of rebuilding it.

## Repository

- **Records.** Update [deployment_status.json](../cloud/deployment_status.json) to the INR3,120/2,960 budget the next time hosted state is read back.
- **Before any promotion,** bind the source commit, image digest, compatible backend/UI/worker revisions and rollback in a new release.

## Preserved requirements

- **Input limit.** Rider questions are at most 100 words, rejected before retrieval or reservation without truncation.
- **One call.** One Haiku generation slot per turn, and none when nothing is retrieved. There is no verification, correction, retry or fallback call.
- **Failures.** Malformed, outage, quota, integrity and gate failures are SYSTEM_ERROR.
- **Owner-only changes.** Never restart stopped billing or refund the ledgers without the owner.
- **Deferred.** Photo, voice and compaction stay deferred.
