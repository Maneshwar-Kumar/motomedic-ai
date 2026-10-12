"""Hosted API client. Keys stay on the UI server; no model or retrieval here."""
import json
import hashlib
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
RUNTIME_POLICY = 'open-manual-haiku-draft-verify-v10_13'
CHECK_ERROR_COPY = 'I couldn\u2019t check the answer right now. Please try again shortly.'

class APIError(RuntimeError):
    """Sanitized message, never provider bodies or credentials."""
    def __init__(self,message,*,terminal=False):
        super().__init__(message)
        self.terminal=terminal

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise APIError('The service address changed. Please reconnect.')

def operation_id():
    return uuid.uuid4().hex

def valid_id(value):
    return isinstance(value, str) and re.fullmatch(r'[a-zA-Z0-9_-]{16,128}', value)

def validate_view(view, *, expected_policy=None):
    if not isinstance(view, dict) or view.get('schema_version') != 'motomedic-rider-api-v1':
        raise APIError('The service returned an incompatible response.')
    if expected_policy is not None and view.get('runtime_policy') != expected_policy:
        raise APIError(CHECK_ERROR_COPY)
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
    delivery = view.get('delivery')
    if delivery is not None:
        if (type(delivery) is not dict or not {'operation_id','response_sha256','runtime_lock','manual_checksum','index_id'} <= set(delivery) or set(delivery)-{'operation_id','response_sha256','runtime_lock','manual_checksum','index_id','evidence_payload_sha256','verification_binding_sha256','event_protocol'} or
                type(delivery.get('operation_id')) is not str or not re.fullmatch(r'[a-f0-9]{32}',delivery['operation_id']) or
                type(delivery.get('runtime_lock')) is not str or not re.fullmatch(r'[a-f0-9]{64}',delivery['runtime_lock']) or
                delivery.get('manual_checksum') != MANUAL_SHA or delivery.get('index_id') != INDEX_ID):
            raise APIError('The saved response bindings could not be verified.')
        if delivery.get('event_protocol') not in (None, 'operation-sequence-v1'):
            raise APIError('The saved event bindings could not be verified.')
        digest = hashlib.sha256(json.dumps(response,sort_keys=True,separators=(',',':'),
            ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()
        for key in ('evidence_payload_sha256','verification_binding_sha256'):
            value=delivery.get(key)
            if value is not None and (type(value) is not str or not re.fullmatch(r'[a-f0-9]{64}',value)):
                raise APIError('The saved verification bindings could not be verified.')
        verified=view.get('verified_delivery')
        if verified is not None:
            if (type(verified) is not dict or verified.get('operation_id')!=delivery['operation_id'] or
                    verified.get('runtime_lock')!=delivery['runtime_lock'] or
                    verified.get('manual_checksum')!=MANUAL_SHA or verified.get('index_id')!=INDEX_ID or
                    verified.get('presentation_sha256')!=digest or
                    verified.get('evidence_payload_sha256')!=delivery.get('evidence_payload_sha256') or
                    verified.get('binding_sha256')!=delivery.get('verification_binding_sha256') or
                    verified.get('text_sha256')!=hashlib.sha256(response['natural_language'].encode('utf-8')).hexdigest()):
                raise APIError('The saved verification bindings could not be verified.')
        if delivery.get('response_sha256') != digest:
            raise APIError('The saved response changed. Retrieve the original operation.')
    return view

class RiderAPI:
    def __init__(self, base_url, token, *, timeout=180, allow_loopback=False, visitor=None, cache_mode='bypass', network=None,answers_enabled=True):
        p = urlsplit(base_url)
        local = allow_loopback and p.hostname in {'127.0.0.1', 'localhost'}
        if not p.hostname or (p.scheme != 'https' and not (local and p.scheme == 'http')):
            raise APIError('A secure hosted service address is required.')
        if p.username or p.password or p.query or p.fragment:
            raise APIError('The service address is invalid.')
        if not callable(token) and (not isinstance(token, str) or not token or '\r' in token or '\n' in token):
            raise APIError('The service connection is not configured.')
        self.base_url, self.token, self.timeout = base_url.rstrip('/'), token, timeout
        self.engineering_loopback = local
        if cache_mode not in ('bypass', 'enabled'):
            raise APIError('Invalid cache mode.')
        self.cache_mode = cache_mode
        self.visitor = visitor
        self.network = network
        self.answers_enabled=answers_enabled is True
        self.opener = build_opener(NoRedirect())

    def request(self, method, path, payload=None, request_id=None, *, on_verified=None, on_progress=None, on_chunk=None, stream=False):
        if method!='GET' and not self.answers_enabled:
            from rider_ui.public_gateway import PREVIEW_MESSAGE
            raise APIError(PREVIEW_MESSAGE,terminal=True)
        try:
            credential = self.token() if callable(self.token) else self.token
        except Exception:
            raise APIError('The service connection needs to be refreshed.') from None
        if type(credential) is not str or not credential or '\r' in credential or '\n' in credential:
            raise APIError('The service connection needs to be refreshed.')
        headers = {'Authorization': 'Bearer ' + credential,
                   'Accept': 'text/event-stream' if stream else 'application/json'}
        if self.visitor:
            headers['X-MotoMedic-Visitor'] = self.visitor
        if self.network:
            headers['X-MotoMedic-Network'] = self.network
        if request_id:
            headers['Idempotency-Key'] = request_id
        raw = None if payload is None else json.dumps(payload, allow_nan=False).encode('utf-8')
        if raw is not None:
            headers['Content-Type'] = 'application/json'
        try:
            with self.opener.open(Request(self.base_url + path, raw, headers, method=method), timeout=self.timeout) as res:
                if getattr(res,'status',200) == 202:
                    raise APIError('This request is still processing. Retrieve its saved result shortly.')
                if stream and res.headers.get_content_type() == 'text/event-stream':
                    from rider_ui.verified_sse import read_verified_stream
                    def chunks():
                        reader = getattr(res,'read1',res.read)
                        while True:
                            data = reader(4096)
                            if not data:
                                break
                            yield data
                    return read_verified_stream(chunks(),on_verified,operation_id=request_id,
                                                on_progress=on_progress,on_chunk=on_chunk,
                                                expected_policy=None if self.engineering_loopback else RUNTIME_POLICY)
                if res.headers.get_content_type() != 'application/json':
                    raise APIError('The service returned an unexpected response format.')
                data = res.read(MAX_BYTES + 1)
                if len(data) > MAX_BYTES:
                    raise APIError('The service response exceeded the display limit.')
                result=json.loads(data)
                if path != '/v1/catalogue':
                    validate_view(result,expected_policy=None if self.engineering_loopback else RUNTIME_POLICY)
                return result
        except HTTPError as exc:
            terminal=False
            try:
                body=exc.read(MAX_BYTES+1)
                data=json.loads(body) if len(body)<=MAX_BYTES else None
                terminal=type(data) is dict and data.get('operation_terminal') is True
            except Exception:
                pass
            exc.close()
            messages = {409: 'This session changed. Reconnect to retrieve the latest step.',
                        429: CHECK_ERROR_COPY,
                        401: 'The service connection needs to be refreshed.',
                        403: 'The service connection needs to be refreshed.'}
            raise APIError(messages.get(exc.code, CHECK_ERROR_COPY),terminal=terminal) from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise APIError(CHECK_ERROR_COPY) from None

    def catalogue(self):
        data = self.request('GET', '/v1/catalogue')
        if (not isinstance(data, dict) or data.get('schema_version') != 'motomedic-rider-api-v1'
                or data.get('manual_checksum') != MANUAL_SHA or data.get('index_id') != INDEX_ID):
            raise APIError('The service manual does not match the selected source.')
        if data.get('question_input') != 'open':
            raise APIError('The service cannot yet accept rider questions. Please reconnect later.')
        if not self.engineering_loopback and data.get('streaming') != 'DRAFT_VERIFY_STREAM':
            raise APIError('The service cannot yet check and stream rider answers. Please reconnect later.')
        return data

    def start(self, query, request_id, *, view=None, on_verified=None, on_progress=None, on_chunk=None):
        try:
            query = validate_message(query)
        except LimitError as exc:
            message = ('Keep your question to 100 words or fewer.'
                       if exc.reason == 'MESSAGE_WORD_LIMIT'
                       else 'Enter a question of up to 100 words and 2,000 characters.')
            raise APIError(message, terminal=True) from None
        payload = {
            'query': query, 'bike_variant': 'Himalayan BS6',
            'manual_checksum': MANUAL_SHA, 'index_id': INDEX_ID,
            'confirmed_himalayan_bs6': True, 'cache_mode': self.cache_mode}
        path = '/v1/sessions'
        if view:
            validate_view(view,expected_policy=None if self.engineering_loopback else RUNTIME_POLICY)
            path += '/'+view['session_id']+'/questions'
            payload['expected_version'] = view['version']
        return validate_view(self.request('POST',path,payload,request_id,
                                         stream=True,on_verified=on_verified,on_progress=on_progress,on_chunk=on_chunk))

    def feedback(self, view, choice_id, request_id, *, on_verified=None, on_progress=None, on_chunk=None):
        validate_view(view,expected_policy=None if self.engineering_loopback else RUNTIME_POLICY)
        if not valid_id(view.get('session_id')):
            raise APIError('The session identifier is invalid.')
        return validate_view(self.request('POST', '/v1/sessions/' + view['session_id'] + '/feedback', {
            'expected_version': view['version'], 'choice_id': choice_id,
            'cache_mode': self.cache_mode}, request_id,stream=True,on_verified=on_verified,on_progress=on_progress,on_chunk=on_chunk))

    def recover(self, session_id):
        if not valid_id(session_id):
            raise APIError('The session identifier is invalid.')
        return validate_view(self.request('GET', '/v1/sessions/' + session_id))

    def recover_operation(self, request_id):
        if not re.fullmatch(r'[a-f0-9]{32}', request_id):
            raise APIError('The request identifier is invalid.')
        view = validate_view(self.request('GET', '/v1/operations/' + request_id))
        if view.get('delivery') and view['delivery']['operation_id'] != request_id:
            raise APIError('The saved response belongs to another request.')
        return view

