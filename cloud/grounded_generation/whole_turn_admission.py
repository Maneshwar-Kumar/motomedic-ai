"""Atomic whole-turn capacity with pacing; reservations survive uncertain calls.

Uses the existing global daily/rate ledger and a non-expiring conservative
allocation. Does not increase account limits or authorize provider spending.
Serving atomically reserves the turn's single Haiku generation call (one
transport attempt) before it starts; there is no verification or correction
phase. Historical draft/verify reservations remain charged and readable.
"""
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import threading
import time
from generation_providers import ProviderFailure
from cloud.grounded_generation.claude_budget import (
    ALLOCATION as CLAUDE_ALLOCATION, VERSION as CLAUDE_VERSION,
    validate_ledger as validate_claude_ledger)
from cloud.grounded_generation.token_ceiling import (GRANT_DOCUMENT, DEFAULT_TOKEN_CEILING,
    MAX_TOKEN_CEILING, resolve_token_ceiling)

VERSION = 'whole-turn-capacity-v1'
# Allocation identity stays unchanged: a runtime upgrade cannot replenish it.
PACING_VERSION = 'whole-turn-sealed-unused-pacing-v5-single-generation'
SEALED_VERSIONS = (PACING_VERSION, 'whole-turn-sealed-unused-pacing-v4-haiku-roles',
                   'whole-turn-sealed-unused-pacing-v3-variable-model', 'whole-turn-sealed-unused-pacing-v2')
PLAN_VERSION = 'whole-turn-single-generation-native-envelope-v1'
ALLOCATION = 'grounded-primary-nonrecurring-v1'
MAX_TOKENS = 999200
MAX_ATTEMPTS = 100
CALL_TOKENS = 9992
GEMMA = 'gemma-4-26b-a4b-it'
FLASH = 'gemini-2.5-flash-lite'
HAIKU = 'claude-haiku-5-5'
GEMMA_INPUT_TPM = 16000
FLASH_INPUT_TPM = 250000
MODEL_INPUT_LIMITS = {GEMMA: 256000 - 1800, FLASH:1048576, HAIKU: 1000000 - 1800}
# Retired model limits above validate existing immutable events only. New
# serving reservations and permits are scoped to the owner-selected model.
SERVING_MODELS = (HAIKU,)
MAX_OUTPUT_TOKENS = 1800
MAX_CALL_TOKENS = max(MODEL_INPUT_LIMITS.values()) + MAX_OUTPUT_TOKENS
GENERATE = 'generate'
# Retired draft/verify stages remain valid only for reading historical events.
STAGES = ('draft', 'verify', 'correction', 'reverify', GENERATE)
SLOT_SECONDS = 61
MAX_SLEEP_SECONDS = 60
# A permit may return at most one second after its recorded time. The extra
# second in SLOT_SECONDS preserves the observed rolling 60-second input quota.
MAX_PERMIT_AGE_SECONDS = 1
_OPERATION_DEADLINE = ContextVar('grounded_operation_deadline', default=None)


