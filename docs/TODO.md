# TODO

Items that touch Google Cloud, billing or provider spending need the owner's explicit approval first. See [status](STATUS.md) and the [decision log](DECISIONS.md).

## Answer quality (local, no approval needed)

These come from the [held-out test](../evals/20261025_heldout_v1/README.md) and the [regression baseline](../evals/20261029_regression_v1/README.md), most urgent first. Every change must pass the [regression gate](../evals/regression/README.md). A quality claim needs a **new** held-out set, because both question sets have been seen.

0. **Uncited limit sentences fail closed.** On not-in-the-manual questions, the model writes "The manual does not give X" as an uncited answer item, and the turn becomes SYSTEM_ERROR. That happened on N03, N08 and N09 in the baseline, and on H24 on 25 October. It is a regression from the quality round's wording rule. Options:
   - a gate rule that treats an uncited answer item on an UNSUPPORTED route as a suppressed disclaimer, so the rider sees the cited facts and the fixed fallback. CI can check this from the saved run, with no model call;
   - a prompt rule that sends limit sentences to `disclaimers`. This needs a new regression run.
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

1. **A hosted run of v11.3.** It needs:
   - an image context with the section index at `build/section-index`;
   - a hosted build;
   - a private deployment at 0% traffic;
   - a real-model run of held-out questions, measuring latency, cost and prompt-cache reads.

   Choose exact in-image dense search or a new Qdrant collection ([export_qdrant.py](../cloud/export_qdrant.py)).
2. **Capacity.** 28 attempts remain in the 100-attempt allocation, and USD0.74 in the Haiku USD1 ledger. Decide whether either should change before a larger hosted run.
3. **Service templates.** Restore them or remove the `v15cand` tags before any `--to-latest` routing.
4. **Upload the section index to hosted Qdrant** (optional; the runtime can search the pinned vectors in the image). It needs billing re-enabled. The index is already published as a [GitHub release asset](https://github.com/Maneshwar-Kumar/motomedic-ai/releases/tag/index-f768fbb216836c003701079e).

5. **Rider data retention.** Apply the Firestore TTL policy on `expires_at`, which makes 24-hour expiry real deletion. Keep the `_Default` log bucket at 30 days ([privacy](PRIVACY.md)). Both are hosted changes.
6. **Cloud Trace export.** Spans are log entries today. Exporting them as Cloud Trace spans needs an OpenTelemetry dependency and a new freeze.

## Repository

- **Before any promotion,** bind the source commit, image digest, compatible backend/UI/worker revisions and rollback in a new release.

## Preserved requirements

- **Input limit.** Rider questions are at most 100 words, rejected before retrieval or reservation without truncation.
- **One call.** One Haiku generation slot per turn, and none when nothing is retrieved. There is no verification, correction, retry or fallback call.
- **Failures.** Malformed, outage, quota, integrity and gate failures are SYSTEM_ERROR.
- **Owner-only changes.** Never restart stopped billing or refund the ledgers without the owner.
- **Deferred.** Photo, voice and compaction stay deferred.
