"""Progress is operational; answer streaming reads only the committed buffer."""
from copy import deepcopy
import hashlib
import json
import time
from flask import Response

STAGES = {'retrieving', 'drafting', 'verifying', 'displaying'}
EVENT_PROTOCOL = 'operation-sequence-v1'


def response_hash(view):
    return hashlib.sha256(json.dumps(view['response'], sort_keys=True,
        separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()


def bind_view(view, operation_id, runtime_lock):
    result = deepcopy(view)
    verified = result.get('verified_delivery')
    if result['response'].get('release_gate_passed'):
        if (not verified or verified.get('operation_id') != operation_id or
            verified.get('runtime_lock') != runtime_lock or
            verified.get('manual_checksum') != result['manual_checksum'] or
            verified.get('index_id') != result['index_id'] or
            verified.get('presentation_sha256') != response_hash(result) or
            not verified.get('evidence_payload_sha256') or not verified.get('binding_sha256') or
            verified.get('text_sha256') != hashlib.sha256(result['response']['natural_language'].encode()).hexdigest()):
            raise ValueError('VERIFIED_OPERATION_BINDING_CHANGED')
    result['delivery'] = {'operation_id': operation_id,
        'response_sha256': response_hash(result), 'runtime_lock': runtime_lock,
        'manual_checksum': result['manual_checksum'], 'index_id': result['index_id'],
        'evidence_payload_sha256': (verified or {}).get('evidence_payload_sha256'),
        'verification_binding_sha256': (verified or {}).get('binding_sha256'),
        'event_protocol': EVENT_PROTOCOL}
    return result


def accepted_events(view, operation_id, start_sequence=0):
    binding = view.get('delivery', {})
    if (binding.get('operation_id') != operation_id or
        binding.get('response_sha256') != response_hash(view) or
        binding.get('manual_checksum') != view['manual_checksum'] or
        binding.get('index_id') != view['index_id']):
        raise ValueError('DELIVERY_BINDING_CHANGED')
    body = view['response']
    sequenced = binding.get('event_protocol') == EVENT_PROTOCOL
    sequence = start_sequence
    def event(kind, value):
        nonlocal sequence
        sequence += 1
        if sequenced:
            if kind == 'complete':
                value = {'view': value, 'operation_id': operation_id,
                         'response_sha256': binding['response_sha256']}
            value = {**value, 'sequence': sequence}
        return kind, value
    if body.get('release_gate_passed'):
        verified=view.get('verified_delivery',{})
        if (verified.get('operation_id')!=operation_id or
            verified.get('presentation_sha256')!=response_hash(view) or
            verified.get('runtime_lock')!=binding.get('runtime_lock') or
            verified.get('evidence_payload_sha256')!=binding.get('evidence_payload_sha256') or
            verified.get('binding_sha256')!=binding.get('verification_binding_sha256') or
            verified.get('text_sha256')!=hashlib.sha256(body['natural_language'].encode()).hexdigest()):
            raise ValueError('ACCEPTED_BUFFER_BINDING_CHANGED')
        if body['type'] == 'SYSTEM_ERROR':
            raise ValueError('INVALID_ACCEPTED_SYSTEM_ERROR')
        yield event('progress', {'operation_id': operation_id, 'stage': 'displaying'})
        yield event('verified_block', {'operation_id': operation_id,
            'response_sha256': binding['response_sha256'], 'view': view})
        text = body['natural_language']
        for offset in range(0, len(text), 96):
            yield event('answer_chunk', {'operation_id': operation_id,
                'response_sha256': binding['response_sha256'],
                'offset': offset, 'text': text[offset:offset+96]})
    elif body.get('technical_content'):
        raise ValueError('UNVERIFIED_TECHNICAL_DELIVERY')
    yield event('complete', view)


def stream_operation(read_operation, operation_id, validate_saved=lambda view: view,
                     *, poll_seconds=1, max_seconds=150, clock=time.monotonic, pause=time.sleep):
    """Read durable progress and accepted buffers; never start provider work.

    Cloud Tasks owns the worker lifetime. Disconnecting or exhausting this
    bounded observation window has no effect on execution or saved recovery.
    """
    def events():
        sequence = 0
        deadline = clock()+max_seconds
        heartbeat = clock()+5
        try:
            while clock() < deadline:
                operation = read_operation()
                for row in operation.get('progress', []):
                    if row['sequence'] <= sequence:
                        continue
                    if row['sequence'] != sequence+1 or row['stage'] not in STAGES-{'displaying'}:
                        raise ValueError('INVALID_DURABLE_PROGRESS')
                    sequence = row['sequence']
                    yield encode('progress', {'operation_id': operation_id,
                        'stage': row['stage'], 'sequence': sequence})
                if operation['state'] == 'COMPLETE':
                    saved = validate_saved(operation['view'])
                    for kind, value in accepted_events(saved, operation_id, sequence):
                        yield encode(kind, value)
                    return
                if operation['state'] == 'FAILED':
                    yield encode('error', {'type': 'SYSTEM_ERROR',
                        'error': operation['error'], 'technical_content': False,
                        'operation_terminal': True, 'operation_id': operation_id, 'sequence': sequence+1})
                    return
                if clock() >= heartbeat:
                    yield ': keepalive\n\n'
                    heartbeat = clock()+5
                pause(poll_seconds)
            yield encode('error', {'type': 'SYSTEM_ERROR', 'error': 'OPERATION_STILL_PROCESSING',
                'technical_content': False, 'operation_terminal': False,
                'operation_id': operation_id, 'sequence': sequence+1})
        except Exception:
            yield encode('error', {'type': 'SYSTEM_ERROR', 'error': 'OPERATION_STORE_UNAVAILABLE',
                'technical_content': False, 'operation_terminal': False,
                'operation_id': operation_id, 'sequence': sequence+1})
    return sse_response(events())


def encode(event, body):
    return 'event: '+event+'\ndata: '+json.dumps(body, ensure_ascii=False, allow_nan=False)+'\n\n'


def sse_response(events):
    response = Response(events, content_type='text/event-stream; charset=utf-8')
    response.headers['X-Accel-Buffering'] = 'no'
    return response


def replay_stream(view, operation_id):
    return sse_response(encode(kind, body) for kind, body in accepted_events(view, operation_id))