def _sealed_unused(event):
    """Only a committed proof of an unused future reservation removes pacing."""
    fields = ('state', 'sealed_at', 'sealed_version')
    if not any(field in event for field in fields):
        return False
    sealed_at = event.get('sealed_at')
    if (event.get('state') != 'SEALED_UNUSED' or
            event.get('sealed_version') not in SEALED_VERSIONS or
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
            type(e.get('tokens')) is not int or not 0 <= e['tokens'] <= MAX_CALL_TOKENS or
            e.get('kind') not in ('generation', 'prompt_cache') or
            ('consumed' in e and type(e['consumed']) is not bool) for e in events):
        raise ProviderFailure('PROVIDER_ADMISSION_STORE_INVALID')
    for event in events:
        _sealed_unused(event)
        if ('primary_token_ceiling' in event or 'token_ceiling_scope_sha256' in event) and (
                type(event.get('primary_token_ceiling')) is not int or
                not DEFAULT_TOKEN_CEILING <= event['primary_token_ceiling'] <= MAX_TOKEN_CEILING or
                (event['primary_token_ceiling'] == DEFAULT_TOKEN_CEILING and
                    event.get('token_ceiling_scope_sha256') is not None) or
                (event['primary_token_ceiling'] > DEFAULT_TOKEN_CEILING and
                    (type(event.get('token_ceiling_scope_sha256')) is not str or
                     len(event['token_ceiling_scope_sha256']) != 64 or
                     any(char not in '0123456789abcdef' for char in event['token_ceiling_scope_sha256'])))):
            raise ProviderFailure('PROVIDER_ADMISSION_STORE_INVALID')
        if event.get('model') is not None and (
                event['model'] not in MODEL_INPUT_LIMITS or event.get('stage') not in STAGES or
                type(event.get('input_tokens')) is not int or not 0 < event['input_tokens'] <= MODEL_INPUT_LIMITS[event['model']] or
                type(event.get('output_tokens')) is not int or not 0 < event['output_tokens'] <= MAX_OUTPUT_TOKENS or
                event['tokens'] != event['input_tokens'] + event['output_tokens'] or
                type(event.get('attempt')) is not int or event['attempt'] not in (1, 2)):
            raise ProviderFailure('PROVIDER_ADMISSION_STORE_INVALID')
    return events


def _bound_event(turn, event):
    """A permit or phase cannot replace its immutable durable reservation."""
    index = event['slot']
    row = turn['entries'][index]
    if (event['tokens'] != row['tokens'] or (row['model'] is not None and any(
            event.get(key) != row[key] for key in
            ('model', 'stage', 'input_tokens', 'output_tokens', 'attempt')))):
        raise ProviderFailure('PROVIDER_NATIVE_PLAN_STORE_CHANGED')
    if ('primary_token_ceiling' in turn and
            (event.get('primary_token_ceiling') != turn['primary_token_ceiling'] or
             event.get('token_ceiling_scope_sha256') != turn['token_ceiling_scope_sha256'])):
        raise ProviderFailure('PROVIDER_TOKEN_CEILING_RESERVATION_BINDING_CHANGED')
    if turn['entry_plan_hashes'][index] is not None and any(
            event.get(key) != turn[field][index] for key, field in
            (('plan_sha256', 'entry_plan_hashes'), ('phase', 'entry_phases'),
             ('phase_nonce', 'entry_nonces'))):
        raise ProviderFailure('PROVIDER_NATIVE_PLAN_STORE_CHANGED')


def _plan(plan, attempts):
    if plan is None:
        if type(attempts) is not int or attempts not in (8, 12):
            raise ProviderFailure('WHOLE_TURN_RESERVATION_INVALID')
        # Existing synthetic/retired availability-fallback consumers keep their
        # old conservative reservation. Serving supplies an explicit native plan.
        return [{'model': None, 'input_tokens': 8192, 'output_tokens': 1800,
                 'tokens': CALL_TOKENS} for _ in range(attempts)], 0
    if (type(plan) is not dict or not {'slots'} <= set(plan) <= {'slots', 'request_sha256'} or
            type(plan['slots']) is not list or len(plan['slots']) != 1 or
            ('request_sha256' in plan and (type(plan['request_sha256']) is not str or len(plan['request_sha256']) != 64 or
                any(char not in '0123456789abcdef' for char in plan['request_sha256'])))):
        raise ProviderFailure('WHOLE_TURN_NATIVE_PLAN_INVALID')
    row = deepcopy(plan['slots'][0])
    allowed = {'model', 'stage', 'input_tokens', 'output_tokens', 'attempt', 'maximum_nanodollars'}
    if (type(row) is not dict or not set(row) <= allowed or row.get('model') != HAIKU or
            row.get('stage') != GENERATE or
            type(row.get('input_tokens')) is not int or not 0 < row['input_tokens'] <= MODEL_INPUT_LIMITS[HAIKU] or
            type(row.get('output_tokens')) is not int or row['output_tokens'] != MAX_OUTPUT_TOKENS or
            type(row.get('attempt')) is not int or row['attempt'] != 1):
        raise ProviderFailure('WHOLE_TURN_NATIVE_PLAN_INVALID')
    row['tokens'] = row['input_tokens'] + row['output_tokens']
    # Maximum 5m cache-write plus output price at the selected native input
    # tier. USD1 allocation identity and old charges are unchanged.
    input_price, output_price = (625, 2500) if row['input_tokens'] > 100000 else (125, 500)
    worst = row['input_tokens'] * input_price + row['output_tokens'] * output_price
    supplied = row.get('maximum_nanodollars', worst)
    if type(supplied) is not int or supplied < worst:
        raise ProviderFailure('CLAUDE_COST_RESERVATION_INVALID')
    row['maximum_nanodollars'] = supplied
    return [row], supplied


