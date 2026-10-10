"""Hosted acceptance runner over the existing BGE snapshot; no parsing/embedding."""
import argparse
from dataclasses import asdict
import json
from pathlib import Path
import unittest

from evidence_registry import EvidenceRegistry, read_json, content_hash
from online_retrieve import Retriever
from reviewed_controller import start_session


class NoInferenceEncoder:
    def encode(self, *args, **kwargs):
        raise AssertionError('Draft evidence must not schedule inference')


def verify(index, output):
    registry = EvidenceRegistry.load('registry', index, 'source_manifest.json')
    cases = read_json('registry/acceptance_scenarios.json')
    if cases['manual_checksum'] != registry.checksum or cases['index_id'] != registry.index_id:
        raise ValueError('Acceptance/source mismatch')
    retriever = Retriever(index, embedding_model=NoInferenceEncoder())
    controller = retriever.reviewed_controller(registry)
    rows = []
    for case in cases['cases']:
        session = start_session(registry, [case['intent']], registry.source['variant'])
        _, response, decisions = controller.next(session, case['query'])
        passed = response.type.value == case['expected_current_route'] and not response.claim_evidence_map and not response.suggested_step_id
        rows.append({'case_id':case['case_id'], 'mode':case['mode'], 'current_route':response.type.value,
                     'reason_codes':response.reason_codes,'draft_gate_passed':passed,
                     'independent_review_status':case['review_status'], 'release_acceptance':'BLOCKED_PENDING_INDEPENDENT_REVIEW'})
    # Contract tests use synthetic reviewed records; they prove software behavior only.
    suite = unittest.defaultTestLoader.loadTestsFromName('test_reviewed_controller')
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    report = {'schema_version':'controller-verification-v1','registry_lock':registry.lock,
              'source_checksum':registry.checksum,'index_id':registry.index_id,
              'scenario_dataset_digest':content_hash(cases),'direct_scenarios':5,'multi_turn_scenarios':3,
              'draft_gate_passes':sum(r['draft_gate_passed'] for r in rows),'cases':rows,
              'synthetic_contract_tests':{'run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors)},
              'release_gate_passed':False,'approved_steps':[sid for sid in registry.candidate['steps'] if registry.step_ready(sid)],
              'scope':'Hosted prebuilt-index reuse and draft rejection; no OEM claim review, semantic-verifier calibration or public demo release.',
              'index_rebuilt':False,'gcp_resources_or_billing_changed':False}
    Path(output).parent.mkdir(parents=True, exist_ok=True)
    Path(output).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    if not result.wasSuccessful() or not all(r['draft_gate_passed'] for r in rows):
        raise SystemExit(1)
    print(json.dumps({'draft_gate_passes':report['draft_gate_passes'],'synthetic_contract_tests':result.testsRun,'release_gate_passed':False}))


if __name__ == '__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--index',type=Path,required=True)
    p.add_argument('--output',type=Path,default=Path('build/controller-verification.json'))
    a=p.parse_args()
    verify(a.index,a.output)
