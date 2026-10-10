"""Presentation only: run python -m streamlit run rider_ui/app.py."""
import os
from pathlib import Path
import sys
import streamlit as st
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rider_ui.client import APIError, RiderAPI, operation_id

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
    return RiderAPI(setting('MOTOMEDIC_RIDER_API_URL'), setting('MOTOMEDIC_RIDER_API_TOKEN'),
                    allow_loopback=setting('MOTOMEDIC_UI_ENGINEERING_LOOPBACK') == '1')

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
        with st.spinner('Checking the applicable manual evidence…'):
            api = client()
            view = api.start(st.session_state.topic_id, value, pending['id']) if kind == 'start' else api.feedback(st.session_state.view, value['id'], pending['id'])
        remember(view, value if kind == 'start' else value['label'])
    except APIError as exc:
        st.session_state.connection_error = str(exc)
    st.rerun()

def reset():
    for k, v in [('messages', []), ('view', None), ('pending', None), ('connection_error', None)]:
        st.session_state[k] = v

for k, v in [('messages', []), ('view', None), ('pending', None), ('connection_error', None), ('catalogue', None)]:
    if k not in st.session_state:
        st.session_state[k] = v
configured = bool(setting('MOTOMEDIC_RIDER_API_URL') and setting('MOTOMEDIC_RIDER_API_TOKEN'))

with st.sidebar:
    st.markdown('<div class="brand-mark">M<span>+</span></div><h2>MotoMedic</h2><p class="sidebar-subtitle">Your next step, backed by the manual.</p>', unsafe_allow_html=True)
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
    st.button('Start a new conversation', on_click=reset, use_container_width=True, disabled=bool(st.session_state.pending))
    st.caption('Experimental advisory aid. Official service support remains available.')
    st.link_button('Contact Royal Enfield ↗', 'mailto:support@royalenfield.com', use_container_width=True)

left, right = st.columns([5, 2])
with left:
    st.markdown('<div class="eyebrow">MOTOMEDIC / RIDER SUPPORT</div>', unsafe_allow_html=True)
    st.title('A clearer next step.')
    st.write('Describe what you notice. We’ll work through one documented question or step at a time.')
with right:
    st.markdown('<div class="source-pill">●&nbsp; Himalayan BS6<br><small>Owner’s manual · 2025 edition</small></div>', unsafe_allow_html=True)
st.divider()

if not configured:
    st.info('The rider interface is ready. The hosted troubleshooting service is not connected yet.')
elif not st.session_state.catalogue:
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
        st.markdown('### What are you noticing?')
        st.write('Start with one symptom or question. Include what you have already checked.')
        if catalogue:
            topic = st.selectbox('Choose the closest topic', catalogue['topics'], index=None,
                                 placeholder='Select a topic', format_func=lambda t: t['label'], disabled=not ready)
            st.session_state.topic_id = topic['id'] if topic else None
        else:
            st.selectbox('Choose the closest topic', [], placeholder='Topics load when the service connects', disabled=True)
            st.session_state.topic_id = None
        st.caption('Available topics come from the hosted controller. Selecting a topic does not establish answer support.')
    cols = st.columns(3)
    for col, title, body in zip(cols, ['01 · Describe', '02 · Check', '03 · Report'],
                               ['Tell us what you can see or hear.', 'Read one supported question or step.', 'Share the result so the next turn remembers it.']):
        with col:
            with st.container(border=True):
                st.markdown('**' + title + '**')
                st.write(body)

labels = {'SUPPORTED': 'Manual-backed response', 'AMBIGUOUS': 'One detail to confirm',
          'UNSUPPORTED': 'No supported next step', 'SAFETY_STOP': 'Safety stop', 'SYSTEM_ERROR': 'Unable to verify right now'}
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
    st.warning(st.session_state.connection_error)
    st.caption('The request may already be saved. Retrieve its result before sending more feedback.')
    if st.button('Reconnect and retrieve result', type='primary'):
        try:
            pending = st.session_state.pending
            with st.spinner('Retrieving the saved response…'):
                view = client().recover_operation(pending['id']) if pending else client().recover(st.session_state.view['session_id'])
            rider_text = None if not pending else pending['value'] if pending['kind'] == 'start' else pending['value']['label']
            remember(view, rider_text)
            st.rerun()
        except APIError as exc:
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
            st.caption('No step results have been recorded yet.')
        for item in view.get('history', []):
            st.text(item['label'])
        st.caption('Reported success does not verify the repair or identify its cause.')

st.caption('Photo observations become available after the live text flow passes its acceptance check.')
st.button('Add a bike photo · coming next', disabled=True)
if not view:
    query = st.chat_input('Describe one symptom or ask a question…', max_chars=2000,
                          disabled=not ready or not st.session_state.get('topic_id') or bool(st.session_state.pending))
    if query and query.strip():
        perform('start', query.strip())
else:
    st.caption('Use the current choices above, or start a new conversation for a different symptom.')
st.markdown('<div class="footer-note">OEM evidence first. One step at a time.</div>', unsafe_allow_html=True)

