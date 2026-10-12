"""Synthetic public inspection identity tests; no cloud/provider calls."""
import base64
import json
import os
import time
import types
import unittest
from unittest.mock import patch
from cloud.arm_a import public_inspection_auth as auth
from cloud.arm_a.test_health import HealthTests

URL = 'https://motomedic-arm-a-279945185781.us-central1.run.app'
CALLER = 'synthetic-ui@synthetic-project.iam.gserviceaccount.com'


def signed_fixture():
    claims = {'iss': 'https://accounts.google.com', 'sub': 'synthetic-subject',
              'aud': URL, 'exp': time.time() + 600, 'email': CALLER, 'email_verified': True}
    body = base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')
    return 'e30.' + body + '.synthetic_signature', claims


def verifier_modules(verifier):
    google=types.ModuleType('google');oauth=types.ModuleType('google.oauth2')
    identity=types.ModuleType('google.oauth2.id_token')
    identity.verify_oauth2_token=verifier;oauth.id_token=identity;google.oauth2=oauth
    return {'google':google,'google.oauth2':oauth,'google.oauth2.id_token':identity}


class PublicInspectionIdentityTests(unittest.TestCase):
    def test_default_private_and_invalid_configuration_fail_closed(self):
        with patch.dict(os.environ, {}, clear=True):self.assertFalse(auth.enabled())
        with patch.dict(os.environ, {auth.FLAG:'unknown'}):
            with self.assertRaises(PermissionError):auth.enabled()

    def test_alternate_header_cannot_substitute_for_full_signed_authorization(self):
        token,_=signed_fixture()
        with patch.dict(os.environ,{auth.AUDIENCE:URL,auth.CALLERS:CALLER}):
            for headers in ({}, {'X-Serverless-Authorization':'Bearer '+token},
                            {'Authorization':'Bearer e30.e30.'}):
                with self.assertRaises(PermissionError):auth.verify_request(headers)

    def test_exact_audience_signature_verifier_and_payload_are_required(self):
        token,claims=signed_fixture();seen=[]
        def verify(value,request,audience):
            seen.append((value,audience,type(request)));return claims
        with patch.dict(os.environ,{auth.AUDIENCE:URL,auth.CALLERS:CALLER}), patch.dict('sys.modules',verifier_modules(verify)):
            self.assertEqual(auth.verify_request({'Authorization':'Bearer '+token}),token)
        self.assertEqual(seen,[(token,URL,auth.CertificateRequest)])
        def reject(*args,**kwargs):raise ValueError('invalid signature')
        with patch.dict(os.environ,{auth.AUDIENCE:URL,auth.CALLERS:CALLER}), patch.dict('sys.modules',verifier_modules(reject)):
            with self.assertRaises(PermissionError):auth.verify_request({'Authorization':'Bearer '+token})

    def test_different_verified_payload_or_audience_fails(self):
        token,claims=signed_fixture()
        for field in ('sub','aud','iss','email','email_verified'):
            changed={**claims,field:'different'}
            with patch.dict(os.environ,{auth.AUDIENCE:URL,auth.CALLERS:CALLER}), patch.dict('sys.modules',
                    verifier_modules(lambda *args,**kwargs:changed)):
                with self.assertRaises(PermissionError):auth.verify_request({'Authorization':'Bearer '+token})
        with patch.dict(os.environ,{auth.AUDIENCE:'https://untrusted.example'}):
            with self.assertRaises(PermissionError):auth.verify_request({'Authorization':'Bearer '+token})

    def test_public_cookie_does_not_authorize_an_external_google_service_account(self):
        token,claims=signed_fixture()
        for allowlist in ('', 'allUsers', '*', CALLER+','+CALLER, 'external@other.iam.gserviceaccount.com'):
            with patch.dict(os.environ,{auth.AUDIENCE:URL,auth.CALLERS:allowlist}), patch.dict('sys.modules',
                    verifier_modules(lambda *args,**kwargs:claims)):
                with self.assertRaises(PermissionError):auth.verify_request({'Authorization':'Bearer '+token})

    def test_certificate_transport_rejects_redirect_targets_and_mutations(self):
        with self.assertRaises(PermissionError):auth.CertificateRequest()('https://untrusted.example')
        with self.assertRaises(PermissionError):auth.CertificateRequest()(auth._CERT_URL,method='POST')


class PublicInspectionHTTPTests(HealthTests):
    # Original private-mode tests are inherited to preserve those bindings.
    def test_anonymous_public_health_is_ready_and_creates_no_state(self):
        with patch.dict(os.environ,{auth.FLAG:'true'}):
            response=self.client.get('/v1/health')
        self.assertEqual(response.status_code,200);self.assertTrue(response.json['ready'])
        self.assertNotIn('evidence',response.json)

    def test_signed_routes_remain_denied_without_verified_identity(self):
        with patch.dict(os.environ,{auth.FLAG:'true',auth.AUDIENCE:URL,auth.CALLERS:CALLER}), patch('builtins.print'):
            for method,path in (('get','/v1/initial-catalogue'),('post','/internal/operations/run'),
                               ('post','/internal/visitors/reserve')):
                response=getattr(self.client,method)(path,json={})
                self.assertEqual(response.status_code,401)

    def test_foreign_signed_account_and_valid_cookie_cannot_dispatch_a_session(self):
        from rider_ui.identity import issue
        _,claims=signed_fixture()
        claims={**claims,'email':'foreign@other-project.iam.gserviceaccount.com','sub':'foreign-subject'}
        body=base64.urlsafe_b64encode(json.dumps(claims).encode()).decode().rstrip('=')
        token='e30.'+body+'.synthetic_signature'
        def unexpected_dispatch():raise AssertionError('No state or dispatch may be reached')
        self.app.add_url_rule('/v1/sessions','test_session_dispatch',unexpected_dispatch,methods=['POST'])
        with patch.dict(os.environ,{auth.FLAG:'true',auth.AUDIENCE:URL,auth.CALLERS:CALLER}), \
                patch.dict('sys.modules',verifier_modules(lambda *args,**kwargs:claims)), patch('builtins.print'):
            response=self.client.post('/v1/sessions',json={},headers={
                'Authorization':'Bearer '+token,'X-MotoMedic-Visitor':issue('s'*64)})
        self.assertEqual(response.status_code,401)
        self.assertEqual(response.json['error'],'AUTH_REQUIRED')

    def test_forged_header_is_denied_and_verified_alternate_header_is_removed(self):
        token,claims=signed_fixture()
        def reject(*args,**kwargs):raise ValueError('forged signature')
        with patch.dict(os.environ,{auth.FLAG:'true',auth.AUDIENCE:URL,auth.CALLERS:CALLER}), patch('builtins.print'), \
                patch.dict('sys.modules',verifier_modules(reject)):
            response=self.client.get('/v1/initial-catalogue',headers={'Authorization':'Bearer '+token})
            self.assertEqual(response.status_code,401)
        with patch.dict(os.environ,{auth.FLAG:'true',auth.AUDIENCE:URL,auth.CALLERS:CALLER}), \
                patch.dict('sys.modules',verifier_modules(lambda *args,**kwargs:claims)):
            response=self.client.get('/v1/initial-catalogue',headers={
                'Authorization':'Bearer '+token,'X-Serverless-Authorization':'Bearer forged'})
            self.assertEqual(response.status_code,410)


if __name__=='__main__':unittest.main()
