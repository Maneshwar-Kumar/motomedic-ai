"""Candidate v5 open-Q&A source authority: v4 plus the scoped v2 structural review.

CANDIDATE ONLY. Kept outside the bound serving tree (cloud/, rider_ui/) so the
frozen v10.14 serving inventory is unchanged; production still constructs v4.
Adopting it requires a new serving version. Import with the project root on sys.path. The v2 package admits additional exact
immutable manual objects together with their whole on-page component, links to
already-approved context (conditions, warnings) and mandatory reviewed displays.
It grants no parent-text, action, diagnosis or OEM-sequence authority. Excluded
children (figure-label artifacts) stay gaps. A missing, changed or unapproved
package fails closed; it never widens silently.
"""
from copy import deepcopy
import json
from constrained_generator import ValidationFailure
from evidence_registry import content_hash
from cloud.grounded_generation.serving_source_authority import SourceAuthority as V4Authority

VERSION = 'open-reviewed-anchor-authority-v5-candidate'
PROPOSAL_PATH = 'reports/grounded_generation/structural_review_v2/proposal.json'
PROPOSAL_SHA = '38dc070964b4e7027ee616db2b387776f338809b36116afda5e79a91a7a1cc3d'
REVIEW_PATH = 'reports/grounded_generation/structural_review_v2/independent_review.json'
REVIEW_SHA = 'd7dfdc6e500788e863cf919b5c86be231a5faeb15fb17285dec0473a27bc58c8'
SOURCE_AUTHORITY = 'OEM_MANUAL_AGENT_READ_ONLY_V2'
DISPLAY_ROLES = {'WARNING', 'FACT', 'LIMITATION'}
FALSE_FLAGS = ('parent_text_authorized', 'action_authority', 'diagnosis_authority', 'oem_sequence_authority',
               'questions_or_expected_answers_included', 'human_signoff', 'existing_approvals_changed')


