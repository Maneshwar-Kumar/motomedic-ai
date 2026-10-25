"""Retrieve provisional owner-manual evidence without generating rider advice.

The bundle deliberately retains source and review gaps. A retrieved passage or
topic link is candidate evidence, never an approved procedure or answer.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from index_manual import DEFAULT_OUT, ROOT, load_jsonl, rank, sha256, tokens


SOURCE = ROOT / "source_manifest.json"
REVIEWED_LINKS = ROOT / "reviewed_graph_links.json"


class SourceMismatch(ValueError):
    """The requested or indexed source does not match the approved PDF."""


def _load_source(
    index_dir: Path, manual_id: str | None, checksum: str | None,
    model: str | None, edition: str | None, language: str | None,
) -> tuple[dict, dict]:
    source = json.loads(SOURCE.read_text(encoding="utf-8"))
    index = json.loads((index_dir / "manifest.json").read_text(encoding="utf-8"))
    if manual_id is not None and manual_id != source["manual_id"]:
        raise SourceMismatch("Requested manual ID does not match the source registry")
    if checksum is not None and checksum.lower() != source["sha256"].lower():
        raise SourceMismatch("Requested PDF checksum does not match the source registry")
    if model is not None and model != source["motorcycle"]:
        raise SourceMismatch("Requested motorcycle model does not match the source registry")
    if language is not None and language != source["language"]:
        raise SourceMismatch("Requested language does not match the source registry")
    if edition is not None and edition != source.get("edition"):
        raise SourceMismatch("Requested edition is not confirmed for this source")
    if index["source_sha256"].lower() != source["sha256"].lower():
        raise SourceMismatch("Index and source registry have different PDF checksums")
    pdf = ROOT / source["file"]
    if not pdf.is_file() or sha256(pdf).lower() != source["sha256"].lower():
        raise SourceMismatch("Source PDF is absent or differs from the indexed PDF")
    if index.get("source_type") != "owner_manual" or source.get("document_type") != "owner_manual":
        raise SourceMismatch("Only the registered owner manual is supported")
    return source, index


def _rerank(candidates: list[dict], chunks: dict[str, dict], query: str, limit: int) -> list[dict]:
    """Cheap local lexical second pass; this is not a cross-encoder."""
    query_terms = set(tokens(query))
    for first_rank, candidate in enumerate(candidates, 1):
        body_terms = set(tokens(chunks[candidate["chunk_id"]]["text"]))
        coverage = len(query_terms & body_terms) / max(len(query_terms), 1)
        candidate["first_stage_rank"] = first_rank
        candidate["reranker"] = "local_term_coverage_v1"
        candidate["rerank_score"] = round(coverage, 4)
    head = sorted(candidates[:limit], key=lambda c: (-c["rerank_score"], c["first_stage_rank"]))
    return head + candidates[limit:]


def assemble(
    query: str,
    *,
    index_dir: Path = DEFAULT_OUT,
    manual_id: str | None = None,
    checksum: str | None = None,
    model: str | None = None,
    edition: str | None = None,
    language: str | None = None,
    bike_variant: str | None = None,
    rerank: bool = True,
    anchor_limit: int = 5,
    linked_page_limit: int = 8,
) -> dict:
    """Return ranked chunks and checked topic links, with explicit release blockers."""
    if not query.strip():
        raise ValueError("A non-empty query is required")
    started = time.perf_counter()
    source, index = _load_source(index_dir, manual_id, checksum, model, edition, language)
    pages = {p["id"]: p for p in load_jsonl(index_dir / "pages.jsonl")}
    chunks = {c["id"]: c for c in load_jsonl(index_dir / "chunks.jsonl")}
    candidates = rank(index_dir, query, max(15, anchor_limit))
    retrieval_ms = round((time.perf_counter() - started) * 1000, 2)
    if rerank:
        candidates = _rerank(candidates, chunks, query, 10)
    else:
        for position, candidate in enumerate(candidates, 1):
            candidate["first_stage_rank"] = position
            candidate["reranker"] = "none"

    anchors = candidates[:anchor_limit]
    anchor_pages = {c["page_id"] for c in anchors}
    selected_page_ids = list(dict.fromkeys(c["page_id"] for c in anchors))
    links = json.loads(REVIEWED_LINKS.read_text(encoding="utf-8"))
    included_links = []
    for link in links:
        if link.get("type") != "TOPIC_RELATED_REVIEWED":
            continue
        left, right = link["from"], link["to"]
        if left not in anchor_pages and right not in anchor_pages:
            continue
        other = right if left in anchor_pages else left
        if other not in pages:
            raise SourceMismatch(f"Checked topic link targets missing page {other}")
        if other not in selected_page_ids and len(selected_page_ids) - len(anchor_pages) >= linked_page_limit:
            continue
        if other not in selected_page_ids:
            selected_page_ids.append(other)
        included_links.append({
            "from": left, "to": right, "type": link["type"],
            "provenance": link["provenance"],
            "review_status": "provisional_agent_checked",
            "implies_procedure_order": False,
        })

    evidence_pages = []
    for page_id in selected_page_ids:
        page = pages[page_id]
        evidence_pages.append({
            "evidence_id": page_id,
            "pdf_page": page["pdf_page"],
            "printed_page": page["printed_page"],
            "section": page["section"],
            "text": page["text"],
            "role": "ranked_anchor" if page_id in anchor_pages else "checked_topic_context",
        })
    unresolved = []
    if not source.get("edition"):
        unresolved.append("manual_edition_unconfirmed")
    if not source.get("variant") or bike_variant != source.get("variant"):
        unresolved.append("bike_variant_applicability_unconfirmed")
    unresolved.extend([
        "procedure_parent_and_warning_scope_not_verified",
        "table_figure_and_prerequisite_coverage_not_verified",
    ])
    return {
        "query": query,
        "manual_id": source["manual_id"],
        "model": source["motorcycle"],
        "edition": source.get("edition"),
        "language": source["language"],
        "source_sha256": source["sha256"],
        "source_type": "owner_manual",
        "index_model": index["embedding_model"],
        "search_method": "dense_lsa_plus_bm25_rrf",
        "reranker": "local_term_coverage_v1" if rerank else "none",
        "candidate_chunks": candidates,
        "evidence_pages": evidence_pages,
        "expanded_links": included_links,
        "unresolved_gates": unresolved,
        "bundle_status": "CANDIDATE_EVIDENCE_ONLY",
        "may_generate_procedural_advice": False,
        "timing_ms": {
            "retrieval": retrieval_ms,
            "total": round((time.perf_counter() - started) * 1000, 2),
        },
    }


def evaluate(index_dir: Path = DEFAULT_OUT, *, rerank: bool = True) -> dict:
    """In-sample diagnostic only; these draft cards are not release gold."""
    cases = json.loads((ROOT / "golden_qa.json").read_text(encoding="utf-8"))["cases"]
    rows = []
    for case in cases:
        required = {c["evidence_page_id"] for c in case["citations"]}
        bundle = assemble(case["question"], index_dir=index_dir, rerank=rerank)
        found = {page["evidence_id"] for page in bundle["evidence_pages"]}
        rows.append({"case_id": case["id"], "required_pages": sorted(required),
                     "found_pages": sorted(required & found), "complete": required <= found})
    return {"case_count": len(rows), "complete_evidence_count": sum(r["complete"] for r in rows),
            "reranker": "local_term_coverage_v1" if rerank else "none",
            "evaluation_status": "in_sample_provisional_cards", "cases": rows}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?")
    parser.add_argument("--manual-id")
    parser.add_argument("--checksum")
    parser.add_argument("--model")
    parser.add_argument("--edition")
    parser.add_argument("--language")
    parser.add_argument("--bike-variant")
    parser.add_argument("--no-rerank", action="store_true")
    parser.add_argument("--evaluate", action="store_true")
    parser.add_argument("--compact", action="store_true", help="omit full page text from printed JSON")
    args = parser.parse_args()
    if args.evaluate:
        result = evaluate(rerank=not args.no_rerank)
    else:
        if args.query is None:
            parser.error("query is required unless --evaluate is used")
        result = assemble(args.query, manual_id=args.manual_id, checksum=args.checksum,
                          model=args.model, edition=args.edition, language=args.language,
                          bike_variant=args.bike_variant, rerank=not args.no_rerank)
        if args.compact:
            for page in result["evidence_pages"]:
                page["text"] = page["text"][:240]
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
