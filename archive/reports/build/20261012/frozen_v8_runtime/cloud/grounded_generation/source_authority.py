"""Exact source authority and generic source-linked assembly, independent of answers.

Retrieval supplies immutable chunk IDs. Source-content decisions authorize raw
objects, not rider questions, canonical wording or factual answer scopes. Only
registered actions retain controller eligibility. This loader adds no steps and
never imports the retired ReadOnlyRegistry overlay. Integrity errors raise;
ordinary absent review is reported as a non-rider-resolvable gap.
"""
from copy import deepcopy
import hashlib
import json
from pathlib import Path
from constrained_generator import ValidationFailure
from evidence_registry import content_hash
from cloud.grounded_generation.context import project
from cloud.grounded_generation.source_context import BINDING_PATH, BINDING_SHA256

VERSION = 'generic-exact-source-authority-v1'
FRESH_PATH = 'reports/grounded_generation/read_only_scopes_v1/scopes.json'
FRESH_SHA = 'e8763b1a4e1f99f6efca0885eb62f832d0938837e4495a2c0a23ba3e8b988fb4'
STRUCTURAL_PATH = 'reports/grounded_generation/generic_source_v1/structural_review.json'
# Filled only after independent original-page structural review is complete.
STRUCTURAL_SHA = '2fb64c8a642c4ef25494c4baa1f80adc8392de50dcbb3eeb50222da69513d725'
MANUAL_AUTHORITIES = {'OEM_MANUAL', 'OEM_ORIGINAL_PDF_CANDIDATE'}


def _read(path, sha=None):
    try:
        raw = Path(path).read_bytes()
    except OSError:
        raise ValidationFailure('SOURCE_AUTHORITY_PACKAGE_UNAVAILABLE') from None
    got = hashlib.sha256(raw).hexdigest()
    if sha is not None and got != sha:
        raise ValidationFailure('SOURCE_AUTHORITY_PACKAGE_CHANGED')
    return json.loads(raw), got


