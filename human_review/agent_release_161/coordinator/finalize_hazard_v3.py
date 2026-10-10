"""Coordinator exact-version signature after independent hazard re-review."""
import copy
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

H = Path(__file__).resolve().parent
ROOT = H.parents[2]
A = H.parent
P = H / 'approved_package_v3'
C = A / 'checker' / 'review_inventory_v3.json'

def read(p):
    return json.loads(p.read_text(encoding='utf-8'))

def raw(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def canon(x):
    return hashlib.sha256(json.dumps(x, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')).hexdigest()

def text_hash(x):
    return hashlib.sha256(x.encode('utf-8')).hexdigest()

def rel(p):
    return p.relative_to(ROOT).as_posix()

def save(p, x):
    p.write_text(json.dumps(x, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')

assert not (H / 'release_manifest_v3.json').exists(), 'Signed versions are immutable'
assert C.is_file(), 'Independent checker inventory must exist before signing'
review = read(C)
checks = {x['record_id']: x for x in review['records']}
assert len(checks) == len(review['records']) == 161
assert review.get('structural_errors', []) == []
assert review.get('unchanged_carryforward_case_count') == 159
assert review.get('freshly_reviewed_case_count') == 2
assert review.get('history_mismatches') == []
assert review.get('whole_corpus_quality_pass_claimed') is False
assert review.get('remaining_quality_findings_count') == 10
independent_audits = {}
for prefix in ('object_audit', 'preservation_baseline', 'source_inspection'):
    path = review[prefix + '_file']
    digest = review[prefix + '_sha256']
    assert raw(ROOT / path) == digest, (prefix, 'independent audit changed')
    independent_audits[path] = digest
package_outputs = read(P / 'package_manifest.json')['outputs']
for name, digest in package_outputs.items():
    assert raw(P / name) == digest, (name, 'package changed after preparation')
for name, digest in review['package_outputs'].items():
    assert raw(P / name) == digest, (name, 'independently reviewed package changed')
assert set(package_outputs) <= set(review['package_outputs']), 'Checker must bind all package artifacts'
for x in review['records']:
    assert raw(ROOT / x['path']) == x['sha256'], (x['record_id'], 'checker bytes changed')
    assert x['final_check_verdict'] == 'PASS_SCOPED_RELEASE'

previous = read(H / 'release_manifest_v2.json')
reg = read(P / 'candidate_registry.json')
sources = read(P / 'source_objects.json')['sources']
routes = {x['record_id']: x for x in read(P / 'trusted_routes.json')['routes']}
fixtures = {x['record_id']: x for x in read(P / 'session_fixtures.json')['records']}
constraints = {x['record_id']: x for x in read(P / 'case_constraints.json')['records']}
correction = read(P / 'hazard_location_corrections.json')
source_id = correction['key_parts_source_id']
authority = raw(A / 'owner_authority.json')
assert authority == previous['authority_sha256']
records = []
for old in previous['records']:
    row = copy.deepcopy(old)
    rid = row['record_id']
    check = checks[rid]
    route = routes[rid]
    sid = route.get('step_id')
    b = row['artifact_bindings']
    b['case_locator']['file'] = rel(P / 'session_fixtures.json')
    b['canonical_answer_locator']['file'] = rel(P / ('candidate_registry.json' if sid else 'trusted_routes.json'))
    row['checker_inventory_sha256'] = raw(C)
    assert check['final_route_sha256'] == canon(route)
    if sid:
        assert check['final_step_sha256'] == canon(reg['steps'][sid])
        assert check['final_dependency_sha256'] == canon(reg['dependencies'][sid])
    if rid not in ('EXP001', 'EXP002'):
        assert b['case_sha256'] == canon(fixtures[rid])
        assert b['route_sha256'] == canon(route)
        assert b['constraint_sha256'] == canon(constraints[rid])
        if sid:
            assert b['step_sha256'] == canon(reg['steps'][sid])
            assert b['dependency_sha256'] == canon(reg['dependencies'][sid])
        for k, digest in b['rule_sha256s'].items():
            assert digest == canon(reg['rules'][k])
        for k, digest in b['source_sha256s'].items():
            assert digest == canon(sources[k])
        assert check['sha256'] == row['checker_report_sha256'], '159 prior reviews must stay exact'
    else:
        authored_path = P / 'authored_cases' / (rid + '.json')
        proposal = read(authored_path)['candidate_case']
        assert check['plan_sha256'] == raw(authored_path)
        assert check.get('authored_case_sha256') == canon(proposal)
        assert check.get('authored_identification_verdict') == 'PASS_SCOPED_AUTHORED_IDENTIFICATION'
        row['original_planner_file'] = row['planner_file']
        row['original_planner_file_sha256'] = row['planner_file_sha256']
        row['original_planner_case_locator'] = copy.deepcopy(b['planner_case_locator'])
        row['original_planner_case_sha256'] = b['planner_case_sha256']
        row['planner_file'] = rel(authored_path)
        row['planner_file_sha256'] = raw(authored_path)
        b['planner_case_locator'] = {'file': rel(authored_path), 'key': 'candidate_case'}
        b['planner_case_sha256'] = canon(proposal)
        b['original_canonical_answer_sha256'] = text_hash(proposal['canonical_answer'])
        b['canonical_answer_locator']['key'] = sid
        b['canonical_answer_sha256'] = canon(reg['steps'][sid]['claims'])
        b['step_id'] = sid
        b['step_sha256'] = canon(reg['steps'][sid])
        b['dependency_id'] = sid
        b['dependency_sha256'] = canon(reg['dependencies'][sid])
        b['rule_sha256s'] = {k: canon(reg['rules'][k]) for k in reg['steps'][sid]['applicability_rule_ids']}
        b['case_sha256'] = canon(fixtures[rid])
        b['route_sha256'] = canon(route)
        b['constraint_sha256'] = canon(constraints[rid])
        b['source_sha256s'][source_id] = canon(sources[source_id])
        b['authored_identification_locator'] = {'file': rel(authored_path), 'key': 'candidate_case', 'field': 'branch_context'}
        b['authored_identification_sha256'] = canon(proposal['branch_context'])
        b['authored_revision'] = proposal['candidate_revision']
        row['approved_scopes'].append('AUTHORED_IDENTIFICATION_CONTENT')
        row['approved_scope_description'] = 'Exact source content and initial response under typed eligibility; corrected right-hand triangle-marked authored identification content only; no adaptive execution, public figure display or general vision approval.'
        row['checker_report_locator'] = {'file': check['path'], 'key': rid}
        row['checker_report_sha256'] = check['sha256']
        row['checker_findings'] = check.get('findings', [])
        row['finding_dispositions'] = [{'finding': f, 'disposition': 'CORRECTED_EXACT_HAZARD_LOCATION_OR_PRESERVED_SCOPE_LIMIT', 'final_artifact_verified': True, 'checker_file': check['path']} for f in check.get('findings', [])]
        row['specific_limits'] = check.get('specific_limits', row['specific_limits'])
        row['correction_review_scope'] = 'Both exact current responses and full retained authored unsure/context reviewed; only hazard-location correction and initial route are signed, not a full adaptive conversation.'
    records.append(row)

manifest = copy.deepcopy(previous)
manifest.update(schema_version='agent-coordinator-release-v3', approved_package=rel(P), supersedes_manifest_sha256=raw(H / 'release_manifest_v2.json'), records=records, checker_inventory={'file': rel(C), 'sha256': raw(C)}, source_review_scope='SOURCE_CONTENT_AND_INITIAL_ROUTE; two corrected authored identification content scopes only', quality_all161_pass_claimed=False, correction_coordinator_actor='/root/hazard_coordinator', signed_at_utc=datetime.now(timezone.utc).isoformat())
outputs = {path: digest for path, digest in previous['outputs'].items() if '/coordinator/approved_package_v2/' not in path and path != 'human_review/agent_release_161/checker/review_inventory_v2.json' and path not in ('human_review/agent_release_161/checker/records_v2/EXP001.json', 'human_review/agent_release_161/checker/records_v2/EXP002.json')}
outputs.update({rel(p): raw(p) for p in sorted(P.rglob('*.json'))})
outputs.update({x['path']: x['sha256'] for x in review['records']})
outputs[rel(C)] = raw(C)
outputs[rel(H / 'corrective_review_v3/candidate_bindings_v3.json')] = raw(H / 'corrective_review_v3/candidate_bindings_v3.json')
outputs[rel(H / 'release_manifest_v2.json')] = raw(H / 'release_manifest_v2.json')
outputs.update(independent_audits)
manifest['outputs'] = outputs
manifest['corrective_review'] = {'changed_records': ['EXP001', 'EXP002'], 'scope': correction['scope'], 'unaffected_case_count': 159, 'independent_hazard_review': {'inventory': rel(C), 'sha256': raw(C)}, 'new_source_id': source_id, 'new_source_sha256': canon(sources[source_id]), 'remaining_quality_revisions': {'count': 10, 'status': 'OPEN_OUTSIDE_TWO_HAZARD_CORRECTIONS', 'record_ids': [x['record_id'] for x in correction['remaining_quality_revisions']['records']]}, 'frozen_judge_results': correction['frozen_judge_results'], 'all161_quality_pass_claimed': False, 'full_adaptive_release_claimed': False}
assert manifest['record_count'] == len(records) == 161
assert {x['record_id'] for x in records} == {x['record_id'] for x in previous['records']}
assert manifest['counts'] == {'APPROVED_AGENT_RELEASE': 161}
assert manifest['adaptive_continuation_approved'] is False
assert manifest['display_figures_approved'] is False
assert manifest['live_provider_calls'] == 0
for path, digest in outputs.items():
    assert raw(ROOT / path) == digest, ('bound output changed', path)
save(H / 'release_manifest_v3.json', manifest)
print(json.dumps({'release_manifest': rel(H / 'release_manifest_v3.json'), 'release_manifest_sha256': raw(H / 'release_manifest_v3.json'), 'checker_inventory': manifest['checker_inventory'], 'counts': manifest['counts'], 'bound_output_file_count': len(outputs), 'new_step_id': routes['EXP001']['step_id'], 'remaining_quality_revisions': manifest['corrective_review']['remaining_quality_revisions']}, indent=2))
