"""Author exact, version-bound candidate claim maps; never approve or run inference.

Selectors below are deliberately authored from inspected OEM objects. Policy claims
use the TRD or source manifest, never an unrelated motorcycle page. Sentence-level
maps retain the complete source bundle where a sentence has several propositions.
"""
from collections import Counter
from pathlib import Path
import hashlib
import json
import re
from zipfile import ZipFile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
OUT = Path(__file__).resolve().parent
INDEX = ROOT / 'build/index-bge-final'

# page, literal OEM fragment. Table fragments retain all headers/cells in the object.
GEN = {
1:[(11,'Do not tow a motorcycle')],2:[(11,'Do not pull a trailer')],
3:[(13,'equipped with convex'),(13,'much wider view'),(13,'Use care when judging')],
4:[(15,'maximum payload as defined')],
5:[(14,'add weight to the handlebars'),(14,'Keep luggage weight'),(14,'Distribute weight'),(15,'Do not load weight')],
6:[(14,'Do not exceed 110'),(9,'Do not exceed the legal speed'),(15,'Do not load weight')],
7:[(18,'Unleaded gasoline')],
8:[(18,'Fuel tank capacity'),(18,'above values are approximate'),(8,'hand held electronic'),(8,'Do not smoke'),(8,'well ventilated'),(8,'cap slowly'),(8,'air space'),(27,'highly explosive'),(27,'EVAP canister'),(27,'permanent stain')],
9:[(18,'Low fuel warning'),(18,'above values are approximate')],
10:[(20,'Gross vehicle weight'),(20,'beyond the allowed gross'),(15,'maximum payload as defined')],
11:[(20,'Standard seat height'),(20,'Low seat height'),(20,'guidance only')],
12:[(16,'Spark plug gap')],13:[(16,'Idle RPM')],
14:[(21,'SS-47G'),(21,'actual capacity'),(21,'wrong oil grade')],
15:[(17,'Wet multi plate'),(17,'6 Speed')],
16:[(19,'overloading/erratic'),(19,'not approved')],
17:[(19,'USB 2.0 Type C'),(65,'greater than 2.5'),(65,'only when engine')],
18:[(65,'no data transfer')],19:[(65,'fast / dash'),(65,'Duration of charging')],
20:[(64,'rainy conditions'),(65,'closed and locked')],21:[(64,'only one mobile')],
22:[(26,'Key can be removed only'),(26,'Do not switch OFF'),(26,'potential accident')],
23:[(26,'extreme left'),(26,'OFF position'),(26,'Do not switch OFF'),(26,'potential accident'),(13,'firm and flat')],
24:[(31,'Push the switch for headlight flash')],25:[(32,'Performance + ABS ON'),(32,'Performance + Rear ABS OFF'),(32,'ECO + ABS ON'),(32,'ECO + Rear ABS OFF')],
26:[(48,'phone is connected'),(48,'phone is not connected')],
27:[(60,'reset to 00:00')],28:[(49,'either km/l')],
29:[(50,'Celsius'),(50,'Fahrenheit')],
30:[(50,'English'),(50,'Italian'),(50,'Spanish'),(50,'Portuguese'),(51,'German'),(51,'French')],
31:[(53,'current firmware version')],32:[(54,'favorite function')],33:[(55,'Apple music alone')],34:[(56,'call and message')],
35:[(57,'active navigation')],36:[(57,'only when the vehicle is in dynamic')],
37:[(60,'reset only by authorised'),(60,'plan for scheduled service')],
38:[(60,'450'),(60,'4,900'),(60,'every 5,000'),(124,'average riding conditions')],
39:[(61,'indication will be'),(61,'between 1 to 6')],
40:[(45,'Any two'),(45,'Any four')],41:[(62,'vehicle components fault')],
42:[(33,'ABS ON to OFF')],43:[(33,'dynamic condition we can change'),(33,'Throttle to be closed'),(33,'Clutch should be pressed'),(33,'condition are not met')],
44:[(71,'6000'),(71,'Avoid full throttle'),(71,'sudden accelerations'),(71,'specified pay load'),(71,'over an hour')],
45:[(71,'501'),(71,'Avoid full throttle'),(71,'sudden accelerations')],
46:[(115,'Service the motorcycle'),(115,'sufficient quantity'),(115,'correct tyre pressure'),(115,'loose fasteners'),(115,'Condition of the tyres'),(115,'engine oil level'),(115,'lights and horn'),(115,'chain tension'),(115,'Clutch cable')],
47:[(16,'Champion'),(16,'Spark plug gap')],48:[(54,'Android:'),(54,'iOS:')],
49:[(9,'extended front forks'),(15,'extended front forks'),(15,'mance of the motorcycle')],50:[(11,'remains too hot')],
59:[(121,'dim/weak horn')],60:[(121,'problem is not rectified')],
86:[(63,'continuously above 5'),(66,'Failure to do so')],
91:[(58,'')],94:[(67,'recommended spare parts'),(67,'substitute for good riding')]
}

