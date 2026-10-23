"""Record coordinator's completed independent original-page scoped inspection.

This command checks bindings and records an inspection already performed by the
coordinator. It does not infer approval from hashes or grant human signoff.
"""
from pathlib import Path
import hashlib
import json
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from evidence_registry import content_hash

PROPOSAL_SHA='405269fa7d31274a1e5c6260bbee3e762c8cf2898a5401a4f71e97e155afa1f0'
MANUAL_SHA='cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89'


def main():
    folder=ROOT/'reports/build/20261012/source_context_refinement_v2'
    proposal=folder/'proposal_v3.json'
    assert hashlib.sha256(proposal.read_bytes()).hexdigest()==PROPOSAL_SHA
    review=json.loads(proposal.read_bytes())
    manual=ROOT/'royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf'
    assert hashlib.sha256(manual.read_bytes()).hexdigest()==MANUAL_SHA
    assert review['manual_checksum']==MANUAL_SHA
    assert review['parent_text_authorized'] is False and review['action_authority'] is False
    assert review['questions_or_expected_answers_included'] is False
    evidence_path=ROOT/'build/index-bge-final/evidence.jsonl'
    assert hashlib.sha256(evidence_path.read_bytes()).hexdigest()==review['immutable_evidence_sha256']
    evidence={r['id']:r for r in map(json.loads,evidence_path.read_text(encoding='utf-8').splitlines())}
    fresh_path=ROOT/'reports/grounded_generation/read_only_scopes_v1/scopes.json'
    assert hashlib.sha256(fresh_path.read_bytes()).hexdigest()==review['source_object_review_sha256']
    fresh=json.loads(fresh_path.read_bytes())
    for row in review['original_pdf_pages'].values():
        assert hashlib.sha256((ROOT/row['path']).read_bytes()).hexdigest()==row['sha256']
    new_sources={}
    for eid,row in review['bindings'].items():
        original=evidence[eid]
        assert content_hash(original)==row['indexed_object_sha256']
        assert content_hash(original['raw_object'])==row['raw_object_sha256']
        assert content_hash(original['provenance'])==row['provenance_sha256']
        assert sorted(p['page_no'] for p in original['provenance'])==row['source_pages']
        assert set(row['required_evidence_ids'])==set(review['bindings'])
        assert not row.get('reviewed_source_annotations')
        if row['source_object']:
            assert content_hash(row['source_object'])==row['source_object_sha256']
            assert row['source_object']==fresh['source_objects'][eid]['source_object']
        else:
            new_sources[eid]={'authority':'OEM_MANUAL_AGENT_COMPONENT_CONTEXT_V2',
                'evidence_id':eid,'manual_sha256':MANUAL_SHA,'index_id':review['index_id'],
                'object_type':original['type'],'exact_text':original['raw_object']['text'],
                'provenance':original['provenance'],'raw_object_sha256':row['raw_object_sha256'],
                'review_status':'APPROVED_AGENT_EXACT_SOURCE_CONTENT',
                'requires_visual_verification':False,'index_membership':True}
    assert evidence['evidence_3f8de8466049af12783de7d0']['raw_object']['data']['table_cells'][11]['text']=='3 L \u00b1 0.5* L'
    result={'version':'independent-component-context-review-v3',
        'decision':'APPROVED_EXACT_SOURCE_OBJECT_CONTEXT_ONLY',
        'authority':'AGENT_SOURCE_CONTEXT_REVIEW','reviewer':'/root',
        'proposer':'/root/retrieval_evidence','reviewed_on':'2026-10-12',
        'proposal_sha256':PROPOSAL_SHA,'manual_checksum':MANUAL_SHA,
        'index_id':review['index_id'],'original_pdf_pages':review['original_pdf_pages'],
        'approved_evidence_ids':sorted(review['bindings']),
        'new_source_objects':new_sources,
        'approved_scopes':['EXACT_SOURCE_CONTENT_FOR_TWO_PDF64_WARNING_OBJECTS',
                           'EXACT_FOUR_OBJECT_COMPONENT_CONTEXT_REFINEMENT'],
        'inspection':{'full_original_pages_visually_inspected':[18,64],
            'printed_labels':[16,62],'manual_and_index_hashes_checked':True,
            'raw_provenance_and_object_hashes_checked':True,
            'complete_table_headers_units_rows_and_approximation_preserved':True,
            'all_three_warning_paraphrases_checked_against_original_pages':True,
            'fuel_component_separated_from_unrelated_tyre_and_charger_context':True,
            'raw_plus_minus_glyph_valid_no_index_correction':True},
        'context_reason':'PDF18 places tyre tables and rim notes in the left column and the fuel specifications with their asterisk approximation in the right. PDF64 has the fuel warning above CHARGER PORT in the left column; USB warnings belong to the charger section. The four exact fuel objects retain both fuel warnings and the approximation. This refinement changes only their source-context closure; all other dependency scopes retain the frozen packages.',
        'human_signoff':False,'existing_161_approval_changed':False,
        'parent_text_authorized':False,'new_authored_action_authority':False,
        'excluded_scopes':review['excluded_scopes'],'provider_calls':0,
        'answer_quality_acceptance':False,'deployment_authorized':False}
    result['supersedes']={'review_path':'reports/build/20261012/source_context_refinement_v2/independent_review.json',
        'review_sha256':'1a48941c62bc7e614d2b598a87f3a93ec0e02bd270f269c0826eae70d894fd94',
        'reason':'The v2 draft embedded two descriptors decoded through Windows cp1252. The current scoped review cross-checks exact descriptor contents against original UTF-8 source authority. Raw source/index objects and reviewed page meaning are unchanged.'}
    target=folder/'independent_review_v3.json'
    if target.exists():raise RuntimeError('NEVER_OVERWRITE_COMPLETED_REVIEW')
    target.write_text(json.dumps(result,indent=2,ensure_ascii=True)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({'review_sha256':hashlib.sha256(target.read_bytes()).hexdigest(),
        'evidence_objects':len(review['bindings']),'new_source_content_objects':len(new_sources),
        'decision':result['decision']}))


if __name__=='__main__':main()
