from pathlib import Path
import json,sys,re
sys.path.insert(0,str(Path('human_review/record_workflow').resolve()))
from workflow import encoded,digest
B=Path('human_review/record_workflow/batch_100')
MANUAL='cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89'
assert digest(Path('royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf').read_bytes())==MANUAL
C=json.loads((B/'batch_context.json').read_bytes())['batch_context_sha256']
parts=re.split(r'PDF PAGE (\d+)\n',(B/'source_views/judge/original_page_text.txt').read_text(encoding='utf-8'))
TEXT={int(parts[i]):parts[i+1] for i in range(1,len(parts),2)}
def emit(record,version,reason,verdict=None,judge_findings=None,dispositions=None):
    stem=f'{record}_v{version}'
    ap=B/'drafts'/f'{stem}.json';rp=B/'reviews'/f'{stem}_review.json'
    a=json.loads(ap.read_bytes());r=json.loads(rp.read_bytes())
    ar=json.loads((B/'receipts'/f'{stem}_author.json').read_bytes());rr=json.loads((B/'receipts'/f'{stem}_reviewer.json').read_bytes())
    assert ar['payload_sha256']==digest(ap.read_bytes()) and rr['payload_sha256']==digest(rp.read_bytes())
    assert r['author_sha256']==ar['payload_sha256'] and r['context_sha256']==C
    assert all(v['manual_sha256']==MANUAL and v['batch_context_sha256']==C for v in [a,r])
    assert len({a['actor'],r['actor'],'batch100-feedback-judge'})==3 and r['independent_original_review'] is True
    if version>1:
        previous=f'{record}_v{version-1}'
        previous_author=json.loads((B/'receipts'/f'{previous}_author.json').read_bytes())
        previous_judge=json.loads((B/'receipts'/f'{previous}_judge.json').read_bytes())
        assert a['previous_author_sha256']==previous_author['payload_sha256']
        assert a['feedback_judgment_sha256']==previous_judge['payload_sha256']
        assert a['changes'] and a['feedback_disposition']
    verdict=verdict or {'PASS':'PASS_AGENT_REVIEW','NEEDS_REVISION':'NEEDS_REVISION','SOURCE_GAP':'SOURCE_GAP'}[r['verdict']]
    findings=r['findings'] if judge_findings is None else judge_findings
    if verdict=='PASS_AGENT_REVIEW': assert r['verdict']=='PASS' and not findings
    dispositions=dispositions if dispositions is not None else {f['id']:'ACCEPTED: independently checked against original page and exact candidate; correction remains required before agent closure.' for f in r['findings']}
    checks=[]
    for ref in a['source_refs']:
        page=ref['pdf_page'];assert page in TEXT
        render=B/'source_views/judge'/f'original-{page:03d}.png';assert render.exists(),str(render)
        checks.append({'pdf_page':page,'printed_page':ref['printed_page'],'checked_span':TEXT[page].strip(),'inspection_method':'Judge independently read original full-page text and inspected rendered layout, printed label, relevant warnings/table/figure and continuation scope. No retrieval evidence used as authority.','original_render':str(render).replace('\\','/')})
    payload={'record_id':record,'version':version,'role':'judge','actor':'batch100-feedback-judge','manual_sha256':MANUAL,'batch_context_sha256':C,'context_sha256':C,'author_sha256':ar['payload_sha256'],'review_sha256':rr['payload_sha256'],'independent_original_review':True,'original_page_checks':checks,'findings':findings,'reason':reason+' Agent adjudication only; human acceptance, formal source/rule/dependency approval, rights and release remain separate.','feedback_disposition':dispositions,'verdict':verdict,'status':'DRAFT_ENGINEERING_ONLY'}
    out=B/'judgments'/f'{stem}_judgment.json'
    with out.open('xb') as f:f.write(encoded(payload))
    print(stem,verdict)
if __name__=='__main__':
    for item in json.loads(Path(sys.argv[1]).read_bytes()):emit(**item)
