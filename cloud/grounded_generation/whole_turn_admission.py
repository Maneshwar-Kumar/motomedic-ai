"""Atomic whole-turn capacity with pacing; reservations survive uncertain calls.

Uses the existing global daily/rate ledger and a non-expiring conservative
allocation. Does not increase account limits or authorize provider spending.
Serving atomically reserves each draft/verification pair, including the allowed
Gemma retry, before that phase begins. One correction phase may be reserved
after rejection. Explicit compatibility consumers retain full-turn reservation.
"""
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
import threading
import time
from generation_providers import ProviderFailure
from cloud.grounded_generation.claude_budget import (
    ALLOCATION as CLAUDE_ALLOCATION, VERSION as CLAUDE_VERSION)

VERSION = 'whole-turn-capacity-v1'
# Allocation identity stays unchanged: a runtime upgrade cannot replenish it.
PACING_VERSION = 'whole-turn-sealed-unused-pacing-v3-variable-model'
LEGACY_PACING_VERSION = 'whole-turn-sealed-unused-pacing-v2'
PLAN_VERSION = 'whole-turn-model-native-envelope-v1'
ALLOCATION = 'grounded-primary-nonrecurring-v1'
MAX_TOKENS = 999200
MAX_ATTEMPTS = 100
CALL_TOKENS = 9992
GEMMA = 'gemma-4-26b-a4b-it'
HAIKU = 'claude-haiku-5-5'
GEMMA_INPUT_TPM = 16000
MODEL_INPUT_LIMITS = {GEMMA: 256000 - 1800, HAIKU: 1000000 - 1800}
MAX_OUTPUT_TOKENS = 1800
STAGES = ('draft', 'verify', 'correction', 'reverify')
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
            event.get('sealed_version') not in (PACING_VERSION, LEGACY_PACING_VERSION) or
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
            type(e.get('tokens')) is not int or not 0 <= e['tokens'] <= MAX_TOKENS or
            e.get('kind') not in ('generation', 'prompt_cache') or
            ('consumed' in e and type(e['consumed']) is not bool) for e in events):
        raise ProviderFailure('PROVIDER_ADMISSION_STORE_INVALID')
    for event in events:
        _sealed_unused(event)
        if event.get('model') is not None and (
                event['model'] not in MODEL_INPUT_LIMITS or event.get('stage') not in STAGES or
                type(event.get('input_tokens')) is not int or not 0 < event['input_tokens'] <= MODEL_INPUT_LIMITS[event['model']] or
                type(event.get('output_tokens')) is not int or not 0 < event['output_tokens'] <= MAX_OUTPUT_TOKENS or
                event['tokens'] != event['input_tokens'] + event['output_tokens'] or
                type(event.get('attempt')) is not int or event['attempt'] not in (1, 2)):
            raise ProviderFailure('PROVIDER_ADMISSION_STORE_INVALID')
    return events


def _role_identity(plan, entries, verifier_stage):
    from evidence_registry import content_hash
    if 'role_plan' in plan:
        return content_hash({key: plan[key] for key in ('role_plan',
            'initial_haiku_counter_headroom_tokens', 'known_verifier_prefix_native_tokens')})
    return content_hash([entries[0]['model'], next(
        row['model'] for row in entries if row.get('stage') == verifier_stage)])


def _bound_event(turn, event):
    """A permit or phase cannot replace its immutable durable reservation."""
    index = event['slot']
    row = turn['entries'][index]
    if (event['tokens'] != row['tokens'] or (row['model'] is not None and any(
            event.get(key) != row[key] for key in
            ('model', 'stage', 'input_tokens', 'output_tokens', 'attempt')))):
        raise ProviderFailure('PROVIDER_NATIVE_PLAN_STORE_CHANGED')
    if turn['entry_plan_hashes'][index] is not None and any(
            event.get(key) != turn[field][index] for key, field in
            (('plan_sha256', 'entry_plan_hashes'), ('phase', 'entry_phases'),
             ('phase_nonce', 'entry_nonces'))):
        raise ProviderFailure('PROVIDER_NATIVE_PLAN_STORE_CHANGED')


