"""Compile explicit agent adjudications. No inference, approvals or producer edits.

The plans are human-readable editorial decisions made after reading the claims,
OEM excerpts, original continuation pages/figures, TRD and owner feedback. They
are not computed by a lexical matcher. PDF token checks only verify extraction.
"""
import copy
import hashlib
import importlib.util
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET
import pymupdf

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
def digest(data): return hashlib.sha256(data).hexdigest()
def encoded(value): return (json.dumps(value,ensure_ascii=False,sort_keys=True,indent=2)+'\n').encode('utf-8')

# Each pipe separates an exact answer sentence. mN is the existing record's
# Nth manual object, pN a TRD paragraph, xNAME a checked supplementary source.
# '-' is nontechnical discourse. Policy is never labelled OEM authority.
GEN_PLANS = {
1:'m0|m0',2:'m0|m0',3:'-|m0 m1|m2',4:'m0 p5|m0 p138 xcontact',
5:'m0|m1 m2 m3',6:'m0|m1',7:'m0|m0 p5',
8:'-|m0 m1|m2 m3 m4 m5|m7|m6 m8|m9',9:'-|m0 m1|m0 m1 p96',
10:'-|m0 m1|m2',11:'-|m0 m1|m2 p99',12:'m0|p5 p99',13:'m0|m0 p5 p96',
14:'-|m0|m0 p5|m1|m2',15:'-|m0 m1|p96 p99',16:'-|m0|m1 p5 p138',
17:'m0|m1 m2',18:'-|m0',19:'m0|m1',20:'m0|m1',21:'m0|m0 p5',22:'m0|m1 m2',
23:'m0 m1|m2 m3 m4',24:'m0|p96',25:'m0 m1 m2 m3|p96 p99',26:'m0|m1',
27:'-|m0|p96',28:'m0',29:'m0 m1|p96 p99',30:'m0 m1 m2 m3 m4 m5|p72 p99',
31:'-|m0|m0 p5',32:'m0|p96',33:'m0|m0 p5',34:'-|m0',35:'m0|p96',36:'m0 xupshift|p96',
37:'m0|m1 p5',38:'m0 m1 m2|xmaintenance p99',39:'m0 m1|p96',40:'m0 m1|p99',
41:'m0 p96|p96 p138',42:'m0|p122',43:'m0 m1 m2|m1 m2 p98|p5 p122',
44:'-|m0|m1 m2 m3 m4',45:'-|m0 m1|m1 m2',46:'-|m0 m1 m2 m3 m4 m5 m6 m7 m8|p98',
47:'m0 m1 p5|p5 p138',48:'m0 m1 p72|xcontact',49:'m0 m1 m2|m0 p122 p138',
50:'m0|m0|m0 p5',
51:'p72 p99|p99 xcontact',52:'xfit p98|xfit p99 xcontact',53:'p120|p120 p99',
54:'p94 p130|p94 p138',55:'p94|p94 p79 p138',56:'p98 p100 p108',
57:'p98 p100|xfit',58:'p124|p106 p116 xissues|p98',59:'m0 p96 p106|m0 p98',
60:'p118|m0 p118 p106',61:'p80 p114|p79 p130',62:'-|p79|p79 p94',
63:'p79|p114 p138',64:'p79 p127|p94 p127',65:'p78 p147|p94 p147',
66:'p76 p96|p112',67:'-|p76 p99|p98 p99',68:'p94 p183|p94 p130',
69:'p183 p259|p183',70:'p183 p99|p183 p100',71:'p80 p142|p142 xcontact',
72:'p80|p142',73:'p79 p130|p80 p142',74:'p86|p86 p129',75:'p130|p130 p138',
76:'p127 p130|p130 p142',77:'p144 p130|p127 p144',78:'p79|p80 p129',
79:'p106|p92 p100 p106 p116',80:'p98 p100|p106 p98',81:'p85 p86|p86 p129',
82:'p100|p94 p100',83:'p146|p146 p114',84:'p148 p195|p148',85:'-|p5 p129|xcontact p129',
86:'m0|m1|p84 p129',87:'p75|p75 p80',88:'p85 p86|p86 p127',89:'-|p83 p112|p78 p79',
90:'-|p83|p76 p79',91:'p146|xanalog xdigital p98',92:'p149|p149 p220',
93:'p100|p100 p127',94:'p100 p146|m0 p122|p122 p146',95:'p94|p94 p79',
96:'p144|p129 p138',97:'xpermissions xswitchpermission xdisplay|xdisplay p226',98:'p148 p195|p195 p98',
99:'p124|xissues|p98 p146',100:'xdisplay xpermissions p3|xdisplay p226'
}
EXP_PLANS = {
1:'m0|xhazard|xhazard p98|m1|m2 m3|m4|m5|m6',2:'m0 p98|m0 m1|m2',
3:'m0|m1 m2 m3',4:'m0',5:'m0',6:'m0|xmenu|m1 m2|m4 m5 m6|m7 m8 m9|m9 m10|p5 p122',
7:'-|m1|xmode p98|m1 p5|p5 p122',8:'xmenu p5 p122|m0 m1|m2|m1 m3|m4 xtripconfirm|m5',
9:'-|m0|m1',10:'m0|p96',11:'m0 m1 p98|m1|p5 p122|m0 m1|m1',
12:'m0|m1|m2 m3|m4|m5|m6|m7',13:'m0 m1 m2|m2',14:'m0|m0 p5 p138',
15:'m0|m1 m2 m4|m4|m1 m4 p98|m1 m2 m3 p5|m3 p98|p96 p138',
16:'-|m0|m0 xparkingwarning|m1 m3|m4',17:'m0 m2 m3 m4|m5|m6|m7',18:'m0',19:'m1',
20:'-|m0|m0 m1 m2|m3',21:'m0|m1|m2',22:'m0|m1|m2',23:'-|m0|m0',
24:'-|m0 m1 m2 m3 m5|m4 m5',25:'m0 m1|m1|m2',26:'m0 m1|m2',
27:'m0 m1|m1 p114 p138',28:'m0|p96|m0 p98',29:'m0 m1|m2 m3',30:'m0 p98',
31:'p108 p106|m0|m1',32:'p79 p114 xchainflag|p138',33:'m0',34:'m0|m0 p5',
35:'m0|m1|m2 m3',36:'m0 m1',37:'m1 m2|m1 p5',38:'m0|m0 p5|p138',39:'m0',
40:'m0 m2|m0 m2 p127|p138',41:'m0 xloaded|p99 p127',
42:'xwashpressure|xwashcold xwashlow|xwashforce xwashcluster',43:'-|m0 xwashcold',
44:'m0|m1|m1 p5',45:'-|m0|m1',46:'m0',47:'m0 p98',48:'m0|m1',
49:'p146 p96|m0 p146|m1 p98',50:'p80 p142|p142 xcontact'
}

