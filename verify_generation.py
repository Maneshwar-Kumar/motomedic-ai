"""Private hosted engineering evaluation with prebuilt immutable index reuse."""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import unittest

from evidence_registry import EvidenceRegistry, read_json, content_hash
from online_retrieve import Retriever
from reviewed_controller import start_session
from constrained_generator import ConstrainedGenerator
from generation_contracts import RuntimeConfig
from verify_controller import NoInferenceEncoder


class ForbiddenProvider:
    def __init__(self): self.calls = 0
    def complete(self, *args):
        self.calls += 1
        raise AssertionError("Real draft source must stop before generation or verification")


def verify(index, output):
    registry = EvidenceRegistry.load('registry', index, 'source_manifest.json')
    cases = read_json('registry/acceptance_scenarios.json')
    if cases['manual_checksum'] != registry.checksum or cases['index_id'] != registry.index_id:
        raise ValueError('Acceptance/index mismatch')
    gen, judge = ForbiddenProvider(), ForbiddenProvider()
    from constrained_generator import SemanticSupportAdapter
    pipeline = ConstrainedGenerator(gen, SemanticSupportAdapter(judge))
    controller = Retriever(index, embedding_model=NoInferenceEncoder()).reviewed_controller(registry)
    controller.response_generator = pipeline
    controller.audience = 'end_user'
    rows = []
    for case in cases['cases']:
        session = replace(start_session(registry,[case['intent']],registry.source['variant']),
                          generation_lock=pipeline.config.lock)
        updated,response,_ = controller.next(session,case['query'])
        followups = []
        for i, turn in enumerate(case.get('turns_after_review', [])):
            # Real draft paths must never acquire a pending action/question.
            try:
                controller.feedback(updated, turn.get('outcome', 'OBSERVED_ABNORMAL'), f'draft-followup-{i}')
                rejected = False
            except ValueError:
                rejected = True
            followups.append({'turn_index':i,'unissued_feedback_rejected':rejected})
        passed = (response.type.value == 'UNSUPPORTED' and not response.claim_evidence_map and
                  not response.suggested_step_id and not updated.pending_step_id and
                  all(f['unissued_feedback_rejected'] for f in followups))
        rows.append({'case_id':case['case_id'],'mode':case['mode'],'route':response.type.value,
                     'reason_codes':response.reason_codes,'passed':passed,'followups':followups,
                     'split':'REGRESSION_NOT_HELD_OUT','source_review':'DRAFT'})
    suite = unittest.defaultTestLoader.loadTestsFromName('test_constrained_generator')
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    report = {'schema_version':'generation-engineering-evaluation-v1',
              'commit':subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
              'source_checksum':registry.checksum,'index_id':registry.index_id,
              'registry_lock':registry.lock,'runtime_versions':RuntimeConfig().versions(),
              'runtime_lock':pipeline.config.lock,'scenario_digest':content_hash(cases),
              'cases':rows,'real_source_gate_passes':sum(r['passed'] for r in rows),
              'real_source_generation_calls':gen.calls,'real_source_verification_calls':judge.calls,
              'synthetic_tests':{'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)},
              'live_provider_calls':0,'provider_cost_usd':0,'ci_cost_usd':None,
              'ci_cost_status':'NOT_MEASURED','semantic_accuracy':'NOT_EVALUATED',
              'held_out_cases':0,'approved_real_steps':[], 'release_gate_passed':False,
              'index_rebuilt':False,'gcp_resources_or_billing_changed':False}
    Path(output).parent.mkdir(parents=True,exist_ok=True)
    Path(output).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    if not result.wasSuccessful() or not all(r['passed'] for r in rows) or gen.calls or judge.calls:
        raise SystemExit(1)
    print(json.dumps({'real_source_gate_passes':report['real_source_gate_passes'],
                      'synthetic_tests':result.testsRun,'live_provider_calls':0}))


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path('build/generation-engineering-evaluation.json'))
    args = p.parse_args()
    verify(args.index,args.output)
