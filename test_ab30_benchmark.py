import json,os,unittest
from pathlib import Path
from unittest.mock import patch
import ab30_benchmark as run
class Contracts(unittest.TestCase):
 def test_local_live_denied(self):
  with patch.dict(os.environ,{'GITHUB_ACTIONS':'false'}):
   with self.assertRaisesRegex(ValueError,'HOSTED_ONLY'):run.validate_authority()
 def test_frozen30(self):
  cases=run.read(run.ROOT/'reports/ab30_v1_cases.json')['cases']
  self.assertEqual(len(cases),30);self.assertEqual(len({c['record_id'] for c in cases}),30)
  self.assertEqual(len([n for n in range(30) if n%2==0]),15)
  for c in cases:
   self.assertEqual(run.sha(run.ROOT/c['planner_path']),c['planner_sha256'])
   original=run.read(run.ROOT/c['planner_path'])['candidate_case']
   query=original.get('question') or original['branch_context']['producer']['question']
   self.assertEqual(query,c['query'])
 def test_finite_scope(self):
  protocol=run.read(run.ROOT/'reports/ab30_v1_protocol.json')
  self.assertEqual(protocol['maximum_provider_calls'],90);self.assertEqual(protocol['cells'],60)
  self.assertEqual(protocol['retries'],0);self.assertFalse(protocol['fallback'])
if __name__=='__main__':unittest.main()
