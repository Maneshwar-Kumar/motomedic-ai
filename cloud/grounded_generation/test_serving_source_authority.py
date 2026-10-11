"""Real pinned-source/context checks; synthetic payloads, zero provider calls."""
from copy import deepcopy
import os
from pathlib import Path
import unittest
from approved_registry import ApprovedEvidenceRegistry
from constrained_generator import ValidationFailure
from cloud.grounded_generation.source_authority import SourceAuthority as PriorAuthority
from cloud.grounded_generation.serving_source_authority import SourceAuthority, REFINEMENT_REVIEW_SHA

ROOT = Path(__file__).resolve().parents[2]
INDEX = Path(os.environ.get('MOTOMEDIC_TEST_INDEX', str(ROOT / 'build/index-bge-final')))
FUEL = 'evidence_3f8de8466049af12783de7d0'
NOTE = 'evidence_64de3cc72b85735055b58fec'
WARN = 'evidence_a03ccd44ab2d6b5db6bab123'
PUMP = 'evidence_c5bacd3bd5b428c8950b0ce1'
REFINED = {FUEL, NOTE, WARN, PUMP}


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = ApprovedEvidenceRegistry.load(ROOT, INDEX)
        cls.prior = PriorAuthority(cls.base, INDEX)
        cls.original = SourceAuthority(cls.base, INDEX)

    def setUp(self):
        self.s = deepcopy(self.original)

    def bundle(self, eid=FUEL):
        chunk = next(c for c in self.s.chunks.values() if eid in c['evidence_ids'])
        return {'index_id': self.s.index_id, 'manual_checksum': self.s.checksum,
                'hits': [deepcopy(chunk)]}

    def test_exact_fuel_component_closure_retains_both_warnings_and_footnote(self):
        payload = self.s.assemble(self.bundle())
        self.assertEqual(self.s._closure({FUEL}), REFINED)
        self.assertEqual(set(payload['required_evidence_ids']), REFINED)
        self.assertEqual(len(payload['required_display']), 3)
        self.assertTrue(self.s.validate(payload))
        pages = {p['pdf_page'] for p in payload['citation_mapping']}
        self.assertEqual(pages, {18, 64})
        cells = payload['evidence'][FUEL]['source_object']['content']['data']['table_cells']
        text_index = cells['fields'].index('text')
        self.assertEqual(cells['rows'][11][text_index], '3 L ± 0.5* L')

    def test_other_dependency_scopes_unchanged_and_no_whole_parent_text(self):
        for eid in set(self.prior.links) - REFINED:
            self.assertEqual(self.s.links[eid], self.prior.links[eid])
        self.assertFalse(self.s.assemble(self.bundle())['action_authority'])
        for eid in REFINED:
            self.assertEqual(self.s.context_proofs[eid], {REFINEMENT_REVIEW_SHA})

    def test_output_selection_cannot_drop_refuel_warning_or_approximation(self):
        payload = self.s.assemble(self.bundle())
        selected = self.s.select(payload, {FUEL})
        self.assertEqual(set(selected['required_evidence_ids']), REFINED)
        self.assertEqual(len(selected['required_display']), 3)

    def test_new_exact_source_raw_mutation_rejected(self):
        payload = self.s.assemble(self.bundle())
        self.s.evidence[WARN]['raw_object']['text'] += ' unreviewed alteration'
        with self.assertRaisesRegex(ValidationFailure, 'OBJECT_CHANGED'):
            self.s.validate(payload)

    def test_changed_required_warning_projection_rejected(self):
        payload = self.s.assemble(self.bundle())
        payload['required_display'] = []
        with self.assertRaisesRegex(ValidationFailure, 'ADMITTED_CONTEXT_CHANGED'):
            self.s.validate(payload)

    def test_independently_complete_anchor_survives_unreviewed_search_sibling(self):
        for chunk in self.s.chunks.values():
            direct = set(chunk['evidence_ids'])
            complete = direct & self.s.complete_context_ids
            unknown = direct - self.s.complete_context_ids
            if complete and unknown:
                payload = self.s.assemble({'index_id': self.s.index_id,
                    'manual_checksum': self.s.checksum, 'hits': [chunk]})
                if payload['evidence']:
                    self.assertTrue(payload['gaps'])
                    self.assertTrue(all(g['rider_resolvable'] is False for g in payload['gaps']))
                    self.assertFalse(unknown & set(payload['evidence']))
                    return
        self.fail('No mixed independently complete reviewed anchor fixture exists')


if __name__ == '__main__': unittest.main()
