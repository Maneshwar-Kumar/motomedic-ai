"""Progress is operational; answer streaming reads only the committed buffer."""
from copy import deepcopy
import hashlib
import json
from queue import Queue
from threading import Thread
import time
from flask import Response

STAGES = {'retrieving', 'drafting', 'verifying', 'displaying'}


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
        'verification_binding_sha256': (verified or {}).get('binding_sha256')}
    return result


def accepted_events(view, operation_id):
    binding = view.get('delivery', {})
    if (binding.get('operation_id') != operation_id or
        binding.get('response_sha256') != response_hash(view) or
        binding.get('manual_checksum') != view['manual_checksum'] or
        binding.get('index_id') != view['index_id']):
        raise ValueError('DELIVERY_BINDING_CHANGED')
    body = view['response']
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
        yield ('progress', {'operation_id': operation_id, 'stage': 'displaying'})
        yield ('verified_block', {'operation_id': operation_id,
            'response_sha256': binding['response_sha256'], 'view': view})
        text = body['natural_language']
        for offset in range(0, len(text), 96):
            yield ('answer_chunk', {'operation_id': operation_id,
                'response_sha256': binding['response_sha256'],
                'offset': offset, 'text': text[offset:offset+96]})
    elif body.get('technical_content'):
        raise ValueError('UNVERIFIED_TECHNICAL_DELIVERY')
    yield ('complete', view)


def stream_operation(work, operation_id):
    """work emits stage IDs, returns the DURABLY SAVED view; no drafts accepted.

    The independent worker continues to commit on a client disconnect. The
    bounded queue holds at most a handful of stage events plus the saved view;
    operation recovery never initiates generation again.
    """
    messages = Queue()
    def progress(stage):
        if stage not in STAGES or stage == 'displaying':
            raise ValueError('INVALID_PRIVATE_PROGRESS_STAGE')
        messages.put(('progress', {'operation_id': operation_id, 'stage': stage}))
    def run():
        try:
            messages.put(('saved', work(progress)))
        except Exception:
            messages.put(('error', {'type': 'SYSTEM_ERROR',
                'error': 'OPERATION_NOT_COMMITTED', 'technical_content': False,
                'operation_terminal': False, 'operation_id': operation_id}))
    def events():
        # Start only when the response is consumed, after all admission checks.
        Thread(target=run, daemon=True).start()
        while True:
            kind, body = messages.get()
            if kind == 'saved':
                try:
                    for event, value in accepted_events(body, operation_id):
                        yield encode(event, value)
                except Exception:
                    yield encode('error', {'type': 'SYSTEM_ERROR',
                        'error': 'DELIVERY_BINDING_CHANGED', 'technical_content': False,
                        'operation_terminal': False, 'operation_id': operation_id})
                return
            yield encode(kind, body)
            if kind == 'error':
                return
    return sse_response(events())


def encode(event, body):
    return 'event: '+event+'\ndata: '+json.dumps(body, ensure_ascii=False, allow_nan=False)+'\n\n'


def sse_response(events):
    response = Response(events, content_type='text/event-stream; charset=utf-8')
    response.headers['X-Accel-Buffering'] = 'no'
    return response


def replay_stream(view, operation_id):
    return sse_response(encode(kind, body) for kind, body in accepted_events(view, operation_id))
