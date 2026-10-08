"""Regression checks for the provisional, source-linked dialogue controller."""

import unittest

from diagnose import (
    CARDS_PATH,
    FLOW_PATH,
    GOLD_PATH,
    Session,
    build_cache,
    load_json,
    lookup_cache,
    validate_dialogues,
)


class DiagnosisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.flow = load_json(FLOW_PATH)
        cls.dialogues = load_json(GOLD_PATH)
        cls.cards = load_json(CARDS_PATH)

    def test_all_atomic_cases_follow_expected_route(self):
        validate_dialogues(self.flow, self.dialogues, self.cards)

    def test_unresolved_fuse_offers_remaining_documented_check(self):
        session = Session.start(self.flow, "The engine will not start.")
        for answer in ["no", "yes", "no", "yes", "still"]:
            session.reply(answer)
        self.assertEqual(session.current, "q_spark_connection")
        self.assertEqual(session.attempted_actions, ["a_fuse"])

    def test_uncertain_abs_never_becomes_confirmed_fault(self):
        session = Session.start(self.flow, "The ABS indicator is on.")
        session.reply("unsure")
        self.assertEqual(session.current, "q_abs_at_speed")
        result = session.reply("unsure")
        self.assertEqual(result["node_id"], "t_abs_unclear")
        self.assertEqual(result["route"], "AMBIGUOUS")

    def test_exact_cache_is_disabled_and_version_bound(self):
        from tempfile import TemporaryDirectory
        from pathlib import Path

        with TemporaryDirectory() as folder:
            destination = Path(folder) / "cache.json"
            build_cache(self.flow, self.dialogues, self.cards, destination)
            cache = load_json(destination)
            self.assertIsNone(lookup_cache(self.flow, cache, "no_start", ["yes"], self.flow["source_sha256"], "prototype_manual_scope"))
            hit = lookup_cache(self.flow, cache, "no_start", ["yes"], self.flow["source_sha256"], "prototype_manual_scope", allow_draft=True)
            self.assertEqual(hit["node_id"], "t_electrical_service")
            self.assertIsNone(lookup_cache(self.flow, cache, "no_start", ["yes"], "0" * 64, "prototype_manual_scope", allow_draft=True))
            self.assertIsNone(lookup_cache(self.flow, cache, "no_start", ["yes"], self.flow["source_sha256"], "different_variant", allow_draft=True))
            self.assertIsNone(lookup_cache(self.flow, cache, "no_start", ["no", "yes", "yes", "yes"], self.flow["source_sha256"], "prototype_manual_scope", allow_draft=True))


if __name__ == "__main__":
    unittest.main()
