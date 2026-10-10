"""Read-only exact artifact audit; writes only the judge's closure artifacts."""
from pathlib import Path
import json,sys
sys.path.insert(0,str(Path('human_review/record_workflow').resolve()))
from workflow import digest,encoded
B=Path('human_review/record_workflow/batch_100')
M='cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89'
assert digest(Path('royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf').read_bytes())==M
C=json.loads((B/'batch_context.json').read_bytes())['batch_context_sha256']
records=[]
for i in range(1,101):
    rid=f'GEN{i:03d}'
    paths=list((B/'drafts').glob(f'{rid}_v*.json'))
    assert paths,rid
    ap=max(paths,key=lambda p:int(p.stem.rsplit('_v',1)[1]))
    a=json.loads(ap.read_bytes());v=a['version'];stem=f'{rid}_v{v}'
    rp=B/'reviews'/f'{stem}_review.json';jp=B/'judgments'/f'{stem}_judgment.json'
    r=json.loads(rp.read_bytes());j=json.loads(jp.read_bytes())
    ah=digest(ap.read_bytes());rh=digest(rp.read_bytes());jh=digest(jp.read_bytes())
    assert j['verdict']=='PASS_AGENT_REVIEW' and r['verdict']=='PASS',stem
    assert j['author_sha256']==r['author_sha256']==ah and j['review_sha256']==rh,stem
    assert all(x['manual_sha256']==M and x['batch_context_sha256']==C for x in [a,r,j]),stem
    assert r['context_sha256']==j['context_sha256']==C,stem
    assert len({a['actor'],r['actor'],j['actor']})==3,stem
    assert r['independent_original_review'] and j['independent_original_review'],stem
    assert not r['findings'] and not j['findings'],stem
    pages={x['pdf_page'] for x in a['source_refs']}
    assert pages <= {x['pdf_page'] for x in r['original_page_checks']},stem
    assert pages <= {x['pdf_page'] for x in j['original_page_checks']},stem
    for check in j['original_page_checks']:
        assert check['printed_page']==str(check['pdf_page']-2),stem
        assert Path(check['original_render']).exists(),stem
    assert a['origin_declaration']=='Generated based on feedback from the first 11 cases',stem
    if v>1:
        prior=f'{rid}_v{v-1}'
        assert a['previous_author_sha256']==digest((B/'drafts'/f'{prior}.json').read_bytes()),stem
        assert a['feedback_judgment_sha256']==digest((B/'judgments'/f'{prior}_judgment.json').read_bytes()),stem
        assert a['changes'] and a['feedback_disposition'],stem
    records.append({'record_id':rid,'version':v,'author_path':str(ap).replace('\\','/'),'author_sha256':ah,'review_path':str(rp).replace('\\','/'),'review_sha256':rh,'judge_path':str(jp).replace('\\','/'),'judge_sha256':jh,'agent_verdict':j['verdict'],'expected_route':a['expected_route'],'source_pages':sorted(pages),'status':'DRAFT_ENGINEERING_ONLY'})
assert len({x['record_id'] for x in records})==100
report={'manual_sha256':M,'batch_context_sha256':C,'actor':'batch100-feedback-judge','records':records,'record_count':100,'revised_records':sum(x['version']>1 for x in records),'revision_budget_maximum':3,'maximum_used_revision_cycles':max(x['version']-1 for x in records),'binding_audit':'PASS','agent_loop_scope':'Exact engineering candidate handling only; actual rights, source limitations, human acceptance, formal source/rule/dependency approval and release remain separate. Synthetic policy/failure fixtures are not infrastructure tests or new OEM procedures.'}
with (B/'judgments/judge_closure_audit.json').open('xb') as f:f.write(encoded(report))
text='''# Hundred-case independent judge closure\n\nAll 100 native GEN candidates have exact current author, independent source/experience review and judge bindings. The latest candidate handling passes agent review. All remain engineering drafts; this is not human acceptance, formal source/rule/dependency approval, public permission or release.\n\nThirteen records required one revision: GEN008 refuelling safety context; GEN014 lubricant caution; GEN016 and GEN021 safety-stop routing; GEN037 unsupported owner reset; GEN052 accessible variant discovery; GEN057 and GEN058 focused follow-up; GEN059 no-start applicability; GEN086 complete ABS safety dependencies; GEN091 both display-layout sources and accessible observation; GEN094 ABS bypass safety stop; GEN099 separate open warning clarification. Frozen initial findings and exact revised content are preserved. No record needed a second or third revision.\n\nOriginal manual bytes were independently checked against the registered checksum. The judge independently read original full-page text and rendered layouts, including tables, diagrams, continuation pages, printed labels and relevant warnings. Every author source page has both reviewer and judge checks. The exact inventory and content hashes are in judge_closure_audit.json. Named actors are distinct; hashes establish content identity, not signed human reviewer identity.\n\nScoped abstention passes do not approve unavailable requested guidance. Actual limitations for GEN004 accessory-specific GMA payload, GEN047 exact plug ordering part, GEN048 current OS compatibility, GEN050 exhaust-touch clearance and GEN097/GEN100 display rights remain for the human source/rights queue. Synthetic missing-warning, unit, mapping, figure and recovery fixtures do not claim an actual new extraction failure. Operational timeout/corruption examples are policy cases, not executed infrastructure evaluations.\n\nNo source registry, cache, provider/controller code, deployed service, index, billing or secret was changed.\n'''
with (B/'judgments/JUDGE_CLOSURE_AUDIT.md').open('x',encoding='utf-8') as f:f.write(text)
print('Judge binding audit PASS:100 latest records;',report['revised_records'],'revised; max cycles',report['maximum_used_revision_cycles'])
