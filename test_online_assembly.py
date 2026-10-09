import json
import os
from pathlib import Path
import unittest
import numpy as np
from online_retrieve import Retriever, dependency_coverage

class DependencyTests(unittest.TestCase):
    def test_empty_approved_set_never_proves_sufficiency(self):
        manifest={"manual_checksum":"sha","version":"v1","review_status":"APPROVED","steps":{"s":{"review_status":"APPROVED","required_evidence_ids":[],"action_evidence_ids":[]}}}
        self.assertFalse(dependency_coverage("sha",[],{},manifest,"s")["coverage_established"])
    def test_missing_warning_is_reported_and_blocks(self):
        manifest={"manual_checksum":"sha","version":"v1","review_status":"APPROVED","steps":{"s":{"review_status":"APPROVED","required_evidence_ids":["action","warning"],"action_evidence_ids":["action"]}}}
        result=dependency_coverage("sha",["action"],{},manifest,"s")
        self.assertEqual(result["missing_evidence_ids"],["warning"])
        self.assertFalse(result["coverage_established"])
        self.assertFalse(dependency_coverage("different",["action"],{},manifest,"s")["coverage_established"])
    def test_unreviewed_objects_do_not_pass(self):
        manifest={"manual_checksum":"sha","version":"v1","review_status":"APPROVED","steps":{"s":{"review_status":"APPROVED","required_evidence_ids":["a"],"action_evidence_ids":["a"]}}}
        self.assertFalse(dependency_coverage("sha",["a"],{"a":{"review_status":"UNREVIEWED"}},manifest,"s")["coverage_established"])

class HostedArtifactTests(unittest.TestCase):
    def test_candidate_bundles_attach_typed_objects_and_remain_blocked(self):
        root=Path(os.environ.get("MOTOMEDIC_TEST_INDEX",str(Path(__file__).parent/"build/index-bge-final")))
        if not root.exists():self.skipTest("Download the hosted BGE index artifact for this integration check")
        smoke=json.loads((root/"server_smoke.json").read_text())
        vectors={case["query"]:np.asarray(case["vector"],dtype="float32") for case in smoke["cases"]}
        class SavedOnlineEncoder:
            def encode(self,query,**kwargs):return vectors[query]
        retriever=Retriever(root,embedding_model=SavedOnlineEncoder())
        for query in vectors:
            bundle=retriever.search(query)
            self.assertFalse(bundle["may_generate_procedural_advice"])
            self.assertFalse(bundle["coverage_established"])
            self.assertEqual(bundle["dependency_review_status"],"MISSING")
            self.assertEqual(set(bundle["attached_evidence_ids"]),{e["id"] for e in bundle["evidence_objects"]})
            self.assertTrue(all(e["source_sha256"]==smoke["source_sha256"] for e in bundle["evidence_objects"]))
            self.assertTrue(all(e["provenance"] for e in bundle["evidence_objects"]))
if __name__ == "__main__":unittest.main()
