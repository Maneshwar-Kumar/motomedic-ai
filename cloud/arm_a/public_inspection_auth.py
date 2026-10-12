"""Verify application identity when anonymous service inspection is enabled.

Health is public; every other request keeps Google signature/audience validation
before the existing visitor, edge and Tasks identity restrictions. No model calls.
"""
import json
import base64
import os
import re
import threading
import time
from urllib.parse import urlsplit

FLAG = 'MOTOMEDIC_PUBLIC_INSPECTION_ENABLED'
AUDIENCE = 'MOTOMEDIC_SERVICE_AUDIENCE'
CALLERS = 'MOTOMEDIC_SERVICE_ALLOWED_CALLERS'
_CERT_URL = 'https://www.googleapis.com/oauth2/v1/certs'
_lock = threading.RLock()
_cached = [None, 0]


def enabled():
    value = os.environ.get(FLAG, 'false').strip().lower()
    if value not in ('true', 'false'):
        raise PermissionError('INSPECTION_CONFIGURATION_INVALID')
    return value == 'true'


class CertificateRequest:
    def __call__(self, url, method='GET', **kwargs):
        if url != _CERT_URL or method != 'GET':
            raise PermissionError('CERTIFICATE_ENDPOINT_INVALID')
        with _lock:
            if _cached[0] is not None and time.monotonic() < _cached[1]:
                return _cached[0]
            from google.auth.transport.requests import Request
            kwargs['timeout'] = 10
            response = Request()(url=url, method=method, **kwargs)
            if response.status == 200:
                _cached[:] = [response, time.monotonic() + 300]
            return response


def verify_request(headers):
    """Accept the complete Authorization JWT, never a stripped alternate header."""
    audience = os.environ.get(AUDIENCE, '')
    parsed = urlsplit(audience)
    if (parsed.scheme != 'https' or not parsed.hostname or
            not parsed.hostname.endswith('.run.app') or parsed.path or
            parsed.username or parsed.password or parsed.query or parsed.fragment):
        raise PermissionError('INSPECTION_AUDIENCE_REQUIRED')
    allowed = os.environ.get(CALLERS, '').split(',')
    if (not 1 <= len(allowed) <= 10 or len(set(allowed)) != len(allowed) or
            any(not re.fullmatch(r'[A-Za-z0-9_.-]+@[A-Za-z0-9.-]+\.iam\.gserviceaccount\.com', email) for email in allowed)):
        raise PermissionError('EXACT_SERVICE_CALLERS_REQUIRED')
    value = headers.get('Authorization', '')
    scheme, separator, token = value.partition(' ')
    if (not separator or scheme.casefold() != 'bearer' or len(value) > 16000 or
            not re.fullmatch(r'[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', token)):
        raise PermissionError('SIGNED_IDENTITY_REQUIRED')
    try:
        from google.oauth2.id_token import verify_oauth2_token
        claims = verify_oauth2_token(token, CertificateRequest(), audience=audience)
        raw = json.loads(base64.urlsafe_b64decode(token.split('.')[1] + '=' * (-len(token.split('.')[1]) % 4)))
        if (type(claims) is not dict or type(raw) is not dict or raw != claims or
                claims.get('iss') not in ('https://accounts.google.com', 'accounts.google.com') or
                claims.get('aud') != audience or claims.get('email') not in allowed or
                claims.get('email_verified') is not True or type(claims.get('sub')) is not str or
                not 1 <= len(claims['sub']) <= 200):
            raise ValueError()
        return token
    except Exception:
        raise PermissionError('VERIFIED_IDENTITY_REQUIRED') from None
