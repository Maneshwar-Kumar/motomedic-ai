"""Private live question/API/browser acceptance; no tokens or rider text logged."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import time
import uuid

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from tools.connect_arm_a_ui import run, document, SECRET, REGION, OUT
from rider_ui.identity import issue

API='https://motomedic-arm-a-279945185781.us-central1.run.app'


def result(view,seconds):
    response=view['response']
    return {'type':response['type'],'technical_content':response.get('technical_content'),
            'release_gate_passed':response.get('release_gate_passed'),
            'text_sha256':hashlib.sha256(response['natural_language'].encode()).hexdigest(),
            'pages':sorted(set(c['pdf_page'] for c in response.get('cited_pages',[]))),
            'session_id':view['session_id'],'version':view['version'],'seconds':seconds}


def api_acceptance():
    from rider_ui.client import RiderAPI
    secret=run(['secrets','versions','access','1','--secret='+SECRET]).strip()
    identity=run(['auth','print-identity-token']).strip()
    cap=issue(secret)
    api=RiderAPI(API,lambda:identity,visitor=cap,timeout=190)
    catalogue=api.catalogue()
    assert catalogue['question_input']=='open' and catalogue['diagnostic_wizard'] is False
    receipts=[]
    key=uuid.uuid4().hex
    streamed=[]
    started=time.perf_counter()
    first=api.start('Can I use E20 petrol?',key,on_verified=lambda v:streamed.append(result(v,time.perf_counter()-started)))
    assert first['response']['type']=='SUPPORTED' and first['response']['release_gate_passed'] is True
    assert len(streamed)==1
    receipts.append({'name':'raw_question_verified_stream','result':result(first,time.perf_counter()-started),'first_verified':streamed[0]})
    started=time.perf_counter();recovered=api.recover_operation(key)
    assert recovered==first
    receipts.append({'name':'saved_operation_recovery','seconds':time.perf_counter()-started,'same_view':True})
    started=time.perf_counter()
    second=api.start('Why do vehicles look farther in my mirrors?',uuid.uuid4().hex,view=first)
    assert second['session_id']==first['session_id'] and second['version']>first['version']
    assert second['response']['type']=='SUPPORTED' and 13 in [c['pdf_page'] for c in second['response']['cited_pages']]
    receipts.append({'name':'new_question_outside_initial30_same_session','result':result(second,time.perf_counter()-started)})
    started=time.perf_counter()
    third=api.start('Are mirrors smaller than vehicles?',uuid.uuid4().hex,view=second)
    assert third['response']['type']=='UNSUPPORTED' and third['response']['technical_content'] is False
    receipts.append({'name':'different_proposition_abstains','result':result(third,time.perf_counter()-started)})
    started=time.perf_counter()
    fourth=api.start('Can I use E30 fuel?',uuid.uuid4().hex,view=third)
    assert fourth['response']['type']=='UNSUPPORTED'
    receipts.append({'name':'unsupported_fuel_abstains','result':result(fourth,time.perf_counter()-started)})
    receipt={'schema_version':'private-arm-a-question-acceptance-v1','passed':True,'api':API,'catalogue':catalogue,'checks':receipts,'provider_calls':0,'source_display':'METADATA_ONLY','latency_p95_measured':False,'browser_test_included':False}
    (OUT/'live_question_acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt))


def browser_acceptance():
    from playwright.sync_api import sync_playwright
    ui=document(['run','services','describe','motomedic-rider-ui','--region='+REGION])
    url=ui['status']['url']
    assert url.startswith('https://motomedic-rider-ui-') and url.endswith('.run.app')
    identity=run(['auth','print-identity-token']).strip()
    checks=[]
    with sync_playwright() as p:
        browser=p.chromium.launch(headless=True)
        context=browser.new_context(extra_http_headers={'Authorization':'Bearer '+identity},viewport={'width':1440,'height':1000})
        page=context.new_page()
        errors=[];page.on('pageerror',lambda e:errors.append(type(e).__name__))
        page.goto(url,wait_until='networkidle',timeout=90000)
        page.get_by_role('heading',name='What would you like to know?',exact=True).wait_for(timeout=90000)
        page.screenshot(path=str(OUT/'live_ui_connected.png'),full_page=True)
        # Streamlit's visible label is the pointer target over the styled input.
        page.get_by_text('My motorcycle is a Himalayan BS6',exact=True).click()
        assert page.get_by_role('checkbox',name='My motorcycle is a Himalayan BS6').is_checked()
        entry=page.get_by_role('textbox',name='Ask a question\u2026',exact=True)
        entry.fill('Can I use E20 petrol?');entry.press('Enter')
        page.get_by_text('Manual-backed response',exact=True).last.wait_for(timeout=180000)
        page.get_by_role('textbox',name='Ask another question\u2026',exact=True).wait_for(timeout=30000)
        checks.append({'name':'browser_managed_identity_raw_question_supported','passed':True})
        page.screenshot(path=str(OUT/'live_ui_desktop.png'),full_page=True)
        followup=page.get_by_role('textbox',name='Ask another question\u2026',exact=True)
        followup.fill('Can I use E30 fuel?');followup.press('Enter')
        try:
            page.get_by_text('I could not verify a supported answer to this question in the selected manual.',exact=False).last.wait_for(timeout=30000)
        except Exception:
            page.screenshot(path=str(OUT/'live_ui_followup_failure.png'),full_page=True)
            (OUT/'live_ui_followup_failure.txt').write_text(page.locator('body').inner_text(),encoding='utf-8')
            raise
        checks.append({'name':'browser_followup_abstention','passed':True})
        checks.append({'name':'desktop_no_overflow','passed':page.evaluate('document.documentElement.scrollWidth <= innerWidth')})
        page.screenshot(path=str(OUT/'live_ui_followup.png'),full_page=True)
        page.reload(wait_until='networkidle')
        page.get_by_role('heading',name='What would you like to know?',exact=True).wait_for(timeout=90000)
        checks.append({'name':'refresh_stable_visitor_connection','passed':page.get_by_text('Sign in to the private demo before continuing.',exact=True).count()==0})
        page.set_viewport_size({'width':390,'height':844})
        page.screenshot(path=str(OUT/'live_ui_mobile.png'),full_page=True)
        checks.append({'name':'mobile_no_overflow','passed':page.evaluate('document.documentElement.scrollWidth <= innerWidth')})
        checks.append({'name':'no_browser_page_errors','passed':not errors})
        context.close();browser.close()
    receipt={'schema_version':'private-arm-a-browser-acceptance-v1','passed':all(c['passed'] for c in checks),'url':url,'private_iam':True,'managed_ui_to_backend_identity':True,'checks':checks,'provider_calls':0,'photos_tested':False,'anonymous_access':False}
    (OUT/'live_browser_acceptance.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(receipt));assert receipt['passed']


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--browser',action='store_true');args=parser.parse_args()
    if args.browser:browser_acceptance()
    else:api_acceptance()
