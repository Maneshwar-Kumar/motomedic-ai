import time
import unittest
import base64
import json
from rider_ui.identity import issue, verify, platform_subject

def token(subject):
    raw=json.dumps({'sub':subject,'iss':'https://accounts.google.com','exp':time.time()+600}).encode()
    body=base64.urlsafe_b64encode(raw).decode().rstrip('=')
    return 'Bearer e30.'+body+'.platform-verified-test-double'


class IdentityTests(unittest.TestCase):
    def test_stable_private_visitor_survives_refresh_and_reset(self):
        secret='test-only-key-'+'x'*64
        subject=platform_subject({'Authorization':token('private-owner')})
        first=issue(secret,now=time.time()-10,principal=subject)
        again=issue(secret,principal=subject)
        self.assertEqual(first.split('.')[0],again.split('.')[0])
        self.assertEqual(verify(secret,first,'ui-service'),verify(secret,again,'ui-service'))
        other=issue(secret,principal='another-owner')
        self.assertNotEqual(verify(secret,first,'ui-service'),verify(secret,other,'ui-service'))

    def test_unverified_or_missing_private_identity_fails_closed(self):
        for headers in ({},{'Authorization':'Bearer invalid'},{'Authorization':token('')}):
            with self.assertRaises(PermissionError): platform_subject(headers)


if __name__=='__main__': unittest.main()
