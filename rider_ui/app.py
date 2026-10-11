"""Presentation only: run python -m streamlit run rider_ui/app.py."""
import os
from pathlib import Path
import sys
import streamlit as st
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rider_ui.client import APIError, RiderAPI, operation_id
from rider_ui.safeguards import LIMITS
from rider_ui.verified_sse import PROGRESS_LABELS
from rider_ui.identity import issue, verify, cloud_run_token, platform_subject

st.set_page_config(page_title='MotoMedic · Rider assistant', page_icon='🏍️', layout='wide')
st.markdown(Path(__file__).with_name('theme.css').read_text(encoding='utf-8'), unsafe_allow_html=True)

def setting(name):
    value = os.environ.get(name)
    if value is not None:
        return value
    try:
        return st.secrets.get(name, '')
    except (FileNotFoundError, st.errors.StreamlitSecretNotFoundError):
        return ''

def client():
    url = setting('MOTOMEDIC_RIDER_API_URL')
    managed = setting('MOTOMEDIC_RIDER_AUTH') == 'cloud_run'
    credential = (lambda:cloud_run_token(url)) if managed else setting('MOTOMEDIC_RIDER_API_TOKEN')
    anonymous = setting('MOTOMEDIC_RIDER_ACCESS') in ('anonymous_edge', 'public_gateway')
    network = None
    if anonymous:
        try:
            capability = st.context.headers.get('X-MotoMedic-Edge-Visitor')
            verify(setting('MOTOMEDIC_VISITOR_SECRET'), capability, 'anonymous-edge-v1')
            if setting('MOTOMEDIC_RIDER_ACCESS') == 'anonymous_edge':
                network = st.context.headers.get('X-MotoMedic-Edge-Network')
                verify(setting('MOTOMEDIC_VISITOR_SECRET'), network, 'anonymous-network-v1')
            st.session_state.visitor_capability = capability
        except (PermissionError, ValueError):
            raise APIError('Please refresh to reconnect securely.') from None
    if not anonymous and 'visitor_capability' not in st.session_state and setting('MOTOMEDIC_VISITOR_SECRET'):
        try:
            principal = platform_subject(st.context.headers) if managed and os.environ.get('K_SERVICE') else None
            st.session_state.visitor_capability = issue(setting('MOTOMEDIC_VISITOR_SECRET'),principal=principal)
        except (PermissionError,ValueError):
            raise APIError('Sign in to the private demo before continuing.') from None
    return RiderAPI(url, credential,
                    allow_loopback=setting('MOTOMEDIC_UI_ENGINEERING_LOOPBACK') == '1',
                    visitor=st.session_state.get('visitor_capability'),
                    cache_mode=setting('MOTOMEDIC_CACHE_MODE') or 'bypass', network=network)

def remember(view, rider_text=None):
    if rider_text:
        st.session_state.messages.append(('rider', rider_text))
    st.session_state.view = view
    st.session_state.messages.append(('assistant', view))
    st.session_state.pending = None
    st.session_state.connection_error = None

def perform(kind, value):
    pending = {'id': operation_id(), 'kind': kind, 'value': value}
    st.session_state.pending = pending
    try:
        with st.spinner('Connecting to MotoMedic...'):
            api = client()
            progress_slot = st.empty()
            answer_slot = st.empty()
            displayed = ['']
            def progress(stage):
                # Backend stages are operational events, never simulated timing.
                progress_slot.caption(PROGRESS_LABELS[stage])
            def verified(view):
                st.session_state.pending['verified'] = view
            def chunk(text):
                displayed[0] += text
                answer_slot.text(displayed[0])
            callbacks = {'on_verified':verified,'on_progress':progress,'on_chunk':chunk}
            view = api.start(value, pending['id'], view=st.session_state.view, **callbacks) if kind == 'start' else api.feedback(st.session_state.view, value['id'], pending['id'], **callbacks)
        remember(view, value if kind == 'start' else value['label'])
    except APIError as exc:
        if exc.terminal:
            st.session_state.pending = None
        st.session_state.connection_error = str(exc)
    st.rerun()