EXP = {
1:[(29,'cannot be activated'),(29,'Ignition switch ON'),(29,'30 minutes'),(29,'strain on battery'),(30,'Turn signals do not work'),(29,'prolonged stoppage')],
2:[(30,'simultaneously'),(30,'Turn signals do not work'),(29,'strain on battery')],
3:[(31,'returned to the center'),(31,'Left turn'),(31,'Push to cancel'),(31,'Right turn')],
4:[(30,'High beam indicator')],5:[(32,'Home button on left')],
6:[(42,'only in the dark theme'),(39,'settings menu'),(40,'up & down'),(41,'background option'),(41,'Auto and dark theme'),(41,'joystick center'),(42,'brightness option'),(42,'increased by joystick'),(42,'home button')],
7:[(32,'Mode button on right'),(42,'analog to digital')],
8:[(43,'trip preference selected'),(43,'joystick center'),(44,'reset trip option'),(44,'Reset trip 1'),(44,'confirmation popup'),(44,'home button')],
9:[(38,'range values are estimates'),(38,'fuel range value will be updated')],
10:[(38,'12.5 V')],
11:[(63,'continuously above 5'),(66,'attains a speed'),(66,'Failure to do so')],
12:[(69,'Do not release the brake'),(67,'both brakes simultaneously'),(67,'substitute for good riding'),(67,'longer stopping distance'),(67,'cornering'),(67,'stopping distance required'),(67,'instrument cluster'),(67,'Failure to adhere')],
13:[(68,'damaged teeth'),(68,'damages and dents'),(68,'teeth edges')],
14:[(68,'debris at the end')],
15:[(68,'falling over'),(68,'made upright'),(68,'neutral lamp'),(68,'wait for a few seconds'),(80,'extreme care')],
16:[(80,'side stand is only designed'),(79,'firm and flat'),(79,'Extend side stand'),(80,'both stands')],
17:[(79,'firm and flat'),(79,'Hold handle bar'),(79,'both the legs'),(79,'fulcrum lever'),(79,'Lock the steering'),(80,'extreme care'),(80,'both stands')],
18:[(81,'tool kit is strapped')],19:[(81,'first aid kit')],
20:[(83,'350 ml'),(83,'level surface upright'),(83,'cold condition'),(83,'over fill')],
21:[(21,'2.1 L'),(21,'actual capacity'),(83,'over fill')],
22:[(21,'TOTAL COOLELF'),(87,'Total is ready'),(86,'Never open a radiator')],
23:[(86,'Never open a radiator')],
24:[(21,'DOT 4'),(88,'Do not mix'),(88,'sealer container'),(88,'rubber seals'),(88,'harmful chemical')],
25:[(88,'upright position'),(88,'Rear: Check'),(89,'insufficient brake fluid')],
26:[(88,'upright position'),(88,'Front: Check'),(89,'insufficient brake fluid')],
27:[(90,'brake pads must be checked'),(91,'pads need to be replaced')],
28:[(91,'mild noise')],
29:[(101,'9 - 11 mm'),(101,'right hand lock'),(102,'engine is cold'),(101,'free play present')],
30:[(122,'RPM raises disproportionately')],
31:[(102,'desired free play'),(122,'Poor pickup')],
32:[(102,'chain slackness')],33:[(104,'12 V - 8 Ah')],34:[(105,'checking the battery voltage')],
35:[(105,'black negative'),(104,'remove ignition key'),(107,'positive terminal first'),(107,'firmly connected')],
36:[(108,'LED lighting system'),(108,'Contact an Royal')],37:[(110,'license plate illuminator'),(110,'Contact an Royal')],
38:[(109,'clockwise or anti clockwise')],39:[(114,'high pressure compressed air')],
40:[(116,'first notch position'),(117,'3 rd')],41:[(117,'196 kg')],
42:[(118,'')],43:[(119,'warm water')],
44:[(120,'For re-use after storage'),(120,'month or longer')],
45:[(123,'not dumped'),(123,'store them in a container')],
46:[(122,'adulteration')],47:[(121,'dim/weak horn')],
48:[(63,'continuously above 5'),(66,'Failure to do so')],
49:[(105,'checking the battery voltage'),(121,'dim/weak horn')],50:[]
}

