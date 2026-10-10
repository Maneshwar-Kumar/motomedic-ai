"""Integrity and fail-closed regressions for the completed editorial review.

These tests do not score semantic accuracy. The explicit adjudication is the
semantic review artifact; tests protect its identity, coverage and boundaries.
"""
import copy
import hashlib
import json
import unittest
from pathlib import Path
import review_support as review

HERE=Path(__file__).resolve().parent
def load(name):return json.loads((HERE/name).read_bytes())
def require(condition,reason):
    if not condition:raise ValueError(reason)

def validate(report,sources,corrections):
    source=sources['sources']; original=load('claim_bindings.json')
    require(report['input_binding_sha256']==review.digest((HERE/'claim_bindings.json').read_bytes()),'Stale binding input')
    require(report['review_code_sha256']==review.digest((HERE/'review_support.py').read_bytes()),'Stale review implementation')
    require(report['feedback_sha256']==review.digest((review.ROOT/'human_review/subagent_feedback.md').read_bytes()),'Feedback changed')
    require(report['batch100_completion_sha256']==review.digest((review.ROOT/'human_review/record_workflow/batch_100_completion.json').read_bytes()),'Batch completion changed')
    require(report['first50_inventory_sha256']==review.digest((review.ROOT/'human_review/record_workflow/inventory.json').read_bytes()),'Legacy inventory changed')
    require(len(report['records'])==150 and {r['record_id'] for r in report['records']}=={r['record_id'] for r in original['records']},'Missing or duplicated record')
    require(report['provider_calls']==0 and report['independent_human_approval'] is False and report['runtime_authorized'] is False,'Unauthorized approval/inference')
    count=0
    for record,prior in zip(report['records'],original['records']):
        require(record['record_id']==prior['record_id'],'Records reordered')
        require(record['draft_sha256']==review.digest((review.ROOT/record['draft_path']).read_bytes()),'Draft changed')
        require(record['answer']==prior['answer'],'Untracked answer change')
        require(record['remaining_blocks']==prior['remaining_blocks'],'Source hold removed')
        require(record['source_approval'] is False and record['runtime_authorized'] is False and record['cache_authorized'] is False,'Draft promoted')
        plans=(review.GEN_PLANS if record['record_id'].startswith('GEN') else review.EXP_PLANS)[int(record['record_id'][3:])].split('|')
        require(len(record['claims'])==len(prior['claims'])==len(plans),'Claim omitted')
        for c,old,plan in zip(record['claims'],prior['claims'],plans):
            count+=1
            require(c['claim_id']==old['claim_id'] and c['exact_claim_text']==old['exact_claim_text'] and c['answer_span']==old['answer_span'],'Claim/span changed')
            require(c['agent_support_adjudicated'] is True and c['semantic_support_approved'] is False,'Adjudication/approval conflated')
            require(len(c['support_evidence_ids'])==len(c['source_spans']),'Source span lost')
            require(bool(c['support_evidence_ids']) or plan=='-','Unsupported claim silently passed')
            for eid,span in zip(c['support_evidence_ids'],c['source_spans']):
                require(eid in source and span['evidence_id']==eid,'Invalid citation')
                require(span['text_span']==source[eid]['text_span'],'Source locator changed')
                require(span['text_sha256']==source[eid].get('text_sha256'),'Source hash changed')
            for eid in c['manual_evidence_ids']:require(source[eid]['authority'].startswith('OEM'),'Policy mislabelled OEM')
            for eid in c['policy_evidence_ids']:require(not source[eid]['authority'].startswith('OEM'),'OEM mislabelled policy')
        for branch in record['branch_scope_review']:
            text=(review.ROOT/record['draft_path']).read_bytes().decode('utf-8-sig')
            require(text[slice(*branch['draft_span'])]==branch['exact_text'],'Conditional branch changed')
    require(count==371,'Claim count changed')
    require(not any(x['status']=='NORMALIZATION_OR_EXTRACTION_REVIEW_REQUIRED' for x in report['original_extraction_checks']),'Extraction discrepancy left unresolved')
    for s in source.values():
        if s.get('text_sha256'):require(review.digest(s['exact_text'].encode())==s['text_sha256'],'Source text tampered')
    require({r['record_id'] for r in corrections['records']}==set(review.ISSUES),'Unresolved candidate correction omitted')
    for c in corrections['records']:
        require(c['formal_source_approval'] is False and c['runtime_authorized'] is False,'Correction promoted')
        require(review.digest(c['answer'].encode())==c['answer_sha256'],'Corrected answer changed')
        for claim in c['claims']:
            require(c['answer'][slice(*claim['answer_span'])]==claim['exact_claim_text'],'Correction span invalid')
            require(all(e in source for e in claim['support_evidence_ids']),'Correction citation invalid')
    return {'records':150,'answer_claims':371,'corrected_candidates':4,'semantic_accuracy_metric':'NOT_MEASURED','formal_approvals':0,'provider_calls':0}

class ReviewTests(unittest.TestCase):
    def setUp(self):self.r=load('support_review.json');self.s=load('reviewed_sources.json');self.c=load('corrected_candidates.json')
    def check(self):return validate(self.r,self.s,self.c)
    def test_actual_review(self):self.assertEqual(self.check()['records'],150)
    def test_missing_record(self):
        self.r['records'].pop()
        with self.assertRaises(ValueError):self.check()
    def test_missing_warning_claim(self):
        self.r['records'][7]['claims'].pop()
        with self.assertRaises(ValueError):self.check()
    def test_invented_citation(self):
        self.r['records'][0]['claims'][0]['support_evidence_ids'][0]='invented'
        with self.assertRaises(ValueError):self.check()
    def test_changed_unit_or_number(self):
        s=next(v for v in self.s['sources'].values() if '589' in v['exact_text']);s['exact_text']=s['exact_text'].replace('589','5890')
        with self.assertRaises(ValueError):self.check()
    def test_false_oem_policy(self):
        r=next(x for x in self.r['records'] if x['record_id']=='GEN071');r['claims'][0]['manual_evidence_ids']=r['claims'][0]['support_evidence_ids']
        with self.assertRaises(ValueError):self.check()
    def test_cleared_source_conflict(self):
        next(x for x in self.r['records'] if x['record_id']=='EXP040')['remaining_blocks']=[]
        with self.assertRaises(ValueError):self.check()
    def test_runtime_promotion(self):
        self.r['records'][0]['runtime_authorized']=True
        with self.assertRaises(ValueError):self.check()
    def test_changed_correction(self):
        self.c['records'][0]['answer']='Everything is normal.'
        with self.assertRaises(ValueError):self.check()
    def test_missing_correction(self):
        self.c['records'].pop()
        with self.assertRaises(ValueError):self.check()

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(ReviewTests)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    stats=validate(load('support_review.json'),load('reviewed_sources.json'),load('corrected_candidates.json'))
    stats.update(tests_run=result.testsRun,tests_passed=result.wasSuccessful())
    (HERE/'support_validation.json').write_bytes(review.encoded(stats))
    raise SystemExit(0 if result.wasSuccessful() else 1)
