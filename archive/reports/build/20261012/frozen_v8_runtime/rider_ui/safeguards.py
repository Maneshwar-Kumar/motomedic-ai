"""Versioned input/admission/context checks for UI and hosted service integration.

No process-local counters: production must reserve with a managed transaction.
These checks never approve technical content or replace the evidence controller.
"""
from dataclasses import dataclass
from io import BytesIO
import hashlib
import json
import warnings

VERSION = 'rider-safeguards-v1'

@dataclass(frozen=True)
class Limits:
    message_characters: int = 2000
    message_utf8_bytes: int = 8000
    json_request_bytes: int = 16384
    photo_bytes: int = 5 * 1024 * 1024
    photo_pixels: int = 20_000_000
    photo_dimension: int = 10000
    normalized_photo_dimension: int = 1600
    photos_per_turn: int = 1
    photos_per_session: int = 3
    photos_per_day: int = 6
    turns_per_minute: int = 6
    turns_per_day: int = 30
    turns_per_session: int = 20
    input_tokens: int = 8192
    output_tokens: int = 1800
    provider_request_bytes: int = 24000
    idle_expiry_seconds: int = 1800
    session_expiry_seconds: int = 86400
    media_expiry_seconds: int = 900

LIMITS = Limits()

class LimitError(ValueError):
    def __init__(self, reason, status=413):
        super().__init__(reason)
        self.reason, self.status = reason, status


def validate_message(text):
    if type(text) is not str or not text.strip():
        raise LimitError('MESSAGE_REQUIRED', 400)
    if len(text) > LIMITS.message_characters:
        raise LimitError('MESSAGE_CHARACTER_LIMIT')
    try:
        encoded = text.encode('utf-8', errors='strict')
    except UnicodeError:
        raise LimitError('INVALID_TEXT_ENCODING', 400) from None
    if len(encoded) > LIMITS.message_utf8_bytes:
        raise LimitError('MESSAGE_BYTE_LIMIT')
    if any(ord(c) < 32 and c not in '\n\r\t' for c in text):
        raise LimitError('INVALID_TEXT_CONTROL', 400)
    # Injection-looking input is still DATA. No keyword filter can approve advice.
    return text.strip()


