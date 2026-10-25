"""Server-side finalization of Sonnet drafts with the production validators and v5 authority.

Run from the project root with PYTHONPATH=. (venv). Mirrors verified_qa: validate_draft,
numeric citation guard, then select() closure + server-required displays appended.
"""
import json
import sys
from pathlib import Path

E = Path(sys.argv[1])
sys.path.insert(0, '.')  # repo-root runtime is byte-identical to frozen v10.14
sys.path.insert(0, 'reports/grounded_generation/structural_review_v2/candidate')
import serving_source_authority_v5 as v5
from approved_registry import ApprovedEvidenceRegistry
from cloud.grounded_generation.verified_qa import validate_draft, validate_numeric_citation_provenance

idx = Path('build/index-bge-final').resolve()
sa = v5.SourceAuthority(ApprovedEvidenceRegistry.load(Path('.').resolve(), idx), idx)
mapping = json.loads((E / 'alias_mapping_PRIVATE.json').read_text())
rep = {r['case_id']: r for r in json.loads(Path('reports/evals/20261023_stage_replay_v1/replay_v5.json').read_text(encoding='utf-8'))['results']}
COVER = {'COMPLETE': 'COMPLETE', 'PARTIAL': 'PARTIAL', 'UNANSWERABLE': 'NONE', 'NEEDS_CLARIFICATION': 'NONE', 'NONE': 'NONE'}
(E / 'finalized').mkdir(exist_ok=True)
summary = {}
for q, cid in sorted(mapping.items()):
    raw = json.loads((E / 'drafts' / (q + '.json')).read_text(encoding='utf-8'))
    hits = [{'id': h['chunk_id'], 'evidence_ids': sa.chunks[h['chunk_id']]['evidence_ids'],
             'parent_section_id': sa.chunks[h['chunk_id']]['parent_section_id']} for h in rep[cid]['final_hits']]
    payload = sa.assemble({'index_id': sa.index_id, 'manual_checksum': sa.checksum, 'hits': hits})
    draft = {'route': raw.get('route'), 'coverage': COVER.get(raw.get('question_coverage') or raw.get('coverage'), raw.get('question_coverage')),
             'claims': [{'text': c.get('text'), 'role': c.get('role'), 'evidence_ids': list(c.get('evidence_ids') or [])} for c in raw.get('claims', [])],
             'unanswered_parts': list(raw.get('unanswered_parts') or []),
             'clarification_question': raw.get('clarification_question') or '', 'rider_resolvable': bool(raw.get('rider_resolvable'))}
    status, code, claims, selected = 'VALID', None, [], {}
    try:
        validate_draft(draft, payload['evidence'])
        validate_numeric_citation_provenance(draft['claims'], payload['evidence'])
        used = {e for c in draft['claims'] for e in c['evidence_ids']}
        selected = sa.select(payload, used) if used else {}
    except Exception as exc:  # production treats these as SYSTEM_ERROR before verification
        status, code = 'REJECTED', (getattr(exc, 'code', None) or str(exc) or type(exc).__name__)[:120]
    if status == 'VALID':
        claims = [{**c, 'origin': 'DRAFT'} for c in draft['claims']]
        claims += [{'text': d['text'], 'role': d['response_role'], 'evidence_ids': list(d['evidence_ids']),
                    'origin': 'SOURCE_REQUIRED_DISPLAY'} for d in selected.get('required_display', [])]
    out = {'route': draft['route'], 'question_coverage': draft['coverage'], 'unanswered_parts': draft['unanswered_parts'],
           'claims': claims, 'draft_validation': status, 'draft_rejection_code': code}
    (E / 'finalized' / (q + '.json')).write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding='utf-8')
    summary[q] = (cid, draft['route'], draft['coverage'], status, code, len(claims))
for q, row in summary.items():
    print(q, *row)
