"""Recovery and failure tests with deterministic synthetic evidence, no model downloads."""
import unittest
from pathlib import Path
import numpy as np

from online_retrieve import Retriever, RetrievalSystemError
from retrieval_policy import RetrievalPolicy, ranking_signals


class Encoder:
    def __init__(self):
        self.calls = 0
    def encode(self, query, **kwargs):
        self.calls += 1
        return np.array([1.0, 0.0])


class Tokenizer:
    model_max_length = 512
    def encode(self, text, **kwargs):
        return text.split()
    def decode(self, values, **kwargs):
        return " ".join(values)
    def num_special_tokens_to_add(self, **kwargs):
        return 3


class Reranker:
    tokenizer = Tokenizer()
    def __init__(self, fail=False):
        self.calls = 0
        self.fail = fail
    def predict(self, pairs, **kwargs):
        self.calls += 1
        if self.fail:
            raise TimeoutError("test outage")
        # Prefer the other section; the mandatory action/warning must survive.
        return np.array([1.0 if "other" in passage else 0.0 for _, passage in pairs])


def fixture():
    r = Retriever.__new__(Retriever)
    r.root = Path(".")
    r.manifest = {"source_sha256":"sha", "source":{}, "index_id":"synthetic"}
    r.model, r.reranker = Encoder(), Reranker()
    r.chunks = [
        {"id":"c1", "index_text":"check action", "parent_section_id":"p1", "evidence_ids":["action"], "citations":[{"page_id":"page1"}]},
        {"id":"c2", "index_text":"other check", "parent_section_id":"p2", "evidence_ids":["other"], "citations":[{"page_id":"page2"}]},
    ]
    r.parents = {"p1":{"id":"p1", "evidence_ids":["action"], "child_ids":["c1"]},
                 "p2":{"id":"p2", "evidence_ids":["other"], "child_ids":["c2"]}}
    r.evidence = {eid:{"id":eid, "review_status":"APPROVED", "source_sha256":"sha", "provenance":[{"pdf_page":1}], "extraction_check_status":"PASSED"}
                  for eid in ("action", "warning", "other")}
    r.graph = {"edges":[]}
    r.vectors = np.array([[1.0,0.0],[0.99,0.1]])
    r.bm25 = {"postings":{}, "idf":{}, "k1":1.5, "b":0.75, "lengths":[2,2], "avgdl":2}
    manifest = {"manual_checksum":"sha", "version":"reviewed-fixture-v1", "review_status":"APPROVED",
                "steps":{"step":{"review_status":"APPROVED", "action_evidence_ids":["action"], "required_evidence_ids":["action","warning"]}}}
    return r, manifest


def search(r, manifest, **kwargs):
    return r.search("check", limit=1, dependency_manifest=manifest, step_id="step",
                    applicability_status="CONFIRMED", **kwargs)


