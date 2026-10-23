"""Replay recorded immutable retrieval IDs after implementation; no providers.

This is projection/admission regression evidence. It does not tune retrieval or
prompts from held-out questions and does not establish model token counts,
answer correctness, live latency, or release acceptance.
"""
from pathlib import Path
import hashlib
import json
import os
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from approved_registry import ApprovedEvidenceRegistry
from cloud.grounded_generation.source_authority import SourceAuthority as PriorAuthority
from cloud.grounded_generation.serving_source_authority import SourceAuthority
from cloud.grounded_generation.verified_qa import compact_source_evidence


def wire_size(value):
    return len(json.dumps(value, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8'))


def main():
    index = Path(os.environ.get('MOTOMEDIC_TEST_INDEX', str(ROOT / 'build/index-bge-final')))
    base = ApprovedEvidenceRegistry.load(ROOT, index)
    prior, current = PriorAuthority(base, index), SourceAuthority(base, index)
    frozen = ROOT / 'reports/grounded_generation/v8/run_38160944967/claude-fallback-result.json'
    old = json.loads(frozen.read_text(encoding='utf-8'))
    rows = []
    for recorded in old['rows']:
        if recorded['turn_number'] == 1 and recorded['case_id'] == 'H801':
            continue
        controls = recorded['view']['runtime_controls']['source_admission']
        chunk_ids = controls['chunk_ids']
        bundle = {'index_id': current.index_id, 'manual_checksum': current.checksum,
                  'hits': [current.chunks[cid] for cid in chunk_ids]}
        before, after = prior.assemble(bundle), current.assemble(bundle)
        rows.append({'case_id': recorded['case_id'], 'turn_number': recorded['turn_number'],
            'recorded_immutable_chunk_ids': chunk_ids,
            'prior_admitted_objects': len(before['evidence']), 'current_admitted_objects': len(after['evidence']),
            'prior_compact_evidence_bytes': wire_size(compact_source_evidence(before['evidence'])),
            'current_compact_evidence_bytes': wire_size(compact_source_evidence(after['evidence'])),
            'current_admitted_evidence_ids': after['required_evidence_ids'],
            'current_source_gaps': after['gaps'], 'exact_model_token_count': None,
            'exact_count_pending_hosted_provider_scope': True})
    result = {'schema_version': 'provider-free-recorded-evidence-replay-v1',
        'label': 'SYNTHETIC_LOCAL_PROJECTION_AND_ADMISSION_REGRESSION',
        'manual_checksum': current.checksum, 'index_id': current.index_id,
        'original_v8_result_sha256': hashlib.sha256(frozen.read_bytes()).hexdigest(),
        'source_authority_lock': current.lock,
        'source_bound_files': current._files,
        'prompt_or_retrieval_tuning_performed': False, 'heldout_questions_used_as_prompt_enrichment': False,
        'provider_calls': 0, 'model_loaded': False, 'index_rebuilt': False,
        'factual_answer_acceptance': False, 'latency_acceptance': False,
        'limits': 'Evidence wire sizes exclude complete runtime/schema/history/final response overhead. Exact authorized provider counting remains necessary and fail-closed in the request path.',
        'rows': rows}
    target = ROOT / 'reports/build/20261012/evidence_projection_replay.json'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'report': str(target), 'rows': [{k: v for k, v in row.items()
        if k in ('case_id', 'prior_admitted_objects', 'current_admitted_objects',
                 'prior_compact_evidence_bytes', 'current_compact_evidence_bytes')} for row in rows]}, indent=2))


if __name__ == '__main__': main()
