# MotoMedic TODO

The section-template answer path is implemented, tested without a provider and frozen as [serving manifest v11](reports/public_evaluator/20261025/serving_manifest_v11.json). It is not deployed. Each item below that touches GCP, billing, the Haiku ledger or provider spending needs the owner's explicit scope first. See [status](docs/STATUS.md).

## Next

1. **Owner scope for a hosted v11 run.** It covers:
   - preparing the image context with the section index at `build/section-index`;
   - a hosted build and private deployment at 0% traffic;
   - one real-model run of the 30 development questions plus new held-out questions;
   - measuring latency, cost and prompt-cache reads at effort `high`.

   Decide whether dense search uses exact in-image search or a new hosted Qdrant collection ([export_qdrant.py](cloud/export_qdrant.py) reads the section index).
2. **Haiku capacity.** The ledger has 50,144 tokens left under its 2,000,000 ceiling, which covers only a few single-call turns. Running the hosted evaluation needs an owner decision on the ceiling.
3. **Service templates.** Restore them or remove the `v15cand` tags before any `--to-latest` routing.
4. **Publish the section index** as a release asset under an owner publication scope, so reviewers can download it instead of rebuilding it.

## Answer quality

Evidence is in the [v3 evaluation](reports/evals/20261025_answer_release_v3/README.md).
- **Restatement.** Haiku restates facts across `answer` and `policy`. Restore v2's "do not restate a fact in two sections" line and re-measure.
- **Internal wording.** Wording such as "sections supplied" reached 2 of 30 answers.
- **Deterministic checks to consider.** Not enforced now:
  - block internal words and label patterns in rider text;
  - a total length cap;
  - procedure steps only when the question asks how.
- **Warnings outside the retrieved sections.** For example, the general loading warning on page 15 reaches the model only when its section is retrieved. Measure how often this matters before changing retrieval.

## Repository

- **Root modules.** Root-level modules outside the serving import graph (the reviewed controller, approved registry and related tests) are historical tooling. Remove them or move them to history in a checked change.
- **Before any promotion,** bind the source commit, image digest, compatible backend/UI/worker revisions and rollback.

## Preserved requirements

- Rider questions are at most 100 words, rejected before retrieval or reservation without truncation.
- One Haiku generation slot per turn, and none when nothing is retrieved. There is no correction, verification or retry call.
- Malformed, outage, quota, integrity and gate failures are SYSTEM_ERROR.
- Never restart stopped billing, reset or refund the ledgers, or activate a fallback model without the owner.
- Photo, voice and compaction remain deferred.