def _plan(plan, attempts, phase='initial'):
    if plan is None:
        if type(attempts) is not int or attempts not in (8, 12):
            raise ProviderFailure('WHOLE_TURN_RESERVATION_INVALID')
        # Existing synthetic/retired availability-fallback consumers keep their
        # old conservative reservation. Serving supplies an explicit native plan.
        return [{'model': None, 'input_tokens': 8192, 'output_tokens': 1800,
                 'tokens': CALL_TOKENS} for _ in range(attempts)], 0
    metadata_keys = {'role_plan', 'forecast_method', 'forecast_is_not_unknown_final_answer_guarantee',
        'fixed_verifier_native_tokens', 'fixed_correction_native_tokens',
        'unknown_verifier_byte_allowance', 'unknown_correction_byte_allowance',
        'initial_haiku_counter_headroom_tokens', 'known_verifier_prefix_native_tokens'}
    correction_bindings = {'correction_request_sha256', 'rejected_binding_sha256', 'verdict_sha256'}
    if (type(plan) is not dict or not set(plan) <= {'slots'} | metadata_keys | correction_bindings or
            (set(plan) - correction_bindings) not in ({'slots'}, {'slots'} | metadata_keys) or
            type(plan['slots']) is not list or len(plan['slots']) not in (3, 6) or
            phase not in ('initial', 'correction') or (phase == 'correction' and len(plan['slots']) != 3)):
        raise ProviderFailure('WHOLE_TURN_NATIVE_PLAN_INVALID')
    rows = deepcopy(plan['slots'])
    allowed = {'model', 'stage', 'input_tokens', 'output_tokens', 'attempt', 'maximum_nanodollars'}
    for row in rows:
        if (type(row) is not dict or not set(row) <= allowed or
                row.get('model') not in MODEL_INPUT_LIMITS or row.get('stage') not in STAGES or
                type(row.get('input_tokens')) is not int or not 0 < row['input_tokens'] <= MODEL_INPUT_LIMITS[row['model']] or
                type(row.get('output_tokens')) is not int or row['output_tokens'] != MAX_OUTPUT_TOKENS or
                type(row.get('attempt')) is not int or row['attempt'] not in (1, 2)):
            raise ProviderFailure('WHOLE_TURN_NATIVE_PLAN_INVALID')
        if row['model'] == GEMMA and row['input_tokens'] > GEMMA_INPUT_TPM:
            raise ProviderFailure('PROVIDER_MODEL_INPUT_RATE_LIMIT')
        row['tokens'] = row['input_tokens'] + row['output_tokens']
        if row['model'] == HAIKU:
            # Maximum5m cache-write plus output price at the selected native
            # input tier. USD1 allocation identity and old charges are unchanged.
            input_price, output_price = (625, 2500) if row['input_tokens'] > 100000 else (125, 500)
            worst = row['input_tokens'] * input_price + row['output_tokens'] * output_price
            supplied = row.get('maximum_nanodollars', worst)
            if type(supplied) is not int or supplied < worst:
                raise ProviderFailure('CLAUDE_COST_RESERVATION_INVALID')
            row['maximum_nanodollars'] = supplied
        elif type(row.get('maximum_nanodollars', 0)) is not int or row.get('maximum_nanodollars', 0) != 0:
            raise ProviderFailure('CLAUDE_COST_MODEL_MISMATCH')
    drafter = rows[0]['model']
    verifier = HAIKU if drafter == GEMMA else GEMMA
    expected = [(model, stage, attempt) for stage, model in
        (('draft', drafter), ('verify', verifier), ('correction', drafter), ('reverify', verifier))
        for attempt in range(1, 3 if model == GEMMA else 2)]
    if len(rows) == 3:
        expected = expected[:3] if phase == 'initial' else expected[3:]
    if [(row['model'], row['stage'], row['attempt']) for row in rows] != expected:
        raise ProviderFailure('WHOLE_TURN_MODEL_ROLE_PLAN_INVALID')
    for left, right in zip(rows, rows[1:]):
        if left['stage'] == right['stage'] and any(left[key] != right[key] for key in ('input_tokens', 'output_tokens')):
            raise ProviderFailure('WHOLE_TURN_RETRY_ENVELOPE_CHANGED')
    for key in correction_bindings & set(plan):
        if (phase != 'correction' or type(plan[key]) is not str or len(plan[key]) != 64 or
                any(char not in '0123456789abcdef' for char in plan[key])):
            raise ProviderFailure('WHOLE_TURN_CORRECTION_BINDING_CHANGED')
    if 'role_plan' in plan and phase == 'correction' and not correction_bindings <= set(plan):
        raise ProviderFailure('WHOLE_TURN_CORRECTION_BINDING_REQUIRED')
    if 'role_plan' in plan:
        from evidence_registry import content_hash
        from cloud.grounded_generation.role_contracts import CONTRACT, ROUTING_THRESHOLD
        role = plan['role_plan']
        role_keys = {'version', 'route', 'routing_contract_sha256', 'gemma_routing_input_tokens',
            'selected_draft_input_tokens', 'initial_draft_request_sha256', 'stable_context_sha256',
            'draft_model_contract_sha256', 'verifier_contract_sha256'}
        route = 'GEMMA_DRAFT_HAIKU_VERIFY' if drafter == GEMMA else 'HAIKU_DRAFT_GEMMA_VERIFY'
        selected = CONTRACT['roles'][route]
        if (type(role) is not dict or set(role) != role_keys or role.get('version') != CONTRACT['version'] or
                role.get('route') != route or role.get('routing_contract_sha256') != content_hash(CONTRACT) or
                role.get('draft_model_contract_sha256') != content_hash(selected['draft']) or
                role.get('verifier_contract_sha256') != content_hash(selected['verifier']) or
                type(role.get('gemma_routing_input_tokens')) is not int or role['gemma_routing_input_tokens'] <= 0 or
                (role['gemma_routing_input_tokens'] > ROUTING_THRESHOLD) != (drafter == HAIKU) or
                type(role.get('selected_draft_input_tokens')) is not int or role['selected_draft_input_tokens'] <= 0 or
                type(plan.get('initial_haiku_counter_headroom_tokens')) is not int or
                not 0 <= plan['initial_haiku_counter_headroom_tokens'] <= (512 if drafter == HAIKU else 0) or
                (phase == 'initial' and role['selected_draft_input_tokens'] +
                    plan['initial_haiku_counter_headroom_tokens'] != rows[0]['input_tokens']) or
                any(type(role.get(key)) is not str or len(role[key]) != 64 or
                    any(char not in '0123456789abcdef' for char in role[key]) for key in
                    ('initial_draft_request_sha256', 'stable_context_sha256')) or
                plan.get('forecast_method') != 'NATIVE_FIXED_SCAFFOLD_PLUS_BOUNDED_PRIVATE_OUTPUT_BYTES' or
                plan.get('forecast_is_not_unknown_final_answer_guarantee') is not True or
                any(type(plan.get(key)) is not int or plan[key] < 0 for key in
                    metadata_keys - {'role_plan', 'forecast_method', 'forecast_is_not_unknown_final_answer_guarantee'})):
            raise ProviderFailure('WHOLE_TURN_ROLE_FORECAST_BINDING_CHANGED')
    return rows, sum(row.get('maximum_nanodollars', 0) for row in rows)