def reset():
    for k, v in [('messages', []), ('view', None), ('pending', None), ('connection_error', None)]:
        st.session_state[k] = v

for k, v in [('messages', []), ('view', None), ('pending', None), ('connection_error', None), ('catalogue', None)]:
    if k not in st.session_state:
        st.session_state[k] = v
configured = bool(setting('MOTOMEDIC_RIDER_API_URL') and
                  (setting('MOTOMEDIC_RIDER_API_TOKEN') or
                   (setting('MOTOMEDIC_RIDER_AUTH')=='cloud_run' and setting('MOTOMEDIC_VISITOR_SECRET'))))

with st.sidebar:
    st.markdown('<div class="brand-mark">M<span>+</span></div><h2>MotoMedic</h2><p class="sidebar-subtitle">Your questions answered, backed by the manual.</p>', unsafe_allow_html=True)
    st.divider()
    st.caption('YOUR MOTORCYCLE')
    st.selectbox('Motorcycle', ['Royal Enfield Himalayan 450'], disabled=True)
    confirmed = st.checkbox('My motorcycle is a Himalayan BS6', disabled=bool(st.session_state.view or st.session_state.pending))
    st.caption('SELECTED SOURCE')
    st.markdown('**Owner’s manual · English**')
    st.caption('RAM00818/A · 4 November 2025')
    with st.expander('Manual details'):
        st.write('This edition is selected for the Himalayan BS6 prototype. Citations identify the exact PDF page and evidence object.')
        st.caption('Manual pages and excerpts are not available for display in this demo.')
    st.divider()
    st.button('Start a new conversation', on_click=reset, use_container_width=True, disabled=bool(st.session_state.pending), help='Clear this chat and start a new conversation.')
    st.caption('Unable to find a resolution? Official service support remains available.')
    st.link_button('Contact Royal Enfield ↗', 'mailto:support@royalenfield.com', use_container_width=True)

left, right = st.columns([5, 2])
with left:
    st.markdown('<div class="eyebrow">MOTOMEDIC / RIDER SUPPORT</div>', unsafe_allow_html=True)
    st.title('MotoMedic handles your routine queries for your Himalayan')
    st.write('Ask a question about your motorcycle. MotoMedic answers when the selected manual supports it, and tells you when it cannot.')
with right:
    st.markdown('<div class="source-pill">●&nbsp; Himalayan BS6<br><small>Owner’s manual · 2025 edition</small></div>', unsafe_allow_html=True)
st.divider()

if configured and not st.session_state.catalogue:
    try:
        st.session_state.catalogue = client().catalogue()
    except APIError as exc:
        st.error(str(exc))
        if st.button('Reconnect to service'):
            st.rerun()

catalogue = st.session_state.catalogue
ready = configured and bool(catalogue) and confirmed
if not st.session_state.messages:
    with st.container(border=True):
        st.markdown('### What would you like to know?')
        st.write('Ask your question in your own words. Include relevant details and anything you have already checked.')
        st.caption('Up to 2,000 characters per message.')
        query = st.chat_input('Ask a question…', key='symptom_input', max_chars=LIMITS.message_characters,
                              disabled=not ready or bool(st.session_state.pending))
        if query and query.strip():
            perform('start', query.strip())
        st.file_uploader('Add a bike photo · coming next', type=['jpg', 'jpeg', 'png', 'webp'], accept_multiple_files=False, max_upload_size=5, disabled=True)
        st.caption('Photos: one per turn, up to 5 MB each; three per conversation. Photo support is coming next.')
    cols = st.columns(3)
    for col, title, body in zip(cols, ['01 · Ask', '02 · Read', '03 · Continue'],
                               ['Ask about your motorcycle.', 'Read a supported answer with source references.', 'Ask another question when you are ready.']):
        with col:
            with st.container(border=True):
                st.markdown('**' + title + '**')
                st.write(body)

