"""Revalidate dynamic source closure and server-owned citations before delivery."""
from dataclasses import replace
from controller_contracts import ResponseType
from constrained_generator import ValidationFailure
from cloud.arm_a.rider_contract import saved_view as legacy_view
from cloud.grounded_generation.feedback import issue_choices

def saved_view(registry,session,response,authority,admitted):
    if 'GENERIC_GROUNDED_GENERATION_DETERMINISTIC_CHECKED' not in response.reason_codes:
        view,_=legacy_view(registry,session,response)
        choices,private=issue_choices(registry,session,response)
        view['choices']=choices;view['response']['reason_codes']=list(response.reason_codes)
        return view,private
    if not admitted or not registry.source_ready():raise ValidationFailure('PRESENTATION_SOURCE_CHANGED')
    if admitted['factual']:authority.validate(admitted['factual'])
    required=set(admitted['required_evidence_ids'])
    for sid,scope in admitted['scopes'].items():
        if not registry.step_ready(sid):raise ValidationFailure('PRESENTATION_ACTION_CHANGED')
        if set(scope['required_evidence_ids'])-required:raise ValidationFailure('PRESENTATION_ACTION_INCOMPLETE')
    expected={(e,p.get('page_no',p.get('pdf_page'))) for e in required for p in registry.evidence[e]['provenance']}
    actual={(c['evidence_id'],c['pdf_page']) for c in response.cited_pages}
    if expected!=actual or any(c.get('manual_checksum')!=registry.checksum or c.get('index_id')!=registry.index_id or
        c.get('pdf_page_index')!=c['pdf_page']-1 for c in response.cited_pages):
        raise ValidationFailure('PRESENTATION_CITATION_CHANGED')
    claims={c['claim_id']:c for c in response.claim_evidence_map}
    if len(claims)!=len(response.claim_evidence_map):raise ValidationFailure('PRESENTATION_CLAIM_ID')
    if any(claims.get(k)!=v for k,v in admitted['mandatory'].items()):
        raise ValidationFailure('MANDATORY_DISPLAY_CHANGED')
    for c in response.claim_evidence_map:
        if c['claim_id'] in admitted['mandatory']:continue
        if not c.get('evidence_ids') or not set(c['evidence_ids'])<=required or c.get('presentation_mode')!='GENERATED_PARAPHRASE':
            raise ValidationFailure('PRESENTATION_CLAIM_CHANGED')
    if response.natural_language!=' '.join(c['text'] for c in response.claim_evidence_map):
        raise ValidationFailure('PRESENTATION_TEXT_CHANGED')
    choices,private=issue_choices(registry,session,response)
    neutral=replace(response,type=ResponseType.UNSUPPORTED,claim_evidence_map=(),cited_pages=())
    view,_=legacy_view(registry,session,neutral)
    view.update(runtime_policy='generic-grounded-presentation-v5',choices=choices)
    view['response']={'type':'SUPPORTED','natural_language':response.natural_language,
        'technical_content':True,'release_gate_passed':True,'semantic_support_proven':False,
        'cited_pages':[dict(c) for c in response.cited_pages],'trace_id':response.trace_id,
        'claim_evidence_map':[dict(c) for c in response.claim_evidence_map],
        'reason_codes':list(response.reason_codes)}
    return view,private
