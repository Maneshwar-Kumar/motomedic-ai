"""Open-Q&A reviewed anchors with exact bounded source dependency closure.

Absent review remains a maintainer gap. A chunk is a search container, so an
unreviewed sibling never discards a independently complete reviewed anchor whose
exact approved dependency closure excludes that sibling. The additional four
object fuel scope is independently original-page reviewed and separately pinned;
this loader grants no new review, parent-body or catalogue authority.
"""
from copy import deepcopy
from constrained_generator import ValidationFailure
from evidence_registry import content_hash
from cloud.grounded_generation.source_authority import SourceAuthority as FrozenAuthority
from cloud.grounded_generation.serving_context import project, VERSION as PROJECTION_VERSION

VERSION = 'open-reviewed-anchor-authority-v2'
REFINEMENT_PATH = 'reports/build/20261012/source_context_refinement_v2/proposal_v3.json'
REFINEMENT_SHA = '405269fa7d31274a1e5c6260bbee3e762c8cf2898a5401a4f71e97e155afa1f0'
REFINEMENT_REVIEW_PATH = 'reports/build/20261012/source_context_refinement_v2/independent_review_v3.json'
REFINEMENT_REVIEW_SHA = 'ebfb2c39cea8d7d980a32325bc1db85448208d0e3d9dcd242eb4043f991d179d'


