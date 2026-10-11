"""Hosted API client. Keys stay on the UI server; no model or retrieval here."""
import json
import re
import uuid
from rider_ui.safeguards import LimitError, validate_message
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

MANUAL_SHA = 'cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89'
INDEX_ID = 'index_a3282c4d98cf54595e4ba168'
STATES = {'SUPPORTED', 'AMBIGUOUS', 'UNSUPPORTED', 'SAFETY_STOP', 'SYSTEM_ERROR'}
OUTCOMES = {'NOT_TRIED', 'OBSERVED_NORMAL', 'OBSERVED_ABNORMAL',
            'ACTION_COMPLETED_UNRESOLVED', 'NOT_APPLICABLE', 'UNCLEAR', 'RESOLVED'}
MAX_BYTES = 256 * 1024

class APIError(RuntimeError):
    """Sanitized message, never provider bodies or credentials."""

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise APIError('The service address changed. Please reconnect.')

def operation_id():
    return uuid.uuid4().hex

def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r'[a-zA-Z0-9_-]{16,128}', value)

def validate_view(view):
    if not isinstance(view, dict) or view.get('schema_version') != 'motomedic-rider-api-v1':
        raise APIError('The service returned an incompatible response.')
    if view.get('manual_checksum') != MANUAL_SHA or view.get('index_id') != INDEX_ID:
        raise APIError('The service manual does not match the selected source.')
    if not valid_id(view.get('session_id')) or type(view.get('version')) is not int or view['version'] < 0:
        raise APIError('The service could not confirm this session.')
    response = view.get('response')
    if response is None:
        raise APIError('The service returned no response.')
    if not isinstance(response, dict) or response.get('type') not in STATES:
        raise APIError('The service could not verify the response status.')
    if not isinstance(response.get('natural_language'), str) or not response['natural_language'].strip():
        raise APIError('The service returned an empty response.')
    technical = response.get('technical_content', True)
    if type(technical) is not bool:
        raise APIError('The service returned an invalid content classification.')
    if response['type'] in {'SUPPORTED', 'SAFETY_STOP'} and technical:
        if response.get('release_gate_passed') is not True or not response.get('cited_pages'):
            raise APIError('The service has not verified this answer for display.')
    citations = response.get('cited_pages', [])
    if not isinstance(citations, list):
        raise APIError('The service returned invalid source references.')
    for c in citations:
        if not isinstance(c, dict):
            raise APIError('The service returned invalid source references.')
        page = c.get('pdf_page')
        if (type(page) is not int or not 1 <= page <= 149 or c.get('pdf_page_index') != page - 1
                or c.get('manual_checksum') != MANUAL_SHA or c.get('index_id') != INDEX_ID
                or not isinstance(c.get('evidence_id'), str) or not c['evidence_id']):
            raise APIError('A source reference could not be verified.')
        if any(k in c for k in ('evidence_uri', 'excerpt', 'crop', 'image', 'text')):
            raise APIError('The service returned source content not permitted for display.')
    choices = view.get('choices', [])
    if not isinstance(choices, list) or len(choices) > 8:
        raise APIError('The service returned invalid feedback choices.')
    ids = set()
    for c in choices:
        if (not isinstance(c, dict) or not isinstance(c.get('id'), str) or not c['id']
                or not isinstance(c.get('label'), str) or not c['label']
                or c.get('outcome') not in OUTCOMES or c['id'] in ids):
            raise APIError('The service returned invalid feedback choices.')
        ids.add(c['id'])
    if response['type'] in {'UNSUPPORTED', 'SAFETY_STOP', 'SYSTEM_ERROR'} and choices:
        raise APIError('The service returned feedback for a stopped path.')
    if view.get('escalation_uri') not in (None, 'mailto:support@royalenfield.com'):
        raise APIError('The support destination could not be verified.')
    history = view.get('history', [])
    if not isinstance(history, list) or any(not isinstance(h, dict) or not isinstance(h.get('label'), str) for h in history):
        raise APIError('The service returned an invalid session history.')
    return view