# The review flags exact draft defects instead of silently changing producer bytes.
ISSUES = {
'EXP027': {'claim':0,'verdict':'SOURCE_AMBIGUITY','reason':'Original PDF91 visibly prints "warm to the indicator". The draft changes this into "wear indicator" before acknowledging ambiguity. Do not establish a replacement threshold from that typo.', 'replacement':'The manual requires scheduled front/rear pad checks. Its printed replacement-threshold wording is unclear; have authorised service assess pad wear.'},
'EXP024': {'claim':1,'verdict':'SOURCE_AMBIGUITY','reason':'PDF88 visibly prints "sealer container". "Sealed" is an editorial interpretation, not an exact source term. Container wording must be clarified before a fluid-handling instruction; the DOT4, no-mixing and same-type rules are supported.', 'replacement':None},
'GEN058': {'claim':2,'verdict':'REVISE_RELEVANCE','reason':'The rider already says the same symptom returned. Re-asking which symptom discards known context. Retain the symptom and ask only for a genuinely missing current observation.', 'replacement':'I will retain the symptom you reported and the previous attempt history.'},
'GEN057': {'claim':0,'verdict':'REVISE_RIDER_LANGUAGE','reason':'NOT_APPLICABLE is a valid internal outcome but exposing its enum in rider text conflicts with the feedback handbook.', 'replacement':'I will record that the control is not fitted, rather than treat it as a normal check, and withhold the action that depends on it.'}
}