# Exact TRD paragraph locators inspected in the authoritative document. OEM facts
# and product rules have separate namespaces and cannot substitute for each other.
POLICY = {
'scope':[5,95,96,99,127,144], 'applicability':[72,94,98,99,120],
'state':[92,100,106,108,116,124], 'source_gap':[78,79,80,114,129],
'ranking':[75,76,82,83,85,86,96,112], 'error':[80,86,129,130,142],
'cache':[94,183,259], 'photo':[146,147], 'voice':[148,195],
'privacy':[149,220], 'injection':[100,225], 'safety':[84,122,129,140],
'rights':[3,32,226], 'citation':[127,130,144], 'escalation':[29,118,129,138]
}
GEN_POLICY = {
51:'applicability',52:'applicability',53:'applicability',54:'source_gap',55:'source_gap',56:'state',57:'state',58:'state',59:'state',60:'escalation',
61:'source_gap',62:'source_gap',63:'source_gap',64:'source_gap',65:'source_gap',66:'ranking',67:'applicability',68:'cache',69:'cache',70:'cache',
71:'error',72:'error',73:'error',74:'error',75:'error',76:'error',77:'citation',78:'error',79:'state',80:'state',81:'error',82:'error',83:'photo',84:'voice',85:'escalation',
86:'safety',87:'ranking',88:'ranking',89:'ranking',90:'ranking',91:'photo',92:'privacy',93:'injection',94:'injection',95:'source_gap',96:'citation',97:'rights',98:'voice',99:'state',100:'rights'
}
VISUAL = {'EXP001':[29], 'EXP003':[31], 'EXP006':[39,41,42], 'EXP007':[32,42],
          'EXP008':[43,44], 'EXP010':[38], 'EXP013':[68], 'EXP015':[68],
          'EXP018':[81], 'EXP025':[88], 'EXP026':[88], 'EXP035':[104,106],
          'EXP038':[109], 'EXP040':[117], 'EXP041':[117], 'EXP042':[118],
          'GEN029':[50], 'GEN030':[50,51], 'GEN091':[58,59]}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def canonical(x):
    return (json.dumps(x,ensure_ascii=False,sort_keys=True,indent=2,allow_nan=False)+'\n').encode('utf-8')


def normalize(t):
    return re.sub(r'\s+',' ',t).strip().casefold()


def source_text(obj):
    raw=obj['raw_object']
    if obj['type']=='table':
        return '\n'.join(f"r{c['start_row_offset_idx']}c{c['start_col_offset_idx']}: {c['text']}" for c in raw['data']['table_cells'])
    return raw.get('text') or raw.get('orig') or ''


