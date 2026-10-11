"""Real browser UI engineering smoke; no hosted or model acceptance implied."""
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
from urllib.request import urlopen
from playwright.sync_api import sync_playwright
from rider_ui.tests.fixture_api import serve

def run():
    out=Path(os.environ.get('MOTOMEDIC_UI_SMOKE_OUTPUT','reports/rider_ui'));out.mkdir(parents=True,exist_ok=True)
    server=serve(0);threading.Thread(target=server.serve_forever,daemon=True).start()
    env=dict(os.environ,MOTOMEDIC_RIDER_API_URL='http://127.0.0.1:'+str(server.server_port),
             MOTOMEDIC_RIDER_API_TOKEN='ui-test-only',MOTOMEDIC_UI_ENGINEERING_LOOPBACK='1',
             STREAMLIT_BROWSER_GATHER_USAGE_STATS='false')
    proc=subprocess.Popen([sys.executable,'-m','streamlit','run','rider_ui/app.py',
                           '--server.address=127.0.0.1','--server.port=8767','--server.headless=true',
                           '--browser.gatherUsageStats=false','--global.developmentMode=false'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                           creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    checks=[]
    try:
        for _ in range(30):
            if proc.poll() is not None: raise RuntimeError("UI process exited before health check")
            try:
                with urlopen('http://127.0.0.1:8767/_stcore/health',timeout=1) as r:
                    if r.status==200: break
            except OSError: time.sleep(1)
        else: raise RuntimeError('UI did not become ready')
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            page=browser.new_page(viewport={'width':1440,'height':1100},device_scale_factor=1)
            errors=[];page.on('pageerror',lambda err:errors.append(str(err)))
            page.goto('http://127.0.0.1:8767',wait_until='networkidle')
            page.get_by_text('MotoMedic handles your routine queries for your Himalayan',exact=True).wait_for(timeout=30000)
            page.locator('.footer-note').wait_for(timeout=30000)
            page.get_by_role('textbox',name='Describe one symptom or ask a question…').wait_for(timeout=30000)
            card = page.locator('[data-testid="stVerticalBlock"]').filter(has=page.get_by_role('heading', name='What are you noticing?', exact=True)).last
            assert card.get_by_role('textbox',name='Describe one symptom or ask a question…').count() == 1
            assert page.get_by_text('Available topics come from the hosted controller.',exact=False).count() == 0
            assert page.get_by_role('combobox',name='Choose the closest topic').count() == 0
            assert page.get_by_text('Select a topic',exact=True).count() == 0
            checks.append({'name':'inline_symptom_input_and_no_category_selector','passed':True})
            page.screenshot(path=str(out/'desktop.png'),full_page=True)
            page.get_by_text('My motorcycle is a Himalayan BS6',exact=True).click()
            page.get_by_role('checkbox',name='My motorcycle is a Himalayan BS6').wait_for()
            page.screenshot(path=str(out/'scope_confirmed.png'),full_page=True)
            entry=page.get_by_role('textbox',name='Describe one symptom or ask a question…')
            entry.fill('Engineering fixture only')
            entry.press('Enter')
            page.get_by_role('button',name='Yes',exact=True).wait_for(timeout=30000)
            page.get_by_role('button',name='Yes',exact=True).click()
            page.get_by_role('button',name='Tried, not fixed',exact=True).wait_for(timeout=30000)
            page.screenshot(path=str(out/'feedback.png'),full_page=True)
            page.get_by_role('button',name='Tried, not fixed',exact=True).click()
            page.get_by_text('No supported next step',exact=True).wait_for(timeout=30000)
            page.get_by_text('What this conversation remembers',exact=True).click()
            page.get_by_text('Tried, not fixed · ACTION_COMPLETED_UNRESOLVED',exact=True).wait_for()
            checks.append({'name':'browser_clarification_action_unresolved_referral','passed':True,'execution':'SYNTHETIC_UI_API_ONLY'})
            checks.append({'name':'no_browser_page_errors','passed':not errors})
            checks.append({'name':'no_horizontal_overflow_desktop','passed':page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')})
            mobile=browser.new_page(viewport={'width':390,'height':844},device_scale_factor=1)
            mobile.goto('http://127.0.0.1:8767',wait_until='networkidle')
            mobile.get_by_text('MotoMedic handles your routine queries for your Himalayan',exact=True).wait_for(timeout=30000)
            mobile.get_by_text('MotoMedic handles your routine queries for your Himalayan',exact=True).scroll_into_view_if_needed()
            mobile.screenshot(path=str(out/'mobile.png'),full_page=True)
            mobile.get_by_role('textbox',name='Describe one symptom or ask a question…').scroll_into_view_if_needed()
            mobile.screenshot(path=str(out/'mobile_input.png'),full_page=True)
            checks.append({'name':'no_horizontal_overflow_mobile','passed':mobile.evaluate('document.documentElement.scrollWidth <= window.innerWidth')})
            browser.close()
        report={'schema_version':'rider-ui-engineering-smoke-v1','checks':checks,
                'live_hosted_acceptance_passed':False,'external_provider_calls':0,'real_retrieval_calls':0,
                'billing_changed':False,'deployment_changed':False}
        (out/'browser_smoke.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(report))
        if not all(c['passed'] for c in checks): raise RuntimeError('Browser check failed')
    finally:
        proc.terminate();proc.wait(timeout=15)
        server.shutdown();server.server_close()
if __name__=='__main__':run()

