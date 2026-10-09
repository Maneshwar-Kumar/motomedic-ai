"""Hybrid retrieval, optional cross-encoder and bounded evidence assembly.

Every returned bundle is candidate evidence; source review and answer gates remain required.
"""
from __future__ import annotations
import argparse
from collections import defaultdict
import json
from pathlib import Path
import time

from online_ingest import digest, tokens, write_json, stable_id


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def dependency_coverage(manual_checksum, attached_ids, evidence, manifest=None, step_id=None):
    result = {"required_evidence_ids": [], "attached_evidence_ids": sorted(attached_ids),
              "missing_evidence_ids": [], "dependency_manifest_version": None,
              "dependency_review_status": "MISSING", "coverage_established": False}
    if not manifest:
        return result
    result["dependency_manifest_version"] = manifest.get("version")
    if manifest.get("manual_checksum") != manual_checksum:
        result["dependency_review_status"] = "CHECKSUM_MISMATCH"
        return result
    step = manifest.get("steps", {}).get(step_id, {})
    required = set(step.get("required_evidence_ids", []))
    actions = set(step.get("action_evidence_ids", []))
    result["required_evidence_ids"] = sorted(required)
    result["missing_evidence_ids"] = sorted(required - set(attached_ids))
    approved = manifest.get("review_status") == "APPROVED" and step.get("review_status") == "APPROVED"
    result["dependency_review_status"] = "APPROVED" if approved else "UNREVIEWED"
    checked = all(evidence.get(eid, {}).get("review_status") == "APPROVED" and
                  evidence[eid].get("source_sha256") == manual_checksum and
                  evidence[eid].get("provenance") and
                  evidence[eid].get("extraction_check_status") == "PASSED" for eid in required)
    result["coverage_established"] = bool(approved and required and actions and actions <= required and
                                         not result["missing_evidence_ids"] and checked)
    return result