class SourceAuthority(V4Authority):
    def __init__(self, base, index_dir, *, proposal_sha=PROPOSAL_SHA, review_sha=REVIEW_SHA):
        super().__init__(base, index_dir)
        if not proposal_sha or not review_sha:
            raise ValidationFailure('STRUCTURAL_V2_REVIEW_NOT_APPROVED')
        v4_lock = self.lock
        proposal = self._package(PROPOSAL_PATH, proposal_sha)
        review = self._package(REVIEW_PATH, review_sha)
        files = json.loads((self.index / 'manifest.json').read_text(encoding='utf-8'))['file_checksums']
        if (proposal.get('manual_checksum') != self.checksum or proposal.get('index_id') != self.index_id
                or proposal.get('immutable_parents_sha256') != files['parents.jsonl']
                or proposal.get('immutable_evidence_sha256') != files['evidence.jsonl']
                or any(proposal.get(flag) is not False for flag in FALSE_FLAGS)):
            raise ValidationFailure('STRUCTURAL_V2_PROPOSAL_IDENTITY')
        if (review.get('proposal_sha256') != proposal_sha
                or review.get('decision') != 'APPROVED_EXACT_SOURCE_OBJECT_CONTEXT_ONLY'
                or review.get('authority') != 'OWNER_DELEGATED_INDEPENDENT_AGENT_SOURCE_STRUCTURE'
                or review.get('manual_checksum') != self.checksum or review.get('index_id') != self.index_id
                or review.get('human_signoff') is not False or review.get('open_findings') != []
                or set(review.get('approved_components', ())) != set(proposal['components'])):
            raise ValidationFailure('STRUCTURAL_V2_REVIEW_IDENTITY')
        for eid, row in proposal['source_objects'].items():
            source, context = row['source_object'], row['context']
            if (content_hash(source) != row['source_object_sha256'] or content_hash(context) != row['context_sha256']
                    or source.get('context_sha256') != row['context_sha256'] or source.get('evidence_id') != eid
                    or source.get('authority') != SOURCE_AUTHORITY or source.get('requires_visual_verification') is not False
                    or context.get('parent_text_authorized') is not False):
                raise ValidationFailure('STRUCTURAL_V2_SOURCE_BINDING')
            if eid in self.sources:
                # An earlier exact approval stays authoritative; v2 never rebinds it.
                if self.bound[eid][0] != row['raw_object_sha256']:
                    raise ValidationFailure('STRUCTURAL_V2_CONFLICTING_BINDING')
                continue
            self._bind(eid, source, row['raw_object_sha256'], row['provenance_sha256'], context)
        approved_by_component = {}
        for pid, row in proposal['parents'].items():
            parent = self.parents.get(pid)
            approved, excluded = set(row['approved_evidence_ids']), set(row['excluded_evidence_ids'])
            if (parent is None or content_hash(parent) != row['parent_object_sha256']
                    or row.get('review_status') != 'APPROVED_EXACT_CHILD_STRUCTURE_V2'
                    or row.get('parent_text_authorized') is not False or approved & excluded
                    or approved | excluded != set(parent['evidence_ids'])
                    or any(not isinstance(reason, str) or not reason for reason in row['excluded_evidence_ids'].values())
                    or pid not in proposal['components'].get(row['component'], {}).get('parent_section_ids', ())):
                raise ValidationFailure('STRUCTURAL_V2_PARENT_MEMBERSHIP')
            approved_by_component.setdefault(row['component'], set()).update(approved)
        parented = {e for p in self.parents.values() for e in p['evidence_ids']}
        for eid, row in proposal.get('unparented', {}).items():
            if (eid in parented or row.get('review_status') != 'APPROVED_EXACT_UNPARENTED_NOTE_CONTEXT_V2'
                    or eid not in proposal['components'].get(row['component'], {}).get('unparented_evidence_ids', ())):
                raise ValidationFailure('STRUCTURAL_V2_UNPARENTED_MEMBERSHIP')
            approved_by_component.setdefault(row['component'], set()).add(eid)
        components = proposal['components']
        for name, component in components.items():
            members = set(component['required_evidence_ids'])
            if members != approved_by_component.get(name) or set(component['excluded_evidence_ids']) & members:
                raise ValidationFailure('STRUCTURAL_V2_COMPONENT_MEMBERSHIP')
            for eid in members:
                if not self.evidence_ready(eid):
                    raise ValidationFailure('STRUCTURAL_V2_MEMBER_NOT_READY')
                self.complete_context_ids.add(eid)
        # Links to other components' members or earlier approvals resolve after all members exist.
        for name, component in components.items():
            members = set(component['required_evidence_ids'])
            external = set(component['external_dependency_evidence_ids'])
            if not external <= self.complete_context_ids or not all(self.evidence_ready(e) for e in external):
                raise ValidationFailure('STRUCTURAL_V2_EXTERNAL_CONTEXT_NOT_APPROVED')
            for claim in component['mandatory_display']:
                if (claim.get('presentation_mode') != 'REVIEWED_PARAPHRASE' or claim.get('response_role') not in DISPLAY_ROLES
                        or not claim.get('text') or not set(claim['evidence_ids']) <= members | external):
                    raise ValidationFailure('STRUCTURAL_V2_DISPLAY_BINDING')
            for eid in members:
                self.links.setdefault(eid, set()).update(members | external)
                self.displays.setdefault(eid, {}).update(
                    {claim['claim_id']: deepcopy(claim) for claim in component['mandatory_display']})
                self.context_proofs.setdefault(eid, set()).add(review_sha)
            if set(component['excluded_evidence_ids']) & self.complete_context_ids:
                raise ValidationFailure('STRUCTURAL_V2_EXCLUDED_OBJECT_ADMITTED')
        for eid, row in proposal['evidence_dependencies'].items():
            targets = set(row['external_dependency_evidence_ids'])
            if (row.get('review_status') != 'APPROVED_SAME_COMPONENT_LIMITATIONS' or row.get('action_authority') is not False
                    or eid not in self.complete_context_ids or not targets <= self.complete_context_ids
                    or not all(self.evidence_ready(t) for t in targets)):
                raise ValidationFailure('STRUCTURAL_V2_DEPENDENCY_BINDING')
            self.links.setdefault(eid, set()).update(targets)
            self.context_proofs.setdefault(eid, set()).add(review_sha)
        self._metadata_hash = content_hash(self.metadata())
        self.lock = content_hash({'version': VERSION, 'v4_lock': v4_lock, 'proposal_sha256': proposal_sha,
                                  'review_sha256': review_sha, 'metadata': self._metadata_hash})
        self.check()
