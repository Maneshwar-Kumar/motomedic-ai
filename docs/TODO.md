# TODO

Items that touch Google Cloud, billing or provider spending need the owner's explicit approval first. See [status](STATUS.md) and the [decision log](DECISIONS.md).

## Answer quality (local, no approval needed)

The quality round of 25 October ([held-out test](../evals/20261025_heldout_v1/README.md)) left these, in order of measured effect. Test each on development questions, then on a **new** held-out set; the 33 held-out questions have been seen.

1. **Reach a second place in the manual.** 6 of 33 held-out shortfalls were facts the 5 chunks did not contain: menu paths that start on page 39, the coolant grade in the lubricants table, the trailer warning on page 11. Options to measure:
   - a larger top-k with the whole-section rule;
   - adding the best-scoring chunk of another chapter;
   - a query rewrite for "how do I" questions.
2. **Scope "the manual does not give X".** Every wrong held-out answer is such a claim, made when the fact sat in a section that was not sent, or was misread. Options:
   - a gate rewrite to "the parts of the manual I checked do not give X";
   - a prompt rule that limits must name what was checked.
3. **Facts left out of sent sections.** About 6 shortfalls (the 12 V LED headlamp, the 350 ml between oil marks, the 10 Nm adjuster bolt) were sent but dropped. Measure a prompt rule to give every value of a cited table row or step.
4. **An uncited "not in the manual" sentence in `answer`.** It failed H24 closed. Measure whether the prompt should send such sentences to `disclaimers`.
5. **Relevance floor.** At −9.0 it refused nothing on new questions. Either calibrate a better relevance signal or remove the floor; MiniLM scores of answerable and unanswerable questions overlap.
6. **Default effort.** On new questions it matched effort high on correctness (21/33 each), with no schema slips, but showed 2 fewer required warnings. Moving the runtime to default effort needs an owner decision and a hosted cost and latency measurement.

## Hosted (needs owner approval)

1. **A hosted run of v11.2.** It needs:
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