class Retriever:
    def __init__(self, index_dir, rerank=False, embedding_model=None):
        import numpy as np
        self.root = Path(index_dir)
        self.manifest = json.loads((self.root / "manifest.json").read_text(encoding="utf-8"))
        for name in ["chunks.jsonl", "parents.jsonl", "evidence.jsonl", "graph.json", "bm25.json", "embeddings.npy"]:
            if digest(self.root / name) != self.manifest["file_checksums"][name]:
                raise ValueError(f"Index integrity failure: {name}")
        self.chunks = read_jsonl(self.root / "chunks.jsonl")
        self.parents = {p["id"]: p for p in read_jsonl(self.root / "parents.jsonl")}
        self.evidence = {e["id"]:e for e in read_jsonl(self.root / "evidence.jsonl")}
        self.graph = json.loads((self.root / "graph.json").read_text(encoding="utf-8"))
        self.bm25 = json.loads((self.root / "bm25.json").read_text(encoding="utf-8"))
        self.vectors = np.load(self.root / "embeddings.npy", allow_pickle=False)
        if self.bm25["chunk_ids"] != [c["id"] for c in self.chunks] or len(self.vectors) != len(self.chunks):
            raise ValueError("Index row mappings disagree")
        model_path = self.root / "embedding_model"
        config = self.manifest["embedding"]
        self.model = embedding_model
        if self.model is None:
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(str(model_path), device="cpu") if model_path.exists() else SentenceTransformer(config["model"], revision=config["revision"], device="cpu")
        self.reranker = None
        if rerank:
            from sentence_transformers import CrossEncoder
            self.reranker = CrossEncoder(str(self.root / "reranker_model"), device="cpu")

    def search(self, query, limit=5, candidate_limit=20, scope=None, rerank=None):
        import numpy as np
        started = time.perf_counter()
        source = self.manifest["source"]
        if scope:
            for key, value in scope.items():
                actual = self.manifest["source_sha256"] if key == "source_sha256" else source.get(key)
                if actual != value:
                    raise ValueError(f"Source scope mismatch: {key}")
        if not query.strip():
            raise ValueError("Query is empty")
        vector = self.model.encode(query, normalize_embeddings=True)
        dense = self.vectors @ vector
        sparse = np.zeros(len(self.chunks))
        bm = self.bm25
        for term in set(tokens(query)):
            for idx, tf in bm["postings"].get(term, []):
                denom = tf + bm["k1"] * (1 - bm["b"] + bm["b"] * bm["lengths"][idx] / max(bm["avgdl"], 1))
                sparse[idx] += bm["idf"][term] * tf * (bm["k1"] + 1) / denom
        fused = defaultdict(float)
        for scores in [dense, sparse]:
            # Zero BM25 matches must not create arbitrary sparse ranks.
            ranking = sorted((i for i in range(len(scores)) if scores is dense or scores[i] > 0), key=lambda i: (-float(scores[i]), self.chunks[i]["id"]))
            for rank, idx in enumerate(ranking[:max(candidate_limit * 2, 50)], 1):
                fused[idx] += 1 / (60 + rank)
        candidates = sorted(fused, key=lambda i: (-fused[i], self.chunks[i]["id"]))[:candidate_limit]
        rerank_scores = {}
        use_reranker = self.reranker is not None if rerank is None else rerank
        if use_reranker:
            if self.reranker is None:
                raise RuntimeError("Requested reranker is not loaded")
            tokenizer = self.reranker.tokenizer
            query_tokens = tokenizer.encode(query, add_special_tokens=False)
            if len(query_tokens) > 128:
                raise ValueError("Please shorten the query for the cross-encoder")
            budget = min(512, tokenizer.model_max_length) - len(query_tokens) - tokenizer.num_special_tokens_to_add(pair=True)
            pairs, owners = [], []
            for i in candidates:
                passage_tokens = tokenizer.encode(self.chunks[i]["index_text"], add_special_tokens=False)
                for start in range(0, max(len(passage_tokens), 1), max(1, budget-32)):
                    fragment = tokenizer.decode(passage_tokens[start:start+budget], skip_special_tokens=True)
                    pairs.append((query, fragment))
                    owners.append(i)
            scores = self.reranker.predict(pairs, batch_size=8)
            for i, score in zip(owners, scores):
                rerank_scores[i] = max(rerank_scores.get(i, float("-inf")), float(score))
            candidates.sort(key=lambda i: (-rerank_scores[i], self.chunks[i]["id"]))
        hits = [{**self.chunks[i], "dense_score": float(dense[i]), "bm25_score": float(sparse[i]),
                 "rrf_score": fused[i], "cross_encoder_score": rerank_scores.get(i)} for i in candidates[:limit]]
        hit_pages = {c["page_id"] for h in hits for c in h["citations"]}
        links = [e for e in self.graph["edges"] if e["type"] == "TOPIC_RELATED_REVIEWED" and e["from"] in hit_pages]
        linked_pages = {e["to"] for e in links}
        related = [c for c in self.chunks if any(p["page_id"] in linked_pages for p in c["citations"])]
        parent_ids = {c["parent_section_id"] for c in hits + related}
        attached = {eid for p in parent_ids for eid in self.parents[p]["evidence_ids"]}
        attached.update(eid for chunk in hits + related for eid in chunk["evidence_ids"])
        if not attached <= self.evidence.keys():
            raise RuntimeError("SYSTEM_ERROR: attached evidence object is missing from the index")
        dependencies = dependency_coverage(self.manifest["source_sha256"], attached, self.evidence)
        assembly_version = stable_id("assembly", self.manifest["source_sha256"], [self.manifest["index_id"],digest(Path(__file__)),"TRD-0.3"])
        return {"index_id": self.manifest["index_id"], "query_id": stable_id("query",self.manifest["source_sha256"],[assembly_version,query,use_reranker]),
                "manual_checksum": self.manifest["source_sha256"], "assembly_version":assembly_version,
                **dependencies, "evidence_ids":sorted(attached),
                "evidence_objects":[self.evidence[eid] for eid in sorted(attached)],
                "applicability_status":"UNCONFIRMED", "sufficiency_status":"NOT_ESTABLISHED",
                "conflicts":[], "missing_conditions":["Confirmed manual/variant fit"],
                "source_gaps":[{"type":"DEPENDENCY_MANIFEST_MISSING","rider_resolvable":False}],
                "source_review_required":True, "source_sha256": self.manifest["source_sha256"],
                "query": query, "hits": hits, "linked_chunks": related, "links": links,
                "parents": [self.parents[p] for p in sorted(parent_ids)],
                "elapsed_seconds": time.perf_counter() - started, "reranked": use_reranker,
                "may_generate_procedural_advice": False,
                "unresolved": ["Source applicability", "Independent evidence review", "Procedure, warning and prerequisite graph", "Claim support gate"]}


