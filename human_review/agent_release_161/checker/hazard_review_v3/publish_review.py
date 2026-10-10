"""Publish the checker's adjudication, separately from mechanical hash checks."""
from pathlib import Path
from datetime import datetime, timezone
import copy
import hashlib
import json

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
BASE = ROOT / 'human_review/agent_release_161'
OLD = BASE / 'coordinator/approved_package_v2'
NEW = BASE / 'coordinator/approved_package_v3'
MANUAL_SHA = 'cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89'
OLD_SENTENCE = 'The hazard button is the triangle-marked button on the left-hand handlebar control shown on PDF29.'
NEW_SENTENCE = 'The hazard button is the triangle-marked button on the right-hand handlebar control.'

def read(path): return json.loads(path.read_text(encoding='utf-8'))
def rawh(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def canon(value): return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode()).hexdigest()
def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
def rel(path): return path.relative_to(ROOT).as_posix()
def indexed(path, key): return {x['record_id']: x for x in read(path)[key]}
def pages(obj):
    result = [x['page_no'] for x in obj.get('provenance', [])]
    result += [obj[k] for k in ('pdf_page', 'pdf_page_one_based') if isinstance(obj.get(k), int)]
    return sorted(set(result))

def main():
    audit = read(OUT / 'candidate_object_audit.json')
    assert audit['package_manifest_sha256'] == rawh(NEW / 'package_manifest.json')
    assert audit['unaffected_case_count'] == 159 and not audit['history_mismatches']
    assert all(all(x['checks'].values()) for x in audit['unaffected_case_checks'])
    manifest = read(NEW / 'package_manifest.json')
    assert all(rawh(NEW / name) == sha for name, sha in manifest['outputs'].items())
    bindings = read(BASE / 'coordinator/corrective_review_v3/candidate_bindings_v3.json')
    reg = read(NEW / 'candidate_registry.json'); oldreg = read(OLD / 'candidate_registry.json')
    sources = read(NEW / 'source_objects.json')['sources']
    routes = indexed(NEW / 'trusted_routes.json', 'routes')
    oldroutes = indexed(OLD / 'trusted_routes.json', 'routes')
    fixtures = indexed(NEW / 'session_fixtures.json', 'records')
    constraints = indexed(NEW / 'case_constraints.json', 'records')
    oldconstraints = indexed(OLD / 'case_constraints.json', 'records')
    source_review = read(OUT / 'source_inspection.json')
    assert source_review['original_pdf_sha256'] == MANUAL_SHA
    for page in source_review['pages']:
        assert rawh(ROOT / page['image_path']) == page['image_sha256']
    source_review['inspection_status'] = 'INDEPENDENTLY_VISUALLY_REVIEWED'
    source_review['reviewed_at_utc'] = datetime.now(timezone.utc).isoformat()
    source_review['visual_adjudication'] = [
        {'pdf_page': 23, 'printed_label': '21', 'finding': 'Item 6 Hazard switch points to the rider right-hand control, adjacent to item 5 Ignition/Engine kill switch.', 'scope': 'Finite original diagram and label relationship; not a rider-photo diagnosis.'},
        {'pdf_page': 29, 'printed_label': '27', 'finding': 'The hazard drawing has the triangle-marked hazard control on the same right-hand assembly. Ignition ON activation, OFF continuation for 30 minutes unless deactivated, OFF activation prohibition, prolonged-stop ignition-off and battery-strain cautions are retained.', 'scope': 'Hazard control identity and stated activation conditions/cautions.'},
        {'pdf_page': 30, 'printed_label': '28', 'finding': 'The warning states turn signals do not work while hazards are ON and trafficator lamps flash simultaneously.', 'scope': 'Hazard warning continuation only; no repair process authorized.'},
    ]
    write(OUT / 'source_inspection.json', source_review)
    oldinventory = read(BASE / 'checker/review_inventory_v2.json')
    rows = copy.deepcopy(oldinventory['records'])
    oldrows = {x['record_id']: x for x in rows}
    judge = read(ROOT / 'human_review/llm_judge_161/results.json')
    open_quality_ids = sorted(x['record_id'] for x in judge['records'] if x['overall'] == 'REVISE' and x['record_id'] not in ('EXP001', 'EXP002'))
    assert len(open_quality_ids) == 10
    report_paths = []
    for record_id in ('EXP001', 'EXP002'):
        authored_file = NEW / 'authored_cases' / f'{record_id}.json'
        authored = read(authored_file); case = authored['candidate_case']
        original_plan_file = BASE / 'planner/plans' / f'{record_id}.json'
        oldcase = read(original_plan_file)['candidate_case']
        oldtext = oldcase['branch_context']['producer']['full_record_text']
        text = case['branch_context']['producer']['full_record_text']
        expected = oldtext.replace(f'# {record_id} v3', f'# {record_id} v4').replace('Original pages: PDF 29-30; printed 27-28.', 'Original pages: PDF 23, 29-30; printed 21, 27-28.')
        expected = expected.replace(OLD_SENTENCE, NEW_SENTENCE) if record_id == 'EXP001' else expected.replace('triangle-marked hazard button on the left-hand handlebar control.', 'triangle-marked hazard button on the right-hand handlebar control.')
        assert text == expected, (record_id, 'undeclared authored text change')
        expected_answer = oldcase['canonical_answer'].replace(OLD_SENTENCE, NEW_SENTENCE) if record_id == 'EXP001' else oldcase['canonical_answer']
        assert case['canonical_answer'] == expected_answer
        for claim in case['claims']:
            assert case['canonical_answer'][slice(*claim['answer_span'])] == claim['exact_claim_text']
        for span in case['branch_context']['reviewed_conditional_spans']:
            assert text[slice(*span['draft_span'])] == span['exact_text']
        assert 'left-hand' not in json.dumps(case).lower()
        sid = routes[record_id]['step_id']; step = reg['steps'][sid]; dep = reg['dependencies'][sid]
        oldsid = oldroutes[record_id]['step_id']; oldstep = oldreg['steps'][oldsid]
        rules = {k: reg['rules'][k] for k in step['applicability_rule_ids']}
        assert canon(constraints[record_id]['transitions']) == canon(oldconstraints[record_id]['transitions'])
        assert [x['text'] for i,x in enumerate(step['claims']) if not (record_id == 'EXP001' and i == 1)] == [x['text'] for i,x in enumerate(oldstep['claims']) if not (record_id == 'EXP001' and i == 1)]
        if record_id == 'EXP002':
            assert canon(step) == canon(oldstep)
        bc = next(x for x in bindings['records'] if x['record_id'] == record_id)
        assert canon(step) == bc['final_step_sha256'] and canon(dep) == bc['final_dependency_sha256']
        assert canon(rules) == bc['final_rules_sha256'] and canon(routes[record_id]) == bc['final_route_sha256']
        assert canon(case) == bc['authored_case_sha256'] and rawh(authored_file) == bc['authored_case_file_sha256']
        ids = set(step['required_evidence_ids']) | set(step['action_evidence_ids']) | set(case['required_candidate_source_ids'])
        for rule in rules.values(): ids.update(rule.get('source_evidence_ids', [])); ids.update(rule.get('policy_source_ids', []))
        for group in case['branch_context']['dependencies']: ids.update(group['evidence_ids'])
        for eid in ids:
            obj = sources[eid]
            assert hashlib.sha256(obj['exact_text'].encode()).hexdigest() == obj['text_sha256']
        source_checks = [{'source_id': eid, 'source_sha256': canon(sources[eid]), 'text_sha256': sources[eid]['text_sha256'], 'original_pdf_pages': pages(sources[eid]), 'authority': sources[eid]['authority'], 'figure_render_inspected': any(n in (23,29,30) for n in pages(sources[eid])), 'review_basis': 'Fresh original-page visual/text review for PDF23/29/30; unchanged exact source/policy objects retain their previous scoped agent review.'} for eid in sorted(ids)]
        finding = ('The corrected current and retained authored identification says right-hand and retains the triangle symbol. Original PDF23 item6 and PDF29 drawing independently support the side/symbol. All other claims, activation states, 30-minute conditional continuation, battery cautions and PDF30 turn-signal warning are unchanged.' if record_id == 'EXP001' else 'The retained full unsure branch now locates the triangle-marked hazard button on the right-hand control. Initial runtime claims/step are unchanged. Hazard status stays conditional; persistent uncertainty or confirmed OFF routes to service without wiring diagnosis. Engineering-only figure scope and reported-issue closure limits are unchanged.')
        limits = copy.deepcopy(oldrows[record_id]['specific_limits'])
        record = {
            'schema_version': 'independent-agent-hazard-correction-check-v3', 'record_id': record_id,
            'checker_actor': 'independent-source-checker', 'checker_agent': '/root/hazard_checker',
            'reviewed_at_utc': datetime.now(timezone.utc).isoformat(),
            'plan_path': rel(authored_file), 'plan_sha256': rawh(authored_file),
            'original_planner_file': rel(original_plan_file), 'original_planner_file_sha256': rawh(original_plan_file),
            'plan_inventory_sha256': rawh(BASE / 'planner/plan_inventory.json'),
            'package_manifest_sha256': rawh(NEW / 'package_manifest.json'), 'package_outputs': manifest['outputs'],
            'final_step_sha256': canon(step), 'final_dependency_sha256': canon(dep),
            'final_rules_sha256': canon(rules), 'final_route_sha256': canon(routes[record_id]),
            'authored_case_sha256': canon(case), 'authored_case_digest': case['case_digest'],
            'authored_case_file_sha256': rawh(authored_file), 'canonical_answer_sha256': canon(step['claims']),
            'case_sha256': canon(fixtures[record_id]), 'constraint_sha256': canon(constraints[record_id]),
            'manual_sha256': MANUAL_SHA, 'candidate_question': case['question'],
            'claim_texts': [x['text'] for x in step['claims']], 'source_checks': source_checks,
            'original_pdf_pages_checked_for_correspondence': [23,29,30], 'visual_pages_inspected': [23,29,30],
            'source_inspection_file': rel(OUT / 'source_inspection.json'), 'source_inspection_sha256': rawh(OUT / 'source_inspection.json'),
            'original_figure_claim_verdict': 'PASS_FINITE_ORIGINAL_MANUAL_RELATIONSHIP',
            'reviewed_full_authored_branch': case['branch_context']['reviewed_conditional_spans'],
            'authored_identification_verdict': 'PASS_SCOPED_AUTHORED_IDENTIFICATION',
            'authored_identification_scope': 'Static source-supported side and triangle-symbol text in the retained branch only; no adaptive runtime execution or public image delivery approval.',
            'verdict': 'PASS_SCOPED_INITIAL_HANDLING', 'final_check_verdict': 'PASS_SCOPED_RELEASE',
            'feedback': finding, 'findings': [finding], 'specific_limits': limits, 'structural_errors': [],
            'preserved_conditions_and_state': ['Initial unknown fact remains UNKNOWN', 'ACTION_COMPLETED_UNRESOLVED remains distinct from OBSERVED_NORMAL', 'No new successors or automatic repeats', 'Customer report does not verify a repair', 'Separate unresolved issues retained', 'Source gap and SYSTEM_ERROR remain distinct'],
            'approval_scope': oldrows[record_id]['approval_scope'], 'exclusions': limits,
            'independent_human_review': False, 'coordinator_final_approval_pending': True,
            'full_adaptive_transitions_approved': False, 'public_figure_delivery_approved': False,
            'general_vision_evaluation_performed': False, 'live_provider_calls': 0, 'deployment_performed': False,
            'remaining_quality_findings_count': 10, 'remaining_quality_findings_record_ids': open_quality_ids,
            'quality_scope': 'Correction-only reassessment of EXP001/EXP002; frozen 161-case judge results remain unchanged; no new whole-corpus quality-pass claim.',
        }
        destination = BASE / 'checker/records_v3' / f'{record_id}.json'
        write(destination, record); report_paths.append(destination)
        newrow = copy.deepcopy(oldrows[record_id])
        newrow.update({key: record[key] for key in ('verdict','final_check_verdict','plan_sha256','final_route_sha256','final_step_sha256','final_dependency_sha256','final_rules_sha256','findings','specific_limits','approval_scope','manual_sha256','checker_actor','structural_errors','authored_case_sha256','authored_identification_verdict')})
        newrow.update({'path': rel(destination), 'sha256': rawh(destination), 'authored_case_file': rel(authored_file), 'authored_case_file_sha256': rawh(authored_file)})
        rows[rows.index(oldrows[record_id])] = newrow
    assert len(rows) == 161 and len({x['record_id'] for x in rows}) == 161
    for row in rows:
        assert rawh(ROOT / row['path']) == row['sha256']
        assert row['final_check_verdict'] == 'PASS_SCOPED_RELEASE'
    inventory = copy.deepcopy(oldinventory)
    inventory.update({
        'schema_version': 'independent161-final-inventory-v3', 'records': rows,
        'package_outputs': manifest['outputs'], 'package_manifest_sha256': rawh(NEW / 'package_manifest.json'),
        'checker_actor': 'independent-source-checker', 'checker_agent': '/root/hazard_checker',
        'count': 161, 'source_inspection': 'Fresh independent Poppler original-page renders and PDFium text extraction for PDF23/29/30; semantic side/symbol and complete hazard-condition/warning adjudication; exact two-case source/span and authored-text check. The other 159 initial/content approvals carry forward only after unchanged canonical route, fixture, constraint, step, dependency, rule, source and original-plan comparisons. No new broad quality pass or runtime claim.',
        'freshly_reviewed_case_count': 2, 'unchanged_carryforward_case_count': 159,
        'source_inspection_file': rel(OUT / 'source_inspection.json'), 'source_inspection_sha256': rawh(OUT / 'source_inspection.json'),
        'object_audit_file': rel(OUT / 'candidate_object_audit.json'), 'object_audit_sha256': rawh(OUT / 'candidate_object_audit.json'),
        'preservation_baseline_file': rel(OUT / 'preservation_baseline.json'), 'preservation_baseline_sha256': rawh(OUT / 'preservation_baseline.json'),
        'preserved_history_file_count': audit['preserved_history_file_count'], 'history_mismatches': [],
        'unaffected_procedure_review_file': 'human_review/agent_release_161/checker/procedure_review_v2.json',
        'unaffected_procedure_review_sha256': rawh(BASE / 'checker/procedure_review_v2.json'),
        'narrow_authored_identification_cases': ['EXP001','EXP002'], 'full_adaptive_transitions_approved': False,
        'public_figure_delivery_approved': False, 'general_figure_verifier_evaluated': False,
        'remaining_quality_findings_count': 10, 'remaining_quality_findings_record_ids': open_quality_ids,
        'frozen_quality_results_file': 'human_review/llm_judge_161/results.json', 'frozen_quality_results_sha256': rawh(ROOT / 'human_review/llm_judge_161/results.json'),
        'whole_corpus_quality_pass_claimed': False, 'provider_calls': 0, 'deployment_performed': False,
        'final_approval': 'COORDINATOR_PENDING',
    })
    write(BASE / 'checker/review_inventory_v3.json', inventory)
    summary = {'verdict': 'PASS_TWO_SCOPED_HAZARD_CORRECTIONS', 'records': [{'record_id': p.stem, 'path': rel(p), 'sha256': rawh(p)} for p in report_paths], 'inventory_path': 'human_review/agent_release_161/checker/review_inventory_v3.json', 'inventory_sha256': rawh(BASE / 'checker/review_inventory_v3.json'), 'unaffected_cases_verified': 159, 'frozen_history_files_verified': audit['preserved_history_file_count'], 'remaining_quality_findings': open_quality_ids, 'coordinator_signature_pending': True}
    write(OUT / 'check_summary_v3.json', summary)
    print(json.dumps(summary, ensure_ascii=True, indent=2))

if __name__ == '__main__': main()
