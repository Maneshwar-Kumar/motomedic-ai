"""Exact coordinator-approved v3 scope projected into the shared evidence contract.

This overlay does not rewrite signed artifacts, grant provider/deployment authority,
create human signoff, alter index bytes, or infer successor edges. Only approval
status/presentation metadata are projected; technical content stays exact-bound.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path

from evidence_registry import EvidenceRegistry, content_hash, read_json
from human_review.agent_release_161.approval_consumer import (
    ApprovalConsumer, MANUAL_SHA, RELEASE_SHA, object_hash, require)

MANIFEST = 'human_review/agent_release_161/coordinator/release_manifest_v3.json'
ADAPTER_VERSION = 'coordinator-v3-registry-overlay-v1'
# Immutable hosted snapshot; prevents a rewritten manifest retaining the same index ID.
INDEX_EVIDENCE_SHA = '792408e533d68f99b0787056e02c4a9f2edf6ea1e06b4b0591b743753a6bc2c8'
QUALITY_HOLDS = frozenset(('GEN043', 'GEN053', 'GEN056', 'EXP030', 'EXP044',
                           'EXP049', 'a_switches_on', 'a_refuel', 'a_reconnect', 'a_cool_engine'))


class ApprovedEvidenceRegistry(EvidenceRegistry):
    coordinator_scoped_authority = True
    terminal_initial_scope_only = True

    @classmethod
    def load(cls, project_root, index_dir, source_path=None):
        root, index = Path(project_root).resolve(), Path(index_dir).resolve()
        consumer = ApprovalConsumer(root, MANIFEST)
        source = read_json(root / 'source_manifest.json')
        if source_path is not None:
            require(read_json(source_path) == source, 'Source metadata differs from approved source')
        manifest = read_json(index / 'manifest.json')
        require(manifest['index_id'] == consumer.registry['index_id'], 'Approval/index mismatch')
        require(manifest['source_sha256'].lower() == MANUAL_SHA, 'Approval/manual mismatch')
        require(manifest['file_checksums']['evidence.jsonl'] == INDEX_EVIDENCE_SHA,
                'Immutable evidence manifest binding changed')
        raw = (index / 'evidence.jsonl').read_bytes()
        require(hashlib.sha256(raw).hexdigest() == manifest['file_checksums']['evidence.jsonl'],
                'Immutable evidence index changed')
        import json
        evidence = {}
        for line in raw.decode('utf-8').splitlines():
            if line:
                obj = json.loads(line)
                require(obj['id'] not in evidence, 'Duplicate immutable evidence identity')
                evidence[obj['id']] = obj
        return cls(consumer, evidence, source)

    def __init__(self, consumer, evidence, source):
        self._consumer = consumer
        self.approved_sources = deepcopy(consumer.sources)
        self.candidate = deepcopy(consumer.registry)
        self.source = deepcopy(source)
        self.evidence = deepcopy(evidence)
        self.reviews = {'authority': 'OWNER_DELEGATED_AGENT_COORDINATOR',
                        'release_manifest_sha256': RELEASE_SHA, 'decisions': []}
        self.checksum = self.candidate['manual_checksum']
        self.index_id = self.candidate['index_id']
        self.version = ADAPTER_VERSION
        self._owners = {}
        self._bound = {}
        self._raw_hashes = {}
        for rid, decision in consumer.records.items():
            if not consumer.scope_ready(rid, 'INITIAL_ROUTE'):
                continue
            b = decision['artifact_bindings']
            self._bound[rid] = deepcopy(b)
            for kind, key in (('step', 'step_id'), ('dependency', 'dependency_id'),
                              ('procedure', 'procedure_id')):
                if b.get(key):
                    self._owners.setdefault((kind, b[key]), set()).add(rid)
            for key in b['rule_sha256s']:
                self._owners.setdefault(('rule', key), set()).add(rid)
            for key, sha in b['source_sha256s'].items():
                self._owners.setdefault(('evidence', key), set()).add(rid)
                require(key not in self._raw_hashes or self._raw_hashes[key] == sha,
                        'Conflicting source binding')
                self._raw_hashes[key] = sha
        self._project_scopes()
        self._snapshots = {}
        for kind, key in self._owners:
            if kind != 'evidence' or key in self.evidence:
                self._snapshots[(kind, key)] = content_hash(self.target(kind, key))
        self._source_hash = content_hash(self.source)
        self._metadata_hash = content_hash({k: v for k, v in self.candidate.items()
                                           if k not in ('steps', 'rules', 'dependencies', 'procedures')})
        self.validate()
        self.refresh_lock()

    def _project_scopes(self):
        for (kind, key), owners in self._owners.items():
            if kind == 'evidence':
                source = self.approved_sources[key]
                if source.get('authority') not in ('OEM_MANUAL', 'OEM_ORIGINAL_PDF_CANDIDATE'):
                    continue  # Policy references are never presented as manual citations.
                require(source.get('manual_sha256', '').lower() == self.checksum,
                        'Bound source manual differs')
                if key in self.evidence:
                    obj = self.evidence[key]
                    require(obj.get('source_sha256', '').lower() == self.checksum,
                            'Indexed source checksum differs')
                    raw_object = obj.get('raw_object', {})
                    text = raw_object.get('text', '')
                    if source.get('object_type') == 'table':
                        import json
                        cells = raw_object.get('data', {}).get('table_cells', [])
                        require(cells == source.get('table_cells'), 'Indexed table cells changed')
                        encodings = (json.dumps(cells, ensure_ascii=False, sort_keys=True),
                                     '\n'.join(f"r{c['start_row_offset_idx']}c{c['start_col_offset_idx']}: {c['text']}" for c in cells))
                        require(source['exact_text'] in encodings, 'Indexed table text changed')
                    else:
                        require(text == source['exact_text'],
                                'Indexed text differs from independently checked source')
                    require(obj.get('provenance') == source.get('provenance'),
                            'Indexed provenance differs from approved source')
                    require(obj.get('type') == source.get('object_type'),
                            'Indexed evidence type differs from approved source')
                else:
                    require(key.startswith('originalpdf_') and source.get('index_membership') is False,
                            'Missing approved indexed source')
                    require(type(source.get('pdf_page')) is int, 'Supplement page missing')
                    self.evidence[key] = {
                        'id': key, 'type': 'original_pdf_supplement',
                        'source_sha256': self.checksum,
                        'index_membership': False, 'private_supplement': True,
                        'provenance': [{'page_no': source['pdf_page'], 'bbox': source.get('bbox')}],
                        'raw_object': {'text': source['exact_text']},
                        'approval_authority': 'OWNER_DELEGATED_AGENT_COORDINATOR'}
                self.evidence[key]['review_status'] = 'APPROVED'
                self.evidence[key]['extraction_check_status'] = 'PASSED'
            else:
                obj = self.target(kind, key)
                obj['review_status'] = 'APPROVED'
                if kind == 'step':
                    obj['authoring_blockers'] = []
                    for claim in obj.get('claims', []):
                        # Exact approved authored paraphrase; no extra wording added.
                        claim['presentation_mode'] = 'REVIEWED_PARAPHRASE'
                elif kind == 'dependency':
                    obj['scope_review_complete'] = True
                elif kind == 'procedure':
                    require(all(self._consumer.records[r].get('procedure_boundary_approved') is True
                                for r in owners), 'Unapproved procedure boundary')
                    obj['boundaries_checked'] = True

    def _unchanged(self, kind, key):
        try:
            return content_hash(self.target(kind, key)) == self._snapshots[(kind, key)]
        except (KeyError, TypeError, ValueError):
            return False

    def _scope_intact(self, rid):
        try:
            b = self._bound[rid]
            if content_hash(self.source) != self._source_hash:
                return False
            metadata = {k: v for k, v in self.candidate.items()
                        if k not in ('steps', 'rules', 'dependencies', 'procedures')}
            if content_hash(metadata) != self._metadata_hash:
                return False
            for kind, field in (('step', 'step_id'), ('dependency', 'dependency_id'),
                                ('procedure', 'procedure_id')):
                if b.get(field) and not self._unchanged(kind, b[field]):
                    return False
            if any(not self._unchanged('rule', key) for key in b['rule_sha256s']):
                return False
            for key, sha in b['source_sha256s'].items():
                if object_hash(self.approved_sources[key]) != sha:
                    return False
                if self.approved_sources[key].get('authority') in ('OEM_MANUAL', 'OEM_ORIGINAL_PDF_CANDIDATE') and not self._unchanged('evidence', key):
                    return False
            return True
        except (KeyError, TypeError, ValueError):
            return False

    def approved(self, kind, target_id):
        if kind == 'source':
            return target_id == self.source.get('manual_id') and self.source_ready()
        owners = self._owners.get((kind, target_id), ())
        return bool(owners and all(self._scope_intact(rid) for rid in owners) and
                    (kind != 'evidence' or target_id in self.evidence))

    def source_ready(self):
        return (content_hash(self.source) == self._source_hash and
                self.source.get('sha256', '').lower() == self.checksum and
                self.checksum == MANUAL_SHA and
                self.index_id == 'index_a3282c4d98cf54595e4ba168' and
                self.source.get('applicability_policy', {}).get('version') == 'owner-himalayan-bs6-v1')

    def step_ready(self, sid):
        try:
            rid = self.candidate['steps'][sid]['canonical_record_id']
            if rid in QUALITY_HOLDS:
                return False
            dep = self.candidate['dependencies'][sid]
            if dep.get('categories', {}).get('figures'):
                return False  # Shared text verifier cannot validate these images.
            return super().step_ready(sid)
        except (KeyError, TypeError, ValueError):
            return False

    def reviewed_evidence(self):
        """One integrity pass per bound scope for this overlay construction only.

        The cache is local to this call and discarded before returning; subsequent
        controller/provider gates recheck mutable objects against exact snapshots.
        """
        intact = {rid: self._scope_intact(rid) for rid in self._bound}
        result = {}
        for eid, obj in self.evidence.items():
            owners = self._owners.get(('evidence', eid), ())
            ready = bool(owners and all(intact[rid] for rid in owners) and
                         self._unchanged('evidence', eid) and
                         obj.get('source_sha256', '').lower() == self.checksum.lower() and
                         obj.get('provenance'))
            result[eid] = {**obj, 'review_status': 'APPROVED' if ready else 'UNREVIEWED',
                           'extraction_check_status': 'PASSED' if ready else 'PENDING'}
        return result

    def verified_safety_claims(self, sid):
        """Finite approved warning text only; never a general generator bypass.

        Safety precedence must retain exact reviewed warnings during outages.
        This grants no action, successor or semantic-provider authority.
        """
        try:
            step = self.step(sid)
            if step.kind != 'SAFETY_STOP' or not self.source_ready() or not self.step_ready(sid):
                return False
            required = set(step.required_evidence_ids)
            if not step.claims or any(c.get('response_role') not in ('FACT', 'WARNING', 'PREREQUISITE')
                                      or c.get('presentation_mode') != 'REVIEWED_PARAPHRASE'
                                      or c.get('verbatim_warning')
                                      or not c.get('evidence_ids')
                                      or not set(c['evidence_ids']) <= required for c in step.claims):
                return False
            categories = self.candidate['dependencies'][sid]['categories']
            for category, role in (('warnings', 'WARNING'), ('prerequisites', 'PREREQUISITE')):
                covered = {eid for c in step.claims if c['response_role'] == role
                           for eid in c['evidence_ids']}
                if not set(categories.get(category, [])) <= covered:
                    return False
            return True
        except (KeyError, TypeError, ValueError):
            return False

    def validate(self):
        require(self.source_ready(), 'Approved source identity changed')
        for sid, step in self.candidate['steps'].items():
            require(self.approved('step', sid), 'Changed or unbound approved step')
            require(step['step_id'] == sid and step['manual_checksum'] == self.checksum,
                    'Invalid step identity')
            require(step['kind'] in ('ACTION', 'LOOKUP', 'SAFETY_STOP'), 'Invalid step kind')
            require(not step.get('next_step_ids') and not step.get('next_step_evidence_ids'),
                    'Initial authority has no successor edges')
            require(step['unresolved_route'] == 'ESCALATE_NO_APPROVED_NEXT_STEP',
                    'Unexpected approved continuation policy')
            dep = self.candidate['dependencies'][sid]
            require(dep['step_id'] == sid and dep['index_id'] == self.index_id and
                    dep['manual_checksum'] == self.checksum and
                    dep['version'] == step['dependency_manifest_version'], 'Dependency identity mismatch')
            required = set(step['required_evidence_ids'])
            require(required and len(required) <= 256 and required == set(dep['required_evidence_ids']),
                    'Missing or excessive mandatory evidence')
            require(set(step['action_evidence_ids']) == set(dep['action_evidence_ids']) and
                    set(step['action_evidence_ids']) <= required, 'Action dependency mismatch')
            require(required <= self.evidence.keys(), 'Missing mandatory evidence object')
            require(all(set(ids) <= required for ids in dep['categories'].values()),
                    'Dependency category outside mandatory closure')
            require(all(self.evidence_ready(key) for key in required), 'Unapproved evidence dependency')
        require(all(self.approved('rule', key) for key in self.candidate['rules']), 'Unbound rule')
        return True

    def refresh_lock(self):
        super().refresh_lock()
        self.lock = content_hash([self.lock, RELEASE_SHA, ADAPTER_VERSION,
                                  hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                                  self.approved_sources, sorted(QUALITY_HOLDS)])
