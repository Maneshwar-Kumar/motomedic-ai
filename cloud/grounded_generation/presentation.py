"""Server-owned citation presentation; free wording is not a semantic certificate."""
from cloud.arm_a.rider_contract import saved_view as legacy_view, issue_choices
from evidence_registry import content_hash
from controller_contracts import ResponseType

def saved_view(registry, session, response):
    if response.type!=ResponseType.SUPPORTED or not response.claim_evidence_map:
        return legacy_view(registry,session,response)
    if 'GROUNDED_GENERATION_DETERMINISTIC_CHECKED' not in response.reason_codes:
        return legacy_view(registry,session,response)
    sids=[code[6:] for code in response.reason_codes if code.startswith('scope:')]
    if not sids or len(sids)!=len(set(sids)) or not registry.source_ready(): raise ValueError('SOURCE_BINDING')
    required=set()
    mandatory={}
    for sid in sids:
        if not registry.step_ready(sid): raise ValueError('SCOPE_BINDING')
        step=registry.step(sid)
        required.update(step.required_evidence_ids)
        mandatory.update({c['claim_id']:c for c in step.claims if c['response_role'] in ('WARNING','PREREQUISITE') or not c['evidence_ids']})
    expected={(eid,p.get('page_no',p.get('pdf_page'))) for eid in required for p in registry.evidence[eid]['provenance']}
    actual={(c['evidence_id'],c['pdf_page']) for c in response.cited_pages}
    if expected!=actual or any(c.get('manual_checksum')!=registry.checksum or c.get('index_id')!=registry.index_id or
        c.get('pdf_page_index')!=c['pdf_page']-1 for c in response.cited_pages): raise ValueError('CITATION_BINDING')
    claim_ids=[c['claim_id'] for c in response.claim_evidence_map]
    if len(claim_ids)!=len(set(claim_ids)): raise ValueError('CLAIM_ID')
    claimed={c['claim_id']:c for c in response.claim_evidence_map}
    if any(claimed.get(key)!=value for key,value in mandatory.items()): raise ValueError('MANDATORY_DISPLAY_CHANGED')
    for c in response.claim_evidence_map:
        if c['claim_id'] in mandatory: continue
        if (not c.get('evidence_ids') or not set(c['evidence_ids'])<=required or
            c.get('presentation_mode')!='GENERATED_PARAPHRASE'): raise ValueError('CLAIM_BINDING')
    if response.natural_language!=' '.join(c['text'] for c in response.claim_evidence_map): raise ValueError('PRESENTATION_BINDING')
    choices,private=issue_choices(registry,session,response)
    from dataclasses import replace
    # Reuse history/retention adapter without claiming exact wording for new text.
    neutral=replace(response,type=ResponseType.UNSUPPORTED,claim_evidence_map=(),cited_pages=())
    view,_=legacy_view(registry,session,neutral)
    view.update(runtime_policy='grounded-generation-presentation-v1',choices=choices)
    view['response']={'type':'SUPPORTED','natural_language':response.natural_language,
        'technical_content':True,'release_gate_passed':True,
        'semantic_support_proven':False,'cited_pages':[dict(c) for c in response.cited_pages],
        'trace_id':response.trace_id}
    return view,private