def load_sources():
    objects=[json.loads(line) for line in (INDEX/'evidence.jsonl').read_text(encoding='utf-8').splitlines()]
    evidence={}
    for obj in objects:
        text=source_text(obj)
        evidence[obj['id']]={'evidence_id':obj['id'],'authority':'OEM_MANUAL','object_type':obj['type'],
            'manual_sha256':obj['source_sha256'],'index_id':'index_a3282c4d98cf54595e4ba168',
            'object_sha256':sha(canonical(obj)), 'provenance':obj['provenance'],
            'exact_text':text,'text_sha256':sha(text.encode('utf-8')),
            'text_span':[0,len(text)],'review_status':'BINDING_AUTHORED_NOT_FORMALLY_APPROVED'}
        if obj['type']=='table':
            evidence[obj['id']]['table_cells']=obj['raw_object']['data']['table_cells']
        if obj['type']=='picture':
            evidence[obj['id']]['requires_visual_verification']=True
    trd=ROOT/'03_TRD.docx'; doc_sha=sha(trd.read_bytes())
    with ZipFile(trd) as z: tree=ET.fromstring(z.read('word/document.xml'))
    ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main'}
    paragraphs=tree.findall('.//w:p',ns)
    policy={}
    for group,indices in POLICY.items():
        ids=[]
        for i in indices:
            text=''.join(n.text or '' for n in paragraphs[i].findall('.//w:t',ns))
            assert text
            eid='policy_'+sha((doc_sha+':'+str(i)+':'+text).encode('utf-8'))[:24]
            evidence[eid]={'evidence_id':eid,'authority':'PRODUCT_POLICY','source_path':'03_TRD.docx',
                'source_sha256':doc_sha,'paragraph_index':i,'exact_text':text,
                'text_sha256':sha(text.encode('utf-8')),'text_span':[0,len(text)],'version':'TRD-v0.4'}
            ids.append(eid)
        policy[group]=ids
    manifest_path=ROOT/'source_manifest.json';data=manifest_path.read_bytes();manifest=json.loads(data)
    for key in ('display_policy','applicability_policy','oem_service_route'):
        text=json.dumps(manifest[key],ensure_ascii=False,sort_keys=True)
        eid='policy_'+sha((sha(data)+':/'+key+':'+text).encode('utf-8'))[:24]
        evidence[eid]={'evidence_id':eid,'authority':'PRODUCT_POLICY','source_path':'source_manifest.json',
            'source_sha256':sha(data),'json_pointer':'/'+key,'exact_text':text,'text_span':[0,len(text)],
            'text_sha256':sha(text.encode('utf-8'))}
        policy[key]=[eid]
    return objects,evidence,policy


def select(objects,page,fragment):
    matches=[o['id'] for o in objects if any(p['page_no']==page for p in o['provenance'])
             and (normalize(fragment) in normalize(source_text(o)) if fragment else o['type']=='picture')]
    if not matches: raise ValueError(f'Missing exact source selector {page}: {fragment}')
    # All matches are retained where layout splits/duplicates source text.
    return matches


def answer_spans(answer):
    starts=[0]+[m.end() for m in re.finditer(r'(?<=[.!?])\s+(?=[A-Z])',answer)]
    ends=starts[1:]+[len(answer)]
    return [(start,end,answer[start:end].rstrip()) for start,end in zip(starts,ends)]


