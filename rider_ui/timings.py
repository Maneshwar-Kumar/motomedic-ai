"""Allowlisted timing presentation, separate from the verified saved response."""
import math


def _seconds(value):
    if type(value) not in (int, float):
        return None
    try:
        value = float(value)
    except OverflowError:
        return None
    return value if math.isfinite(value) and value >= 0 else None


def _mapping(value):
    return value if type(value) is dict else {}


def _phase(composition, field, count_field, provider_field):
    attempts = composition.get('attempts')
    count = composition.get(count_field)
    if type(count) is int and count == 0:
        return None, 'not_required', None
    if type(attempts) is not list or not attempts:
        return None, 'not_recorded', None
    if type(count) is not int or count != len(attempts):
        return None, 'not_recorded', None
    durations = [_seconds(_mapping(attempt).get(field)) for attempt in attempts]
    if any(value is None for value in durations):
        return None, 'not_recorded', None
    provider = [_seconds(_mapping(_mapping(attempt).get(provider_field)).get('provider_seconds'))
                for attempt in attempts]
    seconds = _seconds(sum(durations))
    http = None if any(value is None for value in provider) else _seconds(sum(provider))
    return seconds, 'recorded' if seconds is not None else 'not_recorded', http


def timing_summary(view, delivery=None):
    """Five presentation rows; missing measurements stay missing.

    Retrieval includes ranking and evidence assembly, so the rows are not an
    additive waterfall. Draft/verifier phases include counting and admission
    waits. Delivery is measured by the UI client after an accepted SSE block,
    and never inserted into or inferred from the verified view.
    """
    controls = _mapping(_mapping(view).get('runtime_controls'))
    admission = _mapping(controls.get('source_admission'))
    policy = _mapping(admission.get('retrieval_policy'))
    stages = _mapping(policy.get('stages_seconds'))
    composition = _mapping(controls.get('composition'))

    def row(label, seconds=None, *, status=None, origin='SERVER_SAVED_TIMING', note=''):
        return {'label': label, 'seconds': seconds,
                'status': status or ('recorded' if seconds is not None else 'not_recorded'),
                'origin': origin, 'note': note}

    retrieval = row('Retrieval and assembly', _seconds(admission.get('retrieval_assembly_seconds')),
                    note='Includes concurrent searches, ranking and evidence assembly; do not add ranking again.')
    ranked = _seconds(stages.get('reranking'))
    ranking = row('Conditional ranking', ranked,
                  status='not_required' if ranked is None and type(policy.get('rerank_attempts')) is int and policy['rerank_attempts'] == 0 else None,
                  note='Conditional reranking only. RRF is included in retrieval; its separate duration is not recorded.')

    phases = {}
    for key, label, field, count, provider in (
            ('generation', 'Draft generation', 'draft_seconds', 'draft_calls', 'draft_provider'),
            ('verification', 'Verification', 'verification_seconds', 'verifier_calls', 'verification_provider')):
        seconds, status, http = _phase(composition, field, count, provider)
        note = 'Includes token counting and required admission/rate-limit waits; correction attempts are included.'
        if http is not None:
            note += ' Model HTTP calls: ' + format(http, '.2f') + ' s.'
        phases[key] = row(label, seconds, status=status, note=note)

    delivery = _mapping(delivery)
    seconds, status = None, 'not_recorded'
    operation = _mapping(_mapping(view).get('delivery')).get('operation_id')
    if (operation is not None and delivery.get('operation_id') == operation and
            delivery.get('origin') == 'UI_CLIENT_MONOTONIC' and delivery.get('transport') == 'sse'):
        if delivery.get('stream_complete') is True:
            seconds = _seconds(delivery.get('streaming_seconds'))
            status = 'recorded' if seconds is not None else 'not_recorded'
        elif delivery.get('stream_complete') is False:
            seconds = _seconds(delivery.get('streaming_elapsed_seconds'))
            status = 'interrupted' if seconds is not None else 'not_recorded'
    streaming = row('Answer delivery', seconds, status=status, origin='UI_CLIENT_MONOTONIC',
                    note='UI client receipt from the verified block to stream completion, including rendering callbacks; excludes the wait for verification.')
    if status == 'interrupted':
        streaming['note'] = 'Observed delivery until interruption; this is not a completed-stream duration.'
    return {'retrieval': retrieval, 'ranking': ranking, 'generation': phases['generation'],
            'verification': phases['verification'], 'streaming': streaming}