def main():
    spec=importlib.util.spec_from_file_location('binding_author',HERE/'author_bindings.py')
    author=importlib.util.module_from_spec(spec);spec.loader.exec_module(author)
    bindings=json.loads((HERE/'claim_bindings.json').read_bytes())
    objects,all_sources,_=author.load_sources()
    sources=copy.deepcopy(json.loads((HERE/'bound_sources.json').read_bytes())['sources'])
    policy_by_paragraph={str(x['paragraph_index']):eid for eid,x in all_sources.items() if 'paragraph_index' in x}
    manual=ROOT/'royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf'
    assert digest(manual.read_bytes())==bindings['manual_sha256']
    doc=pymupdf.open(manual)
    originals={}
    def original(page):
        if page not in originals:
            t=doc[page-1].get_text()
            eid='originalpdf_'+digest((bindings['manual_sha256']+':'+str(page)+':'+t).encode())[:24]
            sources[eid]={'evidence_id':eid,'authority':'OEM_ORIGINAL_PDF_CANDIDATE','manual_sha256':bindings['manual_sha256'],
                'pdf_page':page,'printed_page':str(page-2),'exact_text':t,'text_sha256':digest(t.encode()),
                'text_span':[0,len(t)],'bbox':list(doc[page-1].rect),'parser':'PyMuPDF '+pymupdf.VersionBind,
                'index_membership':False,'runtime_authorized':False}
            originals[page]=eid
        return originals[page]
    def fragment(page,needle):
        eid=original(page);t=sources[eid]['exact_text']
        assert needle.casefold() in t.casefold(),(page,needle)
        return eid
    extra={
      'menu':fragment(39,'IF PRESS JOYSTICK UP'),'upshift':fragment(57,'GEAR UPSHIFT INDICATOR'),
      'maintenance':fragment(124,'Months'),'parkingwarning':fragment(80,'causing injury'),
      'hazard':fragment(29,'HAZARD LIGHT SWITCH'),'mode':fragment(32,'MODE BUTTON'),
      'tripconfirm':fragment(44,'confirmation popup'),'analog':fragment(58,'For Analog Type'),
      'digital':fragment(59,'For Digital Type'),'loaded':fragment(117,'Tyre pressure'),
      'washpressure':fragment(118,'Do not use high pressure'),'washcold':fragment(118,'cold'),
      'washlow':fragment(118,'low pressure'),'washforce':fragment(118,'great force'),
      'washcluster':fragment(118,'bottom side of instrument'),'chainflag':fragment(103,'70 Nm')}
    for name,key in [('contact','/oem_service_route'),('fit','/applicability_policy'),('display','/display_policy')]:
        extra[name]=next(e for e,x in all_sources.items() if x.get('json_pointer')==key)
    handbook=ROOT/'human_review/subagent_feedback.md';hb=handbook.read_bytes();ht=hb.decode('utf-8')
    for name,needle in [('permissions','The owner explicitly permitted this fuse-location schematic'),('switchpermission','The owner authorised this switch schematic'),('issues','If the engine starts later')]:
        # Keep complete paragraph and exact character locator, not a new policy.
        loc=ht.casefold().find(needle.casefold())
        if loc<0 and name=='issues':loc=ht.find('if the engine starts later')
        assert loc>=0,(name,needle)
        start=ht.rfind('\n\n',0,loc)+2;end=ht.find('\n\n',loc)
        if end<0:end=len(ht)
        t=ht[start:end];eid='feedback_'+digest((digest(hb)+':'+str(start)+':'+t).encode())[:24]
        sources[eid]={'evidence_id':eid,'authority':'OWNER_FEEDBACK_POLICY','source_path':'human_review/subagent_feedback.md',
            'source_sha256':digest(hb),'source_span':[start,end],'exact_text':t,'text_span':[0,len(t)],'text_sha256':digest(t.encode())}
        extra[name]=eid
    results=[];claim_count=0
    for r in bindings['records']:
        rid=r['record_id'];n=int(rid[3:]);plans=(GEN_PLANS if rid.startswith('GEN') else EXP_PLANS)[n].split('|')
        assert len(plans)==len(r['claims']),rid
        raw=(ROOT/r['draft_path']).read_bytes();assert digest(raw)==r['draft_sha256']
        scenario=json.loads(raw) if rid.startswith('GEN') else None
        reviewed=[]
        for claim,plan in zip(r['claims'],plans):
            refs=[]
            for token in plan.split():
                if token=='-':continue
                if token[0]=='m':eid=r['required_manual_evidence_ids'][int(token[1:])]
                elif token[0]=='p':eid=policy_by_paragraph[token[1:]]
                else:eid=extra[token[1:]]
                sources[eid]=sources.get(eid,all_sources.get(eid));assert sources[eid]
                refs.append(eid)
            refs=list(dict.fromkeys(refs))
            c=copy.deepcopy(claim);c['support_evidence_ids']=refs
            c['manual_evidence_ids']=[e for e in refs if sources[e]['authority'].startswith('OEM')]
            c['policy_evidence_ids']=[e for e in refs if not sources[e]['authority'].startswith('OEM')]
            c['verdict']='DISCOURSE' if plan=='-' else 'SUPPORTED_AGENT_REVIEW'
            c['support_relation']='NONTECHNICAL_DISCOURSE' if plan=='-' else ('OEM_PARAPHRASE' if c['manual_evidence_ids'] and not c['policy_evidence_ids'] else 'POLICY_OR_BOUNDED_SCOPE_DERIVATION' if not c['manual_evidence_ids'] else 'OEM_FACT_WITH_EXPLICIT_POLICY_LIMIT')
            c['review_note']='Exact selected object(s) support the stated fact, including its qualifiers and units.' if c['support_relation']=='OEM_PARAPHRASE' else 'Policy supports the withheld action, uncertainty, observation question or scenario behavior; this is not an OEM diagnosis, proof of global absence, or measured runtime behavior.'
            c['source_spans']=[{'evidence_id':e,'text_span':sources[e]['text_span'],'text_sha256':sources[e].get('text_sha256'),
                              'visual_page':next((p['page_no'] for p in sources[e].get('provenance',[]) if sources[e].get('object_type')=='picture'),None)} for e in refs]
            issue=ISSUES.get(rid)
            if issue and issue['claim']==len(reviewed):c.update(verdict=issue['verdict'],review_note=issue['reason'],candidate_replacement=issue['replacement'])
            # No agent decision is inserted into formal approvals.
            c['semantic_support_approved']=False;c['agent_support_adjudicated']=True
            reviewed.append(c);claim_count+=1
        issues=[c['verdict'] for c in reviewed if c['verdict'] not in ('DISCOURSE','SUPPORTED_AGENT_REVIEW')]
        full_text=raw.decode('utf-8-sig')
        branch_lines=[]
        if not scenario:
            for line in full_text.splitlines():
                if line.startswith(('Follow-up/outcome handling:','Follow-up conversations/outcomes:','Exact review checks and source limits:','Source checks for reviewer:')):
                    start=full_text.index(line);branch_lines.append({'draft_span':[start,start+len(line)],'exact_text':line,
                        'review':'AGENT_REVIEWED_CONDITIONAL_SCOPE; see branch dependencies; no instruction beyond this scope authorized'})
        dependencies=branch_dependencies(rid,r,author,objects,all_sources,original,extra,policy_by_paragraph,sources)
        result={k:copy.deepcopy(r[k]) for k in ['record_id','record_version','draft_path','draft_sha256','answer_sha256','answer','workflow_state','agent_review_artifacts','remaining_blocks']}
        result.update(claims=reviewed,review_disposition='REVISE' if issues else 'SUPPORTED_AGENT_REVIEW',
            adjudication_complete=True,branch_scope_review=branch_lines,branch_dependencies=dependencies,
            producer_context={k:scenario.get(k) for k in ['question','conditions','warnings','source_limits','stopping_rules','expected_route','feedback_disposition','forbidden_claims','source_refs']} if scenario else {'full_record_text':full_text},
            applicability={'selection_policy':extra['fit'],'condition':'Himalayan + BS6 confirmed; no technical release on unknown or mismatched bike'},
            source_approval=False,runtime_authorized=False,cache_authorized=False,
            scenario_context=scenario.get('scenario_setup',scenario['question']) if scenario else re.search(r'Rider:\s*["\u201c](.*?)["\u201d]',full_text,re.S).group(1),
            accepted_feedback_source_sha256=digest(hb),
            legacy_attestation_remediation={'new_content_bound_agent_attestation':True,'manual_sha256':bindings['manual_sha256'],
                'draft_sha256':r['draft_sha256'],'scope':'Claim/support and conditional branch review; not independent human/source approval',
                'original_hold_preserved':r['workflow_state']=='BLOCKED_BINDING'})
        results.append(result)
    assert claim_count==371 and len(results)==150
    # Original text corroboration, not semantic scoring. Rendered figures checked
    # separately; token presence never establishes table/figure relationships.
    extraction=[]
    for eid,s in list(sources.items()):
        if s.get('authority')!='OEM_MANUAL':continue
        pages=sorted({p['page_no'] for p in s['provenance']});proof=[original(p) for p in pages]
        if s['object_type']=='picture':state='VISUAL_OBJECT_NOT_TEXT_ENTAILMENT'
        else:
            text=s['exact_text']
            if s['object_type']=='table':text=' '.join(c['text'] for c in s['table_cells'])
            def words(t):
                t=unicodedata.normalize('NFKC',t).casefold()
                t=re.sub(r'(?<=\w)[-\u00ad]\s*\n\s*(?=\w)','',t)
                t=re.sub(r'\b(\d+)\s*(st|nd|rd|th)\b',r'\1 \2',t)
                return set(re.findall(r'[a-z0-9]+',t))
            srcwords=words(' '.join(sources[p]['exact_text'] for p in proof))
            missing=sorted(words(text)-srcwords)
            split_notes={
              'evidence_15e1ce067b76cc524a0448d2':'PDF121 table wraps problem as prob-lem; table row/condition/remedy preserved.',
              'evidence_32a2dfb5649c03d469c7a578':'PDF15 performance sentence continues from the preceding immutable object; GEN049 binds both objects.',
              'evidence_a4bb14d7d40e42aa7a1abdc2':'PDF15 performance splits across immutable objects at perfor-/mance; both objects retained.',
              'evidence_a798d3ba95cd9f9440be754a':'PDF69 table wraps continuously as continu-ously; ABS warning condition unchanged.',
              'evidence_fb5ddc131802596bbfc6777e':'PDF117 table wraps payload as pay-load; original rendered merged tyre-pressure cell and 3rd/6th row roles visually checked.'}
            state='TEXT_TOKENS_CORROBORATED' if not missing else 'MANUALLY_CHECKED_LINE_OR_OBJECT_SPLIT' if eid in split_notes else 'NORMALIZATION_OR_EXTRACTION_REVIEW_REQUIRED'
        extraction.append({'evidence_id':eid,'original_pdf_source_ids':proof,'status':state,
                           'missing_tokens':missing if s['object_type']!='picture' else [],
                           'review_note':split_notes.get(eid) if s['object_type']!='picture' else None})
    report={'schema_version':'agent-claim-support-adjudication-v1','review_kind':'AGENT_EDITORIAL_SOURCE_SUPPORT_REVIEW',
      'independent_human_approval':False,'runtime_authorized':False,'provider_calls':0,
      'manual_sha256':bindings['manual_sha256'],'index_id':bindings['index_id'],
      'input_binding_sha256':digest((HERE/'claim_bindings.json').read_bytes()),
      'batch100_completion_sha256':bindings['batch100_completion_sha256'],
      'first50_inventory_sha256':bindings['first50_inventory_sha256'],
      'feedback_sha256':digest(hb),'review_code_sha256':digest(Path(__file__).read_bytes()),
      'method':'Explicit per-sentence adjudications after reading all answers, selected OEM spans, original continuation pages and rendered figures, policy paragraphs and full conditional branches. No live LLM or automated entailment verdicts. Same chat authored prior bundles; this is not an independent-review identity.',
      'claim_verdict_counts':dict(Counter(c['verdict'] for r in results for c in r['claims'])),
      'record_verdict_counts':dict(Counter(r['review_disposition'] for r in results)),
      'visual_checks':[{'pdf_page':n,'render_sha256':digest((HERE/f'original_pages/page{n:03}.png').read_bytes()),
        'checked':'Original full-page render visually inspected in this chat; exact layout/label scope only, no source approval or public-display permission'}
        for n in [21,29,30,31,32,58,59,68,79,81,88,91,104,106,109,117,118]],
      'original_extraction_checks':extraction,'records':results}
    (HERE/'support_review.json').write_bytes(encoded(report))
    (HERE/'reviewed_sources.json').write_bytes(encoded({'sources':sources}))
    replacements={
      'GEN057':'I will record that the control is not fitted, rather than treat it as a normal check, and withhold the action that depends on it. Can your motorcycle paperwork confirm it is a Himalayan BS6?',
      'GEN058':'Yesterday’s result was customer-reported resolution, not a verified repair. I will reopen the symptom you reported and retain the earlier attempt history; I will not automatically repeat that action.',
      'EXP027':'The manual requires scheduled front/rear pad checks. Its printed replacement-threshold wording is unclear; have authorised service assess pad wear.',
      'EXP024':'No. The manual specifies DOT4 and says not to mix it with other brake fluid. Other fluid can deteriorate rubber seals, cause leakage or a harmful chemical reaction. If the fluid is already mixed or its type is uncertain, have authorised service assess it; this answer does not authorize topping up or flushing.'}
    replacement_plans={'GEN057':['p98 p100','xfit'],'GEN058':['p124','p106 p116 xissues'],
      'EXP027':['m0','m1 p114 p138'],'EXP024':['-','m0 m1 m2','m4 m5','p98 p114 p138']}
    candidates=[]
    for rid,answer in replacements.items():
        old=next(r for r in bindings['records'] if r['record_id']==rid)
        maps=[]
        for (start,end,t),plan in zip(author.answer_spans(answer),replacement_plans[rid],strict=True):
            ids=[]
            for token in plan.split():
                if token=='-':continue
                ids.append(old['required_manual_evidence_ids'][int(token[1:])] if token[0]=='m' else policy_by_paragraph[token[1:]] if token[0]=='p' else extra[token[1:]])
            maps.append({'exact_claim_text':t,'answer_span':[start,start+len(t)],'support_evidence_ids':ids,
              'verdict':'DISCOURSE' if plan=='-' else 'SUPPORTED_AGENT_REVIEW','runtime_authorized':False})
        candidates.append({'record_id':rid,'supersedes_draft_sha256':old['draft_sha256'],'answer':answer,
          'answer_sha256':digest(answer.encode()),'claims':maps,'agent_review_complete':True,
          'producer_record_modified':False,'formal_source_approval':False,'runtime_authorized':False})
    (HERE/'corrected_candidates.json').write_bytes(encoded({'schema_version':'corrected-support-candidates-v1','records':candidates}))
    corrected={r['record_id']:r for r in candidates}
    fixture_records=[]
    for r in results:
        replacement=corrected.get(r['record_id'])
        fixture_records.append({'record_id':r['record_id'],'producer_version':r['record_version'],
          'producer_draft_sha256':r['draft_sha256'],'answer':replacement['answer'] if replacement else r['answer'],
          'answer_sha256':replacement['answer_sha256'] if replacement else r['answer_sha256'],
          'claims':replacement['claims'] if replacement else r['claims'],
          'branch_dependencies':r['branch_dependencies'],'applicability':r['applicability'],
          'producer_context':r['producer_context'],
          'prior_blocks':r['remaining_blocks'],'candidate_revision_applied':replacement is not None,
          'agent_support_review_complete':True,'formal_source_approved':False,'runtime_authorized':False,
          'semantic_verifier_accuracy_measured':False,'default_runtime_result':'SOURCE_HOLD_UNSUPPORTED'})
    (HERE/'candidate_grounding_fixtures.json').write_bytes(encoded({'schema_version':'reviewed-candidate-claim-fixtures-v1',
      'manual_sha256':bindings['manual_sha256'],'index_id':bindings['index_id'],
      'support_review_sha256':digest((HERE/'support_review.json').read_bytes()),
      'corrected_candidates_sha256':digest((HERE/'corrected_candidates.json').read_bytes()),'records':fixture_records}))
    print(json.dumps({'records':len(results),'claims':claim_count,'verdicts':report['record_verdict_counts'],'provider_calls':0}))


