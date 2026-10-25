"""Open manual Q&A: top-5 section retrieval, one Haiku call and the deterministic gate.

No review layer, verifier, authored answer catalog or server-added warning text. A turn:
1. builds the retrieval query (short follow-ups keep the prior rider topic);
2. keeps the fused top 5 chunks and reorders them only when dense and BM25 disagree;
3. sends the whole section of each chunk as plain labelled text, or, when nothing is
   retrieved, returns the fixed fallback and support route with no model call;
4. makes one Haiku call that fills the answer template;
5. releases through the deterministic gate or fails closed as SYSTEM_ERROR.
The returned view is a private buffer: the worker saves it before any byte reaches the rider.
"""
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import threading
import time
import uuid

from controller_contracts import DiagnosticSession
from generation_providers import ProviderFailure
from cloud.grounded_generation import section_assembly as sa
from cloud.grounded_generation import section_retrieval as sr
from cloud.grounded_generation import template_answer as ta

VERSION = 'section-template-questions-v1'
RUNTIME_POLICY = 'open-manual-section-template-v1'
SCHEMA = 'motomedic-rider-api-v1'
SYSTEM_ERROR_TEXT = 'I couldn’t check the answer right now. Please try again shortly.'
HISTORY_TURNS = 3
HISTORY_ANSWER_CHARS = 600


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                                     separators=(',', ':')).encode('utf-8')).hexdigest()


def response_hash(view):
    from cloud.grounded_generation.delivery import response_hash as bound
    return bound(view)


class ManualSource:
    """The selected manual and its verified support route, bound to the pinned index."""
    def __init__(self, manifest, index_identity):
        route = manifest.get('oem_service_route') or {}
        checksum = str(manifest.get('sha256', '')).lower()
        if checksum != index_identity['manual_sha256']:
            raise ValueError('MANUAL_INDEX_SOURCE_MISMATCH')
        if route.get('verified') is not True or route.get('url') != 'mailto:' + str(route.get('email')):
            raise ValueError('SUPPORT_ROUTE_UNVERIFIED')
        self.manual_id, self.checksum = manifest['manual_id'], checksum
        self.variant, self.edition = manifest['variant'], manifest['edition']
        self.support_uri = route['url']
        self.support_market, self.support_market_fit = route.get('market'), route.get('market_fit_status')
        self.index_id = index_identity['index_id']

    @classmethod
    def load(cls, root, index_identity):
        return cls(json.loads((Path(root) / 'source_manifest.json').read_text(encoding='utf-8-sig')), index_identity)

    def identity(self):
        return {'manual_id': self.manual_id, 'manual_checksum': self.checksum, 'variant': self.variant,
                'edition': self.edition, 'support_uri': self.support_uri, 'index_id': self.index_id}


def runtime_lock(source, index_identity, generation_contract):
    return digest({'questions': VERSION, 'runtime_policy': RUNTIME_POLICY, 'source': source.identity(),
                   'index': index_identity,
                   'retrieval': {'version': sr.VERSION, 'top_k': sr.TOP_K, 'rrf_k': sr.RRF_K,
                                 'dense_limit': sr.DENSE_LIMIT, 'fuse_depth': sr.FUSE_DEPTH,
                                 'disagreement_top': sr.DISAGREEMENT_TOP},
                   'assembly': sa.VERSION, 'template': ta.VERSION,
                   'system_prompt_sha256': hashlib.sha256(ta.SYSTEM_PROMPT.encode()).hexdigest(),
                   'generation': generation_contract})


def earlier_turns(history):
    """The last few saved turns as plain lines for the model; data, never instructions."""
    rows = [row for row in history if isinstance(row, dict) and isinstance(row.get('question'), str)]
    lines = []
    for row in rows[-HISTORY_TURNS:]:
        lines.append('Rider: ' + row['question'].strip())
        answer = row.get('response')
        if isinstance(answer, str) and answer.strip():
            answer = answer.strip()
            lines.append('MotoMedic: ' + (answer if len(answer) <= HISTORY_ANSWER_CHARS
                                          else answer[:HISTORY_ANSWER_CHARS].rstrip() + ' ...'))
    return lines


