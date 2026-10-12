"""Real pinned-source/context checks; synthetic payloads, zero provider calls."""
from copy import deepcopy
import os
from pathlib import Path
import unittest
from approved_registry import ApprovedEvidenceRegistry
from constrained_generator import ValidationFailure
from cloud.grounded_generation.source_authority import SourceAuthority as PriorAuthority
from cloud.grounded_generation.serving_source_authority import SourceAuthority, REFINEMENT_REVIEW_SHA
from evidence_registry import content_hash

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


class SyntheticGapRetentionTests(unittest.TestCase):
    """Immutable gap membership checks without source/model/cloud fixtures."""
    def setUp(self):
        self.s = SourceAuthority.__new__(SourceAuthority)
        self.s.index_id = 'synthetic-index'; self.s.checksum = 'synthetic-manual'
        self.s.chunks = {
            'reviewed': {'id':'reviewed', 'evidence_ids':['approved'], 'parent_section_id':'p1'},
            'gap': {'id':'gap', 'evidence_ids':['unreviewed'], 'parent_section_id':'p2'}}
        self.s._chunk_hashes = {cid: content_hash(c) for cid, c in self.s.chunks.items()}
        self.s.complete_context_ids = {'approved'}
        self.s.check = lambda: None
        self.s.evidence_ready = lambda eid: eid == 'approved'
        self.s._closure = lambda ids: set(ids)
        self.s._payload = lambda ids, anchors, gaps: {'evidence': {eid:{} for eid in ids},
            'required_evidence_ids':sorted(ids), 'anchor_evidence_ids':sorted(anchors), 'gaps':gaps}
        self.bundle = {'index_id':self.s.index_id, 'manual_checksum':self.s.checksum,
            'hits':[deepcopy(self.s.chunks['reviewed'])],
            'retained_gap_hits':[deepcopy(self.s.chunks['gap'])]}

    def test_retained_immutable_hit_regenerates_gap_without_admitting_unreviewed_content(self):
        payload = self.s.assemble(self.bundle)
        self.assertEqual(set(payload['evidence']), {'approved'})
        self.assertEqual(payload['gaps'], [{'type':'SOURCE_CONTEXT_COMPLETENESS_REVIEW_REQUIRED',
            'chunk_id':'gap', 'evidence_ids':['unreviewed'], 'rider_resolvable':False}])

    def test_retained_gap_sibling_cannot_admit_dropped_reviewed_anchor_or_warning(self):
        self.s.chunks['gap']['evidence_ids'] = ['discarded', 'unreviewed']
        self.s._chunk_hashes['gap'] = content_hash(self.s.chunks['gap'])
        self.s.complete_context_ids.update({'discarded', 'warning'})
        self.s.evidence_ready = lambda eid: eid in self.s.complete_context_ids
        self.s._closure = lambda ids: set(ids) | ({'warning'} if 'discarded' in ids else set())
        self.bundle['retained_gap_hits'] = [deepcopy(self.s.chunks['gap'])]
        payload = self.s.assemble(self.bundle)
        self.assertEqual(payload['required_evidence_ids'], ['approved'])
        self.assertEqual(payload['anchor_evidence_ids'], ['approved'])
        self.assertNotIn('discarded', payload['evidence'])
        self.assertNotIn('warning', payload['evidence'])
        self.assertEqual(payload['gaps'][0]['evidence_ids'], ['unreviewed'])

    def test_selected_gap_chunk_retains_complete_approved_sibling_closure(self):
        self.s.chunks['gap']['evidence_ids'] = ['discarded', 'unreviewed']
        self.s._chunk_hashes['gap'] = content_hash(self.s.chunks['gap'])
        self.s.complete_context_ids.update({'discarded', 'warning'})
        self.s.evidence_ready = lambda eid: eid in self.s.complete_context_ids
        self.s._closure = lambda ids: set(ids) | ({'warning'} if 'discarded' in ids else set())
        self.bundle['hits'] = [deepcopy(self.s.chunks['gap'])]
        self.bundle['retained_gap_hits'] = []
        payload = self.s.assemble(self.bundle)
        self.assertEqual(set(payload['required_evidence_ids']), {'discarded', 'warning'})
        self.assertEqual(payload['anchor_evidence_ids'], ['discarded'])
        self.assertEqual(payload['gaps'][0]['evidence_ids'], ['unreviewed'])

    def test_legacy_unselected_evidence_retention_cannot_reenter_admission(self):
        self.bundle['retained_approved_evidence_ids'] = ['approved']
        with self.assertRaisesRegex(ValidationFailure, 'UNSELECTED_SOURCE_ANCHOR_RETENTION'):
            self.s.assemble(self.bundle)

    def test_truly_unavailable_selected_dependency_is_a_gap_without_incomplete_admission(self):
        self.s._closure = lambda ids: set(ids) | {'missing-warning'}
        payload = self.s.assemble(self.bundle)
        self.assertEqual(payload['required_evidence_ids'], [])
        self.assertEqual(payload['anchor_evidence_ids'], [])
        self.assertIn({'type': 'SOURCE_OBJECT_OR_CONTEXT_REVIEW_REQUIRED', 'chunk_id': 'reviewed',
            'evidence_ids': ['missing-warning'], 'rider_resolvable': False}, payload['gaps'])

    def test_retained_skeleton_mutations_fail_closed(self):
        for field, value in (('evidence_ids',['approved']), ('parent_section_id','wrong'), ('id','unknown')):
            with self.subTest(field=field):
                bundle = deepcopy(self.bundle); bundle['retained_gap_hits'][0][field] = value
                with self.assertRaises(ValidationFailure):self.s.assemble(bundle)

    def test_retained_raw_gap_dictionary_or_content_is_not_trusted(self):
        for extra in ('gaps', 'source_object', 'index_text'):
            with self.subTest(extra=extra):
                bundle = deepcopy(self.bundle); bundle['retained_gap_hits'][0][extra] = 'external'
                with self.assertRaisesRegex(ValidationFailure,'GAP_HIT_INVALID'):self.s.assemble(bundle)

    def test_retained_hits_are_deduplicated_only_after_each_membership_check(self):
        bundle = deepcopy(self.bundle)
        bundle['hits'].append(deepcopy(self.s.chunks['gap']))
        self.assertEqual(len(self.s.assemble(bundle)['gaps']), 1)
        bundle['retained_gap_hits'][0]['evidence_ids'] = ['approved']
        with self.assertRaisesRegex(ValidationFailure,'MEMBERSHIP_CHANGED'):self.s.assemble(bundle)

    def test_retained_gap_bound_fails_without_truncation(self):
        bundle = deepcopy(self.bundle)
        bundle['retained_gap_hits'] *= 26
        with self.assertRaisesRegex(ValidationFailure,'BOUND_NO_TRUNCATION'):self.s.assemble(bundle)

    def test_retained_immutable_chunk_mutation_is_rejected(self):
        self.s.chunks['gap']['evidence_ids'] = ['approved']
        with self.assertRaisesRegex(ValidationFailure,'INDEX_CHUNK_CHANGED'):self.s.assemble(self.bundle)


if __name__ == '__main__': unittest.main()