class RiderAPI:
    def __init__(self, base_url, token, *, timeout=90, allow_loopback=False):
        p = urlsplit(base_url)
        local = allow_loopback and p.hostname in {'127.0.0.1', 'localhost'}
        if not p.hostname or (p.scheme != 'https' and not (local and p.scheme == 'http')):
            raise APIError('A secure hosted service address is required.')
        if p.username or p.password or p.query or p.fragment:
            raise APIError('The service address is invalid.')
        if not isinstance(token, str) or not token or '\r' in token or '\n' in token:
            raise APIError('The service connection is not configured.')
        self.base_url, self.token, self.timeout = base_url.rstrip('/'), token, timeout
        self.opener = build_opener(NoRedirect())

    def request(self, method, path, payload=None, request_id=None):
        headers = {'Authorization': 'Bearer ' + self.token, 'Accept': 'application/json'}
        if request_id:
            headers['Idempotency-Key'] = request_id
        raw = None if payload is None else json.dumps(payload, allow_nan=False).encode('utf-8')
        if raw is not None:
            headers['Content-Type'] = 'application/json'
        try:
            with self.opener.open(Request(self.base_url + path, raw, headers, method=method), timeout=self.timeout) as res:
                if res.headers.get_content_type() != 'application/json':
                    raise APIError('The service returned an unexpected response format.')
                data = res.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise APIError('The service response exceeded the display limit.')
                return json.loads(data)
        except HTTPError as exc:
            exc.close()
            messages = {409: 'This session changed. Reconnect to retrieve the latest step.',
                        429: 'The demo reached its request limit. Please try again later.',
                        401: 'The service connection needs to be refreshed.',
                        403: 'The service connection needs to be refreshed.'}
            raise APIError(messages.get(exc.code, 'The service is temporarily unavailable. Reconnect before continuing.')) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise APIError('The service is temporarily unavailable. Reconnect before continuing.') from None

    def catalogue(self):
        data = self.request('GET', '/v1/catalogue')
        if (not isinstance(data, dict) or data.get('schema_version') != 'motomedic-rider-api-v1'
                or data.get('manual_checksum') != MANUAL_SHA or data.get('index_id') != INDEX_ID):
            raise APIError('The service manual does not match the selected source.')
        topics = data.get('topics')
        if (not isinstance(topics, list) or not topics or len(topics) > 200
                or any(not isinstance(t, dict) or not isinstance(t.get('id'), str) or not isinstance(t.get('label'), str) for t in topics)
                or len({t['id'] for t in topics}) != len(topics)):
            raise APIError('The service could not load the available topics.')
        return data

    def start(self, topic, query, request_id):
        try:
            query = validate_message(query)
        except LimitError:
            raise APIError('Enter a message of up to 2,000 characters.') from None
        return validate_view(self.request('POST', '/v1/sessions', {
            'topic_id': topic, 'query': query, 'bike_variant': 'Himalayan BS6',
            'manual_checksum': MANUAL_SHA, 'index_id': INDEX_ID,
            'confirmed_himalayan_bs6': True, 'cache_mode': 'bypass'}, request_id))

    def feedback(self, view, choice_id, request_id):
        if not valid_id(view.get('session_id')):
            raise APIError('The session identifier is invalid.')
        return validate_view(self.request('POST', '/v1/sessions/' + view['session_id'] + '/feedback', {
            'expected_version': view['version'], 'choice_id': choice_id,
            'cache_mode': 'bypass'}, request_id))

    def recover(self, session_id):
        if not valid_id(session_id):
            raise APIError('The session identifier is invalid.')
        return validate_view(self.request('GET', '/v1/sessions/' + session_id))

    def recover_operation(self, request_id):
        if not re.fullmatch(r'[a-f0-9]{32}', request_id):
            raise APIError('The request identifier is invalid.')
        return validate_view(self.request('GET', '/v1/operations/' + request_id))