def validate_request_body(raw):
    if type(raw) is not bytes or len(raw) > LIMITS.json_request_bytes:
        raise LimitError('REQUEST_BODY_LIMIT')
    def unique(pairs):
        d = {}
        for key, value in pairs:
            if key in d:
                raise LimitError('DUPLICATE_JSON_KEY', 400)
            d[key] = value
        return d
    try:
        d = json.loads(raw.decode('utf-8'), object_pairs_hook=unique,
                       parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
    except LimitError:
        raise
    except (UnicodeError, ValueError, RecursionError):
        raise LimitError('INVALID_JSON', 400) from None
    if type(d) is not dict:
        raise LimitError('JSON_OBJECT_REQUIRED', 400)
    return d


def normalize_photo(raw, declared_mime):
    """Check actual decoding; return sanitized JPEG bytes. Never fetch a URL.

    Call after authenticated atomic admission and before any vision inference.
    Decode and normalization in production also need worker CPU/memory/time bounds.
    """
    from PIL import Image, UnidentifiedImageError
    allowed = {'image/jpeg': 'JPEG', 'image/png': 'PNG', 'image/webp': 'WEBP'}
    if declared_mime not in allowed:
        raise LimitError('PHOTO_TYPE', 415)
    if type(raw) is not bytes or not raw or len(raw) > LIMITS.photo_bytes:
        raise LimitError('PHOTO_BYTE_LIMIT')
    try:
        with warnings.catch_warnings():
            warnings.simplefilter('error', Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as image:
                if image.format != allowed[declared_mime]:
                    raise LimitError('PHOTO_CONTENT_TYPE_MISMATCH', 415)
                w, h = image.size
                if min(w, h) < 1 or max(w, h) > LIMITS.photo_dimension or w*h > LIMITS.photo_pixels:
                    raise LimitError('PHOTO_PIXEL_LIMIT')
                if getattr(image, 'n_frames', 1) != 1:
                    raise LimitError('ANIMATED_PHOTO', 415)
                image.verify()
            with Image.open(BytesIO(raw)) as image:
                from PIL import ImageOps
                image = ImageOps.exif_transpose(image)
                image.thumbnail((LIMITS.normalized_photo_dimension, LIMITS.normalized_photo_dimension))
                clean = Image.new('RGB', image.size, 'white')
                if 'A' in image.getbands():
                    rgba = image.convert('RGBA');clean.paste(rgba, mask=rgba.getchannel('A'))
                else:
                    clean.paste(image.convert('RGB'))
                out = BytesIO();clean.save(out, format='JPEG', quality=85)
                return out.getvalue()
    except LimitError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError,
            Image.DecompressionBombError, Image.DecompressionBombWarning):
        raise LimitError('PHOTO_DECODE_FAILED', 415) from None


@dataclass(frozen=True)
class Usage:
    """Trusted server counts within minute and rolling 24h windows; never request JSON."""
    minute_turns: int = 0
    day_turns: int = 0
    session_turns: int = 0
    day_photos: int = 0
    session_photos: int = 0


def check_admission(usage, *, photos=0):
    if not isinstance(usage, Usage) or any(type(x) is not int or x < 0 for x in vars(usage).values()):
        raise LimitError('INVALID_SERVER_USAGE', 503)
    if type(photos) is not int or not 0 <= photos <= LIMITS.photos_per_turn:
        raise LimitError('PHOTOS_PER_TURN', 400)
    if usage.minute_turns >= LIMITS.turns_per_minute or usage.day_turns >= LIMITS.turns_per_day:
        raise LimitError('VISITOR_RATE_LIMIT', 429)
    if usage.session_turns >= LIMITS.turns_per_session:
        raise LimitError('CONVERSATION_TURN_LIMIT', 429)
    if (usage.day_photos + photos > LIMITS.photos_per_day or
            usage.session_photos + photos > LIMITS.photos_per_session):
        raise LimitError('PHOTO_COUNT_LIMIT', 429)
    return Usage(usage.minute_turns+1, usage.day_turns+1, usage.session_turns+1,
                 usage.day_photos+photos, usage.session_photos+photos)


class AtomicAdmission:
    """Store must implement atomic reserve with ownership, dedupe and TTL.

    store.reserve(principal_id, session_id, operation_id, photos, policy_version,
                  update) invokes update(trusted_usage) INSIDE one transaction.
    Same identity+operation returns its existing reservation; mismatched replay
    rejects. Reservation precedes retrieval/provider work; failure spends the slot.
    No default in-memory store is supplied and store outage fails closed.
    """
    def __init__(self, store):
        self.store = store

    def reserve(self, principal_id, session_id, operation_id, *, photos=0):
        if any(type(x) is not str or not x or len(x) > 128 for x in
               (principal_id, session_id, operation_id)):
            raise LimitError('AUTHENTICATED_IDENTITY_REQUIRED', 401)
        try:
            return self.store.reserve(principal_id, session_id, operation_id, photos, VERSION,
                                      lambda usage: check_admission(usage, photos=photos))
        except LimitError:
            raise
        except Exception:
            raise LimitError('ADMISSION_UNAVAILABLE', 503) from None


def diagnostic_projection(session):
    """Deterministic state projection; never an LLM summary or a truncated history.

    Complete immutable events stay in the session store. All active outcomes and
    facts inform the controller; superseded events remain auditable in that store.
    """
    return {'manual_checksum': session.manual_checksum,
            'bike_variant': session.bike_variant, 'edition': session.edition,
            'symptoms': list(session.current_symptoms),
            'pending_step_id': session.pending_step_id, 'pending_rule_id': session.pending_rule_id,
            'excluded_branches': list(session.excluded_branches),
            'attempts': [{'attempt_id': a.attempt_id, 'step_id': a.step_id,
                          'outcome': a.outcome_enum.value,
                          'facts': {k: {'value': v.value, 'type': v.value_type,
                                        'unit': v.unit, 'confirmed': v.confirmed}
                                    for k,v in a.observed_details}}
                         for a in session.active_attempts()]}


def check_model_request(policy, payload, schema, token_count, *, output_tokens=1800):
    """Count the COMPLETE provider input, including schema/system wrappers.

    token_count(body) must be a trusted exact-model tokenizer/countTokens adapter.
    Missing/failed counting blocks new serving runtime; no silent truncation.
    It is NOT chars/4 and does not count only the rider's message.
    """
    if type(policy) is not str or not policy or type(payload) is not dict or type(schema) is not dict:
        raise LimitError('INVALID_MODEL_REQUEST', 503)
    if type(output_tokens) is not int or not 1 <= output_tokens <= LIMITS.output_tokens:
        raise LimitError('MODEL_OUTPUT_BUDGET', 503)
    try:
        encoded_schema = json.dumps(schema, ensure_ascii=False, allow_nan=False)
        encoded_payload = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    except (ValueError, TypeError, RecursionError):
        raise LimitError('INVALID_MODEL_REQUEST', 503) from None
    body = {'systemInstruction': {'parts': [{'text': policy + '\nReturn only JSON matching: ' +
                                            encoded_schema}]},
            'contents': [{'role': 'user', 'parts': [{'text': encoded_payload}]}],
            'generationConfig': {'maxOutputTokens': output_tokens, 'thinkingConfig': {'thinkingLevel': 'minimal'}}}
    try:
        wire = json.dumps(body, ensure_ascii=False, allow_nan=False).encode('utf-8')
    except (ValueError, UnicodeError, TypeError):
        raise LimitError('INVALID_MODEL_REQUEST', 503) from None
    if len(wire) > LIMITS.provider_request_bytes:
        raise LimitError('MODEL_CONTEXT_BYTE_LIMIT', 503)
    try:
        count = token_count(body)
    except Exception:
        raise LimitError('TOKEN_COUNT_UNAVAILABLE', 503) from None
    if type(count) is not int or count < 1:
        raise LimitError('TOKEN_COUNT_UNAVAILABLE', 503)
    if count > LIMITS.input_tokens:
        raise LimitError('MODEL_CONTEXT_TOKEN_LIMIT', 503)
    # Caller sends THIS body verbatim; do not add a transcript after admission.
    return body, {'policy_version': VERSION, 'input_tokens': count, 'max_output_tokens': output_tokens,
                  'request_bytes': len(wire), 'policy_sha256': hashlib.sha256(policy.encode()).hexdigest()}
