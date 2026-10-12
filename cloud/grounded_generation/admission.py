"""Retired fixed-envelope admission retained for historical synthetic consumers.

Reserve worst-case tokens before EACH generation attempt. Uncertain calls retain
their reservation. This rolling ledger is not serving authority: Haiku serving
uses WholeTurnAdmission's native roles and permanent token/USD1 allocations.
The old envelope below must never cap assembled evidence in the active runtime.
"""
from datetime import datetime,timedelta,timezone
from generation_providers import ProviderFailure

VERSION='provider-reservations-v2-conservative-token-minute'

class ProviderAdmission:
    def __init__(self,client,now=None):
        self.client=client;self.now=now or (lambda:datetime.now(timezone.utc))
    def __call__(self,tokens,kind):
        from google.cloud import firestore
        if type(tokens) is not int or not 0<=tokens<=9992 or kind not in ('generation','prompt_cache'):
            raise ProviderFailure('PROVIDER_RESERVATION_INVALID')
        ref=self.client.collection('arm_a_usage').document('grounded-provider-global-v1')
        @firestore.transactional
        def reserve(tx):
            from cloud.grounded_generation.whole_turn_admission import _events
            now=self.now();snap=ref.get(transaction=tx)
            events=[e for e in _events(snap.to_dict() if snap.exists else {}) if e['at']>now-timedelta(hours=24)]
            generated=[e for e in events if e['kind']=='generation']
            # Maximum 100 attempts/day and 999,200 reserved tokens/day. Gemma
            # account quota and the unchanged project budget can stop earlier.
            if (len(events)>=120 or len(generated)>=100 or sum(e['tokens'] for e in events)+tokens>999200 or
                sum(e['at']>now-timedelta(minutes=1) for e in generated)>=6 or
                sum(e['tokens'] for e in events if e['at']>now-timedelta(minutes=1))+tokens>10000):
                raise ProviderFailure('PROVIDER_DAILY_OR_RATE_LIMIT')
            tx.set(ref,{'events':events+[{'at':now,'tokens':tokens,'kind':kind}],
                'expires_at':now+timedelta(hours=24),'controls_version':VERSION})
        try: reserve(self.client.transaction())
        except ProviderFailure: raise
        except Exception: raise ProviderFailure('PROVIDER_ADMISSION_STORE_UNAVAILABLE') from None