class ConditionalTests(unittest.TestCase):
    def test_missing_review_skips_rerank_even_with_uncertain_ranks(self):
        r, _ = fixture()
        b = r.search("check", limit=1)
        self.assertTrue(b["retrieval_policy"]["initial_ranking_signals"]["ranking_uncertain"])
        self.assertEqual(b["retrieval_action"],"SOURCE_REVIEW_REQUIRED")
        self.assertEqual(r.reranker.calls,0)
        self.assertEqual(b["retrieval_policy"]["recovery_attempts"],0)

    def test_clear_ranking_skips_rerank(self):
        r, m = fixture()
        r.parents["p1"]["evidence_ids"].append("warning")
        r.bm25.update(postings={"check":[(0,1)]},idf={"check":1.0})
        b = search(r,m)
        self.assertEqual(b["retrieval_action"],"CONTINUE_GATES")
        self.assertTrue(b["coverage_established"])
        self.assertFalse(b["may_generate_procedural_advice"])
        self.assertEqual(r.reranker.calls,0)

    def test_one_rerank_preserves_mandatory_evidence(self):
        r, m = fixture()
        r.parents["p1"]["evidence_ids"].append("warning")
        b = search(r,m)
        self.assertEqual(b["hits"][0]["id"],"c2")
        self.assertTrue({"action","warning"} <= set(b["attached_evidence_ids"]))
        self.assertTrue(b["coverage_established"])
        self.assertEqual(r.reranker.calls,1)
        self.assertEqual(b["retrieval_policy"]["rerank_attempts"],1)
        self.assertFalse(b["may_generate_procedural_advice"])

    def test_missing_warning_fetches_once_without_reembedding(self):
        r, m = fixture()
        b = search(r,m)
        self.assertEqual(b["retrieval_policy"]["recovery_attempts"],1)
        self.assertEqual(b["retrieval_policy"]["recovery"]["fetched_evidence_ids"],["warning"])
        self.assertTrue(b["coverage_established"])
        self.assertEqual(r.model.calls,1)
        self.assertEqual(r.reranker.calls,1)

    def test_absent_source_dependency_abstains_after_one_recovery(self):
        r, m = fixture()
        del r.evidence["warning"]
        b = search(r,m)
        self.assertEqual(b["retrieval_action"],"UNSUPPORTED")
        self.assertEqual(b["missing_evidence_ids"],["warning"])
        self.assertEqual(b["retrieval_policy"]["recovery_attempts"],1)
        self.assertEqual(r.reranker.calls,0)
        self.assertFalse(b["source_gaps"][0]["rider_resolvable"])

    def test_unreviewed_warning_and_checksum_mismatch_cannot_trigger_rerank(self):
        for mismatch in (False,True):
            r, m = fixture()
            if mismatch:
                m["manual_checksum"] = "wrong"
            else:
                r.evidence["warning"]["review_status"] = "UNREVIEWED"
            b = search(r,m)
            self.assertEqual(b["retrieval_action"],"SOURCE_REVIEW_REQUIRED")
            self.assertEqual(r.reranker.calls,0)

    def test_reranker_outage_is_system_error_without_retry(self):
        r, m = fixture()
        r.parents["p1"]["evidence_ids"].append("warning")
        r.reranker = Reranker(fail=True)
        with self.assertRaises(RetrievalSystemError) as caught:
            search(r,m)
        self.assertEqual(caught.exception.status,"SYSTEM_ERROR")
        self.assertEqual(caught.exception.telemetry["rerank_attempts"],1)
        self.assertEqual(r.reranker.calls,1)

    def test_terminal_controller_status_skips_all_model_work(self):
        for status in ("SAFETY_STOP","UNSUPPORTED","SYSTEM_ERROR","AMBIGUOUS"):
            r, m = fixture()
            b = search(r,m,gate_status=status)
            self.assertEqual(b["retrieval_action"],status)
            self.assertEqual(r.model.calls,0)
            self.assertEqual(r.reranker.calls,0)

    def test_known_safety_stop_retains_verified_warning_without_model_work(self):
        r, m = fixture()
        b = search(r,m,gate_status="SAFETY_STOP",gate_evidence_ids=["warning"])
        self.assertEqual(b["retrieval_action"],"SAFETY_STOP")
        self.assertEqual(b["attached_evidence_ids"],["warning"])
        self.assertEqual(r.model.calls,0)

    def test_dependency_and_pair_work_bounds_fail_closed(self):
        r, m = fixture()
        with self.assertRaises(RetrievalSystemError):
            search(r,m,policy=RetrievalPolicy(maximum_dependency_ids=1))
        r.parents["p1"]["evidence_ids"].append("warning")
        b = search(r,m,policy=RetrievalPolicy(maximum_rerank_pairs=1))
        self.assertEqual(b["retrieval_action"],"RANKING_UNRESOLVED")
        self.assertEqual(b["retrieval_policy"]["rerank_skip_reason"],"RERANK_PAIR_LIMIT_EXCEEDED")
        self.assertEqual(r.reranker.calls,0)

    def test_unconfirmed_fit_and_disabled_rerank_do_not_run_it(self):
        r, m = fixture()
        r.parents["p1"]["evidence_ids"].append("warning")
        b = r.search("check",limit=1,dependency_manifest=m,step_id="step")
        self.assertEqual(b["retrieval_action"],"AMBIGUOUS")
        self.assertEqual(r.reranker.calls,0)
        b = search(r,m,rerank=False)
        self.assertEqual(b["retrieval_action"],"RANKING_UNRESOLVED")
        self.assertEqual(r.reranker.calls,0)

    def test_long_query_keeps_full_text_and_records_skip(self):
        r, m = fixture()
        r.parents["p1"]["evidence_ids"].append("warning")
        query = "check " * 129
        b = r.search(query,limit=1,dependency_manifest=m,step_id="step",applicability_status="CONFIRMED")
        self.assertEqual(b["query"],query)
        self.assertEqual(b["retrieval_action"],"RANKING_UNRESOLVED")
        self.assertEqual(b["retrieval_policy"]["rerank_skip_reason"],"QUERY_EXCEEDS_RERANK_LIMIT")
        self.assertEqual(r.reranker.calls,0)

    def test_nonfinite_scores_fail_closed(self):
        r, m = fixture()
        r.parents["p1"]["evidence_ids"].append("warning")
        r.reranker.predict = lambda pairs, **kw: np.full(len(pairs),np.nan)
        with self.assertRaises(RetrievalSystemError):
            search(r,m)

    def test_sibling_chunks_do_not_count_as_competing_sections(self):
        signals = ranking_signals(["p1","p1"],["p1","p1"],[("p1",0.03)],RetrievalPolicy())
        self.assertFalse(signals["ranking_uncertain"])


if __name__ == "__main__":
    unittest.main()
