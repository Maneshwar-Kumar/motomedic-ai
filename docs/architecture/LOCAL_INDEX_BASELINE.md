# Provisional manual index and Q&A

The Royal Enfield New Himalayan 450 owner's manual is the approved source for this prototype. The PDF checksum is `CF221A29E2F9CD5AF6E80A99774A697C814E8EDA661C27D72E519D8A7E80DA89`. This folder contains a local search baseline, a small source-linked page graph, 27 draft cited reference answer cards, and 37 provisional atomic diagnostic/lookup cases.

The project owner requires the build and operating environment to be online. The local files described below document a provisional retrieval baseline; they are not the final hosted architecture. The TRD remains the implementation contract.

## What was built

| Artifact | Purpose |
| --- | --- |
| `index_manual.py` | Rebuilds and queries the local index; validates citations and exports readable Q&A. |
| `retrieve_evidence.py` | Assembles a provisional evidence bundle from ranked chunks and checked topic links; never emits rider instructions. |
| `source_manifest.json` | Approved source file and checksum, plus applicability and rights fields still to verify. |
| `provisional_index/pages.jsonl` | Extracted page text, printed page label, and section for all 149 PDF pages. |
| `provisional_index/chunks.jsonl` | 153 page-bound chunks with stable IDs and page citations. |
| `provisional_index/embeddings.npy` | 96-dimensional dense document vectors. |
| `provisional_index/components.npy`, `idf.npy`, `vocabulary.json` | Query projection for the same vector space. |
| `provisional_index/graph.json` | 149 page nodes and 116 navigation edges. |
| `reviewed_graph_links.json` | Seven manually checked topic links between troubleshooting and supporting pages. |
| `golden_qa.json` / `golden_qa.md` | 27 cited reference answer cards and old retrieval probes. Compound prompts are not entry prompts. |
| `diagnosis_flow.json` / `diagnose.py` | One-question-at-a-time cited flow and deterministic prototype controller. |
| `golden_dialogues.json` / `golden_dialogues.md` | 37 atomic diagnostic and direct-lookup cases, with typed rider responses and expected branch nodes. |
| `provisional_golden_cache.json` | Exact dialogue-prefix and direct-lookup cache, draft-disabled for release. |
| `provisional_index/retrieval_baseline.json` | Diagnostic retrieval results on the draft questions. |
| `provisional_index/assembly_diagnostic.json` | In-sample cited-page coverage with and without the local reranker. |

The dense vectors are **TF-IDF with latent semantic analysis (LSA)** trained on this manual. They are genuine dense embeddings, but they are not from a pretrained language embedding model. They make the prototype fully reproducible offline without an API key. Sparse BM25 scores are computed at query time and combined with dense ranks using reciprocal rank fusion. This is a baseline to compare with a modern pretrained query/document embedding model, not a claim of state-of-the-art retrieval.

The graph connects adjacent pages with the same extracted section heading and seven reviewed topic-related pages. A topic edge helps retrieve supporting context; it does **not** establish an OEM diagnostic sequence or prerequisite. A future version should add typed procedure, warning, table, figure, and prerequisite nodes after layout review.

## Retrieval and evidence assembly now available

`retrieve_evidence.py` checks the requested owner-manual ID, checksum, model, edition and language against the source registry before search. It runs the existing dense LSA and BM25 reciprocal-rank fusion, optionally applies a small local term-coverage reranker to the first ten candidates, and returns the top five page-bound chunks with full original page text. It expands one hop through the seven provisional, agent-checked topic links in `reviewed_graph_links.json`. Automatically inferred same-section graph edges are excluded from evidence expansion. Every included page carries its PDF and printed page number and every expanded link carries provenance. This is a bounded candidate bundle, not a verified procedure graph.

The current reranker is **not** the proposed cross-encoder. The bundle explicitly reports that the manual edition, variant fit, parent procedure, warning scope, table/figure context and prerequisite coverage remain unverified; `may_generate_procedural_advice` is always false. Retrieval scores and linked pages do not authorize a technical answer. A future generator must receive only an independently reviewed, applicability-checked bundle and pass the claim-to-source gate.

