"""Private UI-only visitor issuance and persistent public proof quotas.

Cloud Run IAM must authenticate the selected request header before this module
is used. This adds an exact service-identity restriction; it is not a standalone
JWT verifier. No cookies, client IPs, proof tokens or rider text are stored.
"""
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
import math
import re
import time

VERSION = 'public-visitor-issuance-v1'
GLOBAL_DOCUMENT = 'public-visitor-global-v1'
MINUTE_LIMIT = 10
DAY_LIMIT = 60
PROOF_SECONDS = 180


class AdmissionLimited(Exception):
    pass


class ProofReplay(Exception):
    pass


class AdmissionUnavailable(Exception):
    pass


def require_edge_identity(headers, platform_owner, service_account, now=None):
    """Restrict an already platform-authenticated caller to the configured UI."""
    if (type(service_account) is not str or
            not re.fullmatch(r'[A-Za-z0-9_.-]+@[A-Za-z0-9.-]+\.iam\.gserviceaccount\.com', service_account) or
            type(platform_owner) is not str or not re.fullmatch(r'[a-f0-9]{64}', platform_owner)):
        raise PermissionError()
    value = headers.get('X-Serverless-Authorization') or headers.get('Authorization', '')
    scheme, separator, token = value.partition(' ')
    if not separator or scheme.casefold() != 'bearer' or len(value) > 16000:
        raise PermissionError()
    try:
        parts = token.split('.')
        if len(parts) != 3:
            raise ValueError()
        claims = json.loads(base64.urlsafe_b64decode(parts[1]+'='*(-len(parts[1])%4)))
        clock = now if now is not None else time.time()
        if (type(claims) is not dict or claims.get('email') != service_account or
                claims.get('email_verified') is not True or
                claims.get('iss') not in ('https://accounts.google.com', 'accounts.google.com') or
                type(claims.get('exp')) not in (int, float) or not math.isfinite(claims['exp']) or
                claims['exp'] <= clock or type(claims.get('sub')) is not str or
                not 1 <= len(claims['sub']) <= 200):
            raise ValueError()
        expected = hashlib.sha256(('motomedic-arm-a-initial-v1:'+claims['sub']).encode()).hexdigest()
        if not hmac.compare_digest(platform_owner, expected):
            raise ValueError()
    except Exception:
        raise PermissionError() from None


class PublicAdmission:
    def __init__(self, client, now=None):
        self.client = client
        self.now = now or (lambda: datetime.now(timezone.utc))

    def reserve(self, proof_sha256):
        if type(proof_sha256) is not str or not re.fullmatch(r'[a-f0-9]{64}', proof_sha256):
            raise ValueError('INVALID_PROOF_HASH')
        from google.cloud import firestore
        global_ref = self.client.collection('arm_a_usage').document(GLOBAL_DOCUMENT)
        proof_ref = self.client.collection('arm_a_usage').document('public-visitor-proof-'+proof_sha256)

        @firestore.transactional
        def transaction(tx):
            now = self.now()
            global_snapshot = global_ref.get(transaction=tx)
            proof_snapshot = proof_ref.get(transaction=tx)
            if proof_snapshot.exists:
                raise ProofReplay()
            previous = global_snapshot.to_dict() if global_snapshot.exists else {}
            if previous and (previous.get('version') != VERSION or
                    previous.get('minute_limit') != MINUTE_LIMIT or previous.get('day_limit') != DAY_LIMIT):
                raise AdmissionUnavailable()
            times = previous.get('visitor_issues', [])
            if type(times) is not list or any(not isinstance(t, datetime) or t.tzinfo is None or t > now for t in times):
                raise AdmissionUnavailable()
            times = [t for t in times if t > now-timedelta(hours=24)]
            if len(times) >= DAY_LIMIT or sum(t > now-timedelta(minutes=1) for t in times) >= MINUTE_LIMIT:
                raise AdmissionLimited()
            tx.set(global_ref, {'version': VERSION, 'minute_limit': MINUTE_LIMIT,
                'day_limit': DAY_LIMIT, 'visitor_issues': times+[now],
                'expires_at': now+timedelta(hours=24)})
            tx.create(proof_ref, {'version': VERSION, 'spent': True,
                'expires_at': now+timedelta(seconds=PROOF_SECONDS)})

        try:
            transaction(self.client.transaction())
        except (ProofReplay, AdmissionLimited, AdmissionUnavailable):
            raise
        except Exception:
            raise AdmissionUnavailable() from None
