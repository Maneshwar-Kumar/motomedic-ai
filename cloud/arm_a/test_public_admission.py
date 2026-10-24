"""Synthetic private visitor-admission boundaries; no clouds/providers/secrets."""
import base64
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import hashlib
import json
import sys
import threading
import time
import types
import unittest
from unittest.mock import patch

from cloud.arm_a.app import create_app
from cloud.arm_a.rider_api import install
from cloud.arm_a.store import FirestoreState
from cloud.arm_a.test_store import Client, Ref, transactional
from cloud.arm_a.public_admission import (PublicAdmission, require_edge_identity,
    AdmissionLimited, ProofReplay, AdmissionUnavailable, GLOBAL_DOCUMENT)

UI = 'motomedic-rider-ui@motomedic-ai-20261009.iam.gserviceaccount.com'
TASK = 'motomedic-answer-task@motomedic-ai-20261009.iam.gserviceaccount.com'


def token(email=UI, subject='synthetic-ui', **changes):
    # Cloud Run platform verification is simulated, not provided by this JWT.
    claims={'iss':'https://accounts.google.com','sub':subject,'email':email,
        'email_verified':True,'exp':time.time()+3600}
    claims.update(changes)
    body=base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')
    return 'synthetic.'+body+'.platform-verified-fixture'


def proof(value):
    return hashlib.sha256(('synthetic-proof:'+str(value)).encode()).hexdigest()


