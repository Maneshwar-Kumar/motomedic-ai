"""IAM-protected rider API service: health, the rider routes and the durable worker.

Answers come only from cloud.grounded_generation.section_questions: top-5 section retrieval,
one Haiku call and the deterministic release gate. No review layer or verifier.
Every request except the startup probe emits one http_request event (route template, status,
error code, latency and trace id; never headers, bodies or rider text).
"""
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
from flask import Flask, g, jsonify, request
from cloud.common import telemetry as tm

ROOT = Path('/app')
SCHEMA = 'motomedic-serving-release-v11'
ARCHITECTURE = 'SECTION_TOP5_SINGLE_CALL_TEMPLATE_GATE'


def cloud_run_owner(headers):
    # Cloud Run IAM MUST remain enabled. Prefer the platform-verified header
    # when both are present; arbitrary client Authorization must not override it.
    value = headers.get('X-Serverless-Authorization') or headers.get('Authorization', '')
    def reject(reason):
        # Operational reason only: no header, token, subject, query or media.
        tm.STDOUT.emit('auth_rejected', severity='WARNING', reason=reason)
        raise PermissionError()
    scheme, separator, credential = value.partition(' ')
    if not separator or scheme.casefold() != 'bearer' or len(value) > 16000:
        reject('BEARER_HEADER_REQUIRED')
    parts = credential.split('.')
    if len(parts) != 3:
        reject('JWT_SHAPE_INVALID')
    try:
        body = json.loads(base64.urlsafe_b64decode(parts[1]+'='*(-len(parts[1])%4)))
    except Exception:
        reject('JWT_PAYLOAD_INVALID')
    if not isinstance(body, dict) or body.get('iss') not in ('https://accounts.google.com','accounts.google.com'):
        reject('ISSUER_INVALID')
    if type(body.get('exp')) not in (int,float) or not math.isfinite(body['exp']):
        reject('EXPIRY_FORMAT_INVALID')
    if body['exp'] <= time.time():
        reject('TOKEN_EXPIRED')
    if not isinstance(body.get('sub'), str) or not 1 <= len(body['sub']) <= 200:
        reject('SUBJECT_FORMAT_INVALID')
    return hashlib.sha256(('motomedic-arm-a-initial-v1:'+body['sub']).encode()).hexdigest()


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def route_template(rule):
    """'/v1/sessions/<session_id>/questions' -> '/v1/sessions/:session_id/questions'."""
    return re.sub(r'<(?:[^:>]+:)?([^>]+)>', r':\1', rule.rule) if rule is not None else 'UNMATCHED'


def create_app(source, telemetry=None):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 16384
    telemetry = telemetry or tm.NULL
    app.config['TELEMETRY'] = telemetry

    def error(route, code, status):
        g.error_code = code
        return jsonify({'type':route, 'error':code, 'technical_content':False}), status

    @app.before_request
    def start_trace():
        g.started, g.trace_id = time.monotonic(), tm.trace_from_headers(request.headers)

    @app.before_request
    def require_identity():
        # Readiness probe is local and returns no rider data; Cloud Run still
        # protects external health requests before they reach this handler.
        if request.path == '/healthz':
            return None
        try:
            from cloud.arm_a.public_inspection_auth import enabled, verify_request
            if enabled():
                if request.path == '/v1/health' and request.method == 'GET':
                    return None
                verified_token = verify_request(request.headers)
                # Cloud Run strips the alternate header's signature. Downstream
                # edge/Tasks checks must read the same fully verified JWT.
                request.environ.pop('HTTP_X_SERVERLESS_AUTHORIZATION', None)
                request.environ['HTTP_AUTHORIZATION'] = 'Bearer ' + verified_token
            request.environ['arm_a_owner'] = cloud_run_owner(request.headers)
        except PermissionError:
            return error('SYSTEM_ERROR','AUTH_REQUIRED',401)

    @app.after_request
    def private_headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.after_request
    def observe(response):
        if request.path != '/healthz':
            key = request.headers.get('Idempotency-Key') or (request.view_args or {}).get('key')
            telemetry.emit('http_request', trace_id=g.get('trace_id'),
                severity='ERROR' if response.status_code >= 500 else 'INFO',
                method=request.method, path=route_template(request.url_rule), http_status=response.status_code,
                error_code=g.get('error_code'), replay=response.headers.get('X-Operation-Replay') == 'true',
                operation_id=key if isinstance(key, str) and re.fullmatch(r'[a-f0-9]{32}', key) else None,
                duration_ms=round((time.monotonic() - g.get('started', time.monotonic())) * 1000, 1))
        return response

    @app.errorhandler(413)
    def oversized(_):
        return error('SYSTEM_ERROR','REQUEST_TOO_LARGE',413)

    # Cloud Run reserves /healthz at external ingress; retain it for the
    # container startup probe and expose an ordinary IAM-protected API path.
    @app.get('/v1/health')
    @app.get('/healthz')
    def health():
        ready = app.config.get('DURABLE_DISPATCH_CONFIGURED') is True
        return jsonify({'ready':ready, 'architecture':ARCHITECTURE,
            'manual_checksum':source.checksum, 'index_id':source.index_id,
            'answer_provider':app.config.get('ANSWER_PROVIDER'), 'verifier_provider':None,
            'review_layer':'NONE', 'streaming':'SAVED_RELEASE_STREAM',
            'durable_dispatch_configured': app.config.get('DURABLE_DISPATCH_CONFIGURED', False),
            'retrieval':app.config.get('RETRIEVAL'), 'dense_backend':app.config.get('DENSE_BACKEND'),
            'prompt_cache':app.config.get('PROMPT_CACHE'),
            'runtime_lock':app.config.get('RUNTIME_LOCK')}), (200 if ready else 503)
    return app


