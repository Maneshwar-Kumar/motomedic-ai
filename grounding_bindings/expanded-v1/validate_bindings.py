"""Validate binding integrity, not semantic entailment or release approval."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('expanded_binding_author',HERE/'author_bindings.py')
author=importlib.util.module_from_spec(spec)
spec.loader.exec_module(author)


def require(ok,reason):
    if not ok: raise ValueError(reason)


def validate(bindings,sources):
    require(len(bindings['records'])==150,'Record count changed')
    require(len({r['record_id'] for r in bindings['records']})==150,'Duplicate record')
    objects,expected,_=author.load_sources()
    require(bindings['manual_sha256']=='cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89','Manual changed')
    require(bindings['index_id']=='index_a3282c4d98cf54595e4ba168','Index changed')
    actual=sources['sources']
    for eid,value in actual.items():
        require(eid in expected and value==expected[eid],'Altered source object or table cells')
    claims=set()
    for record in bindings['records']:
        data=(author.ROOT/record['draft_path']).read_bytes()
        require(author.sha(data)==record['draft_sha256'],'Draft changed')
        if record['record_id'].startswith('GEN'):
            original=json.loads(data);answer=original['answer']
            require(original['version']==record['record_version'],'Version changed')
        else:
            import re
            text=data.decode('utf-8-sig')
            answer=re.search(r'Assistant:\s*["\u201c](.*?)["\u201d](?:\s*\n|\s*$)',text,re.S).group(1)
        require(record['answer']==answer and record['answer_sha256']==author.sha(answer.encode('utf-8')),'Answer changed')
        require(record['runtime_authorized'] is False and record['formal_source_approved'] is False,'Draft promotion forbidden')
        spans=author.answer_spans(answer)
        require(len(spans)==len(record['claims']),'A sentence claim was omitted')
        for claim,(start,_,text) in zip(record['claims'],spans):
            require(claim['claim_id'] not in claims,'Duplicate claim ID');claims.add(claim['claim_id'])
            require(claim['exact_claim_text']==text and claim['answer_span']==[start,start+len(text)],'Invalid answer span')
            require(answer[slice(*claim['answer_span'])]==text,'Claim does not occur verbatim')
            require(claim['semantic_support_approved'] is False,'Semantic approval cannot be inferred')
            if claim['claim_type']!='DISCOURSE': require(bool(claim['support_evidence_ids']),'Unbound sentence')
            for eid in claim['support_evidence_ids']: require(eid in actual,'Missing bound source')
            for eid in claim['manual_evidence_ids']:
                require(actual[eid]['authority']=='OEM_MANUAL','Policy cannot masquerade as OEM evidence')
            for eid in claim['policy_evidence_ids']:
                require(actual[eid]['authority']=='PRODUCT_POLICY','OEM page cannot substantiate application policy')
        n=int(record['record_id'][3:])
        selectors=(author.GEN if record['record_id'].startswith('GEN') else author.EXP).get(n,[])
        curated=list(dict.fromkeys(eid for page,fragment in selectors for eid in author.select(objects,page,fragment)))
        require(record['required_manual_evidence_ids']==curated,'Curated manual binding changed')
        for claim in record['claims']:
            if claim['claim_type']!='DISCOURSE':
                require(claim['manual_evidence_ids']==curated,'Claim attached to wrong existing source')
                require(set(claim['support_evidence_ids'])==set(claim['manual_evidence_ids']+claim['policy_evidence_ids']),'Claim support set altered')
        require(set(record['required_manual_evidence_ids'])<=set(actual),'Required manual source missing')
        require(set(record['required_policy_evidence_ids'])<=set(actual),'Required policy source missing')
        require(set(record['required_figure_evidence_ids'])<=set(actual),'Required figure source missing')
        if record['required_figure_evidence_ids']:
            require('FIGURE_RELATION_AND_VISUAL_VERIFICATION_REQUIRED' in record['remaining_blocks'],'Figure gate removed')
        if record['workflow_state'] in ('BLOCKED_BINDING','BLOCKED_SOURCE_GAP'):
            require(record['workflow_state'] in record['remaining_blocks'],'Historical review/source hold removed')
    return {'record_count':150,'sentence_claim_count':len(claims),'source_count':len(actual),
            'binding_integrity':'PASSED','semantic_entailment':'NOT_EVALUATED',
            'source_or_runtime_approvals_created':0,'provider_calls':0}


class BindingRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bindings=json.loads((HERE/'claim_bindings.json').read_bytes())
        cls.sources=json.loads((HERE/'bound_sources.json').read_bytes())

    def reject(self,change):
        b,s=copy.deepcopy(self.bindings),copy.deepcopy(self.sources)
        change(b,s)
        with self.assertRaises(ValueError):validate(b,s)

    def test_actual_corpus(self):
        self.assertEqual(validate(self.bindings,self.sources)['record_count'],150)

    def test_stale_draft_hash(self):
        self.reject(lambda b,s:b['records'][0].update(draft_sha256='0'*64))

    def test_false_citation(self):
        self.reject(lambda b,s:b['records'][0]['claims'][0]['support_evidence_ids'].append('evidence_invented'))

    def test_omitted_sentence_warning(self):
        self.reject(lambda b,s:b['records'][7]['claims'].pop())

    def test_changed_numeric_source(self):
        def change(b,s):
            source=next(x for x in s['sources'].values() if x.get('table_cells'))
            source['table_cells'][0]['text']='WRONG UNIT'
        self.reject(change)

    def test_policy_cannot_supply_oem_proof(self):
        def change(b,s):
            c=b['records'][0]['claims'][0]
            c['manual_evidence_ids']=[c['policy_evidence_ids'][0]]
        self.reject(change)

    def test_wrong_existing_manual_id(self):
        def change(b,s):
            wrong=next(e for e,v in s['sources'].items() if v['authority']=='OEM_MANUAL' and e not in b['records'][0]['required_manual_evidence_ids'])
            b['records'][0]['claims'][0]['manual_evidence_ids']=[wrong]
        self.reject(change)

    def test_binding_cannot_approve_answer(self):
        self.reject(lambda b,s:b['records'][0].update(runtime_authorized=True))

    def test_prior_review_hold_is_retained(self):
        def change(b,s):
            r=next(r for r in b['records'] if r['workflow_state']=='BLOCKED_BINDING')
            r['remaining_blocks'].remove('BLOCKED_BINDING')
        self.reject(change)


if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(BindingRegressionTests))
    require(result.wasSuccessful(),'Binding regression failure')
    report=validate(json.loads((HERE/'claim_bindings.json').read_bytes()),json.loads((HERE/'bound_sources.json').read_bytes()))
    report['regression_tests']=result.testsRun
    (HERE/'validation.json').write_bytes(author.canonical(report))
    print(json.dumps(report))
