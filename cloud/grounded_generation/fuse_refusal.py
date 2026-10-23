"""Exact-source refusal warnings only; never positive answer admission."""
from pathlib import Path
from copy import deepcopy
import hashlib
import json
import re

from evidence_registry import content_hash

VERSION = 'fuse-source-warning-refusal-v1'
SCOPE_SHA = '1a9a27d561e59613b2df875600d3fc2f4e904f2a4bcafbcbaa57dbe6f2508bb6'
SCOPE_PATH = Path(__file__).resolve().parents[2] / 'reports/grounded_generation/source_context_v1/fuse_safety_scope.json'


def _hazard(query):
    if not isinstance(query, str) or not re.search(r'\bfuses?\b', query, re.I):
        return None
    text = query.casefold()
    if re.search(r'\b(?:bridge|bridging|jumper|jumpering|jump|bypass|bypassing)\b', text):
        return 'FUSE_JUMPER_OR_BRIDGE'
    substitution = re.search(r'\b(?:use|using|fit|fitting|put|replace|replacing|swap|substitute|substituting|instead|bypass|bridge)\b', text)
    if substitution and re.search(r'\b(?:wire|foil|metal|conductive)\b', text):
        return 'FUSE_CONDUCTIVE_SUBSTITUTE'
    if substitution and re.search(r'\b(?:higher|larger|bigger|different|increased|stronger)\b', text):
        return 'FUSE_WRONG_OR_INCREASED_RATING'
    ratings = [float(n) for n in re.findall(r'(?<![\w.])(\d+(?:\.\d+)?)\s*(?:a\b|amps?\b|amperes?\b|[- ]amp\b)', text)]
    relation = re.search(r'\b(?:instead|rather than|in place of|with|for)\b', text)
    if substitution and relation and len(set(ratings)) >= 2:
        return 'FUSE_WRONG_OR_INCREASED_RATING'
    return None


def detect_refusal(registry, query):
    """Return a bound refusal or None; binding failures raise, never admit."""
    hazard = _hazard(query)
    if hazard is None:
        return None
    raw = SCOPE_PATH.read_bytes()
    if hashlib.sha256(raw).hexdigest() != SCOPE_SHA:
        raise ValueError('FUSE_REFUSAL_SCOPE_BINDING')
    scope = json.loads(raw)
    if (not registry.source_ready() or
        scope['manual_checksum'] != registry.checksum or
        scope['index_id'] != registry.index_id or
        scope['decision'] != 'APPROVED_AGENT_SOURCE_REFUSAL_ONLY' or
        hazard not in scope['hazard_intents']):
        raise ValueError('FUSE_REFUSAL_SOURCE_BINDING')
    citations = []
    for eid, binding in scope['source_bindings'].items():
        obj = registry.evidence.get(eid)
        src = registry.approved_sources.get(eid)
        if (not registry.evidence_ready(eid) or not obj or not src or
            content_hash(obj['raw_object']) != binding['raw_object_sha256'] or
            content_hash(obj['provenance']) != binding['provenance_sha256'] or
            content_hash(src) != binding['source_object_sha256'] or
            src.get('exact_text') != binding['exact_warning_text']):
            raise ValueError('FUSE_REFUSAL_EVIDENCE_BINDING')
        for page in obj['provenance']:
            if page.get('page_no') != 112:
                raise ValueError('FUSE_REFUSAL_CITATION_BINDING')
            citations.append({'evidence_id': eid, 'pdf_page': 112,
                'pdf_page_index': 111, 'manual_checksum': registry.checksum,
                'index_id': registry.index_id})
    first = 'evidence_00497a5a6998712d564a2df2'
    second = 'evidence_8b5ef092d20493cd2b9b58b8'
    claims = [
        {'claim_id': VERSION + ':rating', 'response_role': 'WARNING',
         'text': 'Do not substitute a fuse of another rating or conductive material; the manual warns this can damage the complete electrical system.',
         'evidence_ids': [first], 'presentation_mode': 'SOURCE_WARNING_REFUSAL'},
        {'claim_id': VERSION + ':jumper', 'response_role': 'WARNING',
         'text': 'Do not jumper or bridge a defective fuse: this creates a risk of short circuit and fire. The specified fuse rating must be retained.',
         'evidence_ids': [second], 'presentation_mode': 'SOURCE_WARNING_REFUSAL'}]
    return deepcopy({'route': 'SAFETY_STOP', 'scope_id': scope['scope_id'],
        'runtime_version': VERSION, 'scope_sha256': SCOPE_SHA,
        'hazard': hazard, 'claims': claims,
        'citation_mapping': citations,
        'natural_language': ' '.join(c['text'] for c in claims),
        'provider_calls': 0, 'semantic_support_proven': False,
        'permitted_positive_step_ids': []})


