"""Index-free production startup policy checks; no stores, models or providers."""
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cloud.arm_a import app
from tools.serving_release import CURRENT,ROOT as REPOSITORY_ROOT


class ProductionPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.release=json.loads((REPOSITORY_ROOT/CURRENT).read_bytes())

    def test_current_frozen_role_policy_passes_without_provider_construction(self):
        with patch('cloud.grounded_generation.role_router.production_router',
                   side_effect=AssertionError('provider construction forbidden')):
            app.validate_production_policy(self.release)

    def test_old_cache_policy_or_changed_role_contract_rejects(self):
        for field,value in [('prompt_cache','ANTHROPIC_VERIFIER_EVIDENCE_PREFIX_5M'),
                            ('model_routing_contract',None)]:
            changed=deepcopy(self.release);changed[field]=value
            with self.subTest(field=field),self.assertRaisesRegex(RuntimeError,'serving policy mismatch'):
                app.validate_production_policy(changed)
        changed=deepcopy(self.release)
        changed['model_routing_contract']['roles']['HAIKU_DRAFT_GEMMA_VERIFY']['verifier']['model']='changed'
        with self.assertRaisesRegex(RuntimeError,'serving policy mismatch'):
            app.validate_production_policy(changed)

    def test_existing_model_cache_and_verifier_predicates_remain_required(self):
        for field,value in [('schema_version','old'),('primary_model','changed'),
            ('answer_cache_enabled',True),('verifier_enabled',False),
            ('draft_model_contract',None),('verifier_model','changed'),('verifier_contract',None)]:
            changed=deepcopy(self.release);changed[field]=value
            with self.subTest(field=field),self.assertRaisesRegex(RuntimeError,'serving policy mismatch'):
                app.validate_production_policy(changed)

    def test_loader_calls_literal_policy_guard_before_loading_artifacts(self):
        changed=deepcopy(self.release);changed['file_sha256']={}
        changed['prompt_cache']='ANTHROPIC_VERIFIER_EVIDENCE_PREFIX_5M'
        with tempfile.TemporaryDirectory() as name:
            root=Path(name);(root/'arm_a_release.json').write_text(json.dumps(changed),encoding='utf-8')
            with patch.object(app,'ROOT',root),patch.dict('os.environ',{'K_SERVICE':'synthetic-test'}),\
                    patch('cloud.serving_artifacts.load_index',
                          side_effect=AssertionError('artifact load forbidden')):
                with self.assertRaisesRegex(RuntimeError,'serving policy mismatch'):
                    app.load_production()


if __name__=='__main__':unittest.main()