class PublicAdmissionTests(unittest.TestCase):
    def setUp(self):
        google=types.ModuleType('google');cloud=types.ModuleType('google.cloud')
        firestore=types.ModuleType('google.cloud.firestore');firestore.transactional=transactional
        cloud.firestore=firestore;google.cloud=cloud
        modules=patch.dict(sys.modules,{'google':google,'google.cloud':cloud,'google.cloud.firestore':firestore})
        modules.start();self.addCleanup(modules.stop)
        settings=patch.dict('os.environ',{'MOTOMEDIC_EDGE_SERVICE_ACCOUNT':UI})
        settings.start();self.addCleanup(settings.stop)
        self.database=Client();self.now=datetime(2026,10,12,tzinfo=timezone.utc)
        self.admission=PublicAdmission(self.database,now=lambda:self.now)
        source=types.SimpleNamespace(checksum='synthetic-manual',index_id='synthetic-index',variant='Himalayan BS6')
        factory=lambda owner:FirestoreState(self.database,owner,now=lambda:self.now)
        self.app=create_app(source)
        install(self.app,types.SimpleNamespace(source=source),factory,'s'*32)
        self.http=self.app.test_client()

    def reserve(self,value=1,credential=None,raw=None,headers=None):
        selected={'Authorization':'Bearer '+(credential or token()),'Content-Type':'application/json'}
        selected.update(headers or {})
        return self.http.post('/internal/visitors/reserve',
            data=raw if raw is not None else json.dumps({'proof_sha256':proof(value)}),headers=selected)

    def test_exact_ui_identity_returns_only_ready_and_private_headers(self):
        response=self.reserve()
        self.assertEqual(response.status_code,200);self.assertEqual(response.json,{'ready':True})
        self.assertEqual(response.headers['Cache-Control'],'no-store')
        self.assertNotIn('Set-Cookie',response.headers)
        global_body=self.database.data['arm_a_usage/'+GLOBAL_DOCUMENT]
        self.assertEqual(global_body['visitor_issues'],[self.now])
        self.assertEqual(global_body['expires_at'],self.now+timedelta(hours=24))
        spent=self.database.data['arm_a_usage/public-visitor-proof-'+proof(1)]
        self.assertEqual(spent['expires_at'],self.now+timedelta(minutes=3))
        self.assertEqual(set(spent),{'version','spent','expires_at'})
        self.assertNotIn('synthetic-ui',json.dumps(self.database.data,default=str))

    def test_task_or_other_iam_caller_cannot_create_visitor(self):
        for credential in (token(TASK,'synthetic-task'),token('other@project.iam.gserviceaccount.com'),
                token(email_verified=False),token(email=None)):
            with self.subTest(credential_kind=credential.split('.')[0]):
                response=self.reserve(credential=credential)
                self.assertEqual(response.status_code,403);self.assertFalse(self.database.data)

    def test_missing_configuration_and_unauthenticated_requests_fail_closed(self):
        with patch.dict('os.environ',{'MOTOMEDIC_EDGE_SERVICE_ACCOUNT':''}):
            self.assertEqual(self.reserve().status_code,403)
        response=self.http.post('/internal/visitors/reserve',json={'proof_sha256':proof(1)})
        self.assertEqual(response.status_code,401);self.assertFalse(self.database.data)

    def test_platform_verified_header_precedes_client_authorization(self):
        response=self.reserve(headers={'X-Serverless-Authorization':'Bearer '+token(TASK,'task')})
        self.assertEqual(response.status_code,403);self.assertFalse(self.database.data)
        response=self.reserve(credential=token(TASK,'task'),
            headers={'X-Serverless-Authorization':'Bearer '+token()})
        self.assertEqual(response.status_code,200)

    def test_owner_must_match_the_authenticated_claims(self):
        with self.assertRaises(PermissionError):
            require_edge_identity({'Authorization':'Bearer '+token()},'f'*64,UI)

    def test_strict_payload_rejects_duplicates_extra_keys_types_and_invalid_hash(self):
        invalid=['{}','[]','{"proof_sha256":1}',json.dumps({'proof_sha256':'A'*64}),
            json.dumps({'proof_sha256':'a'*63}),
            json.dumps({'proof_sha256':proof(1),'cookie':'private'}),
            '{"proof_sha256":"'+proof(1)+'","proof_sha256":"'+proof(2)+'"}',
            '{"proof_sha256":NaN}','{']
        for body in invalid:
            with self.subTest(body_length=len(body)):
                self.assertEqual(self.reserve(raw=body).status_code,400)
                self.assertFalse(self.database.data)
        self.assertEqual(self.reserve(raw=' '*1025).status_code,413)
        self.assertEqual(self.reserve(headers={'Content-Type':'text/plain'}).status_code,415)

    def test_replay_is_atomic_and_does_not_increment_global_quota(self):
        self.assertEqual(self.reserve().status_code,200);before=deepcopy(self.database.data)
        self.assertEqual(self.reserve().status_code,409);self.assertEqual(self.database.data,before)
        results=[]
        def reserve_same():
            try:self.admission.reserve(proof(2));results.append('created')
            except ProofReplay:results.append('replayed')
        threads=[threading.Thread(target=reserve_same) for _ in range(8)]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertEqual(results.count('created'),1);self.assertEqual(results.count('replayed'),7)
        self.assertEqual(len(self.database.data['arm_a_usage/'+GLOBAL_DOCUMENT]['visitor_issues']),2)

    def test_concurrent_unique_proofs_cannot_exceed_minute_limit(self):
        outcomes=[]
        def reserve_unique(index):
            try:self.admission.reserve(proof(index));outcomes.append('created')
            except AdmissionLimited:outcomes.append('limited')
        threads=[threading.Thread(target=reserve_unique,args=(i,)) for i in range(16)]
        for thread in threads:thread.start()
        for thread in threads:thread.join()
        self.assertEqual(outcomes.count('created'),10);self.assertEqual(outcomes.count('limited'),6)
        self.assertEqual(len(self.database.data),11)
        self.assertEqual(self.reserve(100).status_code,429)

    def test_rolling_day_limit_survives_instances_and_is_not_a_daily_reset(self):
        for group in range(6):
            other=PublicAdmission(self.database,now=lambda:self.now)
            for i in range(10):other.reserve(proof(group*10+i))
            self.now+=timedelta(minutes=1,seconds=1)
        before=deepcopy(self.database.data)
        with self.assertRaises(AdmissionLimited):self.admission.reserve(proof(100))
        self.assertEqual(before,self.database.data)
        self.now+=timedelta(hours=23)
        with self.assertRaises(AdmissionLimited):self.admission.reserve(proof(100))
        self.now+=timedelta(hours=1)
        self.admission.reserve(proof(100))
        self.assertEqual(self.database.data['arm_a_usage/'+GLOBAL_DOCUMENT]['visitor_issues'],[self.now])

    def test_store_outage_and_changed_quota_binding_are_system_errors_without_writes(self):
        with patch.object(Ref,'get',side_effect=RuntimeError('synthetic private outage')):
            response=self.reserve()
        self.assertEqual(response.status_code,503)
        self.assertEqual(response.json['error'],'VISITOR_ADMISSION_UNAVAILABLE')
        self.assertFalse(self.database.data);self.assertNotIn('private outage',response.get_data(as_text=True))
        self.admission.reserve(proof(1))
        self.database.data['arm_a_usage/'+GLOBAL_DOCUMENT]['day_limit']=61
        before=deepcopy(self.database.data)
        with self.assertRaises(AdmissionUnavailable):self.admission.reserve(proof(2))
        self.assertEqual(before,self.database.data)


if __name__=='__main__':unittest.main()
