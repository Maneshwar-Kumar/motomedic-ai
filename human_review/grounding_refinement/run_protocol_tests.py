"""Record actual offline test outcomes; scripted judges cannot measure Gemma accuracy."""
import io
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT))
from human_review.grounding_refinement.verify_batch import sha

MODULES=['test_reviewed_controller','test_constrained_generator','test_gemini_provider',
         'test_conditional_retrieval','human_review.grounding_refinement.test_candidate']

class Results(unittest.TextTestResult):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.rows=[]
    def addSuccess(self,test):
        super().addSuccess(test);self.rows.append({'test':test.id(),'status':'PASS'})
    def addFailure(self,test,err):
        super().addFailure(test,err);self.rows.append({'test':test.id(),'status':'FAIL'})
    def addError(self,test,err):
        super().addError(test,err);self.rows.append({'test':test.id(),'status':'ERROR'})

if __name__=='__main__':
    stream=io.StringIO()
    suite=unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(name) for name in MODULES)
    result=unittest.TextTestRunner(stream=stream,resultclass=Results,verbosity=2).run(suite)
    out=Path(__file__).parent
    (out/'protocol_test_log.txt').write_text(stream.getvalue(),encoding='utf-8')
    report={'scope':'FICTIONAL_OFFLINE_PROTOCOL; no OEM approvals or model accuracy',
            'tests_run':result.testsRun,'success':result.wasSuccessful(),'per_test':result.rows,
            'test_code_sha256':{str(p.relative_to(ROOT)):sha(p) for p in
                [ROOT/(name+'.py') for name in MODULES if '.' not in name]+[out/'test_candidate.py']},
            'live_provider_calls':0}
    (out/'protocol_results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'tests_run':result.testsRun,'success':result.wasSuccessful(),'failures':len(result.failures),'errors':len(result.errors)}))
    if not result.wasSuccessful():print(stream.getvalue());raise SystemExit(1)