def prepare_reranker(root):
    from huggingface_hub import model_info, snapshot_download
    model = "cross-encoder/ms-marco-MiniLM-L6-v2"
    revision = model_info(model).sha
    snapshot_download(model, revision=revision, local_dir=str(root / "reranker_model"),
                      allow_patterns=["*.json", "*.txt", "*.safetensors", "pytorch_model.bin"])
    write_json(root / "reranker_manifest.json", {"model": model, "revision": revision,
        "candidate_limit": 20, "approval": "PROVISIONAL", "trained_for_this_manual": False, "long_passage_policy": "max relevance across token-bounded windows"})


def evaluate(root):
    cases = json.loads((Path(__file__).parent / "golden_qa.json").read_text(encoding="utf-8-sig"))
    if isinstance(cases, dict):
        cases = cases.get("cases", cases.get("questions", []))
    retriever = Retriever(root, rerank=True)
    results = []
    for case in cases:
        expected = {c["pdf_page"] for c in case["citations"]}
        row = {"id": case["id"], "expected_pdf_pages": sorted(expected)}
        for enabled in [False, True]:
            bundle = retriever.search(case["question"], rerank=enabled)
            found = {p["pdf_page"] for c in bundle["hits"] + bundle["linked_chunks"] for p in c["citations"]}
            # Parent context is included in assembly and contributes its child pages.
            children = {cid for p in bundle["parents"] for cid in p["child_ids"]}
            found.update(p["pdf_page"] for c in retriever.chunks if c["id"] in children for p in c["citations"])
            row["cross_encoder" if enabled else "hybrid_only"] = {"complete_cited_page_coverage": expected.issubset(found),
                "found_pdf_pages": sorted(found), "elapsed_seconds": bundle["elapsed_seconds"],
                "hit_chunk_ids": [h["id"] for h in bundle["hits"]]}
        results.append(row)
    report = {"index_id": retriever.manifest["index_id"], "dataset": "27 draft in-sample reference cards",
        "limitations": "Cited-page coverage is not evidence completeness, claim support or a held-out score.",
        "cases": results,
        "complete_cited_page_cases": {key: sum(r[key]["complete_cited_page_coverage"] for r in results) for key in ["hybrid_only", "cross_encoder"]}}
    write_json(root / "retrieval_diagnostic.json", report)
    smoke = []
    import numpy as np
    for query in ["engine will not start", "ABS indicator stays on", "tyre pressure", "engine oil level", "drive chain free play"]:
        vector = retriever.model.encode(query, normalize_embeddings=True)
        smoke.append({"query": query, "vector": vector.tolist(), "expected_dense_chunk_id": retriever.chunks[int(np.argmax(retriever.vectors @ vector))]["id"]})
    write_json(root / "server_smoke.json", {"index_id":retriever.manifest["index_id"], "source_sha256":retriever.manifest["source_sha256"], "cases":smoke})
    pipeline = retriever.manifest
    pipeline["reranker"] = json.loads((root / "reranker_manifest.json").read_text())
    pipeline["retrieval_code_sha256"] = digest(Path(__file__))
    pipeline["evaluation_dataset_sha256"] = digest(Path(__file__).parent / "golden_qa.json")
    pipeline["pipeline_id"] = stable_id("pipeline", pipeline["source_sha256"], [pipeline["index_id"],pipeline["reranker"],pipeline["retrieval_code_sha256"],pipeline["evaluation_dataset_sha256"]])
    for path in root.rglob("*"):
        if path.is_file() and path.name != "manifest.json" and ".cache" not in path.parts:
            pipeline["file_checksums"][str(path.relative_to(root)).replace(chr(92),"/")] = digest(path)
    write_json(root / "manifest.json",pipeline)
    print(json.dumps({k: v for k, v in report.items() if k != "cases"}, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--index", type=Path, default=Path("build/index"))
    p.add_argument("--prepare-reranker", action="store_true")
    p.add_argument("--evaluate", action="store_true")
    p.add_argument("--query")
    p.add_argument("--rerank", action="store_true")
    args = p.parse_args()
    if args.prepare_reranker:
        prepare_reranker(args.index)
    if args.evaluate:
        evaluate(args.index)
    if args.query:
        print(json.dumps(Retriever(args.index, args.rerank).search(args.query), ensure_ascii=False, indent=2))
