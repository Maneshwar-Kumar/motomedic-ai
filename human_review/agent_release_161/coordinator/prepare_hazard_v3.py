"""Prepare the two owner-authorized hazard corrections; never sign or call providers."""
import copy
import hashlib
import json
import shutil
from pathlib import Path

import pymupdf

H = Path(__file__).resolve().parent
ROOT = H.parents[2]
P2 = H / 'approved_package_v2'
P3 = H / 'approved_package_v3'
C = H / 'corrective_review_v3'
VERSION = 'agent-hazard-identification-v4'

def read(p):
    return json.loads(p.read_text(encoding='utf-8'))

def canonical(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()

def raw(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def text_hash(t):
    return hashlib.sha256(t.encode('utf-8')).hexdigest()

def save(p, x):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(x, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')

def rel(p):
    return p.relative_to(ROOT).as_posix()

assert not P3.exists(), 'Create a new immutable version instead of overwriting v3'
assert not (H / 'release_manifest_v3.json').exists()
shutil.copytree(P2, P3)
C.mkdir(exist_ok=True)

manual_path = ROOT / 'royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf'
manual_hash = raw(manual_path)
assert manual_hash == 'cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89'
pdf = pymupdf.open(manual_path)
source_text = pdf[22].get_text()
source_id = 'originalpdf_' + text_hash(manual_hash + ':23:' + text_hash(source_text))[:24]
sources = read(P3 / 'source_objects.json')
source23 = {
    'evidence_id': source_id,
    'authority': 'OEM_ORIGINAL_PDF_CANDIDATE',
    'exact_text': source_text,
    'text_sha256': text_hash(source_text),
    'text_span': [0, len(source_text)],
    'manual_sha256': manual_hash,
    'pdf_page': 23,
    'printed_page': '21',
    'bbox': list(pdf[22].rect),
    'parser': 'PyMuPDF ' + pymupdf.VersionBind,
    'index_membership': False,
    'runtime_authorized': False,
    'visual_provenance': {
        'source_pdf_sha256': manual_hash,
        'render_file': 'human_review/llm_judge_161/root_checks/pdf_023.png',
        'render_sha256': raw(ROOT / 'human_review/llm_judge_161/root_checks/pdf_023.png'),
        'relationship': 'Location of key parts, item 6 Hazard switch, on rider right-hand control; item 5 ignition/engine kill switch adjacent.',
        'review_scope': 'Finite source figure/legend relationship; independent recheck required before coordinator signing; no rider-photo or display approval.',
    },
}
assert source_id not in sources['sources']
sources['sources'][source_id] = source23
save(P3 / 'source_objects.json', sources)

reg = read(P3 / 'candidate_registry.json')
old_sid = 'EXP001:candidate-v3'
new_sid = 'EXP001:candidate-v4'
step = reg['steps'].pop(old_sid)
old_claim = copy.deepcopy(step['claims'][1])
assert old_claim['text'] == 'The hazard button is the triangle-marked button on the left-hand handlebar control shown on PDF29.'
new_text = 'The hazard button is the triangle-marked button on the right-hand handlebar control.'
step['claims'][1]['text'] = new_text
step['claims'][1]['evidence_ids'].append(source_id)
step['claims'][1]['source_spans'][0]['visual_page'] = 29
step['claims'][1]['source_spans'].append({'evidence_id': source_id, 'text_sha256': source23['text_sha256'], 'text_span': source23['text_span'], 'visual_page': 23})
step['step_id'] = new_sid
step['rule_version'] = VERSION
step['dependency_manifest_version'] = VERSION
step['action_evidence_ids'].append(source_id)
step['required_evidence_ids'].append(source_id)
reg['steps'][new_sid] = step
dep = reg['dependencies'].pop(old_sid)
dep['step_id'] = new_sid
dep['version'] = VERSION
dep['action_evidence_ids'].append(source_id)
dep['required_evidence_ids'].append(source_id)
dep['categories']['actions'].append(source_id)
dep['categories']['figures'].extend(['originalpdf_979bc0c9bccf9767693d4b4b', source_id])
reg['dependencies'][new_sid] = dep
for rid in step['applicability_rule_ids']:
    reg['rules'][rid]['rule_version'] = VERSION
hazard_rule = reg['rules']['EXP001:rule:hazard_button_identified']
hazard_rule['source_evidence_ids'].append(source_id)
hazard_rule['clarification_evidence_ids'].append(source_id)
save(P3 / 'candidate_registry.json', reg)

fixtures = read(P3 / 'session_fixtures.json')
next(x for x in fixtures['records'] if x['record_id'] == 'EXP001')['step_id'] = new_sid
save(P3 / 'session_fixtures.json', fixtures)
routes = read(P3 / 'trusted_routes.json')
next(x for x in routes['routes'] if x['record_id'] == 'EXP001')['step_id'] = new_sid
save(P3 / 'trusted_routes.json', routes)
constraints = read(P3 / 'case_constraints.json')
constraint = next(x for x in constraints['records'] if x['record_id'] == 'EXP001')
constraint['eligibility']['rule_objects'] = {rid: copy.deepcopy(reg['rules'][rid]) for rid in step['applicability_rule_ids']}
constraint['case_specific_corrections'].append('Right-hand triangle-marked hazard button identification bound to original PDF23 item6 and PDF29; typed eligibility and all transition limits unchanged.')
save(P3 / 'case_constraints.json', constraints)

authored = {}
for rid in ('EXP001', 'EXP002'):
    plan_path = ROOT / 'human_review/agent_release_161/planner/plans' / (rid + '.json')
    old_case = read(plan_path)['candidate_case']
    case = copy.deepcopy(old_case)
    producer = case['branch_context']['producer']
    full = producer['full_record_text']
    assert full.count('left-hand handlebar control') == 1
    full = full.replace('# ' + rid + ' v3 -', '# ' + rid + ' v4 -', 1)
    full = full.replace('Original pages: PDF 29-30; printed 27-28.', 'Original pages: PDF 23, 29-30; printed 21, 27-28.', 1)
    full = full.replace('left-hand handlebar control', 'right-hand handlebar control', 1)
    if rid == 'EXP001':
        full = full.replace(' on the right-hand handlebar control shown on PDF29.', ' on the right-hand handlebar control.', 1)
        case['canonical_answer'] = case['canonical_answer'].replace(old_claim['text'], new_text, 1)
        case['claims'][1]['exact_claim_text'] = new_text
        for key in ('manual_evidence_ids', 'support_evidence_ids'):
            case['claims'][1][key].append(source_id)
        case['claims'][1]['source_spans'] = copy.deepcopy(step['claims'][1]['source_spans'])
        position = 0
        for claim in case['claims']:
            text = claim['exact_claim_text']
            start = case['canonical_answer'].find(text, position)
            assert start >= 0
            claim['answer_span'] = [start, start + len(text)]
            position = start + len(text)
    producer['full_record_text'] = full
    for branch in case['branch_context']['reviewed_conditional_spans']:
        branch['exact_text'] = branch['exact_text'].replace('left-hand handlebar control', 'right-hand handlebar control')
        start = full.find(branch['exact_text'])
        assert start >= 0
        branch['draft_span'] = [start, start + len(branch['exact_text'])]
    oem_dependency = next(x for x in case['branch_context']['dependencies'] if x['kind'] == 'OEM_BRANCH_CONTEXT')
    oem_dependency['evidence_ids'].append(source_id)
    case['required_candidate_source_ids'] = sorted(set(case['required_candidate_source_ids']) | {source_id})
    case['required_source_locks'][source_id] = {'text_sha256': source23['text_sha256'], 'authority': source23['authority']}
    case['candidate_revision'] = VERSION
    case['producer_version'] = 4
    case['producer_draft_sha256'] = text_hash(full)
    case['revision_provenance'] = {
        'supersedes_planner_case': {'file': rel(plan_path), 'key': 'candidate_case', 'sha256': canonical(old_case)},
        'original_planner_file_sha256': raw(plan_path),
        'original_producer_version': old_case['producer_version'],
        'original_producer_draft_sha256': old_case['producer_draft_sha256'],
        'current_producer_hash_scope': 'UTF8 exact retained full_record_text',
        'decision_authority': 'OWNER_DELEGATED_AGENT_COORDINATOR',
        'correction_scope': 'Hazard button side and original source bindings only; original branch semantics retained; no executable adaptive approval.',
    }
    payload = {k: v for k, v in case.items() if k not in ('case_digest', 'canonical_citations', 'coverage_plan')}
    case['case_digest'] = canonical(payload)
    case['canonical_citations'] = [{'claim_id': x['claim_id'], 'evidence_id': eid, 'source_text_sha256': sources['sources'][eid]['text_sha256']} for x in case['claims'] for eid in x['support_evidence_ids']]
    wrapper = {'schema_version': 'agent-hazard-corrected-authored-case-v4', 'record_id': rid, 'candidate_case': case, 'candidate_case_sha256': canonical(case), 'canonical_answer_sha256': text_hash(case['canonical_answer']), 'original_planner_file': rel(plan_path), 'original_planner_file_sha256': raw(plan_path), 'approval_status': 'AWAITING_INDEPENDENT_CORRECTION_CHECK', 'runtime_authorized': False}
    save(P3 / 'authored_cases' / (rid + '.json'), wrapper)
    authored[rid] = case

branches = read(P3 / 'branch_dependencies.json')
for branch in branches['branches']:
    rid = branch['branch_id'].split(':', 1)[0]
    if rid not in authored:
        continue
    number = int(branch['branch_id'].rsplit(':', 1)[1])
    branch['branch_context'] = copy.deepcopy(authored[rid]['branch_context']['reviewed_conditional_spans'][number])
    branch['source_ids'] = sorted(set(branch['source_ids']) | {source_id})
    branch['source_review_version'] = VERSION
    if rid == 'EXP001':
        branch['parent_step_id'] = new_sid
save(P3 / 'branch_dependencies.json', branches)

judge_path = ROOT / 'human_review/llm_judge_161/results.json'
judge = read(judge_path)
open_quality = [{'record_id': x['record_id'], 'overall': x['overall'], 'rationale': x['rationale'], 'findings': x['findings']} for x in judge['records'] if x.get('overall') == 'REVISE' and x['record_id'] not in ('EXP001', 'EXP002')]
assert len(open_quality) == 10
correction_record = {
    'schema_version': 'hazard-identification-correction-v3',
    'scope': ['EXP001_CURRENT_IDENTIFICATION', 'EXP001_RETAINED_AUTHORED_IDENTIFICATION', 'EXP002_RETAINED_UNSURE_IDENTIFICATION'],
    'changes': [{'record_id': 'EXP001', 'old_text': old_claim['text'], 'new_text': new_text}, {'record_id': 'EXP002', 'old_text': 'If unsure: the source29 drawing shows the triangle-marked hazard button on the left-hand handlebar control.', 'new_text': 'If unsure: the source29 drawing shows the triangle-marked hazard button on the right-hand handlebar control.'}],
    'manual_sha256': manual_hash,
    'key_parts_source_id': source_id,
    'key_parts_source_sha256': canonical(source23),
    'source_pages': [23, 29, 30],
    'source_relationship': 'PDF23 item6 places hazard on rider right-hand control; PDF29 triangle-marked button and activation/battery cautions; PDF30 simultaneous lamps and turn-signal warning.',
    'unchanged_branch_semantics': ['Uncertain observation stays UNKNOWN/UNCLEAR', 'Control differs requires scope reconfirmation', 'No wiring/relay/fuse diagnosis', 'No invented test', 'Still unsure or unexpected operation takes source-limited service route', 'Resolved is customer-reported only', 'No automatic repeat or adaptive edge'],
    'source_review_gaps_retained': True,
    'independent_human_review': False,
    'approval_status': 'AWAITING_INDEPENDENT_CORRECTION_CHECK',
    'frozen_judge_results': {'file': rel(judge_path), 'sha256': raw(judge_path)},
    'remaining_quality_revisions': {'count': 10, 'status': 'OPEN_OUTSIDE_TWO_HAZARD_CORRECTIONS', 'records': open_quality},
    'quality_all161_pass_claimed': False,
    'adaptive_continuation_approved': False,
}
save(P3 / 'hazard_location_corrections.json', correction_record)

outputs = {p.relative_to(P3).as_posix(): raw(p) for p in sorted(P3.rglob('*.json')) if p.name != 'package_manifest.json'}
manifest = {'version': 'agent-scoped-package-v3', 'outputs': outputs, 'approval_status': 'AWAITING_INDEPENDENT_FINAL_CHECK', 'supersedes_package_manifest_sha256': raw(P2 / 'package_manifest.json'), 'correction_scope': correction_record['scope'], 'manual_sha256': manual_hash, 'unaffected_case_count': 159, 'adaptive_continuation_approved': False}
save(P3 / 'package_manifest.json', manifest)

candidate = {'schema_version': 'hazard-correction-candidate-bindings-v3', 'approved_package': rel(P3), 'package_manifest_sha256': raw(P3 / 'package_manifest.json'), 'package_outputs': outputs, 'source23_id': source_id, 'source23_sha256': canonical(source23), 'records': []}
for rid in ('EXP001', 'EXP002'):
    route = next(x for x in routes['routes'] if x['record_id'] == rid)
    sid = route['step_id']
    st = reg['steps'][sid]
    fixture = next(x for x in fixtures['records'] if x['record_id'] == rid)
    constraint = next(x for x in constraints['records'] if x['record_id'] == rid)
    authored_path = P3 / 'authored_cases' / (rid + '.json')
    candidate['records'].append({'record_id': rid, 'step_id': sid, 'final_step_sha256': canonical(st), 'final_dependency_sha256': canonical(reg['dependencies'][sid]), 'final_rules_sha256': canonical({k: reg['rules'][k] for k in st['applicability_rule_ids']}), 'rule_sha256s': {k: canonical(reg['rules'][k]) for k in st['applicability_rule_ids']}, 'final_route_sha256': canonical(route), 'case_sha256': canonical(fixture), 'constraint_sha256': canonical(constraint), 'canonical_answer_sha256': canonical(st['claims']), 'authored_case_file': rel(authored_path), 'authored_case_file_sha256': raw(authored_path), 'authored_case_sha256': canonical(authored[rid]), 'authored_case_digest': authored[rid]['case_digest'], 'claim_texts': [x['text'] for x in st['claims']], 'full_authored_branch': authored[rid]['branch_context']['reviewed_conditional_spans']})
save(C / 'candidate_bindings_v3.json', candidate)
print(json.dumps({'package': rel(P3), 'package_manifest_sha256': candidate['package_manifest_sha256'], 'candidate_bindings': rel(C / 'candidate_bindings_v3.json'), 'candidate_bindings_sha256': raw(C / 'candidate_bindings_v3.json'), 'records': [{k: v for k, v in x.items() if k not in ('claim_texts', 'full_authored_branch', 'rule_sha256s')} for x in candidate['records']]}, indent=2))
