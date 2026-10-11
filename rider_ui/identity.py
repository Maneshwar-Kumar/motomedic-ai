"""Signed ephemeral visitor capability, separate from platform IAM identity."""
import hashlib
import hmac
import re
import secrets
import time
import base64
import json
import math


def issue(secret, now=None, principal=None):
    if len(secret.encode()) < 32:
        raise ValueError('Visitor signing secret is not configured')
    nonce = (hmac.new(secret.encode(),('visitor:'+principal).encode(),hashlib.sha256).hexdigest()
             if principal else secrets.token_hex(32))
    body = nonce+'.'+str(int(now if now is not None else time.time())+86400)
    return body+'.'+hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()


def verify(secret, capability, principal, now=None):
    if (type(secret) is not str or len(secret.encode())<32 or type(capability) is not str or
            not re.fullmatch(r'[a-f0-9]{64}\.[0-9]{10}\.[a-f0-9]{64}', capability)):
        raise PermissionError('VISITOR_CAPABILITY_REQUIRED')
    nonce, expiry, signature = capability.split('.')
    clock = now if now is not None else time.time()
    if not clock < int(expiry) <= clock+86400:
        raise PermissionError('VISITOR_CAPABILITY_EXPIRED')
    body = nonce+'.'+expiry
    expected = hmac.new(secret.encode(), body.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise PermissionError('VISITOR_CAPABILITY_INVALID')
    return hashlib.sha256(('motomedic-rider-v1:'+principal+':'+nonce).encode()).hexdigest()


def cloud_run_token(audience):
    """Fetch an audience-bound identity using the UI's managed service account."""
    from google.auth.transport.requests import Request
    from google.oauth2.id_token import fetch_id_token
    return fetch_id_token(Request(), audience)


def platform_subject(headers):
    """Only for the private IAM-protected UI, after Cloud Run verifies ingress.

    It must not be used on an unauthenticated UI deployment. Stable keyed visitor
    IDs preserve admission counters across refreshes/new conversations.
    """
    value = headers.get('X-Serverless-Authorization') or headers.get('Authorization','')
    scheme, separator, token = value.partition(' ')
    if not separator or scheme.casefold()!='bearer' or len(value)>16000:
        raise PermissionError('Private UI identity is required')
    parts=token.split('.')
    if len(parts)!=3:
        raise PermissionError('Private UI identity is required')
    try:
        body=json.loads(base64.urlsafe_b64decode(parts[1]+'='*(-len(parts[1])%4)))
    except Exception:
        raise PermissionError('Private UI identity is required') from None
    if (type(body) is not dict or body.get('iss') not in ('https://accounts.google.com','accounts.google.com') or
            type(body.get('exp')) not in (int,float) or not math.isfinite(body['exp']) or not time.time()<body['exp'] or
            type(body.get('sub')) is not str or not 1<=len(body['sub'])<=200):
        raise PermissionError('Private UI identity is required')
    return body['sub']
