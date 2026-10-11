"""Pinned, independently approved labels and parent membership, never parent text.

This module cannot approve evidence, lift held contexts or authorize new actions.
The serving retriever separately validates its immutable index files; labels here
come only from the exact SHA-bound source-context review package.
"""
from copy import deepcopy
from functools import lru_cache
import hashlib
import json
from pathlib import Path
from constrained_generator import ValidationFailure
from evidence_registry import content_hash

VERSION='approved-source-context-loader-v1'
BINDING_PATH='reports/grounded_generation/source_context_v1/context_bindings.json'
BINDING_SHA256='7f414ce70696a1e60f97655c577ae2556b8b09f99989af2a747fdb72e73d4aed'
_MANUAL_AUTHORITIES=frozenset(('OEM_MANUAL','OEM_ORIGINAL_PDF_CANDIDATE'))

@lru_cache(maxsize=1)
def _decode(raw):
    return json.loads(raw)

def _manifest():
    try:
        raw=(Path(__file__).resolve().parents[2]/BINDING_PATH).read_bytes()
    except OSError:
        raise ValidationFailure('SOURCE_CONTEXT_BINDING_UNAVAILABLE') from None
    if hashlib.sha256(raw).hexdigest()!=BINDING_SHA256:
        raise ValidationFailure('SOURCE_CONTEXT_BINDING_CHANGED')
    # Always verify current bytes, even with a previously decoded package.
    return _decode(raw)

def context_for(registry,eid):
    """Return a copied labels-only payload or an explicit fail-closed code.

    SOURCE_CONTEXT_REVIEW_REQUIRED is an abstention, not a rider question.
    Distinct integrity codes identify corrupted/mismatched runtime bindings.
    """
    manifest=_manifest()
    if (registry.checksum!=manifest['manual_checksum'] or
        registry.source.get('sha256','').lower()!=manifest['manual_checksum']):
        raise ValidationFailure('SOURCE_CONTEXT_MANUAL_MISMATCH')
    if registry.index_id!=manifest['index_id']:
        raise ValidationFailure('SOURCE_CONTEXT_INDEX_MISMATCH')
    if registry.reviews.get('release_manifest_sha256')!=manifest['release_manifest_sha256']:
        raise ValidationFailure('SOURCE_CONTEXT_RELEASE_MISMATCH')
    if not registry.source_ready():raise ValidationFailure('SOURCE_CONTEXT_REVIEW_REQUIRED')
    evidence=registry.evidence.get(eid)
    source=registry.approved_sources.get(eid)
    if not evidence or not source:raise ValidationFailure('SOURCE_CONTEXT_REVIEW_REQUIRED')
    authority=source.get('authority')
    if authority=='PRODUCT_POLICY':
        if not registry.evidence_ready(eid):raise ValidationFailure('SOURCE_CONTEXT_REVIEW_REQUIRED')
        return {'context_kind':'PRODUCT_POLICY','context_authority':'PRODUCT_POLICY_ONLY_NOT_OEM_MANUAL',
            'evidence_id':eid,'section_path':[],'parent_membership':[],
            'original_object_sha256':content_hash(evidence['raw_object'])}
    if authority not in _MANUAL_AUTHORITIES:
        raise ValidationFailure('SOURCE_CONTEXT_AUTHORITY_MISMATCH')
    row=manifest['bindings'].get(eid)
    if not row:raise ValidationFailure('SOURCE_CONTEXT_REVIEW_REQUIRED')
    if row['evidence_id']!=eid:raise ValidationFailure('SOURCE_CONTEXT_ID_MISMATCH')
    if content_hash(evidence.get('raw_object'))!=row['raw_object_sha256']:
        raise ValidationFailure('SOURCE_CONTEXT_RAW_OBJECT_MISMATCH')
    if content_hash(evidence.get('provenance'))!=row['provenance_sha256']:
        raise ValidationFailure('SOURCE_CONTEXT_PROVENANCE_MISMATCH')
    if content_hash(source)!=row['source_object_sha256']:
        raise ValidationFailure('SOURCE_CONTEXT_SOURCE_OBJECT_MISMATCH')
    if not registry.evidence_ready(eid):raise ValidationFailure('SOURCE_CONTEXT_REVIEW_REQUIRED')
    if row['review_status']!='APPROVED_CONTEXT_LABELS' or not row.get('section_path'):
        raise ValidationFailure('SOURCE_CONTEXT_REVIEW_REQUIRED')
    if (row['context_authority']!='LABELS_ONLY_NO_NEW_ACTION_AUTHORITY' or
        row.get('parent_text_included') is not False or
        any(p.get('parent_text_authorized') is not False for p in row['parents'])):
        raise ValidationFailure('SOURCE_CONTEXT_AUTHORITY_MISMATCH')
    # This whitelist excludes all parent/source text, review prose and any future
    # manifest fields. Membership hashes do not authorize adding parent contents.
    return {'context_kind':'OEM_MANUAL_LABELS','context_authority':row['context_authority'],
        'evidence_id':eid,'section_path':deepcopy(row['section_path']),
        'parent_section_ids':deepcopy(row['parent_section_ids']),
        'immutable_chunk_ids':deepcopy(row['immutable_chunk_ids']),
        'parent_membership':[{'parent_section_id':p['parent_section_id'],
            'parent_object_sha256':p['parent_object_sha256']} for p in row['parents']],
        'source_context_review_sha256':BINDING_SHA256,
        'original_object_sha256':row['raw_object_sha256']}