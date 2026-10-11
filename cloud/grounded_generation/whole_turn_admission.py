"""Atomic whole-turn capacity with pacing; reservations survive uncertain calls.

Uses the existing global daily/rate ledger and a non-expiring conservative
allocation. Does not increase account limits or authorize provider spending.
All future call slots are reserved before the first generation request.
"""
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from contextvars import ContextVar
import threading
import time
from generation_providers import ProviderFailure

VERSION = 'whole-turn-capacity-v1'
ALLOCATION = 'grounded-primary-nonrecurring-v1'
MAX_TOKENS = 999200
MAX_ATTEMPTS = 100
CALL_TOKENS = 9992
SLOT_SECONDS = 61
MAX_SLEEP_SECONDS = 60
# A permit may return at most one second after its recorded time. The extra
# second in SLOT_SECONDS preserves the existing rolling 60-second token cap.
MAX_PERMIT_AGE_SECONDS = 1
_OPERATION_DEADLINE = ContextVar('grounded_operation_deadline', default=None)


@contextmanager
def operation_deadline(deadline):
    """Bind provider admission to the worker's exact durable deadline snapshot."""
    if not isinstance(deadline, datetime) or deadline.tzinfo is None:
        raise ProviderFailure('PROVIDER_OPERATION_DEADLINE_INVALID')
    token = _OPERATION_DEADLINE.set(deadline)
    try:
        yield
    finally:
        _OPERATION_DEADLINE.reset(token)


