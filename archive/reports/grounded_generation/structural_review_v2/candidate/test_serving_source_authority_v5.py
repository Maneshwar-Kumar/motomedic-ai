"""Candidate v5 scoped structural review: real pinned index/packages, zero provider calls.

Run from the project root:
PYTHONPATH=. python reports/grounded_generation/structural_review_v2/candidate/test_serving_source_authority_v5.py -v
"""
from copy import deepcopy
import json
import os
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from approved_registry import ApprovedEvidenceRegistry
from constrained_generator import ValidationFailure
from cloud.grounded_generation.serving_source_authority import SourceAuthority as V4Authority
import serving_source_authority_v5 as v5  # noqa: E402

ROOT = Path(__file__).resolve().parents[4]
INDEX = Path(os.environ.get('MOTOMEDIC_TEST_INDEX', str(ROOT / 'build/index-bge-final')))
PROPOSAL = json.loads((ROOT / v5.PROPOSAL_PATH).read_text(encoding='utf-8'))
LUBRICANT_TABLE = 'evidence_a6950ea73293cda81e695ce1'
APPROXIMATE_NOTE = 'evidence_424971c8f0be958200b09990'
WARNING_SYMBOL = 'evidence_16df2546fcf3ee0edb0cf3ec'
ABS_CAUTION = 'evidence_d867f6c7da84e269ebddf176'
ABS_CHECK_UP = 'evidence_bc21f201712faeaa4da13dbe'
ABS_ABOVE_5_KMH = 'evidence_be61e25b35303514cfe3e5c8'
DOT4_FOOTNOTE = 'evidence_36ee9102cfd9a8ef98c0466d'
SUSPENSION_TABLE = 'evidence_fb5ddc131802596bbfc6777e'


class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = ApprovedEvidenceRegistry.load(ROOT, INDEX)
        cls.prior = V4Authority(cls.base, INDEX)
        cls.original = v5.SourceAuthority(cls.base, INDEX)

    def setUp(self):
        self.s = deepcopy(self.original)

    def chunk_of(self, eid):
        return next((c for c in self.s.chunks.values() if eid in c['evidence_ids']), None)

    def bundle(self, eid):
        chunk = self.chunk_of(eid)
        return {'index_id': self.s.index_id, 'manual_checksum': self.s.checksum, 'hits': [deepcopy(chunk)]}

    def test_unapproved_or_changed_package_fails_closed(self):
        with self.assertRaises(ValidationFailure):
            v5.SourceAuthority(self.base, INDEX, review_sha=None)
        with self.assertRaises(ValidationFailure):
            v5.SourceAuthority(self.base, INDEX, proposal_sha='0' * 64)

    def test_only_scoped_objects_added_and_prior_links_only_extended_in_scope(self):
        members = {e for c in PROPOSAL['components'].values() for e in c['required_evidence_ids']}
        self.assertEqual(self.s.complete_context_ids - self.prior.complete_context_ids,
                         members - self.prior.complete_context_ids)
        for eid in self.prior.links:
            self.assertTrue(self.prior.links[eid] <= self.s.links[eid], eid)
            if eid in PROPOSAL['evidence_dependencies']:
                self.assertEqual(self.s.links[eid] - self.prior.links[eid],
                                 set(PROPOSAL['evidence_dependencies'][eid]['external_dependency_evidence_ids'])
                                 - self.prior.links[eid])
            elif eid not in members:
                self.assertEqual(self.s.links[eid], self.prior.links[eid], eid)

    def test_every_component_member_admits_its_whole_component_with_displays(self):
        for name, component in PROPOSAL['components'].items():
            members = set(component['required_evidence_ids'])
            for eid in members:
                if self.chunk_of(eid) is None:
                    # Unparented footnote: reachable only through its reviewed table dependency.
                    self.assertTrue(any(eid in self.s._closure({t}) for t in PROPOSAL['evidence_dependencies']), eid)
                    continue
                payload = self.s.assemble(self.bundle(eid))
                self.assertTrue(members <= set(payload['required_evidence_ids']), name)
                shown = {c['claim_id'] for c in payload['required_display']}
                self.assertTrue({c['claim_id'] for c in component['mandatory_display']} <= shown, name)
                self.assertFalse(payload['action_authority'])
                self.assertTrue(self.s.validate(payload))

    def test_figure_label_artifacts_remain_gaps(self):
        excluded = PROPOSAL['components']['DISPLAY_LANGUAGE_MENU']['excluded_evidence_ids']
        for eid in excluded:
            payload = self.s.assemble(self.bundle(eid))
            self.assertNotIn(eid, payload['required_evidence_ids'])
            self.assertIn(eid, {e for gap in payload['gaps'] for e in gap['evidence_ids']})

    def test_lubricant_table_carries_approximation_note_and_dot4_footnote(self):
        payload = self.s.assemble(self.bundle(LUBRICANT_TABLE))
        selected = self.s.select(payload, {LUBRICANT_TABLE})
        for eid in (APPROXIMATE_NOTE, DOT4_FOOTNOTE):
            self.assertIn(eid, payload['required_evidence_ids'])
            self.assertIn(eid, selected['required_evidence_ids'])

    def test_suspension_table_carries_merged_cell_clarification(self):
        payload = self.s.assemble(self.bundle(SUSPENSION_TABLE))
        roles = {c['response_role'] for c in payload['required_display'] if SUSPENSION_TABLE in c['evidence_ids']}
        self.assertEqual(roles, {'FACT'})
        self.assertIn('review_note', payload['evidence'][SUSPENSION_TABLE]['reviewed_source_context'])

    def test_warning_symbol_cannot_be_selected_without_tell_tale_cautions(self):
        payload = self.s.assemble(self.bundle(WARNING_SYMBOL))
        selected = self.s.select(payload, {WARNING_SYMBOL})
        self.assertTrue({ABS_CAUTION, ABS_CHECK_UP} <= set(selected['required_evidence_ids']))
        self.assertTrue(any({ABS_CAUTION, ABS_CHECK_UP} <= set(c['evidence_ids']) for c in selected['required_display']))
        # Round-2 review: page-63 objects are not linked, so their broad v4 closure cannot leak in.
        self.assertNotIn(ABS_ABOVE_5_KMH, selected['required_evidence_ids'])
        self.assertEqual({p['pdf_page'] for p in selected['citation_mapping']}, {62})


if __name__ == '__main__':
    unittest.main()
