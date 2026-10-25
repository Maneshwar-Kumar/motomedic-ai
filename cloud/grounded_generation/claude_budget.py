"""Non-recurring Anthropic maximum-cost reservations; no reset or refund."""
from decimal import Decimal, ROUND_CEILING
from cloud.common import ProviderFailure

VERSION='claude-fallback-nonrecurring-one-dollar-v1'
ALLOCATION='owner-haiku-fallback-20261011-validation-v1'
MAX_USD=Decimal('1.00')
MAX_NANODOLLARS=1_000_000_000
MODEL='claude-haiku-5-5'

def nanodollars(value):
    try:
        value=Decimal(str(value))
    except Exception:
        raise ProviderFailure('CLAUDE_COST_RESERVATION_INVALID') from None
    if not value.is_finite() or value<=0:raise ProviderFailure('CLAUDE_COST_RESERVATION_INVALID')
    return int((value*1_000_000_000).to_integral_value(rounding=ROUND_CEILING))


def validate_ledger(previous):
    """Read the existing shared allocation without changing its identity."""
    if type(previous) is not dict:
        raise ProviderFailure('CLAUDE_COST_STORE_INVALID')
    if previous and (previous.get('version') != VERSION or
            previous.get('maximum_nanodollars') != MAX_NANODOLLARS or
            previous.get('model', MODEL) != MODEL):
        raise ProviderFailure('CLAUDE_COST_BINDING_CHANGED')
    spent = previous.get('reserved_nanodollars', 0)
    count = previous.get('reservation_count', 0)
    if (type(spent) is not int or not 0 <= spent <= MAX_NANODOLLARS or
            type(count) is not int or count < 0):
        raise ProviderFailure('CLAUDE_COST_STORE_INVALID')
    return spent, count

class ClaudeBudget:
    def __init__(self,client):self.client=client
    def __call__(self,amount,model):
        if model!=MODEL:raise ProviderFailure('CLAUDE_COST_MODEL_MISMATCH')
        value=nanodollars(amount)
        ref=self.client.collection('arm_a_usage').document(ALLOCATION)
        from google.cloud import firestore
        @firestore.transactional
        def reserve(tx):
            snap=ref.get(transaction=tx)
            previous=snap.to_dict() if snap.exists else {}
            spent,count=validate_ledger(previous)
            if spent+value>MAX_NANODOLLARS:raise ProviderFailure('CLAUDE_SPEND_LIMIT')
            # This allocation has no expiry: retention must never reopen its budget.
            tx.set(ref,{'version':VERSION,'model':model,'maximum_nanodollars':1_000_000_000,
                'reserved_nanodollars':spent+value,'reservation_count':count+1})
        try:reserve(self.client.transaction())
        except ProviderFailure:raise
        except Exception:raise ProviderFailure('CLAUDE_COST_STORE_UNAVAILABLE') from None