def branch_dependencies(rid,r,author,objects,all_sources,original,extra,policies,sources):
    """Bind conditional branch groups to their actual source and policy scope.

    No executable procedure is synthesized from an inspection-required branch.
    The original source card text is preserved verbatim separately.
    """
    p=lambda *ns:[policies[str(n)] for n in ns]
    deps=[]
    def add(kind,ids,note):
        for e in ids:
            if e not in sources:sources[e]=all_sources[e]
        deps.append({'kind':kind,'evidence_ids':list(dict.fromkeys(ids)),'scope':note,'runtime_authorized':False})
    add('STATE_AND_STOPS',p(98,100,106,108,116,118,124,129),
        'Unknown, mismatch, unresolved action, superseding correction, no unjustified repeats, service, customer-reported resolution and failure routing remain distinct.')
    if rid.startswith('GEN'):
        add('RECORD_CONTEXT',r['required_manual_evidence_ids']+r['required_policy_evidence_ids'],
            'Conditions/warnings were checked against final JSON. Engineering scenario outcomes are conditional expectations, not observed failures or OEM procedures.')
        return deps
    n=int(rid[3:])
    special={1:[29,30],2:[29,30],3:[31],4:[30],5:[32],6:[36,39,40,41,42],7:[32,42,43],8:[36,39,43,44],
      10:[37,38,121],11:[63,66],12:[63,66,67,69],13:[63,66,68],14:[68],15:[68,79,80],16:[79,80],17:[79,80],
      18:[34,35,36,81],19:[81],20:[21,72,73,74,75,83],21:[21,83,84,85],22:[21,86,87],23:[86],
      24:[21,88,89],25:[88,89],26:[88,89],27:[90,91],28:[63,66,90,91],29:[101,102],30:[101,102,122],
      31:[101,102,122],32:[102,103],33:[104],34:[38,105,121],35:[34,35,36,104,105,106,107],36:[108],37:[110],
      38:[109],39:[8,27,113,114],40:[116,117],41:[116,117],42:[118,119],43:[118,119],44:[120],45:[123],
      46:[122],47:[121],48:[63,66],49:[105,121],50:[21]}
    pages=special.get(n,[p['pdf_page'] for p in r['source_refs']])
    ids=[original(page) for page in pages]
    add('OEM_BRANCH_CONTEXT',ids,'Only the quoted conditional branch facts are supported. Pages reserved for a future full procedure do not authorize that procedure here. No inferred OEM sequence.')
    add('SOURCE_AND_DISPLAY_LIMITS',p(5,79,114,127,138,146,147,149)+[extra['display'],extra['permissions'],extra['issues']],
        'Source gaps cannot become rider questions; no hidden photo diagnosis, unreviewed crop display, global absence assertion or loss of separate unresolved issues.')
    if n in (27,32,40):add('PRESERVED_SOURCE_GAP',ids+p(114,127),'Original ambiguity, flagged index omission or conflicting preload statement remains blocked despite a completed agent review.')
    return deps

if __name__=='__main__':main()