class ModelAdmission:
    """A model-scoped permit, returning its already reserved hard envelope."""
    pre_reserved = True

    def __init__(self, owner, model, role=None):
        self.owner, self.model, self.role = owner, model, role

    def __call__(self, tokens, kind, *, stage=None):
        return self.owner._permit(tokens, kind, model=self.model, stage=stage, role=self.role)


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

    def for_model(self, model, *, role=None):
        if model not in SERVING_MODELS or role not in (None, 'generation'):
            raise ProviderFailure('PROVIDER_MODEL_ROLE_MISMATCH')
        return ModelAdmission(self, model, role)

    def _reserve_entries(self, operation_id, entries, monetary, deadline, plan_sha, phase):
        from google.cloud import firestore
        from evidence_registry import content_hash
        attempts = len(entries)
        total = sum(row['tokens'] for row in entries)
        nonce = content_hash({'operation_id': operation_id, 'phase': phase, 'plan_sha256': plan_sha})
        usage = self.client.collection('arm_a_usage').document('grounded-provider-global-v1')
        lifetime = self.client.collection('arm_a_usage').document(ALLOCATION)
        claude = self.client.collection('arm_a_usage').document(CLAUDE_ALLOCATION)
        grant = self.client.collection('arm_a_usage').document(GRANT_DOCUMENT)

        @firestore.transactional
        def reserve(tx):
            now = self.now()
            if deadline is not None and now >= deadline:
                raise ProviderFailure('PROVIDER_OPERATION_DEADLINE_EXCEEDED')
            snap = usage.get(transaction=tx)
            allocation_snap = lifetime.get(transaction=tx)
            grant_snap = grant.get(transaction=tx)
            claude_snap = claude.get(transaction=tx) if monetary else None
            previous = snap.to_dict() if snap.exists else {}
            allocation = allocation_snap.to_dict() if allocation_snap.exists else {}
            token_limit, token_authorization = resolve_token_ceiling(allocation,
                grant_snap.to_dict() if grant_snap.exists else None)
            scope_sha = token_authorization['scope_sha256'] if token_authorization else None
            claude_previous = claude_snap.to_dict() if claude_snap is not None and claude_snap.exists else {}
            if allocation and (allocation.get('version') != VERSION or
                    allocation.get('maximum_tokens') != token_limit or
                    allocation.get('maximum_attempts') != MAX_ATTEMPTS):
                raise ProviderFailure('PROVIDER_ALLOCATION_BINDING_CHANGED')
            spent = allocation.get('reserved_tokens', 0)
            count = allocation.get('reserved_attempts', 0)
            if (type(spent) is not int or type(count) is not int or
                    not 0 <= spent <= token_limit or not 0 <= count <= MAX_ATTEMPTS):
                raise ProviderFailure('PROVIDER_ALLOCATION_STORE_INVALID')
            if monetary:
                nano_spent, monetary_count = validate_claude_ledger(claude_previous)
                if nano_spent + monetary > 1000000000:
                    raise ProviderFailure('CLAUDE_SPEND_LIMIT')
            events = _events(previous)
            events = [e for e in events if e['at'] > now - timedelta(hours=24)]
            own = [e for e in events if e.get('operation_id') == operation_id]
            if own:
                raise ProviderFailure('PROVIDER_OPERATION_ALREADY_RESERVED_NO_REPLAY')
            if (len(events) + attempts > 120 or
                    sum(e['kind'] == 'generation' for e in events) + attempts > MAX_ATTEMPTS or
                    sum(e['tokens'] for e in events) + total > token_limit or
                    count + attempts > MAX_ATTEMPTS or spent + total > token_limit):
                raise ProviderFailure('PROVIDER_WHOLE_TURN_ALLOCATION_LIMIT')
            # Retain conservative61-second spacing across the shared ledger.
            # Native context, provider throughput and lifetime money/token
            # limits are separate constraints; historical Google TPM cannot
            # become an assembled-evidence limit for the Haiku generation call.
            start = max([now] + [e['at'] + timedelta(seconds=SLOT_SECONDS)
                                for e in events if not _sealed_unused(e) and
                                e['at'] > now - timedelta(seconds=SLOT_SECONDS)])
            slots = [start + timedelta(seconds=i * SLOT_SECONDS) for i in range(attempts)]
            if (slots[-1] - now).total_seconds() > self.maximum_queue_seconds:
                raise ProviderFailure('PROVIDER_WHOLE_TURN_QUEUE_BOUND')
            if deadline is not None and slots[-1] >= deadline:
                raise ProviderFailure('PROVIDER_OPERATION_DEADLINE_EXCEEDED')
            reserved = [{'at':slot, 'tokens':row['tokens'], 'kind':'generation',
                         'operation_id':operation_id, 'slot':i, 'consumed':False,
                         'primary_token_ceiling':token_limit, 'token_ceiling_scope_sha256':scope_sha,
                         **({key: row[key] for key in ('model', 'stage', 'input_tokens', 'output_tokens', 'attempt')}
                            if row['model'] is not None else {}),
                         **({'plan_sha256': plan_sha, 'phase': phase, 'phase_nonce': nonce}
                            if plan_sha is not None else {})}
                        for i, (slot, row) in enumerate(zip(slots, entries))]
            tx.set(usage, {'events':events + reserved,
                          'expires_at':max(e['at'] for e in events + reserved) + timedelta(hours=24),
                          'controls_version':VERSION})
            # No TTL: a fresh validation run, new visitor or restart cannot
            # replenish this allocation. Unused/uncertain slots stay reserved.
            tx.set(lifetime, {**allocation, 'version':VERSION, 'maximum_tokens':token_limit,
                              'maximum_attempts':MAX_ATTEMPTS,
                              'reserved_tokens':spent + total,
                              'reserved_attempts':count + attempts})
            if monetary:
                tx.set(claude, {'version': CLAUDE_VERSION, 'model': HAIKU,
                    'maximum_nanodollars': 1000000000, 'reserved_nanodollars': nano_spent + monetary,
                    'reservation_count': monetary_count + 1})
            return slots, token_limit, token_authorization

        try:
            slots, token_limit, token_authorization = reserve(self.client.transaction())
        except ProviderFailure:
            raise
        except Exception:
            raise ProviderFailure('PROVIDER_ADMISSION_STORE_UNAVAILABLE') from None
        return slots, nonce, token_limit, token_authorization

    def begin_turn(self, operation_id, attempts=8, *, plan=None):
        if (type(operation_id) is not str or not 1 <= len(operation_id) <= 200 or
                getattr(self.local, 'turn', None) is not None):
            raise ProviderFailure('WHOLE_TURN_RESERVATION_INVALID')
        entries, monetary = _plan(plan, attempts)
        from evidence_registry import content_hash
        plan_sha = content_hash(plan) if plan is not None else None
        deadline = _OPERATION_DEADLINE.get()
        phase = 'initial' if plan is not None else 'compatibility'
        slots, nonce, token_limit, token_authorization = self._reserve_entries(
            operation_id, entries, monetary, deadline, plan_sha, phase)
        attempts = len(entries)
        total = sum(row['tokens'] for row in entries)
        receipt = {'version':VERSION, 'pacing_version':PACING_VERSION,
                   'plan_version': PLAN_VERSION if plan is not None else 'LEGACY_FIXED_ENVELOPE',
                   'reservation_mode': 'SINGLE_GENERATION_CALL' if plan is not None else 'EXPLICIT_COMPATIBILITY',
                   'reserved_attempts':attempts, 'reserved_tokens':total,
                   'reserved_nanodollars': monetary, 'reserved_slots':deepcopy(entries),
                   'primary_token_ceiling':token_limit,
                   'token_ceiling_authorization':deepcopy(token_authorization),
                   'phases': [{'phase':phase, 'phase_nonce':nonce, 'plan_sha256':plan_sha,
                       'reserved_attempts':attempts, 'reserved_tokens':total, 'reserved_nanodollars':monetary}],
                   'maximum_wait_seconds':max(0, (slots[-1] - self.now()).total_seconds()),
                   'sealing_status':'ACTIVE_RESERVATIONS_RETAINED', 'sealed_unused_slots':0}
        # The caller retains this same receipt in its trace. Final sealing
        # updates it without needing to replace an original generation error.
        self.local.turn = {'operation_id':operation_id, 'slots':slots, 'entries':entries, 'next':0,
                           'deadline':deadline, 'receipt':receipt, 'plan_sha256': plan_sha,
                           'entry_plan_hashes': [plan_sha] * attempts,
                           'entry_phases': [phase] * attempts, 'entry_nonces': [nonce] * attempts,
                           'phase':phase}
        self.local.turn.update(primary_token_ceiling=token_limit,
            token_ceiling_scope_sha256=token_authorization['scope_sha256'] if token_authorization else None)
        return receipt

    def __call__(self, tokens, kind):
        return self._permit(tokens, kind)

    def _permit(self, tokens, kind, *, model=None, stage=None, role=None):
        from google.cloud import firestore
        turn = getattr(self.local, 'turn', None)
        if (turn is None or type(tokens) is not int or not 0 < tokens <= MAX_CALL_TOKENS or
                kind != 'generation' or turn['next'] >= len(turn['slots'])):
            raise ProviderFailure('PROVIDER_UNRESERVED_ATTEMPT')
        index = turn['next']
        rows = turn['entries']
        if rows[index]['model'] is not None:
            if model not in SERVING_MODELS or rows[index]['model'] != model:
                raise ProviderFailure('PROVIDER_MODEL_ROLE_MISMATCH')
            if role is not None:
                allowed_stages = {'generation': (GENERATE,)}
                if role not in allowed_stages or rows[index]['stage'] not in allowed_stages[role]:
                    raise ProviderFailure('PROVIDER_MODEL_ROLE_MISMATCH')
                if stage is None:
                    stage = rows[index]['stage']
            # The permit must be bound to either an explicit stage or role.
            if stage is None or rows[index]['stage'] != stage:
                raise ProviderFailure('PROVIDER_MODEL_ROLE_MISMATCH')
            actual_input = tokens - rows[index]['output_tokens']
            if not 0 < actual_input <= rows[index]['input_tokens']:
                raise ProviderFailure('PROVIDER_NATIVE_ENVELOPE_EXCEEDED')
        elif model is not None or tokens > rows[index]['tokens']:
            raise ProviderFailure('PROVIDER_UNRESERVED_ATTEMPT')
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
            _bound_event(turn, event)
            for skipped_index in range(turn['next'], index):
                previous = [e for e in events if e.get('operation_id') == turn['operation_id']
                    and e.get('slot') == skipped_index - 1]
                skipped = [e for e in events if e.get('operation_id') == turn['operation_id']
                    and e.get('slot') == skipped_index]
                if (len(previous) != 1 or previous[0].get('consumed') is not True or
                        len(skipped) != 1 or skipped[0].get('consumed') is not False):
                    raise ProviderFailure('PROVIDER_RETRY_SKIP_UNPROVED')
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
                turn['next'] = index + 1  # Consumed even if worker dies while waiting.
                first = False
            now = self.now()
            bounded(now, now)
            delay = (slot - now).total_seconds()
            if delay <= 0:
                if -delay <= MAX_PERMIT_AGE_SECONDS:
                    return deepcopy(rows[index])
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
                    _bound_event(turn, event)
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

