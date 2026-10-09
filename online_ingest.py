"""Versioned hosted ingestion. Creates candidate evidence, never repair advice."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path
import re
import uuid

ROOT = Path(__file__).resolve().parent
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
TOKEN_RE = re.compile(r"[a-z0-9]+(?:[.'/-][a-z0-9]+)*")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def stable_id(kind, source, value):
    encoded = json.dumps([source, value], sort_keys=True, ensure_ascii=False).encode()
    return kind + "_" + hashlib.sha256(encoded).hexdigest()[:24]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")


def tokens(text):
    return TOKEN_RE.findall(text.lower())


def build_bm25(chunks):
    postings = defaultdict(list)
    lengths = []
    for index, chunk in enumerate(chunks):
        counts = Counter(tokens(chunk["index_text"]))
        lengths.append(sum(counts.values()))
        for term, count in counts.items():
            postings[term].append([index, count])
    n = len(chunks)
    return {"k1": 1.5, "b": 0.75, "tokenizer": TOKEN_RE.pattern,
            "chunk_ids": [c["id"] for c in chunks], "lengths": lengths,
            "avgdl": sum(lengths) / max(n, 1), "postings": dict(postings),
            "idf": {t: math.log(1 + (n - len(p) + 0.5) / (len(p) + 0.5)) for t, p in postings.items()}}


def build(manifest_path, out, parsed_document=None, embedding_model=EMBED_MODEL, max_tokens=240, package_model=True):
    import numpy as np
    from docling.document_converter import DocumentConverter, PdfFormatOption
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.chunking import HybridChunker
    from docling_core.transforms.chunker.tokenizer.huggingface import HuggingFaceTokenizer
    from huggingface_hub import model_info
    from transformers import AutoTokenizer
    from sentence_transformers import SentenceTransformer
    from qdrant_client import QdrantClient, models
    from index_manual import extract_pages

    source = json.loads(manifest_path.read_text(encoding="utf-8-sig"))
    pdf = manifest_path.parent / source["file"]
    checksum = digest(pdf)
    if checksum != source["sha256"].lower():
        raise ValueError("PDF checksum differs from the approved source manifest")
    out.mkdir(parents=True, exist_ok=True)
    if (out / "manifest.json").exists():
        raise ValueError("Output already contains an index; use a fresh version directory")
    print("Source verified; extracting page registry", flush=True)
    pages = extract_pages(pdf)
    if len(pages) != source["pdf_pages"]:
        raise ValueError("Unexpected PDF page count")
    page_lookup = {p["pdf_page"]: p for p in pages}
    write_jsonl(out / "pages.jsonl", pages)
    print("Parsing layout, tables and figures with Docling", flush=True)
    options = PdfPipelineOptions()
    options.do_ocr = False  # This exact source has embedded text; audit extraction gaps.
    options.do_table_structure = True
    options.generate_picture_images = True
    options.images_scale = 1.5
    if parsed_document:
        from docling_core.types.doc import DoclingDocument
        doc = DoclingDocument.model_validate_json(parsed_document.read_text(encoding="utf-8"))
        if doc.origin.filename != source["file"]:
            raise ValueError("Cached parse belongs to a different source")
    else:
        result = DocumentConverter(format_options={InputFormat.PDF: PdfFormatOption(pipeline_options=options)}).convert(pdf)
        doc = result.document
        if str(result.status.value) != "success":
            raise RuntimeError(f"Docling conversion did not succeed: {result.status}")
    write_json(out / "docling_document.json", doc.export_to_dict())
    model_revision = model_info(embedding_model).sha
    tokenizer = HuggingFaceTokenizer(tokenizer=AutoTokenizer.from_pretrained(embedding_model, revision=model_revision), max_tokens=max_tokens)
    chunker = HybridChunker(tokenizer=tokenizer, merge_peers=False, repeat_table_header=True)
    evidence, chunks, parents, edges = {}, [], {}, []
    figures_dir = out / "figures"
    figures_dir.mkdir(exist_ok=True)
    for picture in doc.pictures:
        image = picture.get_image(doc)
        if image is not None:
            image.save(figures_dir / (stable_id("figure", checksum, picture.self_ref) + ".png"))
    for item, _ in doc.iterate_items():
        if not hasattr(item, "prov") or not hasattr(item, "self_ref"):
            continue
        eid = stable_id("evidence", checksum, item.self_ref)
        evidence[eid] = {"id": eid, "docling_ref": item.self_ref, "type": str(item.label.value),
            "provenance": [p.model_dump(mode="json") for p in item.prov], "source_sha256": checksum,
            "raw_object": item.model_dump(mode="json"), "review_status": "UNREVIEWED"}
    search_chunks = []
    overflow_count = 0
    for base_number, base_chunk in enumerate(chunker.chunk(dl_doc=doc)):
        enriched_text = chunker.contextualize(base_chunk)
        encoded = tokenizer.tokenizer.encode(enriched_text, add_special_tokens=False)
        if len(encoded) <= max_tokens - 2:
            search_chunks.append((base_number, base_chunk, enriched_text, 0, False))
        else:
            overflow_count += 1
            for window, start in enumerate(range(0, len(encoded), max_tokens - 34)):
                window_text = tokenizer.tokenizer.decode(encoded[start:start+max_tokens-2], skip_special_tokens=True)
                search_chunks.append((base_number, base_chunk, window_text, window, True))
    previous_headings, current_parent = None, None
    for number, chunk, enriched, window, overflow in search_chunks:
        if not chunk.text.strip():
            continue
        headings = list(chunk.meta.headings or [])
        refs, pdf_pages = [], set()
        for item in chunk.meta.doc_items:
            label = str(item.label.value)
            eid = stable_id("evidence", checksum, item.self_ref)
            prov = [p.model_dump(mode="json") for p in item.prov]
            pdf_pages.update(p["page_no"] for p in prov)
            if eid not in evidence:
                evidence[eid] = {"id": eid, "docling_ref": item.self_ref, "type": label,
                    "provenance": prov, "source_sha256": checksum,
                    "raw_object": item.model_dump(mode="json"), "review_status": "UNREVIEWED"}
            refs.append(eid)
        if not pdf_pages or not pdf_pages.issubset(page_lookup):
            raise ValueError(f"Chunk {number} lacks valid PDF provenance")
        if headings != previous_headings or current_parent is None:
            current_parent = stable_id("section", checksum, [headings, refs, min(pdf_pages)])
        pid = current_parent
        previous_headings = headings
        cid = stable_id("chunk", checksum, [number, window, refs, chunk.text, enriched])
        parents.setdefault(pid, {"id": pid, "type": "section_context", "section_path": headings,
                                 "child_ids": [], "evidence_ids": [], "review_status": "UNREVIEWED"})
        parents[pid]["child_ids"].append(cid)
        parents[pid]["evidence_ids"] = sorted(set(parents[pid]["evidence_ids"] + refs))
        count = tokenizer.count_tokens(enriched)
        chunks.append({"id": cid, "text": chunk.text, "index_text": enriched, "token_count": count,
            "retrieval_window": window, "requires_full_source_context": overflow,
            "section_path": headings, "captions": list(chunk.meta.captions or []),
            "parent_section_id": pid, "parent_procedure_id": None, "evidence_ids": refs,
            "citations": [{"page_id": page_lookup[p]["id"], "pdf_page": p,
                           "printed_page": page_lookup[p]["printed_page"]} for p in sorted(pdf_pages)],
            "contains_warning_marker": bool(re.search(r"\b(?:WARNING|CAUTION)\b", chunk.text, re.I)),
            "scope": {k: source.get(k) for k in ["manual_id", "motorcycle", "variant", "edition", "language"]},
            "source_sha256": checksum, "review_status": "UNREVIEWED"})
        edges.append({"from": cid, "to": pid, "type": "PARENT_SECTION",
                      "provenance": "Docling heading hierarchy", "implies_procedure_order": False})
        for eid in refs:
            edges.append({"from": cid, "to": eid, "type": "CONTAINS_EVIDENCE",
                          "provenance": "Docling chunk metadata", "implies_procedure_order": False})
    if not chunks:
        raise ValueError("Docling produced no searchable chunks")
    if any(c["token_count"] > max_tokens for c in chunks):
        raise ValueError("Oversized enriched chunks would be truncated by the embedding model")
    child_lookup = {c["id"]: c for c in chunks}
    for parent in parents.values():
        parent["text"] = "\n\n".join(dict.fromkeys(child_lookup[c]["text"] for c in parent["child_ids"]))
    links_path = manifest_path.parent / "reviewed_graph_links.json"
    for link in json.loads(links_path.read_text(encoding="utf-8-sig")):
        edges.append({**link, "review_status": "AGENT_CHECKED_PROVISIONAL"})
    for obj in evidence.values():
        for provenance in obj["provenance"]:
            page_no = provenance["page_no"]
            if page_no not in page_lookup:
                raise ValueError("Evidence references a page outside the source PDF")
            edges.append({"from": obj["id"], "to": page_lookup[page_no]["id"], "type": "ON_PAGE",
                "provenance": provenance, "implies_procedure_order": False})
    write_jsonl(out / "evidence.jsonl", evidence.values())
    write_jsonl(out / "chunks.jsonl", chunks)
    write_jsonl(out / "parents.jsonl", parents.values())
    write_json(out / "graph.json", {"nodes": [{"id": p["id"], "type": "page"} for p in pages] +
        [{"id": c["id"], "type": "chunk"} for c in chunks] +
        [{"id": p["id"], "type": "section_context"} for p in parents.values()] +
        [{"id": e["id"], "type": e["type"]} for e in evidence.values()], "edges": edges})
    write_json(out / "bm25.json", build_bm25(chunks))
    print(f"Embedding {len(chunks)} chunks; creating Qdrant vector index", flush=True)
    model = SentenceTransformer(embedding_model, revision=model_revision, device="cpu")
    if any(len(model.tokenizer(c["index_text"], add_special_tokens=True)["input_ids"]) > model.max_seq_length for c in chunks):
        raise ValueError("Embedding input would be truncated")
    vectors = model.encode([c["index_text"] for c in chunks], normalize_embeddings=True,
                           batch_size=4 if max_tokens > 256 else 32, show_progress_bar=True).astype("float32")
    np.save(out / "embeddings.npy", vectors)
    if package_model:
        model.save(str(out / "embedding_model"))
    client = QdrantClient(path=str(out / "qdrant"))
    client.create_collection("owner_manual", vectors_config=models.VectorParams(size=vectors.shape[1], distance=models.Distance.COSINE))
    client.upload_points("owner_manual", [models.PointStruct(
        id=str(uuid.uuid5(uuid.NAMESPACE_URL, c["id"])), vector=v.tolist(),
        payload={"chunk_id": c["id"], "source_sha256": checksum, **c["scope"]}) for c, v in zip(chunks, vectors)])
    client.close()
    versions = {p: importlib.metadata.version(p) for p in ["docling", "docling-core", "sentence-transformers", "qdrant-client", "transformers", "torch", "numpy", "pypdfium2"]}
    covered = {p["page_no"] for e in evidence.values() for p in e["provenance"]}
    qa = {"pdf_pages": len(pages), "chunks": len(chunks), "parent_sections": len(parents),
        "evidence_objects": len(evidence), "oversized_source_chunks_windowed": overflow_count, "type_counts": dict(Counter(e["type"] for e in evidence.values())),
        "pages_without_chunk_evidence": sorted(set(page_lookup) - covered),
        "pages_without_printed_label": [p["pdf_page"] for p in pages if p["printed_page"] is None],
        "warning_marker_chunks": sum(c["contains_warning_marker"] for c in chunks),
        "figure_crops": len(list(figures_dir.glob("*.png"))),
        "needs_review": ["Warning scope and prerequisite links", "Procedure and step boundaries", "Table headers, units and variant fit", "Figure-caption association", "Uncovered pages", "Edition and variant"],
        "may_generate_procedural_advice": False}
    write_json(out / "ingestion_qa.json", qa)
    config = {"source_sha256": checksum, "parser": "Docling", "dependencies": versions,
              "chunker": {"name": "HybridChunker", "max_tokens": max_tokens, "merge_peers": False, "repeat_table_header": True},
              "embedding": {"model": embedding_model, "revision": model_revision, "dimensions": int(vectors.shape[1]), "normalized": True, "metric": "cosine"},
              "code_sha256": digest(Path(__file__)), "cached_parse_sha256": digest(parsed_document) if parsed_document else None, "source_manifest_sha256": digest(manifest_path), "graph_links_sha256": digest(links_path)}
    index_id = stable_id("index", checksum, config)
    files = {str(p.relative_to(out)).replace("\\", "/"): digest(p) for p in sorted(out.rglob("*")) if p.is_file()}
    write_json(out / "manifest.json", {"index_id": index_id, **config, "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": source, "counts": qa, "file_checksums": files, "release_status": "UNREVIEWED_CANDIDATE_INDEX"})
    print(json.dumps({"index_id": index_id, **qa}, indent=2), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, default=ROOT / "source_manifest.json")
    parser.add_argument("--out", type=Path, default=ROOT / "build" / "index")
    parser.add_argument("--parsed-document", type=Path)
    parser.add_argument("--embedding-model", default=EMBED_MODEL)
    parser.add_argument("--max-tokens", type=int, default=240)
    parser.add_argument("--no-package-model", action="store_true")
    args = parser.parse_args()
    if args.max_tokens < 64 or args.max_tokens > 2048:
        parser.error("Use a reviewed token budget between 64 and 2048")
    build(args.manifest, args.out, args.parsed_document, args.embedding_model, args.max_tokens, not args.no_package_model)
