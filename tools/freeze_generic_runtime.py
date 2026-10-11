"""Freeze serving bytes before held-out rider wording is authored; no inference."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/grounded_generation/v5/runtime_freeze.json'

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    if OUT.exists():raise RuntimeError('Do not overwrite an existing serving freeze')
    historical=json.loads((ROOT/'reports/grounded_generation/v4/runtime_freeze.json').read_bytes())
    names=set(historical['file_sha256'])
    names.discard('tools/validate_grounded_generation.py')
    names.update('cloud/grounded_generation/'+name for name in
        ('generic_runtime.py','generic_policy.py','generic_output.py','generic_presentation.py',
         'source_authority.py','test_source_authority.py','test_generic_runtime.py','transitions.py','test_transitions.py'))
    names.update(('reports/grounded_generation/generic_source_v1/structural_review.json',
                  'reports/grounded_generation/read_only_scopes_v1/scopes.json',
                  'approved_registry.py','controller_contracts.py','reviewed_controller.py',
                  'evidence_registry.py','constrained_generator.py','online_retrieve.py',
                  'retrieval_policy.py','source_manifest.json',
                  'tools/validate_generic_generation.py','tools/prepare_grounded_deployment.py'))
    # Expected answers and final rider wording are intentionally not included.
    manifest={'schema_version':'generic-grounded-runtime-freeze-v5','frozen_at_utc':datetime.now(timezone.utc).isoformat(),
        'manual_checksum':'cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89',
        'index_id':'index_a3282c4d98cf54595e4ba168','file_sha256':{name:sha(ROOT/name) for name in sorted(names)},
        'factual_authority':'IMMUTABLE_SOURCE_OBJECT_STRUCTURE_NO_QUESTION_CATALOGUE',
        'procedural_authority':'EXACT_REVIEWED_ELIGIBILITY_AND_DOCUMENTED_TRANSITIONS',
        'separate_semantic_verifier_calls':0,'public_release_approved':False,
        'provider_attempt_allocation':50,'heldout_expected_answers_packaged':False,
        'source_approval_scope':'EXACT_SOURCE_OBJECTS_AND_DOCUMENT_STRUCTURE_ONLY',
        'model_acceptance':'PENDING_REAL_MODEL_EXECUTION_AND_ORIGINAL_PAGE_CLAIM_REVIEW'}
    OUT.write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'freeze_sha256':sha(OUT),'files':len(names),'public_access_opened':False}))

if __name__=='__main__':main()
