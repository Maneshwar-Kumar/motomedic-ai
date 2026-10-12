"""Raw-question HTTP boundary using the existing evidence/answer pipeline."""
import hashlib
import json
import os
import re

from flask import jsonify, request, Response
from cloud.arm_a.visitor import verify
from cloud.arm_a.store import Limited, OperationConflict
from cloud.grounded_generation.feedback import consume_choice
from cloud.grounded_generation.presentation import saved_view
from session_store import SessionConflict
from rider_ui.safeguards import validate_message, LimitError


def install(app, questions, state_factory, visitor_secret, network_required=False, dispatcher=None):
    registry = questions.registry

    def error(route, code, status, terminal=True):
        return jsonify({'type':route, 'error':code, 'technical_content':False,
                        'operation_terminal':terminal}), status

    @app.post('/internal/visitors/reserve')
    def reserve_public_visitor():
        from cloud.arm_a.public_admission import (require_edge_identity, PublicAdmission,
            AdmissionLimited, ProofReplay)
        try:
            require_edge_identity(request.headers, request.environ.get('arm_a_owner'),
                os.environ.get('MOTOMEDIC_EDGE_SERVICE_ACCOUNT'))
        except PermissionError:
            return error('SYSTEM_ERROR', 'EDGE_IDENTITY_REQUIRED', 403)
        if request.mimetype != 'application/json':
            return error('SYSTEM_ERROR', 'JSON_REQUIRED', 415)
        try:
            from cloud.arm_a.app import unique_object
            raw = request.stream.read(1025)
            if len(raw) > 1024:
                return error('SYSTEM_ERROR', 'REQUEST_TOO_LARGE', 413)
            body = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if (type(body) is not dict or set(body) != {'proof_sha256'} or
                    type(body['proof_sha256']) is not str or
                    not re.fullmatch(r'[a-f0-9]{64}', body['proof_sha256'])):
                raise ValueError()
        except (ValueError, TypeError, KeyError, UnicodeError):
            return error('SYSTEM_ERROR', 'INVALID_VISITOR_RESERVATION', 400)
        try:
            store = state_factory(request.environ['arm_a_owner'])
            PublicAdmission(store.client, now=store.now).reserve(body['proof_sha256'])
        except ProofReplay:
            return error('SYSTEM_ERROR', 'VISITOR_PROOF_ALREADY_USED', 409)
        except AdmissionLimited:
            return error('SYSTEM_ERROR', 'VISITOR_CREATION_LIMIT', 429)
        except Exception:
            return error('SYSTEM_ERROR', 'VISITOR_ADMISSION_UNAVAILABLE', 503)
        return jsonify({'ready': True})

    def state():
        owner = verify(visitor_secret, request.headers.get('X-MotoMedic-Visitor'), request.environ['arm_a_owner'])
        network = request.headers.get('X-MotoMedic-Network')
        network_owner = (verify(visitor_secret, network, request.environ['arm_a_owner'])
                         if network_required or network else None)
        store = state_factory(owner)
        store.network_owner = network_owner
        return store

    def current_view(view):
        if getattr(questions,'open_verification',False) and view['response'].get('technical_content'):
            from cloud.grounded_generation.verified_qa import VERSION
            from cloud.grounded_generation.delivery import response_hash
            lock=questions.controller.response_generator.config.lock
            questions.source_authority.check()
            if not registry.source_ready():
                raise ValueError('RECOVERY_SOURCE_IDENTITY_CHANGED')
            binding=view.get('delivery',{})
            verified=view.get('verified_delivery',{})
            if (view.get('runtime_policy')!=VERSION or
                view.get('manual_checksum')!=registry.checksum or
                view.get('index_id')!=registry.index_id or
                verified.get('manual_checksum')!=registry.checksum or
                verified.get('index_id')!=registry.index_id or
                verified.get('source_authority_lock')!=questions.source_authority.lock or
                binding.get('runtime_lock')!=lock or verified.get('runtime_lock')!=lock or
                binding.get('response_sha256')!=response_hash(view) or
                verified.get('operation_id')!=binding.get('operation_id') or
                verified.get('presentation_sha256')!=response_hash(view) or
                verified.get('evidence_payload_sha256')!=binding.get('evidence_payload_sha256') or
                verified.get('binding_sha256')!=binding.get('verification_binding_sha256') or
                verified.get('text_sha256')!=hashlib.sha256(view['response']['natural_language'].encode()).hexdigest()):
                raise ValueError('PRE_VERIFIER_SAVED_ANSWER_RETIRED')
            method = verified.get('verification_method')
            if method == 'COORDINATOR_APPROVED_EXACT_SAFETY_INITIAL_SCOPE':
                # This finite initial response has its own immutable scoped
                # approval. It never represents a model verification verdict.
                questions.check_saved_safety_view(view)
            elif method is not None or view['response'].get('semantic_verification_passed') is not True:
                raise ValueError('PRE_VERIFIER_SAVED_ANSWER_RETIRED')
        return view

    def deliver(view, replay=False):
        current_view(view)
        if 'text/event-stream' not in request.headers.get('Accept',''):
            result = jsonify(view)
        else:
            if getattr(questions, 'open_verification', False):
                from cloud.grounded_generation.delivery import replay_stream
                result = replay_stream(view, view['delivery']['operation_id'])
                if replay:
                    result.headers['X-Operation-Replay'] = 'true'
                return result
            def events():
                response = view['response']
                if response.get('technical_content') and response.get('release_gate_passed'):
                    yield 'event: verified_block\ndata: '+json.dumps({'view':view}, ensure_ascii=False)+'\n\n'
                yield 'event: complete\ndata: '+json.dumps(view, ensure_ascii=False)+'\n\n'
            result = Response(events(), content_type='text/event-stream; charset=utf-8')
            result.headers['X-Accel-Buffering'] = 'no'
        if replay:
            result.headers['X-Operation-Replay'] = 'true'
        return result

    def processing(store, key, operation):
        if operation['state'] == 'QUEUED' and operation.get('dispatch_state') == 'PENDING':
            if dispatcher is None:
                return error('SYSTEM_ERROR','DURABLE_DISPATCH_UNCONFIGURED',503,terminal=False)
            dispatcher.enqueue(store.owner, key, operation['payload_hash'])
            store.mark_dispatched(key)
        if getattr(questions, 'open_verification', False) and 'text/event-stream' in request.headers.get('Accept', ''):
            from cloud.grounded_generation.delivery import stream_operation
            result = stream_operation(lambda: store.operation(key), key, current_view)
            result.headers['X-Operation-Id'] = key
            return result
        return jsonify({'status': 'RUNNING', 'operation_id': key}), 202

    @app.post('/internal/operations/run')
    def durable_worker():
        if not getattr(questions, 'open_verification', False) or dispatcher is None:
            return error('SYSTEM_ERROR', 'DURABLE_DISPATCH_UNCONFIGURED', 503)
        try:
            dispatcher.authenticate(request.headers)
        except PermissionError:
            return error('SYSTEM_ERROR', 'WORKER_IDENTITY_REQUIRED', 403)
        from cloud.arm_a.app import unique_object
        try:
            if request.mimetype != 'application/json':
                raise ValueError()
            raw = request.stream.read(2049)
            if len(raw) > 2048:
                raise ValueError()
            body = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            if (type(body) is not dict or set(body) != {'owner','operation_id','payload_hash'} or
                    not all(type(v) is str for v in body.values()) or
                    not re.fullmatch(r'[a-f0-9]{64}', body['owner']) or
                    not re.fullmatch(r'[a-f0-9]{32}', body['operation_id']) or
                    not re.fullmatch(r'[a-f0-9]{64}', body['payload_hash'])):
                raise ValueError()
        except (ValueError, TypeError, KeyError, UnicodeError):
            return error('SYSTEM_ERROR', 'INVALID_WORKER_REQUEST', 400)
        from cloud.arm_a.durable_dispatch import DurableWorker
        status = DurableWorker(questions, state_factory, current_view).run(
            body['owner'], body['operation_id'], body['payload_hash'])
        return ('', status)

    @app.get('/v1/catalogue')
    def rider_catalogue():
        try:
            state()
        except PermissionError:
            return error('SYSTEM_ERROR','VISITOR_CAPABILITY_REQUIRED',401)
        return jsonify({'schema_version':'motomedic-rider-api-v1',
            'manual_checksum':registry.checksum, 'index_id':registry.index_id,
            'question_input':'open', 'streaming':('DRAFT_VERIFY_STREAM' if getattr(questions,'open_verification',False) else 'VERIFIED_COMPLETE_UNIT_SSE'),
            'question_scope_policy':('ADMITTED_MANUAL_EVIDENCE_GROUNDED_LLM' if hasattr(questions,'feedback') else
                'CONSERVATIVE_REVIEWED_COMPONENT_SCOPE'),
            'diagnostic_wizard':False, 'photos':False,
            'answer_provider':('gemma-4-26b-a4b-it' if hasattr(questions,'feedback') else None)})

    @app.post('/v1/sessions')
    @app.post('/v1/sessions/<session_id>/questions')
    @app.post('/v1/sessions/<session_id>/feedback')
    def rider_question(session_id=None):
        from cloud.arm_a.app import unique_object
        began = False
        try:
            store = state()
        except PermissionError:
            return error('SYSTEM_ERROR','VISITOR_CAPABILITY_REQUIRED',401)
        key = request.headers.get('Idempotency-Key', '')
        if not re.fullmatch(r'[a-f0-9]{32}', key):
            return error('SYSTEM_ERROR','VALID_OPERATION_KEY_REQUIRED',400)
        if request.mimetype != 'application/json':
            return error('SYSTEM_ERROR','JSON_REQUIRED',415)
        try:
            raw = request.stream.read(16385)
            if len(raw)>16384:
                return error('SYSTEM_ERROR','REQUEST_TOO_LARGE',413)
            body = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object,
                parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
            feedback = request.path.endswith('/feedback')
            allowed = ({'expected_version','choice_id','cache_mode'} if feedback else
                       {'query','bike_variant','confirmed_himalayan_bs6','manual_checksum','index_id','cache_mode',
                        'expected_version'} if session_id else
                       {'query','bike_variant','confirmed_himalayan_bs6','manual_checksum','index_id','cache_mode'})
            required = allowed-{'cache_mode'}
            if type(body) is not dict or not required <= body.keys() or body.keys()-allowed:
                raise ValueError()
            if session_id and (not re.fullmatch(r'[a-f0-9]{32}', session_id) or
                               type(body['expected_version']) is not int or body['expected_version']<0):
                raise ValueError()
            if feedback:
                if type(body['choice_id']) is not str:
                    raise ValueError()
            else:
                query = validate_message(body['query'])
                if body['confirmed_himalayan_bs6'] is not True:
                    return error('AMBIGUOUS','BIKE_CONFIRMATION_REQUIRED',400)
                if (body['bike_variant'] != registry.source['variant'] or
                        body['manual_checksum'] != registry.checksum or body['index_id'] != registry.index_id):
                    return error('UNSUPPORTED','SOURCE_OR_VARIANT_MISMATCH',400)
            if body.get('cache_mode','bypass') not in ('bypass','enabled'):
                raise ValueError()
            request.environ['arm_a_cache_enabled'] = (not getattr(questions, 'open_verification', False) and
                body.get('cache_mode','bypass') == 'enabled')
            digest = hashlib.sha256(json.dumps({'path':request.path,'body':body},
                sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        except LimitError as exc:
            return error('SYSTEM_ERROR',exc.reason,exc.status)
        except (ValueError, TypeError, KeyError, UnicodeError):
            return error('SYSTEM_ERROR','INVALID_REQUEST',400)
        try:
            # Replay is operation-scoped and remains recoverable for its full
            # lifetime even when the conversation's idle deadline has elapsed.
            try:
                existing=store.operation(key)
            except KeyError:
                existing=None
            if existing:
                if existing['payload_hash']!=digest:
                    raise OperationConflict()
                if existing['state']=='COMPLETE':
                    return deliver(existing['view'],replay=True)
                if existing['state']=='FAILED':
                    return error('SYSTEM_ERROR',existing['error'],existing['http_status'])
                return processing(store, key, existing)
            old = store.saved(session_id) if session_id else None
            if old and old['version'] != body['expected_version']:
                raise SessionConflict('Stale session')
            if old and old.get('accepted_turns',0)>=20:
                raise Limited()
            session = store.load(session_id) if session_id else questions.new_session()
            if old and session.version!=old['version']:
                raise SessionConflict('Concurrent session')
            if feedback:
                outcome, fact = consume_choice(registry,session,old['choices'],body['choice_id'],body['expected_version'])
            work = None
            if getattr(questions, 'open_verification', False):
                if dispatcher is None:
                    return error('SYSTEM_ERROR','DURABLE_DISPATCH_UNCONFIGURED',503)
                from cloud.arm_a.durable_dispatch import make_work
                current = questions.controller.feedback(session,outcome,key,fact=fact) if feedback else session
                work = make_work(current, old['query'] if feedback else query,
                    (old or {}).get('conversation', []), old['version'] if old else None, questions)
            prior = store.begin(key,digest,work=work) if work is not None else store.begin(key,digest)
            began = prior is None
            if prior:
                if prior['state']=='COMPLETE':
                    return deliver(prior['view'], replay=True)
                if prior['state']=='FAILED':
                    return error('SYSTEM_ERROR',prior['error'],prior['http_status'])
                return processing(store, key, prior)
            if getattr(questions, 'open_verification', False):
                return processing(store, key, store.operation(key))
            if feedback:
                session = questions.controller.feedback(session,outcome,key,fact=fact)
                if hasattr(questions,'feedback'):
                    session,view,choices=questions.feedback(session,old['query'])
                else:
                    session,response,_ = questions.controller.next(session,old['query'])
                    view, choices = saved_view(registry,session,response)
                query = old['query']
            else:
                session,view,choices = questions.answer(session,query)
            view = store.commit_answer(key,session,view,choices,
                expected_version=old['version'] if old else None,query=query)
            return deliver(view)
        except KeyError:
            return error('SYSTEM_ERROR','SESSION_NOT_FOUND',404)
        except Limited:
            return error('SYSTEM_ERROR','APPLICATION_USAGE_LIMIT',429)
        except (SessionConflict,OperationConflict,ValueError):
            if began and not getattr(questions, 'open_verification', False):
                try:
                    store.fail_operation(key,'OPERATION_OR_SESSION_CONFLICT',409)
                except Exception:
                    pass
            return error('SYSTEM_ERROR','OPERATION_OR_SESSION_CONFLICT',409)
        except Exception:
            # An uncertain commit may already have completed. Keep it recoverable
            # rather than declaring it failed or automatically running it again.
            return error('SYSTEM_ERROR','OPERATION_NOT_COMMITTED',503,terminal=False)

    @app.get('/v1/sessions/<session_id>')
    def rider_saved(session_id):
        if not re.fullmatch(r'[a-f0-9]{32}',session_id):
            return error('SYSTEM_ERROR','INVALID_SESSION_KEY',400)
        try:
            return jsonify(current_view(state().saved(session_id)['view']))
        except PermissionError:
            return error('SYSTEM_ERROR','VISITOR_CAPABILITY_REQUIRED',401)
        except KeyError:
            return error('SYSTEM_ERROR','SESSION_NOT_FOUND',404)
        except Exception:
            return error('SYSTEM_ERROR','SESSION_STORE_UNAVAILABLE',503)

    @app.get('/v1/operations/<key>')
    def rider_operation(key):
        if not re.fullmatch(r'[a-f0-9]{32}',key):
            return error('SYSTEM_ERROR','INVALID_OPERATION_KEY',400)
        try:
            store = state()
            result = store.operation(key)
            if result['state']=='FAILED':
                return error('SYSTEM_ERROR',result['error'],result['http_status'])
            if result['state']=='COMPLETE':
                return (deliver(result['view'], replay=True) if getattr(questions, 'open_verification', False)
                        else jsonify(current_view(result['view'])))
            return processing(store, key, result)
        except PermissionError:
            return error('SYSTEM_ERROR','VISITOR_CAPABILITY_REQUIRED',401)
        except KeyError:
            return error('SYSTEM_ERROR','OPERATION_NOT_FOUND',404)
        except Exception:
            return error('SYSTEM_ERROR','OPERATION_STORE_UNAVAILABLE',503)
