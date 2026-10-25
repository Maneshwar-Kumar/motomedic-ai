"""Freeze the v8 serving and validation bytes before fresh rider wording."""
from pathlib import Path
from datetime import datetime,timezone
import json,hashlib
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'reports/grounded_generation/v8/runtime_freeze.json'
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    if OUT.exists():raise RuntimeError('Never overwrite a serving freeze')
    names=set(json.loads((ROOT/'reports/grounded_generation/v6/runtime_freeze.json').read_bytes())['file_sha256'])
    names.update(('cloud/grounded_generation/claude_provider.py','cloud/grounded_generation/fallback_provider.py',
        'cloud/grounded_generation/claude_budget.py','cloud/grounded_generation/test_claude_fallback.py',
        'tools/validate_claude_fallback.py','tools/freeze_claude_evidence_runtime.py','rider_ui/tests/test_client.py',
        'rider_ui/tests/test_progress_stream.py','.github/workflows/claude-evidence-fallback.yml'))
    data={'schema_version':'draft-verify-stream-runtime-freeze-v8','frozen_at_utc':datetime.now(timezone.utc).isoformat(),
        'file_sha256':{p:sha(ROOT/p)for p in sorted(names)},
        'manual_checksum':'cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89',
        'index_id':'index_a3282c4d98cf54595e4ba168','source_approval_scope':'EXACT_IMMUTABLE_SOURCE_OBJECTS_NOT_AUTHORED_RESPONSES',
        'primary_model':'gemma-4-26b-a4b-it','fallback_model':'claude-haiku-5-5','maximum_nonrecurring_claude_usd':1,
        'validation_generation_attempt_cap':24,'validation_reserved_token_cap':239808,
        'exact_response_cache':'DISABLED','public_deployment_changed':False,'billing_changed':False,
        'model_acceptance':'PENDING_ACTUAL_FALLBACK_AND_ORIGINAL_SOURCE_REVIEW'}
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'freeze_sha256':sha(OUT),'files':len(names)}))
if __name__=='__main__':main()
