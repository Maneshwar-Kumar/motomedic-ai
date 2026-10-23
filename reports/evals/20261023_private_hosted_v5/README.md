# Private hosted v10.15 candidate run (reviewed v5 gate)

**Label: owner-authorized private hosted test ([owner_scope_v1.json](owner_scope_v1.json)). 0% public traffic, not public release, no human signoff, not answer-quality acceptance.**

## What was deployed

- **Image.** `arm-a@sha256:c56d978a…0da7041`, built in Cloud Build (`618267e7`). It is an overlay on the exact v10.14 backend image `531b0478…`.
  - The overlay adds the approved [structural_review_v2](../../grounded_generation/structural_review_v2/README.md) package and the v5 gate.
  - It changes one import line in `serving_questions.py`, with sources in [overlay/](overlay/) at commit `5cbf1fd`.
  - The image build ran the installed-release check, which passed.
- **Tagged revisions.** Both are tagged `v15cand`, have minimum 0 instances, and take 0% of public traffic:
  - `motomedic-arm-a-v10-15-cand-v5`
  - `motomedic-answer-worker-v10-15-cand-v5`

  Public traffic stayed 100% on v10.14 throughout. Candidate runtime lock: `14476bad…`.
- **Billing.** Re-linked for the test, with the budget raised from INR 2,700 to 3,120 and the guard from INR 2,540 to 2,960. Billing was disabled again afterwards.

## Runs

| Job | Questions | Client |
|---|---|---|
| `2fa01e0c` | 17 (golden, then partial) before limits | [hosted_v5_client.py](hosted_v5_client.py), source embedded in the build config and hash-checked |
| `759bf9ba` | 13 remaining, paced 15 s apart | same client, `--only`, `--min-interval-seconds 15` |

Each question ran as a fresh session with one POST and no retries, and saved, streamed and recovered views were compared. Artifacts: [hosted_run_2fa01e0c…](hosted_run_2fa01e0c-80b3-40bf-a625-befdc341b9ff/) and [hosted_run_759bf9ba…](hosted_run_759bf9ba-7469-4c89-9df6-59fe917e3c0e/). Scores: [scored_hosted.json](scored_hosted.json) and [scored_hosted_paced.json](scored_hosted_paced.json), produced by [score_hosted.py](score_hosted.py).

## Results

| Check (deployed candidate) | Result |
|---|---|
| Hosted retrieval and admission traced | 30/30 |
| Hosted admitted evidence matches the local v5 replay | 30/30 (final chunk lists 29/30; GEN048's chunk order differed, same admitted set) |
| **Answer evidence admitted to generation (20 answerable)** | **20/20** (deployed v10.14: 8 full, 1 partial) |
| Haiku generation ran | 12 questions. The rest stopped at the shared ledger's token ceiling (`PROVIDER_WHOLE_TURN_ALLOCATION_LIMIT`) with zero calls. |
| Haiku outcomes (12) | 5 SUPPORTED, all correct and citing gold (GEN007, GEN012, GEN025, GEN030, EXP027). 2 UNSUPPORTED (GEN022 fallback despite admitted evidence; N03 correct abstention). 5 SYSTEM_ERROR (3 `VERIFIER_INCONSISTENT_ACCEPTANCE`, 1 `PROVIDER_INCOMPLETE_OR_REFUSED`, 1 `NUMERIC_CLAIM_CITATION_NOT_SUPPORTED`). |

The generation stage for all 30 was measured separately with Sonnet: [20261024_sonnet_generation_v1](../20261024_sonnet_generation_v1/README.md).

## Ledger and limits

- **Shared Haiku ledger after the run:** 72 of 100 attempts, 1,949,856 of 2,000,000 tokens, USD 0.2577 of 1.00. No reset or refund.
- **Reservation size:** each question reserves about 88k tokens, as whole-turn worst-case ceilings.
- **Consequence:** the remaining headroom is below one question, so **no Haiku answer can be produced anywhere, including public, until the owner raises the token ceiling**.
- **Rate limit:** the per-identity cap of 6 turns a minute and 30 a day stopped the first job at the minute limit. The paced job stayed within it.

## State left behind

- **Billing:** disabled (`motomedic-ai-20261009`). The budget stands at INR 3,120 and the guard at INR 2,960.
- **Candidate revisions and tags:** remain at 0% traffic and minimum 0 instances, so they cost nothing.
  - The service templates now describe the candidate revision, while traffic is pinned to v10.14.
  - Before any `--to-latest` routing, restore the templates, or remove the tags with `gcloud run services update-traffic <svc> --remove-tags v15cand`.
- **Run archive object:** stays in the private indices bucket. The conditional IAM grant was not made, because the auto-mode classifier declined it; the job embedded its source instead.
