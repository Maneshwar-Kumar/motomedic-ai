"""Structured logs and trace spans for the answer path. Rider text never reaches them.

Each event is one JSON line on stdout in the Cloud Logging structured format: severity, message
(the event name), the trace ("logging.googleapis.com/trace") and span
("logging.googleapis.com/spanId") that correlate it, then the event's fields.

Two rules keep rider text out, so it cannot be logged by mistake:
- a field name must be in FIELDS;
- a value must be a number, a boolean, None, or a token without spaces (an id, code, version or
  page), or a short list or mapping of those.

Anything else is dropped and its field name recorded in redacted_fields. A rider question is
described only by its length and word count, plus a keyed hash when MOTOMEDIC_LOG_HMAC_KEY is
set, so repeats can be linked without revealing the text. Spans are log entries with a span
id, a parent and a duration, grouped by trace id; they are not exported to Cloud Trace.
Telemetry never fails a turn. Policy: docs/PRIVACY.md.
"""
import hashlib
import hmac
import json
import math
import os
import re
import sys
import uuid

VERSION = 'answer-telemetry-v1'
PROJECT = 'motomedic-ai-20261009'
MAX_ITEMS = 50
_TOKEN = re.compile(r'[A-Za-z0-9_.:/+=-]{0,160}')
_TRACEPARENT = re.compile(r'00-([0-9a-f]{32})-[0-9a-f]{16}-[0-9a-f]{2}')
_CLOUD_TRACE = re.compile(r'([0-9a-f]{32})(?:/\d{1,20})?(?:;o=[01])?')
FIELDS = frozenset('''
    operation_id session_version route reason_codes failure_code provider_calls outcome http_status
    method path error_code replay span_name parent_span_id status error_type duration_ms offset_ms
    retrieval_version index_id chunk_ids dense_top bm25_top sections_disagree reranked
    rerank_skip_reason max_cross_score below_relevance_floor
    assembly_version sections lines warnings pages_sent model_input_chars
    generation_calls input_tokens uncached_input_tokens cache_creation_input_tokens
    cache_read_input_tokens cache_hit_observed output_tokens estimated_cost_usd reservation_mode
    sealing_status
    gate_version coverage citations cited_pages excluded_watchouts suppressed_disclaimers
    suppressed_duplicates rewritten_phrases
    question_chars question_words question_hmac history_turns stage_ms server_ms reason
'''.split())


def new_trace_id():
    return uuid.uuid4().hex


def new_span_id():
    return uuid.uuid4().hex[:16]


def trace_from_headers(headers):
    """The incoming W3C or Cloud Run trace id, or a new one. Only hex ids are accepted."""
    match = _TRACEPARENT.fullmatch((headers.get('traceparent') or '').strip().lower())
    if match and match.group(1) != '0' * 32:
        return match.group(1)
    match = _CLOUD_TRACE.fullmatch((headers.get('X-Cloud-Trace-Context') or '').strip().lower())
    if match and match.group(1) != '0' * 32:
        return match.group(1)
    return new_trace_id()


def question_shape(text, key=None):
    """Length and word count of a rider question, and a keyed hash when a key is configured."""
    key = os.environ.get('MOTOMEDIC_LOG_HMAC_KEY', '') if key is None else key
    text = text if isinstance(text, str) else ''
    shape = {'question_chars': len(text), 'question_words': len(text.split())}
    if key:
        shape['question_hmac'] = hmac.new(key.encode(), text.encode(), hashlib.sha256).hexdigest()[:32]
    return shape


def _clean(value, depth=0):
    """(value, True) when the value may be logged, else (None, False)."""
    if value is None or type(value) in (bool, int):
        return value, True
    if type(value) is float:
        return (round(value, 6), True) if math.isfinite(value) else (None, False)
    if type(value) is str:
        return (value, True) if _TOKEN.fullmatch(value) else (None, False)
    if depth < 2 and type(value) in (list, tuple) and len(value) <= MAX_ITEMS:
        items = [_clean(item, depth + 1) for item in value]
        return ([item for item, _ok in items], True) if all(ok for _item, ok in items) else (None, False)
    if depth < 2 and type(value) is dict and len(value) <= MAX_ITEMS:
        items = {key: _clean(item, depth + 1) for key, item in value.items()}
        if all(type(key) is str and _TOKEN.fullmatch(key) and ok for key, (_item, ok) in items.items()):
            return {key: item for key, (item, _ok) in items.items()}, True
    return None, False


class Telemetry:
    """Writes allowlisted events as JSON lines; tests pass a list's append as the sink."""
    def __init__(self, sink=None, project=PROJECT):
        self.sink = sink or (lambda line: print(line, file=sys.stdout, flush=True))
        self.project = project

    def emit(self, event, *, trace_id=None, span_id=None, severity='INFO', **fields):
        try:
            record = {'severity': severity, 'message': event, 'event': event, 'telemetry': VERSION}
            if trace_id:
                record['logging.googleapis.com/trace'] = 'projects/%s/traces/%s' % (self.project, trace_id)
            if span_id:
                record['logging.googleapis.com/spanId'] = span_id
            redacted = []
            for name, value in fields.items():
                cleaned, ok = _clean(value)
                if name in FIELDS and ok:
                    record[name] = cleaned
                else:
                    redacted.append(name)
            if redacted:
                record['redacted_fields'] = sorted(redacted)
            self.sink(json.dumps(record, separators=(',', ':'), allow_nan=False))
        except Exception:
            pass

    def span(self, name, trace_id, *, span_id=None, parent=None, duration_ms=None, **fields):
        """One finished span as a log entry; returns its span id for children."""
        span_id = span_id or new_span_id()
        self.emit('span', trace_id=trace_id, span_id=span_id, span_name=name, parent_span_id=parent,
                  duration_ms=duration_ms, **fields)
        return span_id


NULL = Telemetry(sink=lambda _line: None)
STDOUT = Telemetry()
