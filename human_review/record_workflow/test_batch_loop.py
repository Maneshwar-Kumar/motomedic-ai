import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import workflow
from batch_loop import ACTORS, Batch
from workflow import ORIGIN, POLICY, digest, encoded


class BatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.batch = Batch(self.root)
        self.batch.home.mkdir(parents=True)
        (self.batch.home / "COORDINATION.md").write_text("Synthetic batch specification; no source approval", encoding="utf-8")
        (self.root / "fixture.pdf").write_bytes(b"Synthetic manual fixture only")
        self.sha = digest((self.root / "fixture.pdf").read_bytes())
        self.batch.store.context = lambda: {"manual_sha256": self.sha, "manual_path": "fixture.pdf", "policy_version": POLICY, "files": {}}
        self.patcher = patch("workflow.MANUAL_SHA", self.sha)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)
        self.other = patch("batch_loop.MANUAL_SHA", self.sha)
        self.other.start()
        self.addCleanup(self.other.stop)
        self.spec = self.batch.init()

    def author(self):
        return {"record_id": "GEN001", "version": 1, "role": "author", "actor": ACTORS["author"],
                "manual_sha256": self.sha, "batch_context_sha256": self.spec["batch_context_sha256"], "origin_declaration": ORIGIN,
                "distinctive_intent": "Synthetic isolated case", "question": "Synthetic question", "answer": "Synthetic answer",
                "turns": [{"speaker": "rider", "text": "Synthetic"}], "conditions": [], "warnings": [], "source_refs": [{"pdf_page": 21, "printed_page": "19"}],
                "source_limits": ["Synthetic fixture only"], "stopping_rules": [], "forbidden_claims": [], "expected_route": "UNSUPPORTED"}

    def publish(self, role, payload):
        path = self.batch.path(payload["record_id"], payload["version"], role)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(encoded(payload))

    def test_batch_pin_survives_live_context_updates_and_receipt_binds_bytes(self):
        author = self.author()
        self.publish("author", author)
        result = self.batch.pump()
        self.assertEqual(result["failures"], [])
        receipt = json.loads(self.batch.receipt("GEN001", 1, "author").read_bytes())
        self.assertEqual(receipt["payload_sha256"], digest(encoded(author)))
        self.batch.store.context = lambda: {"manual_sha256": self.sha, "manual_path": "fixture.pdf", "policy_version": POLICY, "files": {}, "later_annotation": True}
        review = {"record_id": "GEN001", "version": 1, "role": "reviewer", "actor": ACTORS["reviewer"], "manual_sha256": self.sha,
                  "batch_context_sha256": self.spec["batch_context_sha256"], "context_sha256": receipt["context_sha256"], "author_sha256": receipt["payload_sha256"],
                  "independent_original_review": True, "original_page_checks": [{"pdf_page": 21, "printed_page": "19", "checked_span": "Synthetic fixture"}],
                  "findings": [], "reason": "Synthetic review", "verdict": "PASS"}
        self.publish("reviewer", review)
        self.assertEqual(self.batch.pump()["failures"], [])
        self.assertEqual(self.batch.store.native_status()[0]["state"], "AWAITING_JUDGE")
        self.assertFalse(self.batch.store.native_status()[0]["current_context_matches"])

    def test_changed_manual_rejects_pin_and_partial_batch_cannot_finish(self):
        (self.root / "fixture.pdf").write_bytes(b"Changed source")
        self.publish("author", self.author())
        result = self.batch.pump()
        self.assertTrue(result["failures"])
        self.assertIn("manual changed", result["failures"][0]["reason"])
        with self.assertRaisesRegex(ValueError, "All 100"):
            self.batch.finish()
        self.assertFalse((self.batch.store.home / "batch_100_completion.json").exists())

    def test_same_actor_review_is_not_imported(self):
        self.publish("author", self.author())
        self.batch.pump()
        receipt = json.loads(self.batch.receipt("GEN001", 1, "author").read_bytes())
        bad_review = {"record_id": "GEN001", "version": 1, "role": "reviewer", "actor": ACTORS["author"], "manual_sha256": self.sha,
                      "batch_context_sha256": self.spec["batch_context_sha256"], "context_sha256": receipt["context_sha256"], "author_sha256": receipt["payload_sha256"]}
        self.publish("reviewer", bad_review)
        result = self.batch.pump()
        self.assertIn("actor mismatch", result["failures"][0]["reason"])
        self.assertFalse(self.batch.receipt("GEN001", 1, "reviewer").exists())


if __name__ == "__main__":
    unittest.main()
