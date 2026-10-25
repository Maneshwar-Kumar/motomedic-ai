# Section answer path v3: no review layer, top-5 retrieval, plain-text sections (30 questions, 3 arms)

**Label: local diagnostic. The generators were Claude Code subagents run in this session, not the Claude API or the hosted service. The main agent scored the outputs; there was no human review and this is not acceptance.** The design follows the owner's instructions of 24–25 October 2026; the changes are listed below. The 30 questions are the same as in the v2 run, and they are now development cases.

## What changed from v2

| Stage | v2 (reviewed admission) | v3 (this run) |
|---|---|---|
| Review layer | Only reviewed objects (277 of 1,691) could be cited. | Removed: every parsed object of the manual can be cited. |
| Chunk sections | Docling's flat sections. WARNING, CAUTION and NOTE boxes were sections of their own, and running page headers split sections at page breaks. | [Section index](index_v3/manifest.json) `index_a609ca61c635641e0a22dc48`, built from the cached Docling parse (no re-parse); details below. |
| Retrieval | Dense top 20 plus BM25, fused to 20; reranker over 20; 5–8 chunks kept. | Fused top **5** only. When the dense and BM25 top-3 sections differ, the reranker orders those 5 and adds nothing. |
| Model input | Raw parser JSON of a 25–49-object link closure, server-required warning displays and source-gap IDs (median about 45 KB). | The whole content section of each of the 5 chunks, as plain text lines with short labels such as `[E7] (WARNING) …`. Median 5.3 K characters. |
| Prompt and gate | v2 template and gate. | [One system prompt](candidate/template_answer.py) (`SYSTEM_PROMPT`). The gate keeps the v2 rules, applied to labels. |

The section index ([candidate/section_index.py](candidate/section_index.py)) works as follows:
- 121 box chunks are attached to the section they follow, so warnings travel with their content.
- 11 running headers are detected: each is printed at the same top band on 3 or more pages. Ignoring them rejoined 116 page-break continuations.
- The search text is now heading, then box label, then text, and every chunk was re-embedded with BGE-M3 (weights SHA-256 `b5e0ce34…`).
- The result is 154 sections and 532 chunks, covering 145 of 149 pages. The other four pages hold only headings or pictures.

The rules added in the v3 prompt are: plain rider wording; answer only what was asked; give both values when the manual disagrees; a decision for every warning sent; no page numbers.

## Retrieval (19 questions with gold evidence; [retrieval_summary.json](retrieval_summary.json))

| | v2 reviewed path | v3 |
|---|---|---|
| Answer chunk among the chunks kept | 19/19 | 19/19 |
| Every gold object inside what the model receives | 19/19 (after review of exactly these sections) | 19/19, with no review |
| Model input, median | about 45 KB of JSON | 5,261 characters of text (max 14,621) |
| Warnings to decide, median (max) | up to 27, mostly from one unrelated cluster | 7 (21), all from the sections sent |

The reranker ran for all 30 questions, because the dense and BM25 top-3 sections always differed.

## Answers

Each arm ran 30 isolated subagents that read [ANSWER_INSTRUCTIONS_v3.md](ANSWER_INSTRUCTIONS_v3.md) and one input from [inputs/](inputs/). [run_gate_v3.py](run_gate_v3.py) gated each draft against the exact lines sent. Every cited item was checked against its line text ([review_dump.py](review_dump.py)), and every released answer was compared with the package's canonical answer ([judgments_*.json](judgments_haiku.json), [score_v3.py](score_v3.py), [comparison.json](comparison.json)).

| Arm | Released | Matches canonical | Weaker | Unfaithful cited items | Internal wording | Gold warnings shown |
|---|---|---|---|---|---|---|
| v2 run (Sonnet, reviewed admission) | 29 | 29 | 0 | 0 of 54 | 2 | not measured |
| **Haiku** | 24 | 24 | 0 | 0 of 62 | 1 | 4/5 |
| **Haiku, high effort** | **30** | **30** | 0 | 0 of 65 | 2 | 4/5 |
| **Sonnet** | 29 | 28 | 1 (EXP040) | 0 of 44 | 1 | 0/5 |

