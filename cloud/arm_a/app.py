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

    # Cloud Run reserves /healthz at external ingress; retain it for the
    # container startup probe and expose an ordinary IAM-protected API path.
    @app.get('/v1/health')
    @app.get('/healthz')
    def health():
        ready = not app.config.get('GROUNDED_PRIMARY') or app.config.get('DURABLE_DISPATCH_CONFIGURED') is True
        return jsonify({'ready':ready, 'architecture':app.config.get('SERVING_ARCHITECTURE','A_DETERMINISTIC_CANONICAL'),
            'manual_checksum':registry.checksum, 'index_id':registry.index_id,
            'answer_provider':app.config.get('ANSWER_PROVIDER'), 'benchmark_pacing':False,
            'streaming':('DRAFT_VERIFY_STREAM' if app.config.get('GROUNDED_PRIMARY') else 'VERIFIED_COMPLETE_UNIT_SSE'),
            'durable_dispatch_configured': app.config.get('DURABLE_DISPATCH_CONFIGURED', False),
            'reranking':'authenticated-open-hybrid-rank-disagreement-v5',
            'verifier_provider':app.config.get('VERIFIER_PROVIDER'),
            'prompt_cache':app.config.get('PROMPT_CACHE'),
            'model_routing':app.config.get('MODEL_ROUTING_CONTRACT'),
            'runtime_lock':app.config.get('ARM_A_RUNTIME_LOCK', ArmAComposer().config.lock)}), (200 if ready else 503)

    @app.get('/v1/initial-catalogue')
    def catalogue():
        if app.config.get('GROUNDED_PRIMARY'):
            return error('UNSUPPORTED','BENCHMARK_ENDPOINT_RETIRED',410)
        return jsonify({'schema_version':'motomedic-initial-arm-a-v1',
            'intent_resolution':'EXPLICIT_REVIEWED_RECORD_ONLY',
            'bike_variant':registry.source['variant'], 'manual_checksum':registry.checksum,
            'index_id':registry.index_id, 'streaming':True, 'questions':[{'record_id':key,'query':value}
                for key,value in questions.items()], 'adaptive_feedback':False, 'photos':False})

    @app.post('/v1/initial-answer')
    @app.post('/v1/initial-answer/stream')
    def answer():
        if app.config.get('GROUNDED_PRIMARY'):
            return error('UNSUPPORTED','BENCHMARK_ENDPOINT_RETIRED',410)
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
        if app.config.get('GROUNDED_PRIMARY'):
            return error('UNSUPPORTED','BENCHMARK_ENDPOINT_RETIRED',410)
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


def validate_production_policy(lock):
    """Check the installed role policy before models, providers or stores load."""
    from cloud.grounded_generation.cached_verifier import CONTRACT as VERIFIER_CONTRACT, DRAFT_CONTRACT
    from cloud.grounded_generation.role_router import ROUTING_CONTRACT
    if (type(lock) is not dict or lock.get('schema_version') != 'motomedic-serving-release-v10' or
            lock.get('primary_model') != 'gemini-2.5-flash-lite' or
            lock.get('answer_cache_enabled') is not False or
            lock.get('verifier_enabled') is not True or
            lock.get('draft_model_contract') != DRAFT_CONTRACT or
            lock.get('verifier_model') != 'claude-haiku-5-5' or
            lock.get('verifier_contract') != VERIFIER_CONTRACT or
            lock.get('prompt_cache') != 'ANTHROPIC_ROLE_EVIDENCE_PREFIX_5M' or
            lock.get('model_routing_contract') != ROUTING_CONTRACT):
        raise RuntimeError('Production serving policy mismatch')


