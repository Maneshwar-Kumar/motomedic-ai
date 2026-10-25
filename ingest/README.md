# Base-index ingestion

This job parsed and indexed the manual once, before serving. It built the base index `index_a3282c4d98cf54595e4ba168` in GitHub Actions ([workflow](../.github/workflows/ingest-owner-manual.yml)):
- the Docling parse of all 149 pages;
- 532 HybridChunker chunks with a 1,024-token budget;
- BGE-M3 vectors and BM25;
- the evidence objects and pinned reranker files.

That snapshot is public as a [GitHub release asset](https://github.com/Maneshwar-Kumar/motomedic-ai/releases/tag/index-a3282c4d98cf54595e4ba168).

The current answer path does not use this index directly. It uses the **section index** `index_a609ca61c635641e0a22dc48`, which [section_index.py](../cloud/grounded_generation/section_index.py) builds from this index's cached Docling parse without re-parsing. That build:
- regroups the chunks into content sections;
- attaches the WARNING, CAUTION and NOTE boxes;
- rejoins page-break continuations;
- re-embeds the chunks.

Rebuild steps are in [SETUP](../docs/SETUP.md#rebuild-the-section-index).

| File | Role |
| --- | --- |
| [online_ingest.py](online_ingest.py) | Docling parse, chunking, embedding, BM25 and manifest. Its `build_bm25` is reused by the section index. |
| [online_retrieve.py](online_retrieve.py), [retrieval_policy.py](retrieval_policy.py) | The base index's own retrieval, used here only to package the reranker and to evaluate the base index |
| [golden_qa.json](golden_qa.json), [golden_qa.md](golden_qa.md) | The questions used by that evaluation |
| [test_online_assembly.py](test_online_assembly.py), [test_conditional_retrieval.py](test_conditional_retrieval.py) | Regression tests for the base index; run them from this folder |
| [requirements.txt](requirements.txt) | Ingestion dependencies (Docling, sentence-transformers) |

Run the scripts from the repository root, for example `python ingest/online_ingest.py --manifest source/source_manifest.json --out build/index`. The source manifest must sit next to `reviewed_graph_links.json`, as it does in [source/](../source/README.md).

`online_ingest.py` and the source manifest have been edited since the base index was built; the base index manifest records the hashes they had then. Rerunning this job therefore produces a new base index ID. That new ID does not invalidate the section index, which pins its own files.
