# Quality round v1: development measurements (25 October 2026)

These measurements were run locally on the 30 development questions of the [v3 run](../20261025_answer_release_v3/README.md), with no model calls. They set or checked the five changes of [owner decision v6](../../releases/owner_decision_v6.json) before the [held-out test](../20261025_heldout_v1/README.md). The held-out questions were not used here.

## Repetition and internal wording (suggestions 2 and 3)

[replay_v3_drafts.py](replay_v3_drafts.py) replays the 90 saved v3 drafts through the current gate, on the exact inputs each draft was written for ([replay_v3_drafts.json](replay_v3_drafts.json)).

| Arm | Released, v3 gate | Released, v5 gate | Outcome changed | Sentences left out as repeats | Answers with a rewritten phrase |
| --- | --- | --- | --- | --- | --- |
| Haiku, default effort | 24 | 24 | 0 | 6 | 1 |
| Haiku, high effort | 30 | 30 | 0 | 4 | 2 |
| Sonnet | 29 | 29 | 0 | 0 | 1 |

Each of the 10 sentences left out is a policy item restating an answer sentence. An earlier version of the rule (word overlap in either direction) also dropped a watchout that added a consequence (GEN022) and parallel list items such as "ECO + Rear ABS OFF". The rule now asks how much of the later sentence is new: it needs at least 5 content words, at most 20% of them new.

The held-out test then found a case these drafts did not contain. Two answer steps can share their words and differ only in order: "disconnect the black negative first" and "connect the red positive first". Gate v4 dropped the second. Gate v5 compares a policy, watchout or disclaimer item only with items of earlier sections, and never drops an answer item. The table above is the v5 replay; it is identical to v4 on these drafts.

The four meta phrases ("The supplied sections", "The manual sections supplied", "These sections", "the sections shown") are rewritten to "the parts of the manual I checked". Rejecting them would have turned 2 correct Haiku-high answers into SYSTEM_ERROR. Label and field leaks such as `[E12]` are still rejected; none occurred in the 90 drafts.

## Warnings outside the sent sections (suggestion 4)

[measure_dev.py](measure_dev.py) scored each question against all 121 WARNING/CAUTION lines with the pinned cross-encoder ([dev_measurements.json](dev_measurements.json)). Of the 90 top-3 warnings, 66 were not sent; for 20 questions the best-scoring warning was not sent. Reading them, none scored above −4 while being relevant to the question. Most are look-alike text from other chapters.

Attaching chapter-wide warnings would add nothing: chapter-title sections rarely hold warnings. The gap that matters is a subsection that Docling split from its parent. In GEN004 (luggage), the ACCESSORIES AND LUGGAGE warnings did not reach LUGGAGE CATEGORIES. The index now links such subsections to their parent's warnings (see the [TRD](../../docs/TRD.md#2-section-index)). On this manual the rule links two sections, LUGGAGE CATEGORIES and FUEL FILLING LEVEL.

## "Not found" floor (suggestion 6)

The best cross-encoder score over the 5 retrieved chunks:

| Questions | Scores, lowest first |
| --- | --- |
| Answerable (19) | −7.95, −6.11, −5.47, −4.60, −2.19, … 9.23 |
| Unanswerable (11) | −9.16, −8.89, −8.23, −8.14, −6.07, … 7.12 |

The two groups overlap heavily, so the floor is a narrow early exit, not an abstention model. At −9.0 it refuses one development question (N07) and no answerable one. It is set conservatively below the lowest answerable score; the held-out test checks it for false refusals without retuning.