def load_production():
    if not os.environ.get('K_SERVICE'):
        raise RuntimeError('Production app requires Cloud Run IAM environment')
    lock = json.loads((ROOT/'arm_a_release.json').read_text(encoding='utf-8'))
    for name, sha in lock['file_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest() != sha:
            raise RuntimeError('Production runtime binding mismatch')
    validate_production_policy(lock)
    fallback_enabled = os.environ.get('MOTOMEDIC_CLAUDE_FALLBACK_ENABLED') == 'true'
    if fallback_enabled and lock.get('fallback_enabled') is not True:
        raise RuntimeError('Claude fallback serving activation is not authorized by the exact release')
    from google.cloud import firestore
    from cloud.serving_artifacts import load_index
    index = load_index(lock, ROOT/'build/serving-artifacts')
    registry = ApprovedEvidenceRegistry.load(ROOT, index)
    # Load both pinned query and cross-encoder models once per hosted worker.
    from cloud.grounded_generation.serving_retrieval import GuardedRetriever
    from cloud.arm_a.runtime_controls import TokenBudget, VERSION
    from cloud.grounded_generation.verified_qa import DRAFT_POLICY as POLICY, DRAFT_POLICY_SHA256 as POLICY_SHA256
    from sentence_transformers import SentenceTransformer, CrossEncoder
    packaged = ROOT/'build/index'
    if not (packaged/'embedding_model').is_dir() or not (packaged/'reranker_model').is_dir():
        raise RuntimeError('Pinned query model assets are unavailable')
    inherited_manifest = json.loads((packaged/'manifest.json').read_text(encoding='utf-8'))
    if inherited_manifest['embedding'] != lock['index']['embedding']:
        raise RuntimeError('Inherited query model identity differs from the selected index')
    embedding = SentenceTransformer(str(packaged/'embedding_model'), device='cpu', local_files_only=True)
    reranker = CrossEncoder(str(packaged/'reranker_model'), device='cpu', local_files_only=True)
    retriever = GuardedRetriever(index, rerank=True, embedding_model=embedding, cross_encoder=reranker)
    budget = TokenBudget(retriever.model, retriever.manifest['embedding'],
        POLICY, POLICY_SHA256)
    retriever.install_controls(budget)
    # The owner clarified that A must retain an answer LLM. The historical
    # exact-wording composer is kept only for old regression fixtures.
    from cloud.grounded_generation.verified_qa import Composer
    from cloud.grounded_generation.serving_questions import Questions
    from cloud.grounded_generation.provider import GemmaProvider
    from cloud.grounded_generation.whole_turn_admission import WholeTurnAdmission
    client = firestore.Client(project='motomedic-ai-20261009')
    # Gemma drafting has no demonstrated prompt cache support. The separately
    # selected verifier owns its explicitly bound evidence-prefix cache policy.
    reserve_provider = WholeTurnAdmission(client)
    answer_provider = GemmaProvider(reserve_provider,cache_capability='unsupported')
    # Preparation only: deployment and secret access are separate release scopes.
    # Disabled by default; a quota/schema/source failure never selects this fallback.
    if fallback_enabled:
        from cloud.grounded_generation.claude_provider import ClaudeProvider
        from cloud.grounded_generation.claude_budget import ClaudeBudget
        from cloud.grounded_generation.fallback_provider import FallbackProvider
        if not os.environ.get('ANTHROPIC_API_KEY'):
            raise RuntimeError('Claude fallback requires its server-side secret')
        answer_provider = FallbackProvider(answer_provider,
            ClaudeProvider(reserve_provider,reserve_cost=ClaudeBudget(client)))
    if fallback_enabled:
        raise RuntimeError('The paired public evaluator does not activate availability fallback')
    from cloud.grounded_generation.cached_verifier import CachedVerifier
    from cloud.grounded_generation.claude_budget import ClaudeBudget
    if not os.environ.get('ANTHROPIC_API_KEY'):
        raise RuntimeError('The selected verifier requires its server-side managed secret')
    from cloud.grounded_generation.role_router import production_router,ROUTING_CONTRACT
    model_router=production_router(reserve_provider)
    controlled_composer = Composer(router=model_router)
    state_factory = lambda owner:FirestoreState(client,owner)
    app = create_app(registry, retriever, state_factory, [])
    app.config.update(GROUNDED_PRIMARY=True,SERVING_ARCHITECTURE='DRAFT_VERIFY_STREAM_OPEN_MANUAL_QA',
        ANSWER_PROVIDER='gemini-2.5-flash-lite', VERIFIER_PROVIDER='claude-haiku-5-5',
        PROMPT_CACHE='ANTHROPIC_ROLE_EVIDENCE_PREFIX_5M',
        MODEL_ROUTING_CONTRACT=ROUTING_CONTRACT)
    app.config['ARM_A_RUNTIME_LOCK'] = controlled_composer.config.lock
    secret = os.environ.get('MOTOMEDIC_VISITOR_SECRET')
    if secret:
        from cloud.arm_a.rider_api import install
        from cloud.arm_a.durable_dispatch import configured_dispatcher
        dispatcher = configured_dispatcher()
        app.config['DURABLE_DISPATCH_CONFIGURED'] = dispatcher is not None
        install(app, Questions(registry,retriever,composer=controlled_composer), state_factory, secret,
            network_required=os.environ.get('MOTOMEDIC_PUBLIC_NETWORK_REQUIRED') == 'true',
            dispatcher=dispatcher)
    return app