class ModelAdmission:
    """A model-scoped permit, returning its already reserved hard envelope."""
    pre_reserved = True

    def __init__(self, owner, model):
        self.owner, self.model = owner, model

    def __call__(self, tokens, kind, *, stage=None):
        return self.owner._permit(tokens, kind, model=self.model, stage=stage)


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

    def for_model(self, model):
        if model not in MODEL_INPUT_LIMITS:
            raise ProviderFailure('PROVIDER_MODEL_ROLE_MISMATCH')
        return ModelAdmission(self, model)

    def _reserve_entries(self, operation_id, entries, monetary, deadline, plan_sha, phase, *, prior=None):
        from google.cloud import firestore
        from evidence_registry import content_hash
        attempts = len(entries)
        total = sum(row['tokens'] for row in entries)
        offset = len(prior['entries']) if prior is not None else 0
        nonce = content_hash({'operation_id': operation_id, 'phase': phase, 'plan_sha256': plan_sha})
        usage = self.client.collection('arm_a_usage').document('grounded-provider-global-v1')
        lifetime = self.client.collection('arm_a_usage').document(ALLOCATION)
        claude = self.client.collection('arm_a_usage').document(CLAUDE_ALLOCATION)

        @firestore.transactional
        def reserve(tx):
            now = self.now()
            if deadline is not None and now >= deadline:
                raise ProviderFailure('PROVIDER_OPERATION_DEADLINE_EXCEEDED')
            snap = usage.get(transaction=tx)
            allocation_snap = lifetime.get(transaction=tx)
            claude_snap = claude.get(transaction=tx) if monetary else None
            previous = snap.to_dict() if snap.exists else {}
            allocation = allocation_snap.to_dict() if allocation_snap.exists else {}
            claude_previous = claude_snap.to_dict() if claude_snap is not None and claude_snap.exists else {}
            if allocation and (allocation.get('version') != VERSION or
                    allocation.get('maximum_tokens') != MAX_TOKENS or
                    allocation.get('maximum_attempts') != MAX_ATTEMPTS):
                raise ProviderFailure('PROVIDER_ALLOCATION_BINDING_CHANGED')
            spent = allocation.get('reserved_tokens', 0)
            count = allocation.get('reserved_attempts', 0)
            if (type(spent) is not int or type(count) is not int or
                    not 0 <= spent <= MAX_TOKENS or not 0 <= count <= MAX_ATTEMPTS):
                raise ProviderFailure('PROVIDER_ALLOCATION_STORE_INVALID')
            if monetary:
                if claude_previous and (claude_previous.get('version') != CLAUDE_VERSION or
                        claude_previous.get('maximum_nanodollars') != 1000000000 or
                        claude_previous.get('model', HAIKU) != HAIKU):
                    raise ProviderFailure('CLAUDE_COST_BINDING_CHANGED')
                nano_spent = claude_previous.get('reserved_nanodollars', 0)
                monetary_count = claude_previous.get('reservation_count', 0)
                if (type(nano_spent) is not int or not 0 <= nano_spent <= 1000000000 or
                        type(monetary_count) is not int or monetary_count < 0):
                    raise ProviderFailure('CLAUDE_COST_STORE_INVALID')
                if nano_spent + monetary > 1000000000:
                    raise ProviderFailure('CLAUDE_SPEND_LIMIT')
            events = _events(previous)
            events = [e for e in events if e['at'] > now - timedelta(hours=24)]
            own = [e for e in events if e.get('operation_id') == operation_id]
            if prior is None and own:
                raise ProviderFailure('PROVIDER_OPERATION_ALREADY_RESERVED_NO_REPLAY')
            if prior is not None:
                if any(e.get('phase') == 'correction' for e in own):
                    raise ProviderFailure('PROVIDER_CORRECTION_ALREADY_RESERVED_NO_REPLAY')
                if len(own) != offset or {e.get('slot') for e in own} != set(range(offset)):
                    raise ProviderFailure('PROVIDER_RESERVATION_LOST')
                for event in own:
                    _bound_event(prior, event)
                if not any(e.get('stage') == 'verify' and e.get('consumed') is True for e in own):
                    raise ProviderFailure('PROVIDER_CORRECTION_WITHOUT_VERIFICATION')
            if (len(events) + attempts > 120 or
                    sum(e['kind'] == 'generation' for e in events) + attempts > MAX_ATTEMPTS or
                    sum(e['tokens'] for e in events) + total > MAX_TOKENS or
                    count + attempts > MAX_ATTEMPTS or spent + total > MAX_TOKENS):
                raise ProviderFailure('PROVIDER_WHOLE_TURN_ALLOCATION_LIMIT')
            # The observed NORMAL Gemma quota is16000input tokens/minute.
            # Output tokens are not part of that quota. Conservative61-second
            # spacing keeps one permit in a rolling minute across both models;
            # large Haiku inputs are bounded by its native window and USD1 cost.
            start = max([now] + [e['at'] + timedelta(seconds=SLOT_SECONDS)
                                for e in events if not _sealed_unused(e) and
                                e['at'] > now - timedelta(seconds=SLOT_SECONDS)])
            slots = [start + timedelta(seconds=i * SLOT_SECONDS) for i in range(attempts)]
            if (slots[-1] - now).total_seconds() > self.maximum_queue_seconds:
                raise ProviderFailure('PROVIDER_WHOLE_TURN_QUEUE_BOUND')
            if deadline is not None and slots[-1] >= deadline:
                raise ProviderFailure('PROVIDER_OPERATION_DEADLINE_EXCEEDED')
            reserved = [{'at':slot, 'tokens':row['tokens'], 'kind':'generation',
                         'operation_id':operation_id, 'slot':offset + i, 'consumed':False,
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
            tx.set(lifetime, {'version':VERSION, 'maximum_tokens':MAX_TOKENS,
                              'maximum_attempts':MAX_ATTEMPTS,
                              'reserved_tokens':spent + total,
                              'reserved_attempts':count + attempts})
            if monetary:
                tx.set(claude, {'version': CLAUDE_VERSION, 'model': HAIKU,
                    'maximum_nanodollars': 1000000000, 'reserved_nanodollars': nano_spent + monetary,
                    'reservation_count': monetary_count + 1})
            return slots

        try:
            slots = reserve(self.client.transaction())
        except ProviderFailure:
            raise
        except Exception:
            raise ProviderFailure('PROVIDER_ADMISSION_STORE_UNAVAILABLE') from None
        return slots, nonce

    def begin_turn(self, operation_id, attempts=8, *, plan=None, compatibility_full_plan=False):
        if (type(operation_id) is not str or not 1 <= len(operation_id) <= 200 or
                getattr(self.local, 'turn', None) is not None):
            raise ProviderFailure('WHOLE_TURN_RESERVATION_INVALID')
        entries, monetary = _plan(plan, attempts)
        phased = plan is not None and len(entries) == 3
        if plan is not None and len(entries) == 6 and compatibility_full_plan is not True:
            raise ProviderFailure('FULL_NATIVE_PLAN_REQUIRES_EXPLICIT_COMPATIBILITY')
        from evidence_registry import content_hash
        plan_sha = content_hash(plan) if plan is not None else None
        role_identity = _role_identity(plan, entries, 'verify') if plan is not None else None
        deadline = _OPERATION_DEADLINE.get()
        phase = 'initial' if phased else 'compatibility'
        slots, nonce = self._reserve_entries(operation_id, entries, monetary, deadline, plan_sha, phase)
        attempts = len(entries)
        total = sum(row['tokens'] for row in entries)
        receipt = {'version':VERSION, 'pacing_version':PACING_VERSION,
                   'plan_version': PLAN_VERSION if plan is not None else 'LEGACY_FIXED_ENVELOPE',
                   'reservation_mode': 'INITIAL_PAIR_CONDITIONAL_CORRECTION' if phased else 'EXPLICIT_COMPATIBILITY',
                   'reserved_attempts':attempts, 'reserved_tokens':total,
                   'reserved_nanodollars': monetary, 'reserved_slots':deepcopy(entries),
                   'maximum_corrections': 1 if phased else None, 'correction_reserved': False,
                   'phases': [{'phase':phase, 'phase_nonce':nonce, 'plan_sha256':plan_sha,
                       'reserved_attempts':attempts, 'reserved_tokens':total, 'reserved_nanodollars':monetary}],
                   'maximum_wait_seconds':max(0, (slots[-1] - self.now()).total_seconds()),
                   'sealing_status':'ACTIVE_RESERVATIONS_RETAINED', 'sealed_unused_slots':0}
        if plan is not None and 'role_plan' in plan:
            from evidence_registry import content_hash
            receipt['role_forecast_binding'] = deepcopy({key: value for key, value in plan.items() if key != 'slots'})
            receipt['role_forecast_sha256'] = content_hash(plan)
        # The composer retains this same receipt in its trace. Final sealing
        # updates it without needing to replace an original generation error.
        self.local.turn = {'operation_id':operation_id, 'slots':slots, 'entries':entries, 'next':0,
                           'deadline':deadline, 'receipt':receipt, 'plan_sha256': plan_sha,
                           'entry_plan_hashes': [plan_sha] * attempts, 'role_identity': role_identity,
                           'entry_phases': [phase] * attempts, 'entry_nonces': [nonce] * attempts,
                           'phase':phase, 'correction_attempted':False}
        return receipt

    def reserve_correction(self, operation_id, *, plan):
        from evidence_registry import content_hash
        turn = getattr(self.local, 'turn', None)
        if (turn is None or operation_id != turn['operation_id'] or turn['phase'] != 'initial' or
                turn['correction_attempted'] or len(turn['entries']) != 3):
            raise ProviderFailure('PROVIDER_CORRECTION_ALREADY_RESERVED_NO_REPLAY')
        entries, monetary = _plan(plan, 3, phase='correction')
        role_identity = _role_identity(plan, entries, 'reverify')
        if role_identity != turn['role_identity']:
            raise ProviderFailure('PROVIDER_CORRECTION_MODEL_ROLE_BINDING_CHANGED')
        if _OPERATION_DEADLINE.get() != turn['deadline']:
            raise ProviderFailure('PROVIDER_OPERATION_DEADLINE_CHANGED')
        # A failed or uncertain reservation is terminal for this operation; it
        # cannot retry a commit whose result might already have been persisted.
        turn['correction_attempted'] = True
        plan_sha = content_hash(plan)
        slots, nonce = self._reserve_entries(operation_id, entries, monetary, turn['deadline'],
            plan_sha, 'correction', prior=turn)
        turn['entries'].extend(entries)
        turn['slots'].extend(slots)
        turn['entry_plan_hashes'].extend([plan_sha] * len(entries))
        turn['entry_phases'].extend(['correction'] * len(entries))
        turn['entry_nonces'].extend([nonce] * len(entries))
        turn['phase'] = 'correction'
        total = sum(row['tokens'] for row in entries)
        receipt = turn['receipt']
        receipt['reserved_attempts'] += len(entries)
        receipt['reserved_tokens'] += total
        receipt['reserved_nanodollars'] += monetary
        receipt['reserved_slots'].extend(deepcopy(entries))
        receipt['correction_reserved'] = True
        receipt['phases'].append({'phase':'correction', 'phase_nonce':nonce, 'plan_sha256':plan_sha,
            'reserved_attempts':len(entries), 'reserved_tokens':total, 'reserved_nanodollars':monetary,
            'role_forecast_binding':deepcopy({key:value for key,value in plan.items() if key != 'slots'})})
        receipt['maximum_wait_seconds'] = max(receipt['maximum_wait_seconds'],
            max(0, (slots[-1] - self.now()).total_seconds()))
        return receipt['phases'][-1]

    def __call__(self, tokens, kind):
        return self._permit(tokens, kind)

    def _permit(self, tokens, kind, *, model=None, stage=None):
        from google.cloud import firestore
        turn = getattr(self.local, 'turn', None)
        if (turn is None or type(tokens) is not int or not 0 < tokens <= MAX_TOKENS or
                kind != 'generation' or turn['next'] >= len(turn['slots'])):
            raise ProviderFailure('PROVIDER_UNRESERVED_ATTEMPT')
        index = turn['next']
        rows = turn['entries']
        if rows[index]['model'] is not None:
            if model not in MODEL_INPUT_LIMITS:
                raise ProviderFailure('PROVIDER_MODEL_ROLE_MISMATCH')
            while rows[index]['model'] != model:
                # A successful first Gemma attempt can skip ONLY its remaining
                # retry. Mandatory verification/correction stages cannot jump.
                if (index == 0 or rows[index]['attempt'] != 2 or
                        rows[index - 1]['stage'] != rows[index]['stage'] or
                        index + 1 >= len(rows)):
                    raise ProviderFailure('PROVIDER_MODEL_ROLE_MISMATCH')
                index += 1
            if stage is not None and rows[index]['stage'] != stage:
                raise ProviderFailure('PROVIDER_MODEL_ROLE_MISMATCH')
            actual_input = tokens - rows[index]['output_tokens']
            if (not 0 < actual_input <= rows[index]['input_tokens'] or
                    (model == GEMMA and actual_input > GEMMA_INPUT_TPM)):
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

