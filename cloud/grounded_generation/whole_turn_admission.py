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
# Allocation identity stays unchanged: a runtime upgrade cannot replenish it.
PACING_VERSION = 'whole-turn-sealed-unused-pacing-v2'
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


def _sealed_unused(event):
    """Only a committed proof of an unused future reservation removes pacing."""
    fields = ('state', 'sealed_at', 'sealed_version')
    if not any(field in event for field in fields):
        return False
    sealed_at = event.get('sealed_at')
    if (event.get('state') != 'SEALED_UNUSED' or
            event.get('sealed_version') != PACING_VERSION or
            event.get('consumed') not in (None, False) or
            event.get('kind') != 'generation' or
            type(event.get('operation_id')) is not str or
            type(event.get('slot')) is not int or not 0 <= event['slot'] < 12 or
            not isinstance(sealed_at, datetime) or sealed_at.tzinfo is None or
            not isinstance(event.get('at'), datetime) or event['at'] <= sealed_at):
        raise ProviderFailure('PROVIDER_ADMISSION_STORE_INVALID')
    return True


def _events(data):
    events = data.get('events', [])
    if type(events) is not list or any(type(e) is not dict or
            not isinstance(e.get('at'), datetime) or e['at'].tzinfo is None or
            type(e.get('tokens')) is not int or not 0 <= e['tokens'] <= CALL_TOKENS or
            e.get('kind') not in ('generation', 'prompt_cache') or
            ('consumed' in e and type(e['consumed']) is not bool) for e in events):
        raise ProviderFailure('PROVIDER_ADMISSION_STORE_INVALID')
    for event in events:
        _sealed_unused(event)
    return events


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
            events = _events(previous)
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
                                for e in events if not _sealed_unused(e) and
                                e['at'] > now - timedelta(seconds=SLOT_SECONDS)])
            slots = [start + timedelta(seconds=i * SLOT_SECONDS) for i in range(attempts)]
            if (slots[-1] - now).total_seconds() > self.maximum_queue_seconds:
                raise ProviderFailure('PROVIDER_WHOLE_TURN_QUEUE_BOUND')
            if deadline is not None and slots[-1] >= deadline:
                raise ProviderFailure('PROVIDER_OPERATION_DEADLINE_EXCEEDED')
            reserved = [{'at':slot, 'tokens':CALL_TOKENS, 'kind':'generation',
                         'operation_id':operation_id, 'slot':i, 'consumed':False}
                        for i, slot in enumerate(slots)]
            tx.set(usage, {'events':events + reserved,
                          'expires_at':max(e['at'] for e in events + reserved) + timedelta(hours=24),
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
        receipt = {'version':VERSION, 'pacing_version':PACING_VERSION,
                   'reserved_attempts':attempts, 'reserved_tokens':attempts * CALL_TOKENS,
                   'maximum_wait_seconds':max(0, (slots[-1] - self.now()).total_seconds()),
                   'sealing_status':'ACTIVE_RESERVATIONS_RETAINED', 'sealed_unused_slots':0}
        # The composer retains this same receipt in its trace. Final sealing
        # updates it without needing to replace an original generation error.
        self.local.turn = {'operation_id':operation_id, 'slots':slots, 'next':0,
                           'deadline':deadline, 'receipt':receipt}
        return receipt

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
            events = _events(data)
            matches = [e for e in events if e.get('operation_id') == turn['operation_id']
                       and e.get('slot') == index]
            if (len(matches) != 1 or bool(matches[0].get('consumed')) == first):
                raise ProviderFailure('PROVIDER_OPERATION_ALREADY_RESERVED_NO_REPLAY')
            event = matches[0]
            if _sealed_unused(event):
                raise ProviderFailure('PROVIDER_SEALED_UNUSED_ATTEMPT_FORBIDDEN')
            candidate = max(now, event['at'])
            # Delayed counting/transport must not compress several old slots
            # into one real minute. Reposition the permit atomically, respecting
            # other operations' future reservations and actual own permits.
            blockers = [e for e in events if e is not event and not _sealed_unused(e) and
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
        turn = getattr(self.local, 'turn', None)
        self.local.turn = None
        if turn is None:
            return None
        receipt = turn['receipt']
        # A failed/uncertain transaction leaves its status conservative. Never
        # obscure an original provider exception in the composer's finally.
        receipt.update(sealing_status='SEALING_UNCONFIRMED_ACTIVE_POLICY_RETAINED',
                       sealed_unused_slots=0)
        try:
            from google.cloud import firestore
            ref = self.client.collection('arm_a_usage').document('grounded-provider-global-v1')

            @firestore.transactional
            def seal(tx):
                now = self.now()
                snap = ref.get(transaction=tx)
                if not snap.exists:
                    raise ProviderFailure('PROVIDER_RESERVATION_LOST')
                data = snap.to_dict()
                events = _events(data)
                own = [e for e in events if e.get('operation_id') == turn['operation_id']]
                if (len(own) != len(turn['slots']) or
                        {e.get('slot') for e in own} != set(range(len(turn['slots'])))):
                    raise ProviderFailure('PROVIDER_RESERVATION_LOST')
                sealed = 0
                for event in own:
                    if not event.get('consumed') and event['at'] > now and not _sealed_unused(event):
                        event.update(state='SEALED_UNUSED', sealed_at=now,
                                     sealed_version=PACING_VERSION)
                        sealed += 1
                # All events, tokens and allocation totals remain retained.
                # In particular, consumed future permits stay active forever
                # until the ordinary rolling-window retention expires.
                tx.set(ref, data)
                return sealed

            sealed = seal(self.client.transaction())
            receipt.update(sealing_status='SEALED_UNUSED_CONFIRMED', sealed_unused_slots=sealed)
        except Exception:
            pass
        self.local.last_end_receipt = receipt
        return receipt