labels = {'SUPPORTED': 'Answer', 'AMBIGUOUS': 'One detail to confirm',
          'UNSUPPORTED': 'No supported answer', 'SAFETY_STOP': 'Safety stop', 'SYSTEM_ERROR': 'Unable to verify right now'}
for index, (role, value) in enumerate(st.session_state.messages):
    with st.chat_message('user' if role == 'rider' else 'assistant', avatar='🏍️' if role == 'rider' else '🛠️'):
        if role == 'rider':
            st.text(value)
            continue
        response = value['response']
        state = response['type']
        st.caption('Conversation update' if state == 'SUPPORTED' and response.get('technical_content') is False else labels[state])
        # All dynamic text is literal. HTML/CSS above is repository-owned only.
        if state == 'SAFETY_STOP':
            st.error('Safety stop'); st.text(response['natural_language'])
        elif state == 'SYSTEM_ERROR':
            st.warning('Unable to verify right now'); st.text(response['natural_language'])
        else:
            st.text(response['natural_language'])
        citations = response.get('cited_pages', [])
        if citations:
            pages = sorted({c['pdf_page'] for c in citations})
            with st.expander('Source · PDF page' + ('s ' if len(pages) > 1 else ' ') + ', '.join(map(str, pages))):
                st.caption('Owner’s manual · RAM00818/A · 4 November 2025')
                for c in citations:
                    st.text('PDF page ' + str(c['pdf_page']) + ' · ' + c['evidence_id'])
                    if c.get('printed_page_label') is not None:
                        st.caption('Printed page: ' + str(c['printed_page_label']))
                st.caption('Display of original PDF pages and excerpts is restricted.')
        if value.get('escalation_uri'):
            st.link_button('Contact Royal Enfield ↗', value['escalation_uri'])
        if response.get('trace_id'):
            st.caption('Response reference: ' + response['trace_id'])

if st.session_state.connection_error:
    if st.session_state.pending and st.session_state.pending.get('verified'):
        retained = st.session_state.pending['verified']
        st.caption('Verified response received; completion is being recovered')
        st.text(retained['response']['natural_language'])
    st.warning(st.session_state.connection_error)
    st.caption('The request may already be saved. Retrieve its result before sending more feedback.')
    if st.session_state.pending and st.button('Reconnect and retrieve result', type='primary'):
        try:
            pending = st.session_state.pending
            with st.spinner('Retrieving the saved response…'):
                view = client().recover_operation(pending['id']) if pending else client().recover(st.session_state.view['session_id'])
            if pending and pending.get('verified') and view != pending['verified']:
                raise APIError('The saved response changed. Keep this request pending and reconnect.')
            rider_text = None if not pending else pending['value'] if pending['kind'] == 'start' else pending['value']['label']
            remember(view, rider_text)
            st.rerun()
        except APIError as exc:
            if exc.terminal:
                st.session_state.pending = None
            st.session_state.connection_error = str(exc)
            st.error(str(exc))

view = st.session_state.view
if view and not st.session_state.pending:
    choices = view.get('choices', [])
    if choices:
        st.markdown('**' + ('Your observation' if view['response']['type'] == 'AMBIGUOUS' else 'How did it go?') + '**')
        cols = st.columns(min(len(choices), 3))
        for i, choice in enumerate(choices):
            if cols[i % len(cols)].button(choice['label'], key='choice_' + str(view['version']) + '_' + choice['id'], use_container_width=True):
                perform('feedback', choice)
    with st.expander('What this conversation remembers'):
        if not view.get('history'):
            st.caption('No previous checks have been recorded yet.')
        for item in view.get('history', []):
            st.text(item['label'])
        st.caption('Reported success does not verify the repair or identify its cause.')

if view:
    query = st.chat_input('Ask another question…',key='followup_input',max_chars=LIMITS.message_characters,
                          disabled=not ready or bool(st.session_state.pending))
    if query and query.strip():
        perform('start',query.strip())
st.markdown('<div class="footer-note">Built on the Owner\'s Manual, with no misleading instructions on the internet</div>', unsafe_allow_html=True)