- **Haiku at default effort failed closed 6 times, all on structure, never on facts:**
  - an uncited sentence ("confirm with a service centre") put in `answer` (GEN011, EXP040);
  - an absence statement with empty `evidence_ids` (N01, GEN041);
  - `watchout_review` omitted with 17 warnings sent (N02);
  - the field name misspelt as `watch_review` (N05).
- **Haiku at high effort** made none of these errors. It also handled the page 116/117 conflict as asked (EXP040 gives both and suggests authorised service) and included the USB and ignition warnings.
- **Sonnet** was the most concise. It shows no warnings at all, choosing NOT_APPLICABLE even for the 2.5 A USB and ignition-off warnings. It gave only one of the two conflicting notch values (EXP040), and one absence sentence was left uncited (GEN004).
- **Remaining weaknesses:**
  - Both Haiku arms often restate a fact in both `answer` and `policy`. The v3 prompt dropped v2's "do not restate a fact in two sections" line.
  - "Sections supplied/shown" wording appeared in 1–2 answers per arm.
- **Nothing retrieved.** Dense search always returns 5 chunks, so this path never fired. Abstention came from the model routing UNSUPPORTED, which the server turns into the fixed fallback and support route.

## Decision for integration

The bar was: no unfaithful cited statement and at least 27/30 correct for the Haiku arm.
- **Haiku at default effort does not clear it** (24/30). The integration therefore stopped and was reverted.
- **Haiku at high effort clears it** (30/30, 0 unfaithful). The owner accepted this arm as meeting the bar ([owner_decision_v4.json](owner_decision_v4.json)).

Integration therefore uses Haiku with effort `high`. That setting's latency and cost were not measured here, because subagent timings are not API timings.

**Integrated.** The candidate is now the only answer path in the repository:
- Code: [cloud/grounded_generation/](../../cloud/grounded_generation/), in `section_index`, `section_retrieval`, `section_assembly`, `template_answer`, `haiku_answer` and `section_questions`.
- The serving `section_index.py` differs from [candidate/section_index.py](candidate/section_index.py) only in its import path, so the index built here keeps its ID.
- Parity: [serving_parity.py](serving_parity.py) runs the serving modules on the real index. They reproduce all 30 model inputs byte for byte and all 90 gate outcomes of this run ([serving_parity.json](serving_parity.json)), with no model calls.
- Release: frozen in [serving manifest v11](../../releases/serving_manifest_v11.json), then [v11.1](../../releases/serving_manifest_v11_1.json) after the token ceiling was removed and the repository reorganized.
- Owner decisions: [v3](owner_decision_v3.json) (design), [v4](owner_decision_v4.json) (integration bar) and [v5](../../releases/owner_decision_v5.json) (token ceiling, layout).
- Retired: the draft-then-verify and review-gate modules are deleted.
- Not changed: nothing was deployed, and the new index is not uploaded to hosted Qdrant.

## Reproduce

These commands were run from the project root in the layout of commit `7c41236`, with sentence-transformers installed:
1. `python candidate/section_index.py build/index-bge-final build/index-v3-sections <bge_m3_dir>`. In the current layout, run it with `PYTHONPATH=ingest` so it finds `online_ingest.py`.
2. `python build_inputs.py build/index-v3-sections <bge_m3_dir>`
3. Run the generators.
4. `python run_gate_v3.py haiku haiku_high sonnet`
5. `python score_v3.py haiku haiku_high sonnet`

The candidate tests are `python candidate/test_template_answer.py -v`. To check the serving modules against this run in the current layout, use [serving_parity.py](serving_parity.py). To ask a new question with a Claude Code generator, use [tools/local_answer.py](../../tools/local_answer.py) ([docs/EXPERIMENTS.md](../../docs/EXPERIMENTS.md)).