def generation_summary(trace):
    """Counts, cost and ledger outcome only; never prompt, evidence or draft text."""
    trace = dict(trace or {})
    receipt = trace.pop('admission', None) or {}
    trace['admission'] = {k: receipt.get(k) for k in ('reservation_mode', 'reserved_tokens', 'reserved_nanodollars',
                                                      'sealing_status', 'sealed_unused_slots')}
    return trace


class Questions:
    def __init__(self, source, index, retriever, generate, index_identity):
        if not (index.manifest['index_id'] == retriever.manifest['index_id'] == index_identity['index_id']
                == source.index_id):
            raise ValueError('SECTION_INDEX_MISMATCH')
        self.source, self.index, self.retriever, self.generate = source, index, retriever, generate
        self.index_identity = index_identity
        self.index_lock = index_identity['manifest_sha256']
        self.runtime_lock = runtime_lock(source, index_identity, generate.contract)
        self.pipeline_lock = threading.Lock()

    def new_session(self):
        s = self.source
        return DiagnosticSession(uuid.uuid4().hex, s.manual_id, s.checksum, s.variant, s.edition, (),
                                 self.index_lock, self.runtime_lock)

    def answer(self, session, query, *, history=(), progress=None, operation_id=None):
        """Return (session, private view buffer, choices). Open Q&A issues no choices."""
        session = replace(session, version=session.version + 1, pending_step_id=None, pending_rule_id=None)
        operation_id = operation_id or uuid.uuid4().hex
        controls = {'questions': VERSION, 'provider_calls': 0}
        started = time.monotonic()
        if not self.pipeline_lock.acquire(blocking=False):
            return session, self._error(session, operation_id, 'PIPELINE_CONCURRENCY_LIMIT', controls), {}
        try:
            if (session.manual_checksum != self.source.checksum or session.version_lock != self.index_lock or
                    session.generation_lock != self.runtime_lock or session.bike_variant != self.source.variant):
                raise ValueError('SESSION_RUNTIME_CHANGED')
            if progress:
                progress('retrieving')
            found = self.retriever.search(sr.retrieval_query(query, history))
            controls['retrieval'] = {k: found[k] for k in ('version', 'index_id', 'chunk_ids', 'sections_disagree',
                                                           'reranked', 'rerank_skip_reason')}
            if found['index_id'] != self.source.index_id:
                raise ValueError('RETRIEVAL_INDEX_CHANGED')
            assembled = sa.assemble(self.index, found['chunk_ids'])
            controls['assembly'] = {'version': assembled['version'], 'sections': len(assembled['sections']),
                                    'lines': len(assembled['objects']), 'warnings': len(assembled['warnings']),
                                    'text_sha256': hashlib.sha256(assembled['text'].encode()).hexdigest()}
            controls['retrieval_assembly_seconds'] = time.monotonic() - started
            if not assembled['objects']:
                release = ta.no_evidence_release(self.source.support_uri)
            else:
                if progress:
                    progress('drafting')
                text = sa.model_input(query, assembled, earlier_turns(history))
                try:
                    draft, _trace = self.generate(assembled, text, operation_id)
                finally:
                    controls['generation'] = generation_summary(getattr(self.generate, 'last_trace', None))
                    controls['provider_calls'] = controls['generation'].get('generation_calls', 0)
                if progress:
                    progress('checking')
                release = ta.gate(draft, assembled, query, self.source.support_uri)
            controls['gate'] = {'version': release['version'], 'route': release['route'],
                                'coverage': release['coverage'], 'citations': len(release['citations']),
                                'excluded_watchouts': len(release['excluded_watchouts']),
                                'suppressed_disclaimers': release['suppressed_disclaimers']}
            controls['server_seconds'] = time.monotonic() - started
            return session, self._released(session, operation_id, release, assembled, found, controls), {}
        except ta.ReleaseRejected as exc:
            controls['gate'] = {'version': ta.VERSION, 'failure_code': exc.code}
            return session, self._error(session, operation_id, 'GATE_' + exc.code, controls), {}
        except Exception as exc:
            code = str(exc) if isinstance(exc, (ProviderFailure, ValueError, sr.RetrievalError)) else ''
            if not code.replace('_', '').replace(':', '').isalnum() or not code.isupper():
                code = 'OPEN_QA_FAILURE'
            return session, self._error(session, operation_id, code, controls), {}
        finally:
            self.pipeline_lock.release()

    def _base(self, session, route, text, controls, *, technical=False, released=False, cited=(),
              escalation=None, clarification=None, reasons=()):
        return {'schema_version': SCHEMA, 'manual_checksum': self.source.checksum,
                'index_id': self.source.index_id, 'session_id': session.session_id, 'version': session.version,
                'response': {'type': route, 'natural_language': text, 'technical_content': technical,
                             'release_gate_passed': released, 'cited_pages': list(cited),
                             'trace_id': uuid.uuid4().hex, 'reason_codes': list(reasons),
                             'clarification_question': clarification, 'escalation_uri': escalation},
                'choices': [], 'history': [], 'escalation_uri': escalation, 'runtime_policy': RUNTIME_POLICY,
                'provider_calls': controls.get('provider_calls', 0), 'runtime_controls': controls}

    def _error(self, session, operation_id, code, controls):
        controls['failure_code'] = code
        return self._base(session, 'SYSTEM_ERROR', SYSTEM_ERROR_TEXT, controls, reasons=(code,))

    def _released(self, session, operation_id, release, assembled, found, controls):
        cited = [{'evidence_id': c['evidence_id'], 'pdf_page': page, 'pdf_page_index': page - 1,
                  'manual_checksum': self.source.checksum, 'index_id': self.source.index_id}
                 for c in release['citations'] for page in c['pages']]
        called = release['provider_calls'] == 1
        view = self._base(session, release['route'], release['text'], controls, technical=bool(cited),
                          released=called, cited=cited, escalation=release['escalation_uri'],
                          clarification=release.get('clarification_question'),
                          reasons=('TEMPLATE_GATE_RELEASED',) if called else (release.get('reason', 'NOTHING_RETRIEVED'),))
        if called:
            record = {'gate': release['version'], 'route': release['route'], 'coverage': release['coverage'],
                      'text': release['text'], 'citations': release['citations'], 'sections': release['sections'],
                      'watchout_review': release['watchout_review'], 'chunk_ids': found['chunk_ids'],
                      'labels': {label: obj['evidence_id'] for label, obj in assembled['objects'].items()}}
            view['release_delivery'] = {'operation_id': operation_id, 'runtime_lock': self.runtime_lock,
                'manual_checksum': self.source.checksum, 'index_id': self.source.index_id,
                'evidence_payload_sha256': hashlib.sha256(assembled['text'].encode()).hexdigest(),
                'release_sha256': digest(record),
                'text_sha256': hashlib.sha256(release['text'].encode()).hexdigest()}
            view['release_delivery']['presentation_sha256'] = response_hash(view)
        return view

    def validate_saved(self, view):
        """A saved view is delivered only under the runtime, manual and index that released it."""
        if (view.get('runtime_policy') != RUNTIME_POLICY or view.get('manual_checksum') != self.source.checksum or
                view.get('index_id') != self.source.index_id):
            raise ValueError('SAVED_ANSWER_RUNTIME_CHANGED')
        body = view['response']
        if body.get('release_gate_passed') or body.get('technical_content'):
            released = view.get('release_delivery') or {}
            binding = view.get('delivery') or {}
            if (body.get('release_gate_passed') is not True or released.get('runtime_lock') != self.runtime_lock or
                    binding.get('runtime_lock') != self.runtime_lock or
                    released.get('manual_checksum') != self.source.checksum or
                    released.get('index_id') != self.source.index_id or
                    released.get('operation_id') != binding.get('operation_id') or
                    released.get('presentation_sha256') != response_hash(view) or
                    binding.get('response_sha256') != response_hash(view) or
                    released.get('release_sha256') != binding.get('release_binding_sha256') or
                    released.get('evidence_payload_sha256') != binding.get('evidence_payload_sha256') or
                    released.get('text_sha256') != hashlib.sha256(body['natural_language'].encode()).hexdigest()):
                raise ValueError('SAVED_ANSWER_BINDING_CHANGED')
        return view
