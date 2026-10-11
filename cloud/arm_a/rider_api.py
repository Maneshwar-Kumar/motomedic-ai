"""Raw-question HTTP boundary using the existing evidence/answer pipeline."""
import hashlib
import json
import re

from flask import jsonify, request, Response
from cloud.arm_a.visitor import verify
from cloud.arm_a.store import Limited, OperationConflict
from cloud.arm_a.rider_contract import saved_view, consume_choice
from session_store import SessionConflict
from rider_ui.safeguards import validate_message, LimitError


def install(app, questions, state_factory, visitor_secret):
    registry = questions.registry

    def error(route, code, status, terminal=True):
        return jsonify({'type':route, 'error':code, 'technical_content':False,
                        'operation_terminal':terminal}), status

    def state():
        owner = verify(visitor_secret, request.headers.get('X-MotoMedic-Visitor'), request.environ['arm_a_owner'])
        return state_factory(owner)

    def deliver(view, replay=False):
        if 'text/event-stream' not in request.headers.get('Accept',''):
            result = jsonify(view)
        else:
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

    @app.get('/v1/catalogue')
    def rider_catalogue():
        try:
            state()
        except PermissionError:
            return error('SYSTEM_ERROR','VISITOR_CAPABILITY_REQUIRED',401)
        return jsonify({'schema_version':'motomedic-rider-api-v1',
            'manual_checksum':registry.checksum, 'index_id':registry.index_id,
            'question_input':'open', 'streaming':'VERIFIED_COMPLETE_UNIT_SSE',
            'question_scope_policy':questions.descriptors and 'CONSERVATIVE_REVIEWED_COMPONENT_SCOPE',
            'diagnostic_wizard':False, 'photos':False, 'provider_calls':0})

    @app.post('/v1/sessions')
    @app.post('/v1/sessions/<session_id>/questions')
    @app.post('/v1/sessions/<session_id>/feedback')
    def rider_question(session_id=None):
        from cloud.arm_a.app import unique_object
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
            if body.get('cache_mode','bypass') != 'bypass':
                raise ValueError()
            digest = hashlib.sha256(json.dumps({'path':request.path,'body':body},
                sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        except (ValueError, TypeError, KeyError, UnicodeError, LimitError):
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
                return jsonify({'status':'RUNNING','operation_id':key}),202
            old = store.saved(session_id) if session_id else None
            if old and old['version'] != body['expected_version']:
                raise SessionConflict('Stale session')
            if old and old.get('accepted_turns',0)>=20:
                raise Limited()
            session = store.load(session_id) if session_id else questions.new_session()
            if old and session.version!=old['version']:
                raise SessionConflict('Concurrent session')
            if feedback:
                outcome, fact = consume_choice(session,old['choices'],body['choice_id'],body['expected_version'])
            prior = store.begin(key,digest)
            if prior:
                if prior['state']=='COMPLETE':
                    return deliver(prior['view'], replay=True)
                if prior['state']=='FAILED':
                    return error('SYSTEM_ERROR',prior['error'],prior['http_status'])
                return jsonify({'status':'RUNNING','operation_id':key}),202
            if feedback:
                session = questions.controller.feedback(session,outcome,key,fact=fact)
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
            return jsonify(state().saved(session_id)['view'])
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
            result = state().operation(key)
            if result['state']=='FAILED':
                return error('SYSTEM_ERROR',result['error'],result['http_status'])
            return jsonify(result['view']) if result['state']=='COMPLETE' else (
                jsonify({'status':'RUNNING','operation_id':key}),202)
        except PermissionError:
            return error('SYSTEM_ERROR','VISITOR_CAPABILITY_REQUIRED',401)
        except KeyError:
            return error('SYSTEM_ERROR','OPERATION_NOT_FOUND',404)
        except Exception:
            return error('SYSTEM_ERROR','OPERATION_STORE_UNAVAILABLE',503)