def validate_production_policy(lock):
    """Check the installed release policy before models, providers or stores load."""
    from cloud.grounded_generation import section_assembly, section_retrieval, template_answer
    from cloud.grounded_generation.haiku_answer import CONTRACT
    if (type(lock) is not dict or lock.get('schema_version') != SCHEMA or
            lock.get('architecture') != ARCHITECTURE or
            lock.get('generation_model') != CONTRACT['model'] or
            lock.get('generation_contract') != CONTRACT or
            lock.get('retrieval_version') != section_retrieval.VERSION or
            lock.get('assembly_version') != section_assembly.VERSION or
            lock.get('template_version') != template_answer.VERSION or
            lock.get('review_layer') != 'NONE' or lock.get('verifier') != 'NONE' or
            lock.get('answer_cache_enabled') is not False or lock.get('fallback_enabled') is not False or
            type(lock.get('index')) is not dict or lock['index'].get('index_id') != lock.get('index_id') or
            lock['index'].get('manual_sha256') != lock.get('manual_checksum')):
        raise RuntimeError('Production serving policy mismatch')


def load_production():
    if not os.environ.get('K_SERVICE'):
        raise RuntimeError('Production app requires Cloud Run IAM environment')
    lock = json.loads((ROOT/'arm_a_release.json').read_text(encoding='utf-8'))
    for name, sha in lock['file_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != sha:
            raise RuntimeError('Production runtime binding mismatch')
    validate_production_policy(lock)
    if os.environ.get('MOTOMEDIC_CLAUDE_FALLBACK_ENABLED') == 'true':
        raise RuntimeError('Availability fallback is not part of this runtime')
    if not os.environ.get('ANTHROPIC_API_KEY'):
        raise RuntimeError('The Haiku generation call requires its server-side managed secret')
    from cloud.grounded_generation import section_index
    from cloud.grounded_generation.section_assembly import SectionIndex
    from cloud.grounded_generation.section_retrieval import SectionRetriever, QdrantDense
    from cloud.grounded_generation.section_questions import ManualSource, Questions
    from cloud.grounded_generation.haiku_answer import HaikuAnswer
    from cloud.grounded_generation.whole_turn_admission import WholeTurnAdmission
    from cloud.arm_a.store import FirestoreState
    from google.cloud import firestore
    from sentence_transformers import SentenceTransformer, CrossEncoder
    index_dir = ROOT/'build/section-index'
    identity = section_index.verify(index_dir, lock['index'])
    source = ManualSource.load(ROOT, identity)
    # Query models are pinned assets of the base image; the manual is never re-embedded here.
    packaged = ROOT/'build/index'
    if not (packaged/'embedding_model').is_dir() or not (index_dir/'reranker_model').is_dir():
        raise RuntimeError('Pinned query model assets are unavailable')
    inherited = json.loads((packaged/'manifest.json').read_text(encoding='utf-8'))['embedding']
    if {k: v for k, v in identity['embedding'].items() if k not in ('weights_file', 'weights_sha256')} != inherited:
        raise RuntimeError('Query model identity differs from the section index')
    embedding = SentenceTransformer(str(packaged/'embedding_model'), device='cpu', local_files_only=True)
    reranker = CrossEncoder(str(index_dir/'reranker_model'), device='cpu', local_files_only=True)
    retriever = SectionRetriever(index_dir, embedding, reranker)
    qdrant = os.environ.get('MOTOMEDIC_QDRANT_URL')
    if qdrant:
        # The backend is chosen once at startup; a Qdrant failure is SYSTEM_ERROR, never a switch.
        retriever.dense = QdrantDense(qdrant, identity['index_id'], identity['manual_sha256'],
                                      [c['id'] for c in retriever.chunks])
    client = firestore.Client(project='motomedic-ai-20261009')
    generate = HaikuAnswer(WholeTurnAdmission(client))
    telemetry = tm.Telemetry()
    questions = Questions(source, SectionIndex(index_dir), retriever, generate, identity, telemetry=telemetry)
    state_factory = lambda owner: FirestoreState(client, owner)
    app = create_app(source, telemetry=telemetry)
    app.config.update(ANSWER_PROVIDER=generate.contract['model'], PROMPT_CACHE='ANTHROPIC_SYSTEM_PROMPT_5M',
        RETRIEVAL=lock['retrieval_version'], DENSE_BACKEND='QDRANT' if qdrant else 'EXACT_PINNED_VECTORS',
        RUNTIME_LOCK=questions.runtime_lock)
    secret = os.environ.get('MOTOMEDIC_VISITOR_SECRET')
    if secret:
        from cloud.arm_a.rider_api import install
        from cloud.arm_a.durable_dispatch import configured_dispatcher
        dispatcher = configured_dispatcher()
        app.config['DURABLE_DISPATCH_CONFIGURED'] = dispatcher is not None
        install(app, questions, state_factory, secret,
            network_required=os.environ.get('MOTOMEDIC_PUBLIC_NETWORK_REQUIRED') == 'true',
            dispatcher=dispatcher)
    return app
