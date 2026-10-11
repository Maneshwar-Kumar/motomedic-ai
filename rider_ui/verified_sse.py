"""Bounded complete-unit SSE reader for the rider API; no raw token rendering.

The rider service must include a full API-v1 saved view in verified_block.view.
This reader is not compatible with the initial-only Arm A endpoint.
"""
import codecs
import json

from rider_ui.client import APIError, MAX_BYTES, validate_view


def read_verified_stream(chunks, on_verified=None):
    """Validate a whole saved view before publishing; require terminal parity.

    Caller keeps the idempotent operation pending until this function returns.
    A disconnect after a valid unit may be recovered, never rerun automatically.
    """
    decoder = codecs.getincrementaldecoder('utf-8')('strict')
    text, total, verified, complete = '', 0, None, None

    def event(frame):
        nonlocal verified, complete
        fields = {}
        for line in frame.splitlines():
            if not line or line.startswith(':'):
                continue
            name, separator, value = line.partition(':')
            if not separator or name not in ('event', 'data') or name in fields:
                raise APIError('The service stream could not be verified. Retrieve the saved result.')
            fields[name] = value.lstrip(' ')
        if not fields:
            return
        if set(fields) != {'event', 'data'} or complete is not None:
            raise APIError('The service stream could not be verified. Retrieve the saved result.')
        try:
            data = json.loads(fields['data'])
        except (ValueError, RecursionError):
            raise APIError('The service stream could not be verified. Retrieve the saved result.') from None
        if fields['event'] == 'verified_block':
            if verified is not None or type(data) is not dict or set(data) != {'view'}:
                raise APIError('The service stream could not be verified. Retrieve the saved result.')
            verified = validate_view(data['view'])
            response = verified['response']
            if (response['type'] not in {'SUPPORTED', 'SAFETY_STOP'} or
                    response.get('release_gate_passed') is not True or
                    response.get('technical_content') is not True):
                raise APIError('The streamed answer has not passed the display gate.')
            if on_verified:
                on_verified(verified)
        elif fields['event'] == 'complete':
            complete = validate_view(data)
            if verified is not None and verified != complete:
                raise APIError('The service stream changed. Retrieve the saved result.')
            response = complete['response']
            if (response['type'] in {'SUPPORTED', 'SAFETY_STOP'} and
                    response.get('technical_content') is True and verified is None):
                raise APIError('The service did not deliver a verified answer unit.')
        elif fields['event'] == 'error':
            raise APIError('The service could not complete this request. Retrieve its saved result.')
        else:
            raise APIError('The service returned an unsupported stream event.')

    try:
        for chunk in chunks:
            if type(chunk) is not bytes or not chunk:
                raise APIError('The service stream was interrupted. Retrieve the saved result.')
            total += len(chunk)
            if total > MAX_BYTES:
                raise APIError('The service stream exceeded the display limit.')
            text = (text + decoder.decode(chunk)).replace('\r\n', '\n')
            while '\n\n' in text:
                frame, text = text.split('\n\n', 1)
                event(frame)
        text += decoder.decode(b'', final=True)
    except UnicodeError:
        raise APIError('The service stream was interrupted. Retrieve the saved result.') from None
    if text.strip() or complete is None:
        raise APIError('The service stream was interrupted. Retrieve the saved result.')
    return complete
