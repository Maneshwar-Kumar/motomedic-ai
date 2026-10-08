"""Checks the source lock and evidence provenance at the retrieval boundary."""

import unittest

from retrieve_evidence import SourceMismatch, assemble


class EvidenceAssemblyTests(unittest.TestCase):
    def test_wrong_source_fails_before_search(self):
        with self.assertRaises(SourceMismatch):
            assemble("engine will not start", checksum="0" * 64)
        with self.assertRaises(SourceMismatch):
            assemble("engine will not start", model="different motorcycle")

    def test_checked_cross_reference_is_attached_without_approving_advice(self):
        bundle = assemble("The engine will not start and I found a blown fuse")
        pages = {page["evidence_id"]: page for page in bundle["evidence_pages"]}
        self.assertIn("p0121", pages)
        self.assertIn("p0112", pages)
        self.assertEqual(pages["p0112"]["role"], "checked_topic_context")
        self.assertTrue(any(link["from"] == "p0121" and link["to"] == "p0112"
                            for link in bundle["expanded_links"]))
        self.assertFalse(bundle["may_generate_procedural_advice"])
        self.assertIn("bike_variant_applicability_unconfirmed", bundle["unresolved_gates"])

    def test_unverified_navigation_edges_are_not_expanded(self):
        bundle = assemble("The engine will not start and I found a blown fuse")
        self.assertTrue(all(link["type"] == "TOPIC_RELATED_REVIEWED"
                            for link in bundle["expanded_links"]))
        self.assertTrue(all(link["implies_procedure_order"] is False
                            for link in bundle["expanded_links"]))


if __name__ == "__main__":
    unittest.main()
