"""Non-recurring Anthropic maximum-cost reservations; no reset or refund."""
from decimal import Decimal, ROUND_CEILING
from generation_providers import ProviderFailure

VERSION='claude-fallback-nonrecurring-one-dollar-v1'
ALLOCATION='owner-haiku-fallback-20261011-validation-v1'
MAX_USD=Decimal('1.00')

def nanodollars(value):
    value=Decimal(str(value))
    if not value.is_finite() or value<=0:raise ProviderFailure('CLAUDE_COST_RESERVATION_INVALID')
    return int((value*1_000_000_000).to_integral_value(rounding=ROUND_CEILING))

class ClaudeBudget:
    def __init__(self,client):self.client=client
    def __call__(self,amount,model):
        if model!='claude-haiku-5-5':raise ProviderFailure('CLAUDE_COST_MODEL_MISMATCH')
        value=nanodollars(amount)
        ref=self.client.collection('arm_a_usage').document(ALLOCATION)
        from google.cloud import firestore
        @firestore.transactional
        def reserve(tx):
            snap=ref.get(transaction=tx)
            previous=snap.to_dict() if snap.exists else {}
            if previous and (previous.get('version')!=VERSION or previous.get('maximum_nanodollars')!=1_000_000_000):
                raise ProviderFailure('CLAUDE_COST_BINDING_CHANGED')
            spent=previous.get('reserved_nanodollars',0)
            if type(spent)is not int or spent<0:raise ProviderFailure('CLAUDE_COST_STORE_INVALID')
            if spent+value>1_000_000_000:raise ProviderFailure('CLAUDE_SPEND_LIMIT')
            # This allocation has no expiry: retention must never reopen its budget.
            tx.set(ref,{'version':VERSION,'model':model,'maximum_nanodollars':1_000_000_000,
                'reserved_nanodollars':spent+value,'reservation_count':previous.get('reservation_count',0)+1})
        try:reserve(self.client.transaction())
        except ProviderFailure:raise
        except Exception:raise ProviderFailure('CLAUDE_COST_STORE_UNAVAILABLE') from None