class WholeTurnAdmission:
    def __init__(self, client, *, now=None, sleep=time.sleep, maximum_queue_seconds=720):
        self.client = client
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.sleep = sleep
        self.maximum_queue_seconds = maximum_queue_seconds
        self.local = threading.local()

    def begin_turn(self, operation_id, attempts=8):
        from google.cloud import firestore
        if (type(operation_id) is not str or not 1 <= len(operation_id) <= 200 or
                type(attempts) is not int or attempts not in (8, 12) or
                getattr(self.local, 'turn', None) is not None):
            raise ProviderFailure('WHOLE_TURN_RESERVATION_INVALID')
        deadline = _OPERATION_DEADLINE.get()
        usage = self.client.collection('arm_a_usage').document('grounded-provider-global-v1')
        lifetime = self.client.collection('arm_a_usage').document(ALLOCATION)

        @firestore.transactional
        def reserve(tx):
            now = self.now()
            if deadline is not None and now >= deadline:
                raise ProviderFailure('PROVIDER_OPERATION_DEADLINE_EXCEEDED')
            snap = usage.get(transaction=tx)
            allocation_snap = lifetime.get(transaction=tx)
            previous = snap.to_dict() if snap.exists else {}
            allocation = allocation_snap.to_dict() if allocation_snap.exists else {}
            if allocation and (allocation.get('version') != VERSION or
                    allocation.get('maximum_tokens') != MAX_TOKENS or
                    allocation.get('maximum_attempts') != MAX_ATTEMPTS):
                raise ProviderFailure('PROVIDER_ALLOCATION_BINDING_CHANGED')
            spent = allocation.get('reserved_tokens', 0)
            count = allocation.get('reserved_attempts', 0)
            if (type(spent) is not int or type(count) is not int or
                    spent < 0 or count < 0):
                raise ProviderFailure('PROVIDER_ALLOCATION_STORE_INVALID')
            events = previous.get('events', [])
            if type(events) is not list or any(type(e) is not dict or
                    not isinstance(e.get('at'), datetime) or
                    type(e.get('tokens')) is not int or not 0 <= e['tokens'] <= CALL_TOKENS or
                    e.get('kind') not in ('generation', 'prompt_cache') for e in events):
                raise ProviderFailure('PROVIDER_ADMISSION_STORE_INVALID')
            events = [e for e in events if e['at'] > now - timedelta(hours=24)]
            if any(e.get('operation_id') == operation_id for e in events):
                raise ProviderFailure('PROVIDER_OPERATION_ALREADY_RESERVED_NO_REPLAY')
            total = attempts * CALL_TOKENS
            if (len(events) + attempts > 120 or
                    sum(e['kind'] == 'generation' for e in events) + attempts > MAX_ATTEMPTS or
                    sum(e['tokens'] for e in events) + total > MAX_TOKENS or
                    count + attempts > MAX_ATTEMPTS or spent + total > MAX_TOKENS):
                raise ProviderFailure('PROVIDER_WHOLE_TURN_ALLOCATION_LIMIT')
            # A full 9,992-token reservation occupies a rolling 10,000-token
            # minute. Spacing by 61 seconds also obeys six requests/minute.
            start = max([now] + [e['at'] + timedelta(seconds=SLOT_SECONDS)
                                for e in events if e['at'] > now - timedelta(seconds=SLOT_SECONDS)])
            slots = [start + timedelta(seconds=i * SLOT_SECONDS) for i in range(attempts)]
            if (slots[-1] - now).total_seconds() > self.maximum_queue_seconds:
                raise ProviderFailure('PROVIDER_WHOLE_TURN_QUEUE_BOUND')
            if deadline is not None and slots[-1] >= deadline:
                raise ProviderFailure('PROVIDER_OPERATION_DEADLINE_EXCEEDED')
            reserved = [{'at':slot, 'tokens':CALL_TOKENS, 'kind':'generation',
                         'operation_id':operation_id, 'slot':i}
                        for i, slot in enumerate(slots)]
            tx.set(usage, {'events':events + reserved,
                          'expires_at':slots[-1] + timedelta(hours=24),
                          'controls_version':VERSION})
            # No TTL: a fresh validation run, new visitor or restart cannot
            # replenish this allocation. Unused/uncertain slots stay reserved.
            tx.set(lifetime, {'version':VERSION, 'maximum_tokens':MAX_TOKENS,
                              'maximum_attempts':MAX_ATTEMPTS,
                              'reserved_tokens':spent + total,
                              'reserved_attempts':count + attempts})
            return slots

        try:
            slots = reserve(self.client.transaction())
        except ProviderFailure:
            raise
        except Exception:
            raise ProviderFailure('PROVIDER_ADMISSION_STORE_UNAVAILABLE') from None
        self.local.turn = {'operation_id':operation_id, 'slots':slots, 'next':0,
                           'deadline':deadline}
        return {'version':VERSION, 'reserved_attempts':attempts,
                'reserved_tokens':attempts * CALL_TOKENS,
                'maximum_wait_seconds':max(0, (slots[-1] - self.now()).total_seconds())}

    def __call__(self, tokens, kind):
        from google.cloud import firestore
        turn = getattr(self.local, 'turn', None)
        if (turn is None or type(tokens) is not int or not 0 < tokens <= CALL_TOKENS or
                kind != 'generation' or turn['next'] >= len(turn['slots'])):
            raise ProviderFailure('PROVIDER_UNRESERVED_ATTEMPT')
        index = turn['next']
        call_deadline = self.now() + timedelta(seconds=self.maximum_queue_seconds)
        ref = self.client.collection('arm_a_usage').document('grounded-provider-global-v1')

        def bounded(now, candidate):
            if turn['deadline'] is not None and max(now, candidate) >= turn['deadline']:
                raise ProviderFailure('PROVIDER_OPERATION_DEADLINE_EXCEEDED')
            if max(now, candidate) > call_deadline:
                raise ProviderFailure('PROVIDER_WHOLE_TURN_QUEUE_BOUND')

        @firestore.transactional
        def permit(tx):
            now = self.now()
            bounded(now, now)
            snap = ref.get(transaction=tx)
            if not snap.exists:
                raise ProviderFailure('PROVIDER_RESERVATION_LOST')
            data = snap.to_dict()
            matches = [e for e in data['events'] if e.get('operation_id') == turn['operation_id']
                       and e.get('slot') == index]
            if (len(matches) != 1 or bool(matches[0].get('consumed')) == first):
                raise ProviderFailure('PROVIDER_OPERATION_ALREADY_RESERVED_NO_REPLAY')
            event = matches[0]
            candidate = max(now, event['at'])
            # Delayed counting/transport must not compress several old slots
            # into one real minute. Reposition the permit atomically, respecting
            # other operations' future reservations and actual own permits.
            blockers = [e for e in data['events'] if e is not event and
                        (e.get('operation_id') != turn['operation_id'] or e.get('consumed'))]
            while True:
                conflicts = [e['at'] for e in blockers if
                             abs((e['at'] - candidate).total_seconds()) < SLOT_SECONDS]
                if not conflicts:
                    break
                candidate = max(conflicts) + timedelta(seconds=SLOT_SECONDS)
            bounded(now, candidate)
            event.update(at=candidate, consumed=True)
            data['expires_at'] = max(e['at'] for e in data['events']) + timedelta(hours=24)
            tx.set(ref, data)
            return candidate

        first = True
        while True:
            try:
                slot = permit(self.client.transaction())
            except ProviderFailure:
                raise
            except Exception:
                raise ProviderFailure('PROVIDER_ADMISSION_STORE_UNAVAILABLE') from None
            if first:
                turn['next'] += 1  # Consumed even if the worker dies while waiting.
                first = False
            now = self.now()
            bounded(now, now)
            delay = (slot - now).total_seconds()
            if delay <= 0:
                if -delay <= MAX_PERMIT_AGE_SECONDS:
                    return
                # A scheduler pause or slow transaction can make the committed
                # permit stale. Refresh the same consumed slot before sending.
                continue
            self.sleep(min(MAX_SLEEP_SECONDS, delay))

    def end_turn(self):
        self.local.turn = None

