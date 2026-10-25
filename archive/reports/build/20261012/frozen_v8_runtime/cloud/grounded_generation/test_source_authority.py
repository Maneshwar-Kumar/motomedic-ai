"""Meaningful source-admission regressions independent of rider/catalogue wording."""
from copy import deepcopy
from pathlib import Path
import unittest
from approved_registry import ApprovedEvidenceRegistry
from constrained_generator import ValidationFailure
from cloud.grounded_generation.source_authority import SourceAuthority

ROOT = Path(__file__).resolve().parents[2]
INDEX = ROOT / 'build/index-bge-final'

class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = ApprovedEvidenceRegistry.load(ROOT, INDEX)
        cls.original = SourceAuthority(cls.base, INDEX)

    def setUp(self):
        # Keep startup source review and immutable file verification real, while
        # isolating mutations without repeated full approval-consumer loading.
        self.s = deepcopy(self.original)

    def bundle(self, chunk):
        return {'index_id': self.s.index_id, 'manual_checksum': self.s.checksum,
                'query': 'A previously unseen rider phrase is irrelevant to authority',
                'hits': [deepcopy(chunk)]}

    def complete_chunk(self):
        for chunk in self.s.chunks.values():
            payload = self.s.assemble(self.bundle(chunk))
            if payload['required_evidence_ids'] and not payload['gaps']:
                return chunk
        self.fail('No reviewed immutable chunk is admitted')

    def test_query_wording_and_step_ready_are_not_factual_authority(self):
        chunk = self.complete_chunk()
        self.s.base.step_ready = lambda *_: False
        a = self.s.assemble(self.bundle(chunk))
        b = self.bundle(chunk); b['query'] = 'Entirely new natural wording'
        self.assertEqual(a, self.s.assemble(b))
        self.assertFalse(a['action_authority'])

    def test_constructor_rejects_changed_dependency_or_mandatory_display(self):
        base = deepcopy(self.base)
        sid = next(k for k, dep in base.candidate['dependencies'].items()
                   if dep.get('categories', {}).get('warnings'))
        base.candidate['dependencies'][sid]['categories']['warnings'] = []
        with self.assertRaisesRegex(ValidationFailure, 'DEPENDENCY_CHANGED'):
            SourceAuthority(base, INDEX)
        base = deepcopy(self.base)
        base.candidate['dependencies'][sid]['review_status'] = 'UNREVIEWED'
        with self.assertRaisesRegex(ValidationFailure, 'DEPENDENCY_CHANGED'):
            SourceAuthority(base, INDEX)
        base = deepcopy(self.base)
        base.candidate['dependencies'].pop(sid)
        with self.assertRaisesRegex(ValidationFailure, 'DEPENDENCY_INVENTORY_CHANGED'):
            SourceAuthority(base, INDEX)
        base = deepcopy(self.base)
        claim = next(c for step in base.candidate['steps'].values() for c in step['claims']
                     if c['response_role'] == 'WARNING' and c.get('evidence_ids'))
        claim['text'] = 'unreviewed replacement warning'
        with self.assertRaisesRegex(ValidationFailure, 'MANDATORY_DISPLAY_CHANGED'):
            SourceAuthority(base, INDEX)

    def test_authored_fact_mutation_does_not_change_source_authority(self):
        base = deepcopy(self.base)
        claim = next(c for step in base.candidate['steps'].values() for c in step['claims']
                     if c['response_role'] == 'FACT')
        claim['text'] = 'This authored answer is not source authority'
        self.assertEqual(SourceAuthority(base, INDEX).lock, self.original.lock)

    def test_noncore_source_members_receive_reviewed_full_context(self):
        noncore = set()
        for dep in self.s.base.candidate['dependencies'].values():
            if dep.get('review_status') == 'APPROVED' and dep.get('scope_review_complete'):
                members = set(dep['required_evidence_ids']) & set(self.s.sources)
                noncore.update(members - set(dep['action_evidence_ids']))
        self.assertTrue(noncore)
        self.assertLessEqual(noncore, self.s.complete_context_ids)

    def test_no_synthetic_catalogue_or_eight_scope_overlay(self):
        self.assertFalse(hasattr(self.s, 'steps'))
        self.assertTrue(self.s.sources)
        self.assertTrue(all(not key.startswith('readonly_') for key in self.s.sources))
        self.assertEqual(self.s.base.lock, self.base.lock)

    def test_unknown_review_is_explicit_non_rider_gap(self):
        chunk = next(c for c in self.s.chunks.values() if any(e not in self.s.bound for e in c['evidence_ids']))
        payload = self.s.assemble(self.bundle(chunk))
        self.assertFalse(payload['required_evidence_ids'])
        self.assertTrue(payload['gaps'])
        self.assertTrue(all(g['rider_resolvable'] is False for g in payload['gaps']))

    def test_raw_provenance_corruption_raises_not_abstention(self):
        chunk = self.complete_chunk()
        payload = self.s.assemble(self.bundle(chunk))
        eid = payload['required_evidence_ids'][0]
        self.s.evidence[eid]['raw_object']['text'] = 'unreviewed repair'
        with self.assertRaisesRegex(ValidationFailure, 'OBJECT_CHANGED'):
            self.s.validate(payload)

    def test_constructor_rejects_outer_object_corruption_before_snapshot(self):
        for key, changed in [('type', 'picture'), ('index_membership', False)]:
            base = deepcopy(self.base)
            eid = next(e for e in self.original.bound if base.evidence[e].get('type') == 'text')
            base.evidence[eid][key] = changed
            with self.assertRaisesRegex(ValidationFailure, 'OBJECT_IDENTITY_CHANGED'):
                SourceAuthority(base, INDEX)

    def test_outer_object_identity_type_and_flags_corruption_raise(self):
        chunk = self.complete_chunk()
        payload = self.s.assemble(self.bundle(chunk))
        eid = payload['required_evidence_ids'][0]
        original = deepcopy(self.s.evidence[eid])
        for key, changed in [('id', 'invented'), ('type', 'picture'), ('index_membership', False)]:
            self.s.evidence[eid] = deepcopy(original)
            self.s.evidence[eid][key] = changed
            with self.assertRaisesRegex(ValidationFailure, 'OBJECT_IDENTITY_CHANGED'):
                self.s.validate(payload)

    def test_changed_membership_is_integrity_failure(self):
        chunk = self.complete_chunk(); bundle = self.bundle(chunk)
        bundle['hits'][0]['evidence_ids'].append('invented')
        with self.assertRaisesRegex(ValidationFailure, 'MEMBERSHIP_CHANGED'):
            self.s.assemble(bundle)

    def test_output_selection_cannot_drop_mandatory_warning_closure(self):
        chunk = self.complete_chunk(); payload = self.s.assemble(self.bundle(chunk))
        eid = payload['anchor_evidence_ids'][0]
        selected = self.s.select(payload, [eid])
        self.assertLessEqual(self.s._closure({eid}), set(selected['required_evidence_ids']))
        self.assertTrue(self.s.validate(selected))
        with self.assertRaisesRegex(ValidationFailure, 'INVALID_CLAIM_CITATION'):
            self.s.select(payload, ['invented'])

    def test_payload_and_source_authority_mutation_raise(self):
        chunk = self.complete_chunk(); payload = self.s.assemble(self.bundle(chunk))
        payload['required_display'].append({'text': 'replacement instruction'})
        with self.assertRaisesRegex(ValidationFailure, 'ADMITTED_CONTEXT_CHANGED'):
            self.s.validate(payload)
        self.s.contexts[next(iter(self.s.contexts))]['section_path'] = ['invented']
        with self.assertRaisesRegex(ValidationFailure, 'METADATA_CHANGED'):
            self.s.assemble(self.bundle(chunk))

    def test_full_raw_table_and_server_owned_pages_survive(self):
        chunk = next(c for c in self.s.chunks.values() if any(
            self.s.evidence.get(e, {}).get('type') == 'table' and self.s.evidence_ready(e)
            for e in c['evidence_ids']) and self.s.assemble(self.bundle(c))['required_evidence_ids'])
        payload = self.s.assemble(self.bundle(chunk))
        tables = [v for v in payload['evidence'].values() if v['type'] == 'table']
        self.assertTrue(tables)
        self.assertTrue(all(v['source_object']['content']['data']['table_cells'] for v in tables))
        self.assertTrue(all(type(c['pdf_page']) is int for c in payload['citation_mapping']))

if __name__ == '__main__':
    unittest.main()
