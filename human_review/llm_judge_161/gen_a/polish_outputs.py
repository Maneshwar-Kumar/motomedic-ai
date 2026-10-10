import json,re,hashlib
from pathlib import Path
here=Path('human_review/llm_judge_161/gen_a')
def clean(s):
    s=re.sub(r'\b(Page|page|pages|PDF|TRD)(?=\d)',r'\1 ',s)
    s=re.sub(r'\b(all|All|for|at|below|above|of|on|with|than|only|every)(?=\d)',r'\1 ',s)
    s=re.sub(r'\b(in|for|from)(?=GEN\d)',r'\1 ',s)
    s=re.sub(r'(October)(?=\d)',r'\1 ',s)
    s=re.sub(r'(\d)(?=(?:km|rpm|mm|ml)\b)',r'\1 ',s)
    return s
p=here/'records.json'
x=json.loads(p.read_text(encoding='utf-8'))
manual=Path.cwd()/'royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf'
for r in x['records']:
    for k in ['rationale','flow_rationale','smallest_required_correction']:
        r[k]=clean(r[k])
    for f in r['findings']:
        for k in ['consequence','source_or_policy_basis','smallest_fix']:
            f[k]=clean(f[k])
    for c in r['source_checks']:
        c['checked_relationship']=clean(c['checked_relationship'])
        c['original_pdf_path']=str(manual)
        c['original_pdf_sha256']=x['input_hashes'][manual.name]
        if c['layout_visual_inspected']:
            image=(here/f'original_page_{c["pdf_page"]:03}.png').resolve()
            c['original_render_path']=str(image)
            c['original_render_sha256']=hashlib.sha256(image.read_bytes()).hexdigest()
p.write_text(json.dumps(x,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
p=here/'REPORT.md'
s=clean(p.read_text(encoding='utf-8'))
s=s.replace('All50','All 50').replace('for49','for 49').replace('forGEN043','for GEN043').replace('that50','that 50').replace('Original149-page','Original 149-page').replace('the17.0-L','the 17.0-L').replace('USB2-A','USB 2-A').replace('greater-than2.5-A','greater-than-2.5-A').replace('returning text','returning text for 149 pages')
p.write_text(s,encoding='utf-8')
assert len(x['records'])==50
assert all(r['source_checks'] for r in x['records'])
assert all(isinstance(r['answer_quality'],int) and 1<=r['answer_quality']<=5 for r in x['records'])
assert all(f['quote'] in r['current_response'] for r in x['records'] for f in r['findings'])
print(json.dumps({'records_sha256':hashlib.sha256((here/'records.json').read_bytes()).hexdigest(),'quote_coverage':'PASS','source_checks':'PASS','record_count':50}))