class SourceAuthority(FrozenAuthority):
    def __init__(self, base, index_dir):
        super().__init__(base, index_dir)
        frozen_lock = self.lock
        proposal = self._package(REFINEMENT_PATH, REFINEMENT_SHA)
        review = self._package(REFINEMENT_REVIEW_PATH, REFINEMENT_REVIEW_SHA)
        if (review.get('proposal_sha256') != REFINEMENT_SHA
                or review.get('decision') != 'APPROVED_EXACT_SOURCE_OBJECT_CONTEXT_ONLY'
                or review.get('authority') != 'AGENT_SOURCE_CONTEXT_REVIEW'
                or review.get('manual_checksum') != self.checksum or review.get('index_id') != self.index_id
                or proposal.get('manual_checksum') != self.checksum or proposal.get('index_id') != self.index_id
                or proposal.get('questions_or_expected_answers_included') is not False
                or review.get('parent_text_authorized') is not False
                or review.get('new_authored_action_authority') is not False
                or set(review.get('approved_evidence_ids', ())) != set(proposal.get('bindings', {}))):
            raise ValidationFailure('SOURCE_CONTEXT_REFINEMENT_IDENTITY')
        for eid, row in proposal['bindings'].items():
            indexed = self.index_evidence.get(eid)
            if (not indexed or content_hash(indexed) != row['indexed_object_sha256']
                    or row['evidence_id'] != eid or row.get('parent_text_authorized') is not False
                    or set(row['required_evidence_ids']) != set(review['approved_evidence_ids'])):
                raise ValidationFailure('SOURCE_CONTEXT_REFINEMENT_OBJECT_CHANGED')
            source = row.get('source_object')
            if source is not None:
                if content_hash(source) != row['source_object_sha256'] or source != self.sources.get(eid):
                    raise ValidationFailure('SOURCE_CONTEXT_REFINEMENT_SOURCE_CHANGED')
            else:
                source = review.get('new_source_objects', {}).get(eid)
                if (not source or source.get('authority') != 'OEM_MANUAL_AGENT_COMPONENT_CONTEXT_V2'
                        or source.get('raw_object_sha256') != row['raw_object_sha256']
                        or source.get('exact_text') != indexed['raw_object'].get('text')):
                    raise ValidationFailure('SOURCE_CONTEXT_REFINEMENT_SOURCE_CHANGED')
            self._bind(eid, source, row['raw_object_sha256'], row['provenance_sha256'],
                {'section_path': deepcopy(row['section_path']),
                 'context_authority': 'APPROVED_EXACT_COMPONENT_CONTEXT_NO_PARENT_TEXT',
                 'component_review_sha256': REFINEMENT_REVIEW_SHA})
            self.complete_context_ids.add(eid)
            self.links[eid] = set(row['required_evidence_ids'])
            self.displays[eid] = {claim['claim_id']: deepcopy(claim)
                                   for claim in proposal['required_display']}
            self.context_proofs[eid] = {REFINEMENT_REVIEW_SHA}
        self._metadata_hash = content_hash(self.metadata())
        self.lock = content_hash({'version': VERSION, 'projection': PROJECTION_VERSION,
            'frozen_source_authority_lock': frozen_lock,
            'scoped_refinement_sha256': REFINEMENT_SHA,
            'scoped_refinement_review_sha256': REFINEMENT_REVIEW_SHA,
            'metadata': self._metadata_hash})
        self.check()

    def _payload(self, ids, anchors, gaps):
        payload = super()._payload(ids, anchors, gaps)
        for eid, row in payload['evidence'].items():
            row['source_object'] = project(self.evidence[eid]['raw_object'])
            # Original bounds/provenance remain in the immutable server registry.
            # Provider needs authoritative page identities, not every bbox copy.
            row['provenance'] = [{k: deepcopy(v) for k, v in prov.items()
                                  if k not in ('bbox', 'charspan')}
                                 for prov in self.evidence[eid]['provenance']]
            context = row['reviewed_source_context']
            context.pop('parent_membership', None)
            context.pop('immutable_chunk_ids', None)
        payload.pop('payload_sha256')
        payload['projection_version'] = PROJECTION_VERSION
        payload['payload_sha256'] = content_hash(payload)
        return payload

    def assemble(self, bundle):
        self.check()
        if (bundle.get('index_id') != self.index_id or
                bundle.get('manual_checksum', bundle.get('source_sha256')) != self.checksum):
            raise ValidationFailure('SOURCE_AUTHORITY_RETRIEVAL_IDENTITY')
        admitted, anchors, gaps = set(), set(), []
        for hit in bundle.get('hits', ()):
            chunk = self.chunks.get(hit.get('id'))
            if chunk is None:
                raise ValidationFailure('SOURCE_AUTHORITY_UNKNOWN_CHUNK')
            if content_hash(chunk) != self._chunk_hashes[chunk['id']]:
                raise ValidationFailure('SOURCE_AUTHORITY_INDEX_CHUNK_CHANGED')
            if (hit.get('evidence_ids') != chunk['evidence_ids'] or
                    hit.get('parent_section_id') != chunk['parent_section_id']):
                raise ValidationFailure('SOURCE_AUTHORITY_RETRIEVAL_MEMBERSHIP_CHANGED')
            direct = set(chunk['evidence_ids'])
            for eid in sorted(direct):
                if eid not in self.complete_context_ids:
                    gaps.append({'type': 'SOURCE_CONTEXT_COMPLETENESS_REVIEW_REQUIRED',
                                 'chunk_id': chunk['id'], 'evidence_ids': [eid],
                                 'rider_resolvable': False})
                    continue
                closure = self._closure({eid})
                missing = sorted(e for e in closure if not self.evidence_ready(e))
                if missing:
                    gaps.append({'type': 'SOURCE_OBJECT_OR_CONTEXT_REVIEW_REQUIRED',
                                 'chunk_id': chunk['id'], 'evidence_ids': missing,
                                 'rider_resolvable': False})
                    continue
                # Empty links are admissible ONLY because complete_context_ids
                # has exact reviewed context/no-dependency authority for this ID.
                admitted.update(closure)
                anchors.add(eid)
        for eid in bundle.get('retained_approved_evidence_ids', ()):
            if eid not in self.complete_context_ids or not self.evidence_ready(eid):
                raise ValidationFailure('RETAINED_SOURCE_CONTEXT_REVIEW_REQUIRED')
            closure = self._closure({eid})
            if any(not self.evidence_ready(e) for e in closure):
                raise ValidationFailure('RETAINED_SOURCE_CONTEXT_REVIEW_REQUIRED')
            admitted.update(closure)
        if len(admitted) > 256:
            raise ValidationFailure('SOURCE_AUTHORITY_DEPENDENCY_BOUND_NO_TRUNCATION')
        return self._payload(admitted, anchors, gaps)

    def scheduling_context(self, bundle):
        payload = self.assemble(bundle)
        return {'payload': payload, 'required_evidence_ids': payload['required_evidence_ids'],
                'reviewed_anchor_ids': payload['anchor_evidence_ids'],
                'source_gaps': payload['gaps'],
                'dependency_review_status': 'APPROVED' if payload['evidence'] else 'MISSING',
                'coverage_established': bool(payload['evidence']),
                'source_review_required': bool(payload['gaps'])}
