"""Private IAM-protected initial-route API; not the rider UI API-v1."""
import base64
from dataclasses import asdict
import hashlib
import json
import math
import os
from pathlib import Path
import re
import time
import unicodedata
from flask import Flask, Response, jsonify, request
from werkzeug.exceptions import RequestEntityTooLarge

from approved_registry import ApprovedEvidenceRegistry
from cloud.arm_a.composer import ArmAComposer
from cloud.arm_a.store import FirestoreState, Limited, OperationConflict
from diagnose import ReviewedService
from online_retrieve import Retriever

ROOT = Path('/app')


def cloud_run_owner(headers):
    # Cloud Run IAM MUST remain enabled. Prefer the platform-verified header
    # when both are present; arbitrary client Authorization must not override it.
    value = headers.get('X-Serverless-Authorization') or headers.get('Authorization', '')
    def reject(reason):
        # Operational reason only: no header, token, subject, query or media.
        print(json.dumps({'event':'arm_a_auth_rejected','reason':reason}), flush=True)
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


def normalized(text):
    return ' '.join(unicodedata.normalize('NFC', text).casefold().split())


def create_app(registry, retriever, state_factory, cases):
    app = Flask(__name__)
    app.config['MAX_CONTENT_LENGTH'] = 16384
    questions = {c['record_id']:c['query'] for c in cases}

    def error(route, code, status):
        return jsonify({'type':route, 'error':code, 'technical_content':False}), status

    def deliver(view, replay=False):
        if not request.path.endswith('/stream') and 'text/event-stream' not in request.headers.get('Accept',''):
            response = jsonify(view)
        else:
            # All wording/conditions/cautions remain one complete safe unit.
            # This generator is created ONLY after managed state.finish commits.
            def events():
                body = view['response']
                if body['release_gate_passed'] and body['type'] == 'SUPPORTED':
                    yield 'event: verified_block\ndata: '+json.dumps({
                        'block':0, 'session_id':view['session_id'], 'version':view['version'],
                        'natural_language':body['natural_language'], 'cited_pages':body['cited_pages'],
                        'trace_id':body['trace_id'], 'release_gate_passed':True}, ensure_ascii=False)+'\n\n'
                yield 'event: complete\ndata: '+json.dumps(view,ensure_ascii=False)+'\n\n'
            response = Response(events(), content_type='text/event-stream; charset=utf-8')
            response.headers['X-Accel-Buffering'] = 'no'
        if replay:
            response.headers['X-Operation-Replay'] = 'true'
        return response

    @app.before_request
    def require_identity():
        # Readiness probe is local and returns no rider data; Cloud Run still
        # protects external health requests before they reach this handler.
        if request.path == '/healthz':
            return None
        try:
            request.environ['arm_a_owner'] = cloud_run_owner(request.headers)
        except PermissionError:
            return error('SYSTEM_ERROR','AUTH_REQUIRED',401)

    @app.after_request
    def private_headers(response):
        response.headers['Cache-Control'] = 'no-store'
        response.headers['X-Content-Type-Options'] = 'nosniff'
        return response

    @app.errorhandler(413)
    def oversized(_):
        return error('SYSTEM_ERROR','REQUEST_TOO_LARGE',413)

    @app.get('/healthz')
    def health():
        return jsonify({'ready':True, 'architecture':'A_DETERMINISTIC_CANONICAL',
            'manual_checksum':registry.checksum, 'index_id':registry.index_id,
            'provider_calls':0, 'benchmark_pacing':False,
            'streaming':'VERIFIED_COMPLETE_UNIT_SSE',
            'reranking':'conditional-rerank-v1', 'runtime_lock':app.config.get('ARM_A_RUNTIME_LOCK', ArmAComposer().config.lock)})

    @app.get('/v1/initial-catalogue')
    def catalogue():
        return jsonify({'schema_version':'motomedic-initial-arm-a-v1',
            'intent_resolution':'EXPLICIT_REVIEWED_RECORD_ONLY',
            'bike_variant':registry.source['variant'], 'manual_checksum':registry.checksum,
            'index_id':registry.index_id, 'streaming':True, 'questions':[{'record_id':key,'query':value}
                for key,value in questions.items()], 'adaptive_feedback':False, 'photos':False})

    @app.post('/v1/initial-answer')
    @app.post('/v1/initial-answer/stream')
    def answer():
        started = time.perf_counter()
        key = request.headers.get('Idempotency-Key','')
        if not re.fullmatch(r'[A-Za-z0-9_-]{16,100}', key):
            return error('SYSTEM_ERROR','VALID_OPERATION_KEY_REQUIRED',400)
        if request.mimetype != 'application/json':
            return error('SYSTEM_ERROR','JSON_REQUIRED',415)
        try:
            raw = request.stream.read(16385)
            if len(raw) > 16384:
                return error('SYSTEM_ERROR','REQUEST_TOO_LARGE',413)
            body = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object,
                              parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            required = {'record_id','bike_variant','confirmed_himalayan_bs6','manual_checksum','index_id'}
            if not isinstance(body, dict) or not required <= set(body) or set(body)-required-{'query'}:
                raise ValueError()
            if any(type(body[k]) is not str for k in required-{'confirmed_himalayan_bs6'}):
                raise ValueError()
            if type(body['confirmed_himalayan_bs6']) is not bool:
                raise ValueError()
            if 'query' in body and (type(body['query']) is not str or not 1 <= len(body['query']) <= 2000
                                    or len(body['query'].encode('utf-8')) > 8000):
                raise ValueError()
        except RequestEntityTooLarge:
            return error('SYSTEM_ERROR','REQUEST_TOO_LARGE',413)
        except Exception:
            return error('SYSTEM_ERROR','INVALID_REQUEST',400)
        if body['confirmed_himalayan_bs6'] is not True:
            return error('AMBIGUOUS','BIKE_CONFIRMATION_REQUIRED',400)
        if (body['manual_checksum'] != registry.checksum or body['index_id'] != registry.index_id
                or body['bike_variant'] != registry.source['variant']):
            return error('UNSUPPORTED','SOURCE_OR_VARIANT_MISMATCH',400)
        rid = body['record_id']
        if rid not in questions:
            return error('UNSUPPORTED','UNKNOWN_REVIEWED_RECORD',400)
        if 'query' in body and normalized(body['query']) != normalized(questions[rid]):
            return error('UNSUPPORTED','QUERY_RECORD_MISMATCH',400)
        state = state_factory(request.environ['arm_a_owner'])
        payload_hash = hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        try:
            prior = state.begin(key, payload_hash)
            if prior:
                if prior['state'] == 'COMPLETE':
                    return deliver(prior['view'], replay=True)
                return jsonify({'status':'RUNNING','operation_id':key}), 202
        except Limited:
            return error('SYSTEM_ERROR','APPLICATION_USAGE_LIMIT',429)
        except OperationConflict:
            return error('SYSTEM_ERROR','OPERATION_PAYLOAD_CONFLICT',409)
        except Exception:
            return error('SYSTEM_ERROR','ADMISSION_STORE_UNAVAILABLE',503)
        try:
            service = ReviewedService(registry, retriever, state, response_generator=ArmAComposer())
            session = service.start(rid, variant=body['bike_variant'])
            updated, result, _ = service.turn(session.session_id, questions[rid])
            gate = ('ARM_A_EXACT_REVIEWED_CANONICAL_VALIDATED' in result.reason_codes)
            view = {'schema_version':'motomedic-initial-arm-a-v1',
                    'manual_checksum':registry.checksum, 'index_id':registry.index_id,
                    'session_id':session.session_id, 'version':updated.version if updated else session.version,
                    'response':{'type':result.type.value, 'natural_language':result.natural_language,
                        'technical_content':bool(result.claim_evidence_map), 'release_gate_passed':gate,
                        'cited_pages':list(result.cited_pages), 'trace_id':result.trace_id,
                        'reason_codes':list(result.reason_codes)},
                    'architecture':'A_DETERMINISTIC_CANONICAL', 'provider_calls':0,
                    'timing':{'server_total_seconds':time.perf_counter()-started,
                              'retrieval':service.controller.last_retrieval_trace,
                              'composition':service.controller.response_generator.last_trace}}
            # Final view must be durably recorded before leaving the handler.
            return deliver(state.finish(key, view))
        except Exception:
            # Never rerun an uncertain operation; recovery reads its status.
            return error('SYSTEM_ERROR','OPERATION_NOT_COMMITTED',503)

    @app.get('/v1/initial-operations/<key>')
    def recover(key):
        if not re.fullmatch(r'[A-Za-z0-9_-]{16,100}', key):
            return error('SYSTEM_ERROR','INVALID_OPERATION_KEY',400)
        try:
            operation = state_factory(request.environ['arm_a_owner']).operation(key)
            return jsonify(operation['view']) if operation['state'] == 'COMPLETE' else (
                jsonify({'status':'RUNNING','operation_id':key}),202)
        except KeyError:
            return error('SYSTEM_ERROR','OPERATION_NOT_FOUND',404)
        except Exception:
            return error('SYSTEM_ERROR','OPERATION_STORE_UNAVAILABLE',503)
    return app


