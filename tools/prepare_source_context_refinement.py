"""Prepare exact object/context proposal; this command grants no approval."""
from pathlib import Path
import hashlib
import json
import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from evidence_registry import content_hash


def main():
    index = ROOT / 'build/index-bge-final'
    manifest = json.loads((index / 'manifest.json').read_text(encoding='utf-8'))
    evidence = {row['id']: row for row in map(json.loads, (index / 'evidence.jsonl').read_text(encoding='utf-8').splitlines())}
    fresh = json.loads((ROOT / 'reports/grounded_generation/read_only_scopes_v1/scopes.json').read_text(encoding='utf-8'))
    ids = ['evidence_3f8de8466049af12783de7d0', 'evidence_64de3cc72b85735055b58fec',
           'evidence_a03ccd44ab2d6b5db6bab123', 'evidence_c5bacd3bd5b428c8950b0ce1']
    rows = {}
    for eid in ids:
        obj = evidence[eid]
        source = fresh.get('source_objects', {}).get(eid, {}).get('source_object')
        rows[eid] = {'evidence_id': eid, 'raw_object_sha256': content_hash(obj['raw_object']),
            'provenance_sha256': content_hash(obj['provenance']),
            'indexed_object_sha256': content_hash(obj), 'type': obj['type'],
            'source_object': source, 'source_object_sha256': content_hash(source) if source else None,
            'section_path': ['TECHNICAL SPECIFICATIONS', 'FUEL SPECIFICATIONS AND APPROXIMATION']
                if eid in ids[:2] else ['OPERATION OF CONTROLS', 'LOW-FUEL WARNING'],
            'required_evidence_ids': sorted(ids), 'parent_text_authorized': False,
            'context_authority': 'PROPOSED_EXACT_COMPONENT_CONTEXT_REFINEMENT',
            'source_pages': sorted({p['page_no'] for p in obj['provenance']})}
    images = {}
    for page in (18, 64):
        image = ROOT / f'tmp/source-context-refinement-v2/original-{page:03}.png'
        images[str(page)] = {'path': str(image.relative_to(ROOT)).replace('\\', '/'),
                            'sha256': hashlib.sha256(image.read_bytes()).hexdigest()}
    proposal = {'version': 'source-component-context-refinement-v2',
        'decision': 'PROPOSED_REQUIRES_INDEPENDENT_ORIGINAL_PAGE_REVIEW',
        'authority': 'AGENT_SOURCE_CONTEXT_REVIEW', 'reviewer': None,
        'manual_checksum': manifest['source_sha256'], 'index_id': manifest['index_id'],
        'immutable_evidence_sha256': manifest['file_checksums']['evidence.jsonl'],
        'source_object_review_sha256': 'e8763b1a4e1f99f6efca0885eb62f832d0938837e4495a2c0a23ba3e8b988fb4',
        'prior_structural_review_sha256': '2fb64c8a642c4ef25494c4baa1f80adc8392de50dcbb3eeb50222da69513d725',
        'parent_text_authorized': False, 'action_authority': False,
        'questions_or_expected_answers_included': False,
        'original_pdf_pages': images, 'bindings': rows,
        'required_display': [
            {'claim_id': 'source-refinement-fuel-approximation',
             'text': 'The stated fuel values are approximate; actual filling capacity varies.',
             'response_role': 'WARNING', 'evidence_ids': [ids[1]], 'presentation_mode': 'REVIEWED_PARAPHRASE'},
            {'claim_id': 'source-refinement-refuel-earliest',
             'text': 'Do not use the motorcycle for long with the last fuel-indicator segment blinking; refuel at the earliest.',
             'response_role': 'WARNING', 'evidence_ids': [ids[2]], 'presentation_mode': 'REVIEWED_PARAPHRASE'},
            {'claim_id': 'source-refinement-fuel-pump-warning',
             'text': 'Failure to refuel can leave the motorcycle out of fuel and stranded and cause serious fuel-pump damage.',
             'response_role': 'WARNING', 'evidence_ids': [ids[3]], 'presentation_mode': 'REVIEWED_PARAPHRASE'}],
        'excluded_context': {'evidence_ids': ['evidence_1fe8af98a9e6d6027d12f8c8',
            'evidence_a5b62eee4c0caf239437fa68', 'evidence_5b6388c083677b5d5cd6ad4a',
            'evidence_dd285d8b6e6a1682de0e10f0', 'evidence_c762ef2c61505dc7ac7c01d8',
            'evidence_cb7062b4cec26700e3ae1185', 'evidence_f1b023ea7924903fed5dfe5f',
            'evidence_f3dd00ecbff8fd98a8c32736'],
            'reason': 'PDF18 visually separates left tyre-size/pressure and rim notes from the right fuel specification table and its asterisk note. PDF64 visually separates the top-left low-fuel warning from CHARGER PORT and right-column USB warnings. Exclusion applies only to these four exact fuel source objects; all tyre/USB dependencies stay unchanged.'},
        'scope': ['EXACT_SOURCE_OBJECTS', 'EXACT_FUEL_COMPONENT_CONTEXT'],
        'excluded_scopes': ['Whole parent bodies', 'Unreviewed tyre source content', 'New authored procedures',
                            'General vision', 'Public source display', 'Answer-quality release', 'Deployment']}
    destination = ROOT / 'reports/build/20261012/source_context_refinement_v2/new_proposal.json'
    if destination.exists():
        raise RuntimeError('Proposal already exists: preserve exact reviewed bytes and choose a new scoped version')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(proposal, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    print(json.dumps({'proposal': str(destination), 'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
                      'decision': proposal['decision']}, indent=2))


if __name__ == '__main__': main()
