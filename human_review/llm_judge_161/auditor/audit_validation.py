"""Independent review-artifact audit. Writes only the auditor directory."""
from pathlib import Path
import json, hashlib, re, collections, statistics, datetime
BASE=Path(__file__).resolve().parent.parent
ROOT=BASE.parents[1]
OUT=BASE/'auditor'
PIN_CORPUS='3ec75b47a0f2f8de5ee90273829d9673bec8c232a1e998bb2558fa9ed45ea7d8'
PIN_FEEDBACK='ae663a289d0090c3d56fd4ee5826baf3212ec7a1fb2cc5a506427e2d35fede1c'
PIN_RESULTS='88db6d0a9c43ab83d0d23c90528d54b12537c64d1edccfe443bfeae3160b6e9a'
SHARDS={'original_exp':{*(f'EXP{i:03}' for i in range(1,51)),'lookup_oil_grade','lookup_tyre_pressure','lookup_fan_fuse','lookup_starter_duration','lookup_usb_charging','a_fuse','a_switches_on','a_refuel','a_reconnect','a_raise_stand','a_cool_engine'},'gen_a':{f'GEN{i:03}' for i in range(1,51)},'gen_b':{f'GEN{i:03}' for i in range(51,101)}}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def canon(v):return hashlib.sha256(json.dumps(v,sort_keys=True,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()
def norm(v):return re.sub(r'\s+',' ',v)
def strings(v):
 if isinstance(v,str):yield v
 elif isinstance(v,dict):
  for x in v.values():yield from strings(x)
 elif isinstance(v,list):
  for x in v:yield from strings(x)
def counts(rows,key):return dict(sorted(collections.Counter(str(x[key]) for x in rows).items()))
assert sha(BASE/'corpus.json')==PIN_CORPUS
assert sha(BASE/'subagent_feedback.md')==PIN_FEEDBACK
assert sha(BASE/'results.json')==PIN_RESULTS
corpus=json.loads((BASE/'corpus.json').read_text(encoding='utf-8'))
rubric=json.loads((BASE/'rubric.json').read_text(encoding='utf-8'))
cases={x['record_id']:x for x in corpus['records']}
expected=set().union(*SHARDS.values())
assert len(cases)==len(corpus['records'])==161 and set(cases)==expected==set(rubric['case_ids'])
assert len(rubric['case_ids'])==161 and rubric['case_input_sha256']==PIN_CORPUS
for rid,c in cases.items():
 v=dict(c);stored=v.pop('case_sha256');assert canon(v)==stored, rid
for c in corpus['context'].values():assert sha(ROOT/c['frozen_copy'])==c['sha256']
manual=ROOT/'royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf'
assert sha(manual)==corpus['manual_sha256'].lower()
rows=[];actors=[];inputs=[];quote_issues=[];shard_hashes={};rationale_counts={}
enums={'initial_grounding':{'PASS','PARTIAL','FAIL','NOT_VERIFIABLE'},'dialogue_flow':{'PASS','PARTIAL','FAIL','NOT_APPLICABLE','NOT_VERIFIABLE'},'feedback_alignment':{'PASS','PARTIAL','FAIL'},'overall':{'PASS','REVISE','BLOCKED_SOURCE'}}
for s,ids in SHARDS.items():
 d=json.loads((BASE/s/'records.json').read_text(encoding='utf-8'));actors.append(d['judge_actor'])
 assert d['corpus_sha256']==PIN_CORPUS and d['feedback_sha256']==PIN_FEEDBACK
 rr=d['records'];assert len(rr)==len(ids)==len({x['record_id'] for x in rr}) and {x['record_id'] for x in rr}==ids
 rationale_counts[s]=len(set(x['rationale'] for x in rr))
 for path,hash_value in d['input_hashes'].items():
  full=BASE/path if s=='gen_a' and path!=manual.name else ROOT/path
  assert full.is_file(), path;assert sha(full)==hash_value.lower(),path;inputs.append(full.relative_to(ROOT).as_posix())
 for r in rr:
  rid=r['record_id'];c=cases[rid]
  assert r['case_sha256']==c['case_sha256']
  assert r.get('feedback_sha256',PIN_FEEDBACK)==PIN_FEEDBACK
  for key,allowed in enums.items():assert r[key] in allowed
  assert type(r['answer_quality']) is int and 1<=r['answer_quality']<=5
  assert isinstance(r['rationale'],str) and r['rationale'].strip()
  assert isinstance(r['source_checks'],list) and r['source_checks']
  assert isinstance(r['findings'],list)
  if r['overall']!='PASS':assert r['findings']
  for i,f in enumerate(r['findings']):
   for field in ('severity','affected_scope','quote','consequence','source_or_policy_basis','smallest_fix'):assert f.get(field), (rid,i,field)
   if f['affected_scope']=='current_response':haystack=c['current_response']
   elif f['affected_scope']=='authored_followup':haystack=' '.join(strings(c['full_candidate_case']))+' '+c['current_response']
   else:haystack=' '.join(strings(c))
   if norm(f['quote']) not in norm(haystack):quote_issues.append({'record_id':rid,'finding':i,'scope':f['affected_scope']})
  rows.append(dict(r,review_shard=s))
 for name in ['records.json','REPORT.md']:shard_hashes[f'{s}/{name}']=sha(BASE/s/name)
assert len(set(actors))==3 and len(rows)==161 and not quote_issues
assert len({r['rationale'] for r in rows})==161
summary={'cases_reviewed':161,'dimensions':{k:counts(rows,k) for k in enums},'answer_quality_distribution':counts(rows,'answer_quality'),'mean_answer_quality':round(statistics.mean(r['answer_quality'] for r in rows),3),'flow_pass_scope_counts':dict(sorted(collections.Counter(r.get('dialogue_flow_scope','STATIC_AUTHORED_CONTEXT') for r in rows if r['dialogue_flow']=='PASS').items()))}
aggregate=json.loads((BASE/'results.json').read_text(encoding='utf-8'))
for key,val in summary.items():assert aggregate['summary'][key]==val,key
agg={r['record_id']:r for r in aggregate['records']}
assert len(agg)==len(aggregate['records'])==161 and set(agg)==expected
for r in rows:
 a=agg[r['record_id']]
 for k,v in r.items():assert a[k]==v, (r['record_id'],k)
assert aggregate['validation']['quote_match_warnings']==[]
report=(BASE/'REPORT.md').read_text(encoding='utf-8')
report_rows={}
for line in report.splitlines():
 parts=[x.strip() for x in line.split('|')]
 if len(parts)==8 and parts[1] in expected:
  rid=parts[1];assert rid not in report_rows,rid;report_rows[rid]=parts[2:7]
assert set(report_rows)==expected and len(report_rows)==161
for rid,v in report_rows.items():
 r=agg[rid];assert v==[r['initial_grounding'],str(r['answer_quality']),r['dialogue_flow'],r['feedback_alignment'],r['overall']],rid
negative={r['record_id'] for r in rows if r['overall']!='PASS'}
headings=re.findall(r'^### ([A-Za-z0-9_]+) [^\n]* REVISE$',report,re.M)
assert len(headings)==12 and set(headings)==negative
for phrase in ['disjoint','one independent judge per case','LOCAL_SINGLE_TURN_CLARIFICATION_ONLY','STATIC_AUTHORED_CONTEXT','No external Gemma request','no live rider conversation']:
 assert phrase in report,phrase
for scope,n in summary['flow_pass_scope_counts'].items():assert scope in report and str(n) in report
assert str(summary['mean_answer_quality']) in report
observations=[
 {'case_id':'EXP001','scope':'current_response','result':'AGREE_HIGH_FACTUAL_ERROR','exact_quote':'The hazard button is the triangle-marked button on the left-hand handlebar control shown on PDF29.','basis':'Auditor visually inspected complete PDF23/PDF29 renders. PDF23 item6 is on the rider-right control beside item5; PDF29 drawings show that same right-hand hazard switch.'},
 {'case_id':'EXP002','scope':'authored_followup','result':'AGREE_HIGH_FACTUAL_ERROR','exact_quote':'If unsure: the source29 drawing shows the triangle-marked hazard button on the left-hand handlebar control.','basis':'The exact quote occurs in the retained producer full_record_text, not the current initial response. Same original PDF23/PDF29 visual basis. Initial grounding PASS and authored-flow FAIL are consistent.'},
 {'case_id':'a_refuel','scope':'current_response','result':'AGREE_COMPLETENESS_AND_ORDERING','basis':'Read frozen current response and PDF8/PDF27 text. Engine/device-OFF setup occurs after the first action; read-and-return is repeated; PDF27 flap/key/clockwise opening sequence is omitted while key-in-position closure is given.'},
 {'case_id':'a_switches_on','scope':'current_response','result':'AGREE_INTERNAL_CHECKLIST_REFERENCE','basis':'The exact quoted response requires a compact starting checklist without providing rider wording or the next missing observation. Full frozen feedback and accepted control-identification history call for practical compact setup, retaining known facts and correction of only the reported OFF switch.'},
 {'case_id':'a_reconnect','scope':'current_response','result':'AGREE_CLARITY_IMPROVEMENT','basis':'PDF121 names spark plug, cap and high tension cable, while the frozen response says only parts. Proposed naming retains source-limited service referral and invents no access procedure.'},
 {'case_id':'a_cool_engine','scope':'current_response','result':'AGREE_INTERNAL_POLICY_PROSE','basis':'PDF122 engine-too-hot row and PDF37/38 limit inspected in frozen source context; response ends in documented condition/eligibility language. Proposed wording keeps established-condition and service limits without inventing a restart threshold.'},
 {'case_id':'EXP030','scope':'current_response','result':'AGREE_PLAIN_LANGUAGE_IMPROVEMENT','basis':'Current RPM/disproportionately question matches the PDF122 observation but is harder for a rider to answer. Full feedback requests accessible observations. Suggested revs/speed paraphrase preserves the same observation and forbids a new road test.'},
 {'case_id':'EXP044','scope':'current_response','result':'AGREE_CURRENT_TASK_AND_UNKNOWN_HISTORY','basis':'PDF120 prefers authorised-service preparation for re-use and conditions voltage checks on battery refitting. Frozen answer presents retrospective removal/refit guidance without establishing removal history.'},
 {'case_id':'EXP049','scope':'authored_followup','result':'AGREE_MISSING_CONCRETE_CONTINUATION','basis':'Read current dim-lights/weak-horn question and all retained producer follow-up spans; they discuss photo uncertainty but contain no yes/no/unsure routing for that question. PDF121 supplies a source-bounded positive service route; a negative clue does not prove health.'},
 {'case_id':'GEN043','scope':'authored_followup','result':'AGREE_NOT_VERIFIABLE','basis':'Full frozen branch context has zero reviewed conditional spans; source33 supports current throttle/clutch-or-neutral/ABS conditions. Did you meet those conditions? has no authored replies; generic state dependencies are not concrete conversation paths.'},
 {'case_id':'GEN053','scope':'current_response','result':'AGREE_RIDER_SELECTION_SCOPE','basis':'Frozen source_manifest selection policy requires rider confirmation of Himalayan and BS6, with application choosing the manual. Response asks rider to confirm the applicable manual. Suggested question stays within owner selection scope.'},
 {'case_id':'GEN056','scope':'current_response','result':'AGREE_UNANCHORED_CLARIFICATION','basis':'The rider already states uncertainty about what was checked. Current generic normal/unresolved/unsure menu does not identify the prior check or criterion; TRD unknown-not-normal policy supports preserving UNCLEAR and one anchored observation.'},
 {'case_id':'GEN061/GEN087','scope':'runtime_measurement','result':'AGREE_CONDITIONAL_FIXTURE_LIMIT','basis':'Source-gap wording is judged within its trusted engineering fixture, with explicit notes that a fetch outage remains SYSTEM_ERROR. No live failure classification is claimed.'}
]
audit={'schema_version':'independent-judge-deliverable-audit-v1','auditor':'/root/quality_auditor','created_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'audit_verdict':'PASS_REVIEW_DELIVERABLE_WITH_STATED_LIMITS','material_deliverable_inconsistencies':[],'scope':'Independent audit of completeness, frozen bindings, aggregation, exact finding quotes, source/feedback samples and scope honesty of the static LLM-judge deliverable. Not a second source review of all 161 or release approval.','input_bindings':{'corpus_sha256':PIN_CORPUS,'feedback_sha256':PIN_FEEDBACK,'manual_sha256':sha(manual),'results_sha256':sha(BASE/'results.json'),'report_sha256':sha(BASE/'REPORT.md'),'rubric_sha256':sha(BASE/'rubric.json'),'shard_artifact_sha256':shard_hashes},'checks':{'exact_corpus_and_rubric_ids':True,'case_hashes_verified':161,'exact_disjoint_shard_counts':{s:len(ids) for s,ids in SHARDS.items()},'distinct_judge_actors':actors,'declared_shard_input_hash_entries_verified':len(inputs),'unique_declared_shard_input_files_verified':len(set(inputs)),'declared_input_path_resolution':'gen_a basename paths resolve to frozen package; its PDF basename resolves to workspace. Other shard paths are workspace-relative.','finding_count':sum(len(r['findings']) for r in rows),'affected_scope_quote_mismatches':quote_issues,'case_specific_rationales':rationale_counts,'unique_rationales_total':161,'aggregate_matches_shards':True,'report_case_rows_verified':161,'report_actionable_case_headings_verified':12,'report_scope_limits_present':True,'manual_visual_spot_checks':['PDF23 / printed21','PDF29 / printed27']},'recomputed_summary':summary,'finding_spot_checks':observations,'authority_handling':{'no_additional_human_approval_required':True,'latest_owner_delegation_respected':True,'R001_recovery_wait_accepted':True,'R002_separate_scope_preserved':True,'legacy_human_signoff_fields_not_treated_as_a_blocker':True,'approved_release_and_response_artifacts_modified_by_audit':False},'limitations':['One fresh LLM judge reviewed each case in disjoint 61/50/50 shards; these are not three independent ratings per case. The auditor checked artifact completeness and selected conclusions in addition.','Current_response is joined approved claim text or a canonical policy response, not observed Gemma/model/UI output. Static prose review cannot measure deployment behavior, response stability, actual citations, latency or cost.','Seventeen flow passes assess static authored branch context; seven pass only a local clarification. No complete adaptive runtime transition or retention behavior is certified.','The auditor read all material negative rationales and their finding fields and checked source/feedback context for substantial findings; only PDF23/PDF29 were freshly inspected visually by the auditor. Other visual inspection claims belong to named judge agents and their retained artifacts.','All findings are LLM judgments. Coverage, hashes and quote matches are mechanical checks; they are not measured production accuracy or proof of every semantic judgment.','This audit does not edit responses, change release approval, authorize undocumented repair, publish source material, validate general vision/voice performance or deploy anything.']}
(OUT/'audit.json').write_text(json.dumps(audit,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
lines=['# Audit of the 161-case LLM judge deliverable','',
'**Pass for review completeness and reporting accuracy, within the stated static scope.** No material inconsistency was found between the frozen corpus, shard decisions, aggregate results and consolidated report. This is an audit of the review deliverable, not another release approval or proof that the assistant works in deployment.','',
'The three fresh judge agents reviewed disjoint shards of 61, 50 and 50 cases, giving one independent LLM judgment per case. The auditor added separate coverage, binding and selected conclusion checks. There were exactly 161 distinct case results and 161 distinct case-specific rationales. Twelve fresh REVISE decisions, including the hazard-location error, demonstrate that earlier source approval was not merely reproduced as quality passes.','',
'## Checks completed','',
'- Verified the frozen corpus, full feedback, context files and original PDF checksums; recomputed all 161 canonical per-case hashes.','- Verified exact disjoint shard coverage, declared input-file hashes, permitted scores, nonempty rationale/source checks and complete finding fields.','- Matched every finding quote to its affected current response or authored context; zero mismatches.','- Recomputed all aggregate dimension totals, quality distributions and mean; compared every aggregated record with its shard.','- Checked all 161 consolidated case-table rows and all 12 required-revision sections, without duplicate or missing case labels.','- Read the full feedback Markdown, later accepted feedback updates and delegated approval scope. R001 is accepted, R002 remains separate, and stale human-only flags were not used as blockers.','',
'## Results and meaning','',
'Overall: **149 PASS, 12 REVISE**. Initial grounding: **159 PASS, 1 PARTIAL, 1 FAIL**. Mean current-answer quality: **4.553/5**.','',
'Authored-flow ratings: **24 PASS, 5 PARTIAL, 2 FAIL, 1 NOT_VERIFIABLE, 129 NOT_APPLICABLE**. The 24 passes split into **17 static authored-context passes and seven local single-turn clarification passes**. They do not establish complete adaptive conversation execution. Terminal lookups and policy/service stops can appropriately have flow NOT_APPLICABLE.','',
'## Substantial finding checks','',
'The auditor visually inspected the complete retained PDF23 and PDF29 renders and agrees that the hazard switch is on the right-hand control. EXP001 wrongly says left-hand in its current answer; EXP002 repeats that error only in its retained unsure branch. Distinguishing current grounding from authored-flow quality is correct for EXP002.','',
'The frozen response/source context supports the other practical revisions: refuelling setup/order and omitted cap-unlock details (a_refuel); internal controller language (a_switches_on/a_cool_engine); unnamed referred components (a_reconnect); technical RPM wording (EXP030); assumed battery-removal history (EXP044); the missing photo-question continuation (EXP049); absent authored replies to GEN043; application-versus-rider manual selection (GEN053); and the unanchored normal-result clarification despite known uncertainty (GEN056). The fixture notes for GEN061/GEN087 correctly preserve source-gap versus operational-error distinctions. Exact checks and limits are recorded in audit.json.','',
'## Limits','',
'This review examined joined claim text/canonical policy responses and preserved authored context. No external Gemma request, live controller transition, rider photo execution, rendered UI, clickable citation opening, response stability, latency or cost was tested. The auditor did not redo original-source approval for every case; selected factual and policy conclusions were checked independently, with fresh visual inspection limited to PDF23/PDF29. Hash and quote validation establish input identity and report completeness, while content scores remain LLM judgments.','',
'No responses, signed release artifacts, deployment or billing configuration were changed. Corrections proposed by the judges need a new version and the applicable scoped agent checks before those affected responses are served; they do not create a generic human-review requirement.','',
'## Bound artifacts','',f'Corpus SHA-256: `{PIN_CORPUS}`.',f'Feedback SHA-256: `{PIN_FEEDBACK}`.',f'Results SHA-256: `{sha(BASE/"results.json")}`.',f'Consolidated report SHA-256: `{sha(BASE/"REPORT.md")}`.','',f'[Machine-readable audit](<{(OUT/"audit.json").as_posix()}>)',f'[Reproducible artifact validation](<{(OUT/"audit_validation.py").as_posix()}>)']
(OUT/'AUDIT.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
print(json.dumps({'verdict':audit['audit_verdict'],'checks':audit['checks'],'results_sha256':sha(BASE/'results.json'),'report_sha256':sha(BASE/'REPORT.md'),'audit_sha256':sha(OUT/'audit.json'),'audit_markdown_sha256':sha(OUT/'AUDIT.md')},indent=2))