```powershell
python retrieve_evidence.py "engine will not start" --compact
python retrieve_evidence.py --evaluate
python retrieve_evidence.py --evaluate --no-rerank
```

On the 27 draft reference cards, this provisional assembly contains every cited page in 23 cases with or without the local reranker. G006, G009, G012 and G027 still miss at least one cited page. The case-level result is saved in `provisional_index/assembly_diagnostic.json`. This is an in-sample diagnostic, not a held-out benchmark or proof of answer sufficiency. The checked topic links and cards were developed together, and the reranker has not shown a measured gain over the no-rerank setting on this set.

## Rebuild and inspect

Use a Python environment with `numpy` and `pypdfium2`. The bundled Codex workspace Python already has both.

```powershell
python index_manual.py build
python index_manual.py search "engine does not start and the lights are dim" --limit 5
python index_manual.py validate
python index_manual.py export-gold
python index_manual.py evaluate
python diagnose.py validate
python diagnose.py export
python diagnose.py build-cache
python diagnose.py chat "The engine will not start."
```

The build is deterministic apart from its `built_at_utc` timestamp. It uses the PDF bytes in this folder and a fixed random seed. `validate` checks the source checksum, embedding shape, graph node count, unique case IDs, and that every citation maps to the stated PDF and printed page. It cannot establish that every paraphrase is mechanically correct; an independent source reviewer must do that.

## Current retrieval baseline

For the 27 older reference-card questions, at least one cited page appeared in the top five results for 26 cases. All cited pages appeared in the top five for 21 cases and in the top ten for 24 cases. This is an **in-sample diagnostic**, not an end-to-end evaluation of the new interactive dialogues: the same cards informed source inspection and some graph links. The baseline search does not yet expand graph neighbors or apply an answer sufficiency verifier. The misses in `retrieval_baseline.json` show where those components and a stronger embedding model should be tested.

The dialogue prototype asks about one observation at a time, records whether an action fixed the symptom or left it unresolved, then moves to another manual-documented check or an honest escalation. Its question order is a design choice, not an OEM-mandated diagnostic order. A weak horn on its own does not prove a battery fault. The 37 cases cover selected branches and direct owner-manual facts, not every possible customer utterance.

The provisional cache stores exact reviewed-path candidates. Its key includes the manual checksum, flow and policy version, variant scope, intent and typed answers. The runtime refuses this draft cache by default; `--allow-draft` is for local inspection only. Similarity retrieval is never used to choose a cached repair answer. If the source, variant, flow, policy or answer sequence changes, the cache must miss and the grounded controller must run. Independent technical and safety review is still needed before approval.

## Use and limitations

- The PDF is an owner's manual. The Q&A set is limited to its documented troubleshooting, operation, and minor maintenance content. It is not a service-repair corpus.
- Source pages were extracted as text; page layout, table cells, figure relationships, warning scope, and bounding boxes are not yet fully modeled. The lubricant, tyre-pressure, fuse, and troubleshooting tables used in draft cases were visually checked against the PDF.
- The Q&A set is a **draft**. Its answers are cited and source checked by the agent; an independent human review and a held-out evaluation split are still required before it is used as a release golden set.
- A retrieval hit is candidate evidence, not permission to answer. The planned application still needs variant checks, mandatory warning and prerequisite collection, stateful next-step selection, claim-to-source validation, and distinct abstention versus system-error responses.
- A public demo should verify rights to host or display the PDF, confirm the exact bike variant and manual edition, and verify the OEM service contact route.

## Hosted pretrained index

The hosted successor is implemented in `online_ingest.py` and `online_retrieve.py`, with results and limitations in [HOSTED_INDEX_DECISION.md](HOSTED_INDEX_DECISION.md). It parses Docling evidence, preserves parent context and provenance, builds BGE M3 dense vectors, serialized BM25 and a lightweight graph, and provides optional pretrained cross-encoder reranking. The local LSA baseline above remains available for comparison. The selected immutable Qdrant index is served in GCP with private source storage and a conservative lifetime spending guard.
