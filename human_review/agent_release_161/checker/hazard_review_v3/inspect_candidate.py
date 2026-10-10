"""Independently audit candidate identities and print scoped semantic material."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
BASE = ROOT / 'human_review/agent_release_161'
OLD = BASE / 'coordinator/approved_package_v2'
NEW = BASE / 'coordinator/approved_package_v3'

def read(path): return json.loads(path.read_text(encoding='utf-8'))
def rawh(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def canon(value): return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def indexed(path, key): return {x['record_id']: x for x in read(path)[key]}
def changed_paths(a, b, path=''):
    if isinstance(a, dict) and isinstance(b, dict):
        return sum((changed_paths(a.get(k), b.get(k), path + '/' + k) for k in sorted(set(a) | set(b))), [])
    if isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        return sum((changed_paths(x, y, path + '/' + str(i)) for i, (x,y) in enumerate(zip(a,b))), [])
    return [] if a == b else [path]

def main():
    package = read(NEW / 'package_manifest.json')
    assert rawh(NEW / 'package_manifest.json') == '016f0fbbf8e841c1198237defec1357457e6ef02880b8d020c32da4efec40ab0'
    assert all(rawh(NEW / name) == h for name, h in package['outputs'].items())
    oldreg = read(OLD / 'candidate_registry.json'); reg = read(NEW / 'candidate_registry.json')
    olds = read(OLD / 'source_objects.json')['sources']; sources = read(NEW / 'source_objects.json')['sources']
    oldroutes = indexed(OLD / 'trusted_routes.json', 'routes'); routes = indexed(NEW / 'trusted_routes.json', 'routes')
    oldfixtures = indexed(OLD / 'session_fixtures.json', 'records'); fixtures = indexed(NEW / 'session_fixtures.json', 'records')
    oldconstraints = indexed(OLD / 'case_constraints.json', 'records'); constraints = indexed(NEW / 'case_constraints.json', 'records')
    checks = []
    oldrelease = indexed(BASE / 'coordinator/release_manifest_v2.json', 'records')
    for record_id in sorted(oldroutes):
        if record_id in ('EXP001', 'EXP002'): continue
        oldroute = oldroutes[record_id]; route = routes[record_id]
        sid = oldroute.get('step_id')
        same = {'route': canon(oldroute) == canon(route), 'fixture': canon(oldfixtures[record_id]) == canon(fixtures[record_id]), 'constraint': canon(oldconstraints[record_id]) == canon(constraints[record_id])}
        if sid:
            same['step'] = canon(oldreg['steps'][sid]) == canon(reg['steps'][sid])
            same['dependency'] = canon(oldreg['dependencies'][sid]) == canon(reg['dependencies'][sid])
            same['rules'] = all(canon(oldreg['rules'][rule]) == canon(reg['rules'][rule]) for rule in oldreg['steps'][sid]['applicability_rule_ids'])
        same['bound_sources'] = all(canon(sources[eid]) == expected for eid, expected in oldrelease[record_id]['artifact_bindings']['source_sha256s'].items())
        same['original_plan_file'] = rawh(ROOT / oldrelease[record_id]['planner_file']) == oldrelease[record_id]['planner_file_sha256']
        assert all(same.values()), (record_id, same)
        checks.append({'record_id': record_id, 'checks': same, 'verdict': 'UNCHANGED_EXACT_CANONICAL_OBJECTS'})
    assert len(checks) == 159
    unchanged_old_sources = all(canon(obj) == canon(sources[eid]) for eid, obj in olds.items())
    assert unchanged_old_sources
    assert canon(oldreg['procedures']) == canon(reg['procedures'])
    baseline = read(OUT / 'preservation_baseline.json')
    history_mismatches = [name for name, expected in baseline['unchanged_history_file_hashes'].items() if rawh(ROOT / name) != expected]
    assert not history_mismatches, history_mismatches
    bindings_path = BASE / 'coordinator/corrective_review_v3/candidate_bindings_v3.json'
    bindings = read(bindings_path)
    assert rawh(bindings_path) == 'cfe232210834746d1313ae498b0fae7b29f8172cc7d046f034a14a4634e68ff4'
    two = []
    for record_id in ('EXP001', 'EXP002'):
        authored_file = NEW / 'authored_cases' / f'{record_id}.json'
        authored = read(authored_file)
        case = authored['candidate_case']
        oldcase = read(BASE / 'planner/plans' / f'{record_id}.json')['candidate_case']
        route = routes[record_id]; sid = route['step_id']; step = reg['steps'][sid]; dep = reg['dependencies'][sid]
        bc = next(x for x in bindings['records'] if x['record_id'] == record_id)
        rules = {rule: reg['rules'][rule] for rule in step['applicability_rule_ids']}
        assert canon(step) == bc['final_step_sha256'] and canon(dep) == bc['final_dependency_sha256']
        assert canon(rules) == bc['final_rules_sha256'] and canon(route) == bc['final_route_sha256']
        assert canon(case) == bc['authored_case_sha256'] and rawh(authored_file) == bc['authored_case_file_sha256']
        assert canon(step['claims']) == bc['canonical_answer_sha256'] and canon(fixtures[record_id]) == bc['case_sha256']
        assert canon(constraints[record_id]) == bc['constraint_sha256']
        text = case['branch_context']['producer']['full_record_text']
        for span in case['branch_context']['reviewed_conditional_spans']:
            assert text[slice(*span['draft_span'])] == span['exact_text']
        assert 'left-hand' not in json.dumps(case).lower()
        relevant_ids = set(step['required_evidence_ids']) | set(step['action_evidence_ids'])
        for claim in step['claims']:
            relevant_ids.update(claim['evidence_ids']); relevant_ids.update(claim['policy_support_ids'])
            for span in claim['source_spans']:
                obj = sources[span['evidence_id']]
                assert hashlib.sha256(obj['exact_text'].encode()).hexdigest() == span['text_sha256']
        assert not step['adaptive_continuation_authorized'] and not step['next_step_ids']
        two.append({'record_id': record_id, 'authored_file_keys': list(authored), 'authored_case_changed_paths': changed_paths(oldcase, case), 'step': step, 'dependency': dep, 'rules': rules, 'fixture': fixtures[record_id], 'constraint': constraints[record_id], 'authored_record': text, 'reviewed_conditional_spans': case['branch_context']['reviewed_conditional_spans']})
    added = sorted(set(sources) - set(olds))
    assert added == [bindings['source23_id']]
    audit = {
        'schema_version': 'independent-hazard-object-audit-v3',
        'package_manifest_sha256': rawh(NEW / 'package_manifest.json'),
        'candidate_bindings_sha256': rawh(bindings_path),
        'unaffected_case_count': len(checks), 'unaffected_case_checks': checks,
        'old_source_objects_unchanged': unchanged_old_sources,
        'all_parent_procedures_unchanged': True,
        'preserved_history_file_count': len(baseline['unchanged_history_file_hashes']),
        'history_mismatches': history_mismatches,
        'added_source_ids': added,
        'added_source_objects': {eid: sources[eid] for eid in added},
        'candidate_details': two,
    }
    (OUT / 'candidate_object_audit.json').write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(audit, ensure_ascii=True, indent=2))

if __name__ == '__main__': main()