def load_production():
    if not os.environ.get('K_SERVICE'):
        raise RuntimeError('Production app requires Cloud Run IAM environment')
    lock = json.loads((ROOT/'arm_a_release.json').read_text(encoding='utf-8'))
    for name, sha in lock['file_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != sha:
            raise RuntimeError('Production runtime binding mismatch')
    from google.cloud import firestore
    index = ROOT/'build/index'
    registry = ApprovedEvidenceRegistry.load(ROOT, index)
    # Load both pinned query and cross-encoder models once per hosted worker.
    from cloud.arm_a.runtime_controls import GuardedRetriever, TokenBudget, VERSION
    from rider_ui.prompt_policy import load_role_policy
    from cloud.arm_a.composer import ArmAConfig
    retriever = GuardedRetriever(index, rerank=True)
    role_policy, role_lock = load_role_policy('generator')
    budget = TokenBudget(retriever.model, retriever.manifest['embedding'],
        role_policy, hashlib.sha256(role_policy.encode('utf-8')).hexdigest())
    retriever.install_controls(budget)
    # The owner clarified that A must retain an answer LLM. The historical
    # exact-wording composer is kept only for old regression fixtures.
    from cloud.grounded_generation.runtime import Composer, Questions
    from cloud.grounded_generation.provider import GemmaProvider
    from cloud.grounded_generation.admission import ProviderAdmission
    cases = json.loads((ROOT/'reports/ab30_v1_cases.json').read_text(encoding='utf-8'))
    if isinstance(cases, dict):
        cases = cases['cases']
    client = firestore.Client(project='motomedic-ai-20261009')
    controlled_composer = Composer(GemmaProvider(ProviderAdmission(client),
        cache_capability=os.environ.get('MOTOMEDIC_PROVIDER_CACHE_CAPABILITY','unsupported')))
    state_factory = lambda owner:FirestoreState(client,owner)
    app = create_app(registry, retriever, state_factory, cases)
    app.config['ARM_A_RUNTIME_LOCK'] = controlled_composer.config.lock
    secret = os.environ.get('MOTOMEDIC_VISITOR_SECRET')
    if secret:
        from cloud.arm_a.rider_api import install
        install(app, Questions(registry,retriever,composer=controlled_composer), state_factory, secret,
            network_required=os.environ.get('MOTOMEDIC_PUBLIC_NETWORK_REQUIRED') == 'true')
    return app
