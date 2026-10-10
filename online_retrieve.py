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
from retrieval_policy import RetrievalPolicy, ranking_signals, next_retrieval_action


class RetrievalSystemError(RuntimeError):
    """Operational failure must never be interpreted as an unsupported request."""
    status = "SYSTEM_ERROR"


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
    def __init__(self, index_dir, rerank=False, embedding_model=None, cross_encoder=None):
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
        self.reranker = cross_encoder
        if rerank:
            self._load_reranker()

    def reviewed_controller(self, registry, semantic_verifier=None):
        """Bind the server-owned review overlay without changing index files/vectors."""
        from reviewed_controller import ReviewedController
        return ReviewedController(registry, self, semantic_verifier)

    def _load_reranker(self):
        if self.reranker is not None:
            return
        from sentence_transformers import CrossEncoder
        model_path = self.root / "reranker_model"
        if model_path.exists():
            self.reranker = CrossEncoder(str(model_path), device="cpu")
        else:
            config_path = self.root / "reranker_manifest.json"
            if not config_path.exists():
                raise RetrievalSystemError("SYSTEM_ERROR: pinned reranker is unavailable")
            config = json.loads(config_path.read_text(encoding="utf-8"))
            if not config.get("revision"):
                raise RetrievalSystemError("SYSTEM_ERROR: reranker revision is missing")
            self.reranker = CrossEncoder(config["model"], revision=config["revision"], device="cpu")

    def _rank(self, dense, sparse, candidate_limit, policy, allowed_indices=None):
        fused = defaultdict(float)
        rankings = []
        for scores in [dense, sparse]:
            # Zero BM25 matches must not create arbitrary sparse ranks.
            ranking = sorted((i for i in range(len(scores)) if (allowed_indices is None or i in allowed_indices) and (scores is dense or scores[i] > 0)), key=lambda i: (-float(scores[i]), self.chunks[i]["id"]))
            rankings.append(ranking)
            for rank, idx in enumerate(ranking[:max(candidate_limit * 2, 50)], 1):
                fused[idx] += 1 / (60 + rank)
        candidates = sorted(fused, key=lambda i: (-fused[i], self.chunks[i]["id"]))[:candidate_limit]
        sections = {}
        for i in candidates:
            section = self.chunks[i]["parent_section_id"]
            sections[section] = max(sections.get(section, 0), fused[i])
        signals = ranking_signals(
            [self.chunks[i]["parent_section_id"] for i in rankings[0]],
            [self.chunks[i]["parent_section_id"] for i in rankings[1]],
            sorted(sections.items(), key=lambda item: (-item[1], item[0])), policy)
        return candidates, fused, signals

    def _rerank(self, query, candidates, policy):
        import numpy as np
        self._load_reranker()
        tokenizer = self.reranker.tokenizer
        query_tokens = tokenizer.encode(query, add_special_tokens=False)
        if len(query_tokens) > 128:
            return None, 0, "QUERY_EXCEEDS_RERANK_LIMIT"
        budget = min(512, tokenizer.model_max_length) - len(query_tokens) - tokenizer.num_special_tokens_to_add(pair=True)
        if budget <= 32:
            raise RetrievalSystemError("SYSTEM_ERROR: invalid cross-encoder token budget")
        pairs, owners = [], []
        for i in candidates:
            passage_tokens = tokenizer.encode(self.chunks[i]["index_text"], add_special_tokens=False)
            for start in range(0, max(len(passage_tokens), 1), budget-32):
                pairs.append((query, tokenizer.decode(passage_tokens[start:start+budget], skip_special_tokens=True)))
                owners.append(i)
                if len(pairs) > policy.maximum_rerank_pairs:
                    return None, 0, "RERANK_PAIR_LIMIT_EXCEEDED"
        scores = self.reranker.predict(pairs, batch_size=8)
        if len(scores) != len(pairs) or not np.isfinite(scores).all():
            raise RetrievalSystemError("SYSTEM_ERROR: invalid cross-encoder scores")
        rerank_scores = {}
        for i, score in zip(owners, scores):
            rerank_scores[i] = max(rerank_scores.get(i, float("-inf")), float(score))
        return rerank_scores, len(pairs), None

    def _assemble(self, query, candidates, limit, dense, sparse, fused, rerank_scores,
                  dependency_manifest, step_id, applicability_status, retained_ids=()):
        hits = [{**self.chunks[i], "dense_score": float(dense[i]), "bm25_score": float(sparse[i]),
                 "rrf_score": fused[i], "cross_encoder_score": rerank_scores.get(i)} for i in candidates[:limit]]
        hit_pages = {c["page_id"] for h in hits for c in h["citations"]}
        links = [e for e in self.graph["edges"] if e["type"] == "TOPIC_RELATED_REVIEWED" and e["from"] in hit_pages]
        linked_pages = {e["to"] for e in links}
        related = [c for c in self.chunks if any(p["page_id"] in linked_pages for p in c["citations"])]
        parent_ids = {c["parent_section_id"] for c in hits + related}
        attached = {eid for p in parent_ids for eid in self.parents[p]["evidence_ids"]}
        attached.update(eid for chunk in hits + related for eid in chunk["evidence_ids"])
        attached.update(retained_ids)
        if not attached <= self.evidence.keys():
            raise RetrievalSystemError("SYSTEM_ERROR: attached evidence object is missing from the index")
        checksum = self.manifest["source_sha256"]
        dependencies = dependency_coverage(checksum, attached, self.evidence, dependency_manifest, step_id)
        required = set(dependencies["required_evidence_ids"])
        step = (dependency_manifest or {}).get("steps", {}).get(step_id, {})
        actions = set(step.get("action_evidence_ids", []))
        needs_review = (dependencies["dependency_review_status"] != "APPROVED" or not required or
                        not actions or not actions <= required or any(
            self.evidence[eid].get("review_status") != "APPROVED" or
            self.evidence[eid].get("source_sha256") != checksum or
            not self.evidence[eid].get("provenance") or
            self.evidence[eid].get("extraction_check_status") != "PASSED"
            for eid in required if eid in self.evidence))
        assembly_version = stable_id("assembly", checksum, [self.manifest["index_id"],digest(Path(__file__)),digest(Path(__file__).with_name("retrieval_policy.py")),"TRD-0.4"])
        return {"index_id": self.manifest["index_id"],
                "manual_checksum": self.manifest["source_sha256"], "assembly_version":assembly_version,
                **dependencies, "evidence_ids":sorted(attached),
                "evidence_objects":[self.evidence[eid] for eid in sorted(attached)],
                "applicability_status":applicability_status, "sufficiency_status":"NOT_ESTABLISHED",
                "conflicts":[], "missing_conditions":[] if applicability_status == "CONFIRMED" else ["Confirmed manual/variant fit"],
                "source_gaps":[{"type":"DEPENDENCY_REVIEW_REQUIRED","rider_resolvable":False}] if needs_review else [],
                "source_review_required":needs_review, "source_sha256": self.manifest["source_sha256"],
                "query": query, "hits": hits, "linked_chunks": related, "links": links,
                "parents": [self.parents[p] for p in sorted(parent_ids)],
                "may_generate_procedural_advice": False,
                "unresolved": ["Source applicability", "Independent evidence review", "Procedure, warning and prerequisite graph", "Claim support gate"]}

    def search(self, query, limit=5, candidate_limit=None, scope=None, rerank=None, *,
               policy=None, dependency_manifest=None, step_id=None,
               applicability_status="UNCONFIRMED", gate_status=None, gate_evidence_ids=()):
        """Conditional by default; bool rerank overrides are diagnostic ablations.

        Manifest, applicability and gate inputs must come from the trusted registry/controller.
        This boundary always returns candidate evidence and cannot release technical advice.
        """
        import numpy as np
        started = time.perf_counter()
        policy = policy or RetrievalPolicy()
        candidate_limit = policy.candidate_limit if candidate_limit is None else candidate_limit
        if rerank is not None and not isinstance(rerank, bool):
            raise ValueError("Rerank override must be a boolean or None")
        if not 1 <= limit <= candidate_limit <= policy.expanded_candidate_limit:
            raise ValueError("Invalid retrieval limits")
        if applicability_status not in ("CONFIRMED", "UNCONFIRMED", "MISMATCH"):
            raise ValueError("Invalid applicability status")
        if gate_status not in (None, "SAFETY_STOP", "SYSTEM_ERROR", "UNSUPPORTED", "AMBIGUOUS"):
            raise ValueError("Invalid controller gate status")
        if scope:
            for key, value in scope.items():
                actual = self.manifest["source_sha256"] if key == "source_sha256" else (getattr(self, "reviewed_scope", None) or self.manifest["source"]).get(key)
                if actual != value:
                    raise ValueError(f"Source scope mismatch: {key}")
        allowed_indices = None
        if scope:
            allowed_indices = set()
            reviewed_scope = getattr(self, "reviewed_scope", None)
            for i, chunk in enumerate(self.chunks):
                chunk_scope = chunk.get("scope", {})
                matches = True
                for key, value in scope.items():
                    if key == "source_sha256":
                        actual = chunk.get("source_sha256")
                    else:
                        actual = chunk_scope.get(key)
                        # An independently approved whole-manual scope can resolve
                        # null edition/variant tags in the immutable original snapshot.
                        if actual is None and key in ("edition", "variant") and reviewed_scope:
                            actual = reviewed_scope.get(key)
                    if actual != value:
                        matches = False
                        break
                if matches:
                    allowed_indices.add(i)
        if not query.strip():
            raise ValueError("Query is empty")
        mode = "conditional" if rerank is None else "always_diagnostic" if rerank else "off"
        telemetry = {"mode":mode, "policy":policy.to_dict(), "recovery_attempts":0,
                     "rerank_attempts":0, "rerank_pair_count":0, "rerank_skip_reason":None,
                     "stages_seconds":{}, "decisions":[]}
        try:
            if scope and not allowed_indices and gate_status is None:
                raise RetrievalSystemError("SYSTEM_ERROR: selected scope has no indexed chunks")
            step = (dependency_manifest or {}).get("steps", {}).get(step_id, {})
            if len(set(step.get("required_evidence_ids", []))) > policy.maximum_dependency_ids:
                raise RetrievalSystemError("SYSTEM_ERROR: dependency manifest exceeds work bound")
            if len(set(gate_evidence_ids)) > policy.maximum_dependency_ids:
                raise RetrievalSystemError("SYSTEM_ERROR: gate evidence exceeds work bound")
            for eid in gate_evidence_ids:
                evidence = self.evidence.get(eid, {})
                if not (evidence.get("review_status") == "APPROVED" and
                        evidence.get("source_sha256") == self.manifest["source_sha256"] and
                        evidence.get("provenance") and evidence.get("extraction_check_status") == "PASSED"):
                    raise RetrievalSystemError("SYSTEM_ERROR: gate evidence is invalid")
            # Terminal controller decisions need no embedding/model work.
            if gate_status is not None:
                dense = sparse = np.zeros(len(self.chunks))
                candidates, fused, signals = [], {}, {"ranking_uncertain":False, "uncertainty_reasons":[]}
            else:
                stage = time.perf_counter()
                vector = self.model.encode(query, normalize_embeddings=True)
                if np.shape(vector) != (self.vectors.shape[1],) or not np.isfinite(vector).all():
                    raise RetrievalSystemError("SYSTEM_ERROR: invalid query embedding")
                dense = self.vectors @ vector
                sparse = np.zeros(len(self.chunks))
                bm = self.bm25
                for term in set(tokens(query)):
                    for idx, tf in bm["postings"].get(term, []):
                        denom = tf + bm["k1"] * (1 - bm["b"] + bm["b"] * bm["lengths"][idx] / max(bm["avgdl"], 1))
                        sparse[idx] += bm["idf"][term] * tf * (bm["k1"] + 1) / denom
                candidates, fused, signals = self._rank(dense, sparse, candidate_limit, policy, allowed_indices)
                telemetry["stages_seconds"]["first_retrieval"] = time.perf_counter()-stage
            stage = time.perf_counter()
            bundle = self._assemble(query, candidates, limit, dense, sparse, fused, {}, dependency_manifest, step_id, applicability_status, gate_evidence_ids)
            telemetry["stages_seconds"]["initial_assembly"] = time.perf_counter()-stage
            telemetry["initial_ranking_signals"] = signals
            action = next_retrieval_action(bundle, signals, gate_status=gate_status)
            telemetry["decisions"].append(action)
            retained = set(gate_evidence_ids)
            if action == "RECOVER_DEPENDENCIES":
                stage = time.perf_counter()
                telemetry["recovery_attempts"] = 1
                missing = bundle["missing_evidence_ids"]
                # Exact dependency IDs are stronger than a second semantic query.
                retained.update(set(bundle["required_evidence_ids"]) & self.evidence.keys())
                candidates, fused, signals = self._rank(dense, sparse, policy.expanded_candidate_limit, policy, allowed_indices)
                bundle = self._assemble(query, candidates, limit, dense, sparse, fused, {}, dependency_manifest, step_id, applicability_status, retained)
                telemetry["recovery"] = {"requested_evidence_ids":missing,
                    "fetched_evidence_ids":sorted(set(missing) & retained),
                    "remaining_missing_evidence_ids":bundle["missing_evidence_ids"],
                    "candidate_limit":policy.expanded_candidate_limit}
                telemetry["stages_seconds"]["dependency_recovery"] = time.perf_counter()-stage
                action = next_retrieval_action(bundle, signals, recovered=True)
                telemetry["decisions"].append(action)
                if bundle["missing_evidence_ids"]:
                    bundle["source_gaps"].append({"type":"REQUIRED_EVIDENCE_UNAVAILABLE", "rider_resolvable":False,
                                                 "evidence_ids":bundle["missing_evidence_ids"]})
            should_rerank = gate_status is None and (mode == "always_diagnostic" or
                              (mode == "conditional" and action == "RERANK_CANDIDATES"))
            if should_rerank:
                stage = time.perf_counter()
                telemetry["rerank_attempts"] = 1
                # Bound the cross-encoder even when dependency search used a wider pool.
                rerank_candidates = candidates[:candidate_limit]
                scores, pair_count, skip = self._rerank(query, rerank_candidates, policy)
                telemetry["rerank_pair_count"] = pair_count
                telemetry["rerank_skip_reason"] = skip
                telemetry["stages_seconds"]["reranking"] = time.perf_counter()-stage
                if scores is not None:
                    rerank_candidates.sort(key=lambda i: (-scores[i], self.chunks[i]["id"]))
                    # Keep mandatory reviewed evidence across changes in top-k ordering.
                    retained.update(set(bundle["required_evidence_ids"]) & self.evidence.keys())
                    stage = time.perf_counter()
                    bundle = self._assemble(query, rerank_candidates, limit, dense, sparse, fused, scores, dependency_manifest, step_id, applicability_status, retained)
                    telemetry["stages_seconds"]["post_rerank_assembly"] = time.perf_counter()-stage
                    action = next_retrieval_action(bundle, signals, recovered=bool(telemetry["recovery_attempts"]), reranked=True)
                else:
                    action = "RANKING_UNRESOLVED"
                telemetry["decisions"].append(action)
            elif action == "RERANK_CANDIDATES":
                telemetry["rerank_skip_reason"] = "RERANK_DISABLED"
                action = "RANKING_UNRESOLVED"
            else:
                telemetry["rerank_skip_reason"] = action
            telemetry["final_action"] = action
            bundle["retrieval_policy"] = telemetry
            bundle["retrieval_action"] = action
            bundle["reranked"] = bool(telemetry["rerank_attempts"] and not telemetry["rerank_skip_reason"])
            bundle["elapsed_seconds"] = time.perf_counter()-started
            bundle["query_id"] = stable_id("query", self.manifest["source_sha256"], [bundle["assembly_version"],query,mode,policy.to_dict(),step_id,dependency_manifest,applicability_status,gate_status,sorted(gate_evidence_ids)])
            return bundle
        except Exception as exc:
            error = RetrievalSystemError("SYSTEM_ERROR: retrieval, assembly or reranking failed")
            error.telemetry = {**telemetry, "final_action":"SYSTEM_ERROR", "error_class":type(exc).__name__,
                               "elapsed_seconds":time.perf_counter()-started}
            raise error from exc


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
    p.add_argument("--rerank", action="store_true", help="Always rerank for diagnostic comparison")
    p.add_argument("--rerank-mode", choices=["conditional", "off", "always"], default="conditional")
    args = p.parse_args()
    if args.prepare_reranker:
        prepare_reranker(args.index)
    if args.evaluate:
        evaluate(args.index)
    if args.query:
        mode = "always" if args.rerank else args.rerank_mode
        override = {"conditional":None, "off":False, "always":True}[mode]
        print(json.dumps(Retriever(args.index).search(args.query, rerank=override), ensure_ascii=False, indent=2))