def main():
    objects,evidence,policy=load_sources()
    manifest=json.loads((ROOT/'human_review/record_workflow/batch_100_completion.json').read_bytes())
    inventory=json.loads((ROOT/'human_review/record_workflow/inventory.json').read_bytes())
    input_records=[]
    for row in manifest['records']:
        raw=(ROOT/row['draft_path']).read_bytes(); assert sha(raw)==row['draft_sha256']
        a=json.loads(raw)
        input_records.append((row,a['answer'],a['source_refs'],a['expected_route'],'GEN'))
    for row in inventory['records']:
        raw=(ROOT/row['draft_path']).read_bytes();assert sha(raw)==row['draft_sha256']
        text=raw.decode('utf-8-sig')
        match=re.search(r'Assistant:\s*["\u201c](.*?)["\u201d](?:\s*\n|\s*$)',text,re.S)
        assert match,row['record_id']
        source_line=next(l for l in text.splitlines() if l.startswith('Original '))
        region=re.search(r'PDF\s+(.+?);',source_line).group(1)
        pages=[]
        for part in re.findall(r'\d+(?:-\d+)?',region):
            if '-' in part:
                lo,hi=map(int,part.split('-'));pages.extend(range(lo,hi+1))
            else:pages.append(int(part))
        input_records.append((row,match.group(1),[{'pdf_page':p} for p in pages],None,'EXP'))
    rows=[];used=set();unresolved=[]
    for row,answer,refs,route,batch in input_records:
        rid=row['record_id'];n=int(rid[3:]);selectors=(GEN if batch=='GEN' else EXP).get(n,[])
        manual=[]
        for page,fragment in selectors:
            manual.extend(select(objects,page,fragment))
        manual=list(dict.fromkeys(manual))
        kind=GEN_POLICY.get(n,'scope') if batch=='GEN' else ('error' if n==50 else 'scope')
        policies=list(dict.fromkeys(policy[kind]+policy['scope']+policy['oem_service_route']))
        if kind=='rights': policies+=policy['display_policy']
        if kind=='applicability':policies+=policy['applicability_policy']
        if batch=='EXP' and n in (15,31,49):policies+=policy['state']+policy['photo']
        if batch=='EXP' and n in (27,32,40):policies+=policy['source_gap']
        figure_ids=[]
        for page in VISUAL.get(rid,[]):figure_ids+=select(objects,page,'')
        claim_rows=[]
        for start,end,text in answer_spans(answer):
            literal_end=start+len(text)
            claim_id='claim_'+sha((rid+':'+str(row['version'])+':'+row['draft_sha256']+':'+str(start)+':'+text).encode('utf-8'))[:24]
            # A sentence can mix a supported bounded fact with a policy limitation.
            # Its complete bundle is explicit; no automatic entailment is asserted.
            discourse=text in ('Yes.','No.','No.')
            ids=[] if discourse else list(dict.fromkeys(manual+policies))
            claim_rows.append({'claim_id':claim_id,'answer_span':[start,literal_end],'exact_claim_text':text,
                'claim_type':'DISCOURSE' if discourse else ('OEM_FACT_WITH_POLICY_SCOPE' if manual else 'PRODUCT_POLICY_OR_SCENARIO'),
                'support_evidence_ids':ids,'manual_evidence_ids':[] if discourse else manual,
                'policy_evidence_ids':[] if discourse else policies,
                'support_relation':'EXPLICIT_AUTHORED_SOURCE_BUNDLE_REQUIRES_ENTAILMENT_REVIEW',
                'semantic_support_approved':False})
            used.update(ids)
        used.update(figure_ids)
        blocks=[]
        if batch=='EXP' and row['state']!='PASS_AGENT_REVIEW':blocks.append(row['state'])
        if figure_ids:blocks.append('FIGURE_RELATION_AND_VISUAL_VERIFICATION_REQUIRED')
        if batch=='EXP' and n==32:blocks.append('PDF103_FLAGGED_SOURCE_GAP')
        if batch=='EXP' and n==40:blocks.append('CONFLICTING_PRELOAD_SOURCE_STATEMENTS')
        if batch=='EXP' and n==27:blocks.append('PRINTED_PAD_THRESHOLD_AMBIGUOUS')
        for p in row.get('blocker_card_paths',[]):blocks.append(p)
        for claim in claim_rows:
            if claim['claim_type']!='DISCOURSE' and not claim['support_evidence_ids']:unresolved.append(claim['claim_id'])
        rows.append({'record_id':rid,'record_version':row['version'],'draft_path':row['draft_path'],
            'draft_sha256':row['draft_sha256'],'answer_sha256':sha(answer.encode('utf-8')),'answer':answer,
            'source_refs':refs,'expected_route':route,'workflow_state':row.get('state',row.get('terminal_disposition')),
            'binding_status':'EXACT_SOURCE_BUNDLES_AUTHORED_ENTAILMENT_NOT_REVIEWED',
            'claims':claim_rows,'required_manual_evidence_ids':manual,'required_policy_evidence_ids':policies,
            'required_figure_evidence_ids':figure_ids,'remaining_blocks':blocks,
            'agent_review_artifacts':{k:row.get(k) for k in ('review_path','review_sha256','judge_path','judge_sha256','judgment_path','judgment_sha256')},
            'formal_source_approved':False,'runtime_authorized':False})
    assert len(rows)==150 and len({r['record_id'] for r in rows})==150 and not unresolved
    (OUT/'claim_bindings.json').write_bytes(canonical({'schema_version':'expanded-exact-claim-bundles-v1',
        'manual_sha256':manifest['manual_sha256'],'index_id':'index_a3282c4d98cf54595e4ba168',
        'batch100_completion_sha256':sha((ROOT/'human_review/record_workflow/batch_100_completion.json').read_bytes()),
        'first50_inventory_sha256':sha((ROOT/'human_review/record_workflow/inventory.json').read_bytes()),
        'authoring_code_sha256':sha(Path(__file__).read_bytes()),'records':rows}))
    (OUT/'bound_sources.json').write_bytes(canonical({'schema_version':'exact-bound-sources-v1',
        'sources':{eid:evidence[eid] for eid in sorted(used)}}))
    print(json.dumps({'records':len(rows),'sentence_claims':sum(len(r['claims']) for r in rows),
        'exact_source_objects':len(used),'formal_approvals_created':0,'provider_calls':0,
        'binding_status':'AUTHORED_REQUIRES_INDEPENDENT_ENTAILMENT_REVIEW'}))


if __name__=='__main__':main()