class SourceAuthority:
    def __init__(self, base, index_dir):
        self.base = base
        self.root = Path(__file__).resolve().parents[2]
        self.index = Path(index_dir)
        self.checksum, self.index_id = base.checksum, base.index_id
        self._source_hash = content_hash(base.source)
        self._files = {}
        manifest, _ = _read(self.index / 'manifest.json')
        if (manifest['index_id'] != self.index_id or
                manifest['source_sha256'].lower() != self.checksum):
            raise ValidationFailure('SOURCE_AUTHORITY_INDEX_IDENTITY')
        self.parents = self._index_lines('parents.jsonl', manifest)
        self.chunks = self._index_lines('chunks.jsonl', manifest)
        self._chunk_hashes = {cid: content_hash(c) for cid, c in self.chunks.items()}
        self.index_evidence = self._index_lines('evidence.jsonl', manifest)
        self.evidence = base.evidence
        self.sources, self.contexts, self.bound, self.links, self.displays = {}, {}, {}, {}, {}
        self.outer_bound = {}
        self.complete_context_ids = set()
        self.context_proofs = {}
        labels = self._package(BINDING_PATH, BINDING_SHA256)
        if (labels['manual_checksum'] != self.checksum or labels['index_id'] != self.index_id or
                labels['release_manifest_sha256'] != base.reviews['release_manifest_sha256']):
            raise ValidationFailure('SOURCE_AUTHORITY_CONTEXT_IDENTITY')
        # Read SOURCE_CONTENT bindings; no step_ready or ownership scope gate.
        exact = {}
        for record in base._consumer.records.values():
            if 'SOURCE_CONTENT' not in record['approved_scopes']:
                continue
            for eid, sha in record['artifact_bindings']['source_sha256s'].items():
                if eid in exact and exact[eid] != sha:
                    raise ValidationFailure('SOURCE_AUTHORITY_CONFLICTING_BINDING')
                exact[eid] = sha
        for eid, sha in exact.items():
            src = base.approved_sources[eid]
            if content_hash(src) != sha:
                raise ValidationFailure('SOURCE_AUTHORITY_SOURCE_CHANGED')
            if src.get('authority') not in MANUAL_AUTHORITIES:
                continue
            ctx = labels['bindings'].get(eid)
            if not ctx or ctx['review_status'] != 'APPROVED_CONTEXT_LABELS':
                continue
            if ctx['source_object_sha256'] != sha:
                raise ValidationFailure('SOURCE_AUTHORITY_CONTEXT_SOURCE_CHANGED')
            self._bind(eid, src, ctx['raw_object_sha256'], ctx['provenance_sha256'],
                       {'section_path': ctx['section_path'],
                        'parent_section_ids': ctx['parent_section_ids'],
                        'context_authority': 'APPROVED_SOURCE_LABELS_NO_ACTION_AUTHORITY'})
        fresh = self._package(FRESH_PATH, FRESH_SHA)
        if (fresh['manual_checksum'] != self.checksum or fresh['index_id'] != self.index_id or
                fresh['immutable_evidence_file_sha256'] != manifest['file_checksums']['evidence.jsonl']):
            raise ValidationFailure('SOURCE_AUTHORITY_FRESH_IDENTITY')
        # Deliberately never consume fresh['scopes'] or synthesize LOOKUP steps.
        for eid, row in fresh['source_objects'].items():
            if (content_hash(row['source_object']) != row['source_object_sha256'] or
                    content_hash(row['context']) != row['context_sha256'] or
                    row['source_object']['authority'] != 'OEM_MANUAL_AGENT_READ_ONLY_V1' or
                    row['context'].get('parent_text_authorized') is not False):
                raise ValidationFailure('SOURCE_AUTHORITY_FRESH_BINDING')
            self._bind(eid, row['source_object'], row['raw_object_sha256'],
                       row['provenance_sha256'], row['context'])
        # Existing independently checked dependency manifests are projected as
        # source-to-source cautions, not answer-scope selection. Full procedural
        # eligibility remains solely in the deterministic controller.
        expected_dependencies = {key for kind, key in base._snapshots if kind == 'dependency'}
        if set(base.candidate['dependencies']) != expected_dependencies:
            raise ValidationFailure('SOURCE_AUTHORITY_DEPENDENCY_INVENTORY_CHANGED')
        for sid, dep in base.candidate['dependencies'].items():
            if content_hash(dep) != base._snapshots.get(('dependency', sid)):
                raise ValidationFailure('SOURCE_AUTHORITY_DEPENDENCY_CHANGED')
            if dep.get('review_status') != 'APPROVED' or not dep.get('scope_review_complete'):
                continue
            # Verify the originally projected dependency, then consume the
            # frozen consumer's source context and mandatory warning records.
            # Mutated authored FACT wording has no factual admission authority.
            original_dep = base._consumer.registry['dependencies'][sid]
            original_step = base._consumer.registry['steps'][sid]
            rid = base.candidate['steps'][sid]['canonical_record_id']
            binding = base._consumer.records[rid]['artifact_bindings']
            if (content_hash(original_dep) != binding['dependency_sha256'] or
                    content_hash(original_step) != binding['step_sha256']):
                raise ValidationFailure('SOURCE_AUTHORITY_FROZEN_CONTEXT_CHANGED')
            mandatory_claims = []
            for claim in original_step['claims']:
                if claim['response_role'] in ('WARNING', 'PREREQUISITE') and claim.get('evidence_ids'):
                    copy = deepcopy(claim)
                    copy['presentation_mode'] = 'REVIEWED_PARAPHRASE'
                    mandatory_claims.append(copy)
            current_mandatory = [claim for claim in base.candidate['steps'][sid]['claims']
                                 if claim['response_role'] in ('WARNING', 'PREREQUISITE') and claim.get('evidence_ids')]
            if current_mandatory != mandatory_claims:
                raise ValidationFailure('SOURCE_AUTHORITY_MANDATORY_DISPLAY_CHANGED')
            categories = original_dep.get('categories', {})
            mandatory = {e for e in dep['required_evidence_ids']
                         if base.approved_sources.get(e, {}).get('authority') in MANUAL_AUTHORITIES}
            directed = set().union(*(set(categories.get(k, ())) for k in ('warnings', 'prerequisites', 'conditions', 'tables')))
            for eid in mandatory:
                if eid in self.sources:
                    self.complete_context_ids.add(eid)
                    self.context_proofs.setdefault(eid, set()).add(content_hash(dep))
                    self.links.setdefault(eid, set()).update(directed)
                    for claim in mandatory_claims:
                        if claim['response_role'] in ('WARNING', 'PREREQUISITE') and claim.get('evidence_ids'):
                            self.displays.setdefault(eid, {})[claim['claim_id']] = deepcopy(claim)
                            self.links[eid].update(claim['evidence_ids'])
        self.structural = {}
        if STRUCTURAL_SHA is not None:
            review = self._package(STRUCTURAL_PATH, STRUCTURAL_SHA)
            if (review['manual_checksum'] != self.checksum or review['index_id'] != self.index_id or
                    review['immutable_parents_sha256'] != manifest['file_checksums']['parents.jsonl'] or
                    review['source_object_review_sha256'] != FRESH_SHA or
                    review.get('decision') != 'APPROVED_EXACT_SOURCE_OBJECT_CONTEXT_ONLY' or
                    review.get('parent_text_authorized') is not False or
                    review.get('action_authority') is not False):
                raise ValidationFailure('SOURCE_AUTHORITY_STRUCTURE_IDENTITY')
            for pid, row in review['parents'].items():
                if row.get('review_status') != 'APPROVED_EXACT_CHILD_STRUCTURE' or row.get('parent_text_authorized') is not False:
                    raise ValidationFailure('SOURCE_AUTHORITY_STRUCTURE_REVIEW_REQUIRED')
                if content_hash(self.parents[pid]) != row['parent_object_sha256']:
                    raise ValidationFailure('SOURCE_AUTHORITY_PARENT_CHANGED')
                if set(row['evidence_ids']) != set(self.parents[pid]['evidence_ids']):
                    raise ValidationFailure('SOURCE_AUTHORITY_PARENT_MEMBERSHIP')
                self.structural[pid] = deepcopy(row)
                for eid in row['evidence_ids']:
                    self.complete_context_ids.add(eid)
                    self.contexts[eid]['section_path'] = deepcopy(row['section_path'])
                    self.links.setdefault(eid, set()).update(row['required_evidence_ids'])
                    self.displays.setdefault(eid, {}).update({c['claim_id']: deepcopy(c) for c in row['mandatory_display']})
            for eid, row in review.get('unparented', {}).items():
                if row.get('review_status') != 'APPROVED_EXACT_UNPARENTED_NOTE_CONTEXT' or row.get('parent_text_authorized') is not False:
                    raise ValidationFailure('SOURCE_AUTHORITY_STRUCTURE_REVIEW_REQUIRED')
                self.complete_context_ids.add(eid)
                self.contexts[eid]['section_path'] = deepcopy(row['section_path'])
                self.links.setdefault(eid, set()).update(row['required_evidence_ids'])
                self.displays.setdefault(eid, {}).update({c['claim_id']: deepcopy(c) for c in row['mandatory_display']})
            for eid, row in review.get('evidence_dependencies', {}).items():
                if row.get('review_status') != 'APPROVED_SAME_COMPONENT_LIMITATIONS' or row.get('action_authority') is not False:
                    raise ValidationFailure('SOURCE_AUTHORITY_STRUCTURE_REVIEW_REQUIRED')
                self.links.setdefault(eid, set()).update(row['external_dependency_evidence_ids'])
        self._metadata_hash = content_hash(self.metadata())
        self.lock = content_hash({'version': VERSION, 'metadata': self._metadata_hash,
                                  'source': self._source_hash, 'files': self._files})
        self.check()

    def _package(self, relative, sha):
        path = self.root / relative
        value, got = _read(path, sha)
        self._files[str(path)] = got
        return value

    def _index_lines(self, filename, manifest):
        path = self.index / filename
        raw = path.read_bytes()
        expected = manifest['file_checksums'][filename]
        if hashlib.sha256(raw).hexdigest() != expected:
            raise ValidationFailure('SOURCE_AUTHORITY_INDEX_CHANGED')
        result = {}
        for line in raw.decode('utf-8').splitlines():
            row = json.loads(line)
            if row['id'] in result:
                raise ValidationFailure('SOURCE_AUTHORITY_DUPLICATE_ID')
            result[row['id']] = row
        return result

    def _bind(self, eid, source, raw_hash, provenance_hash, context):
        obj = self.evidence.get(eid)
        if not obj or obj.get('id') != eid or obj['source_sha256'].lower() != self.checksum:
            raise ValidationFailure('SOURCE_AUTHORITY_OBJECT_IDENTITY')
        indexed = self.index_evidence.get(eid)
        snapshot = self.base._snapshots.get(('evidence', eid))
        if indexed is not None and (obj.get('id') != indexed['id'] or obj.get('type') != indexed['type']):
            raise ValidationFailure('SOURCE_AUTHORITY_OBJECT_IDENTITY_CHANGED')
        if snapshot is not None:
            if content_hash(obj) != snapshot:
                raise ValidationFailure('SOURCE_AUTHORITY_OBJECT_IDENTITY_CHANGED')
        elif indexed is None or content_hash(obj) != content_hash(indexed):
            raise ValidationFailure('SOURCE_AUTHORITY_OBJECT_IDENTITY_CHANGED')
        if content_hash(obj['raw_object']) != raw_hash or content_hash(obj['provenance']) != provenance_hash:
            raise ValidationFailure('SOURCE_AUTHORITY_OBJECT_CHANGED')
        if source['manual_sha256'].lower() != self.checksum or source['index_id'] != self.index_id:
            raise ValidationFailure('SOURCE_AUTHORITY_SOURCE_IDENTITY')
        if not source.get('requires_visual_verification'):
            self.sources[eid] = deepcopy(source)
            self.contexts[eid] = deepcopy(context)
            self.bound[eid] = (raw_hash, provenance_hash, content_hash(source))
            self.outer_bound[eid] = content_hash({k: v for k, v in obj.items()
                                                   if k not in ('raw_object', 'provenance')})

    def metadata(self):
        return {'sources': self.sources, 'contexts': self.contexts, 'bound': self.bound,
                'outer_object_bindings': self.outer_bound,
                'links': {eid: sorted(ids) for eid, ids in self.links.items()},
                'displays': self.displays, 'structure': self.structural,
                'complete_context_ids': sorted(self.complete_context_ids),
                'context_review_proofs': {e: sorted(v) for e, v in self.context_proofs.items()}}

    def check(self):
        # One metadata pass per request boundary, not per evidence-owner scope.
        if content_hash(self.base.source) != self._source_hash:
            raise ValidationFailure('SOURCE_AUTHORITY_SOURCE_METADATA_CHANGED')
        if not self.base.source_ready():
            raise ValidationFailure('SOURCE_AUTHORITY_APPLICABILITY_CHANGED')
        if content_hash(self.metadata()) != self._metadata_hash:
            raise ValidationFailure('SOURCE_AUTHORITY_METADATA_CHANGED')
        for path, sha in self._files.items():
            if hashlib.sha256(Path(path).read_bytes()).hexdigest() != sha:
                raise ValidationFailure('SOURCE_AUTHORITY_PACKAGE_CHANGED')

    def evidence_ready(self, eid):
        if eid not in self.bound:
            return False
        obj = self.evidence.get(eid)
        if not obj:
            raise ValidationFailure('SOURCE_AUTHORITY_OBJECT_MISSING')
        raw, prov, src = self.bound[eid]
        outer = {k: v for k, v in obj.items() if k not in ('raw_object', 'provenance')}
        if content_hash(outer) != self.outer_bound[eid]:
            raise ValidationFailure('SOURCE_AUTHORITY_OBJECT_IDENTITY_CHANGED')
        if (obj['source_sha256'].lower() != self.checksum or
                content_hash(obj['raw_object']) != raw or content_hash(obj['provenance']) != prov or
                content_hash(self.sources[eid]) != src):
            raise ValidationFailure('SOURCE_AUTHORITY_OBJECT_CHANGED')
        return obj.get('type') not in ('picture', 'figure', 'image')

    def context_for(self, eid):
        if not self.evidence_ready(eid):
            raise ValidationFailure('SOURCE_CONTEXT_REVIEW_REQUIRED')
        return {'context_kind': 'OEM_MANUAL_SOURCE_OBJECT', 'evidence_id': eid,
                'original_object_sha256': self.bound[eid][0], **deepcopy(self.contexts[eid])}

    def _closure(self, anchors):
        result = set(anchors)
        pending = list(anchors)
        while pending:
            eid = pending.pop()
            for linked in self.links.get(eid, ()):
                if linked not in result:
                    result.add(linked)
                    pending.append(linked)
        if len(result) > 256:
            raise ValidationFailure('SOURCE_AUTHORITY_DEPENDENCY_BOUND_NO_TRUNCATION')
        return result

    def _payload(self, ids, anchors, gaps):
        evidence, citations, display = {}, [], {}
        for eid in sorted(ids):
            if not self.evidence_ready(eid):
                raise ValidationFailure('SOURCE_REVIEW_REQUIRED')
            obj = self.evidence[eid]
            evidence[eid] = {'type': obj['type'], 'source_object': project(obj['raw_object']),
                             'reviewed_source_context': self.context_for(eid),
                             'provenance': deepcopy(obj['provenance'])}
            for prov in obj['provenance']:
                page = prov.get('page_no', prov.get('pdf_page'))
                if type(page) is not int or not 1 <= page <= self.base.source['pdf_pages']:
                    raise ValidationFailure('INVALID_SOURCE_PAGE')
                ref = {'evidence_id': eid, 'pdf_page': page}
                if ref not in citations:
                    citations.append(ref)
            for cid, claim in self.displays.get(eid, {}).items():
                if not set(claim['evidence_ids']) <= ids:
                    raise ValidationFailure('MANDATORY_DISPLAY_SOURCE_CONTEXT_MISSING')
                display[cid] = deepcopy(claim)
        payload = {'required_evidence_ids': sorted(ids), 'anchor_evidence_ids': sorted(anchors),
                   'required_display': list(display.values()), 'citation_mapping': citations,
                   'evidence': evidence, 'gaps': gaps, 'authority_lock': self.lock,
                   'action_authority': False}
        payload['payload_sha256'] = content_hash(payload)
        return payload

    def assemble(self, bundle):
        self.check()
        if bundle.get('index_id') != self.index_id or bundle.get('manual_checksum', bundle.get('source_sha256')) != self.checksum:
            raise ValidationFailure('SOURCE_AUTHORITY_RETRIEVAL_IDENTITY')
        admitted, anchors, gaps = set(), set(), []
        for hit in bundle.get('hits', ()):
            chunk = self.chunks.get(hit.get('id'))
            if chunk is None:
                raise ValidationFailure('SOURCE_AUTHORITY_UNKNOWN_CHUNK')
            if content_hash(chunk) != self._chunk_hashes[chunk['id']]:
                raise ValidationFailure('SOURCE_AUTHORITY_INDEX_CHUNK_CHANGED')
            if hit.get('evidence_ids') != chunk['evidence_ids'] or hit.get('parent_section_id') != chunk['parent_section_id']:
                raise ValidationFailure('SOURCE_AUTHORITY_RETRIEVAL_MEMBERSHIP_CHANGED')
            pid = chunk['parent_section_id']
            direct = set(chunk['evidence_ids'])
            # Reviewed whole-parent restoration uses source children, never the
            # unreviewed parent.text string. Other chunks retain exact raw table
            # cells/headers and approved section labels without guessed context.
            unknown_context = sorted(direct - self.complete_context_ids)
            if unknown_context:
                gaps.append({'type': 'SOURCE_CONTEXT_COMPLETENESS_REVIEW_REQUIRED',
                             'chunk_id': chunk['id'], 'evidence_ids': unknown_context, 'rider_resolvable': False})
                continue
            seeds = set(self.structural[pid]['required_evidence_ids']) if pid in self.structural else direct
            closure = self._closure(seeds)
            missing = sorted(e for e in closure if not self.evidence_ready(e))
            if missing:
                gaps.append({'type': 'SOURCE_OBJECT_OR_CONTEXT_REVIEW_REQUIRED',
                             'chunk_id': chunk['id'], 'evidence_ids': missing, 'rider_resolvable': False})
                continue
            admitted.update(closure)
            anchors.update(direct)
        if len(admitted) > 256:
            raise ValidationFailure('SOURCE_AUTHORITY_DEPENDENCY_BOUND_NO_TRUNCATION')
        return self._payload(admitted, anchors, gaps)

    def validate(self, payload):
        self.check()
        signed = {k: v for k, v in payload.items() if k != 'payload_sha256'}
        if payload.get('authority_lock') != self.lock or content_hash(signed) != payload.get('payload_sha256'):
            raise ValidationFailure('SOURCE_AUTHORITY_ADMITTED_CONTEXT_CHANGED')
        expected = self._payload(set(payload['required_evidence_ids']), set(payload['anchor_evidence_ids']), payload['gaps'])
        if expected != payload:
            raise ValidationFailure('SOURCE_AUTHORITY_ADMITTED_CONTEXT_CHANGED')
        return True

    def select(self, payload, used_ids):
        self.validate(payload)
        used = set(used_ids)
        if not used or not used <= set(payload['required_evidence_ids']):
            raise ValidationFailure('INVALID_CLAIM_CITATION')
        required = self._closure(used)
        if not required <= set(payload['required_evidence_ids']):
            raise ValidationFailure('MANDATORY_SOURCE_CONTEXT_MISSING')
        return self._payload(required, used, payload['gaps'])
