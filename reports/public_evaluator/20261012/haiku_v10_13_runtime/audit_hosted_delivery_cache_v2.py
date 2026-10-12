"""Read-only audit of actual hosted delivery/cache receipts; never calls providers.

This consumer proves consistency of saved metadata and recorded transport checks.
It does not independently adjudicate source truth or assert deployment acceptance.
"""
import argparse
from datetime import datetime,timezone
import hashlib,json,re,sys
from pathlib import Path

MODEL='claude-haiku-5-5'
POLICY='open-manual-haiku-draft-verify-v10_13'
ROUTE='HAIKU_DRAFT_HAIKU_VERIFY'
SHA=re.compile(r'[0-9a-f]{64}')
OP=re.compile(r'[0-9a-f]{32}')
ROLES=('private_draft','semantic_verifier')
REPORT_ROOT=Path(__file__).resolve().parent
REPO_ROOT=REPORT_ROOT.parents[3]
sys.path.insert(0,str(REPO_ROOT))

def wire(value):
    return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False,allow_nan=False).encode()

def digest(value):return hashlib.sha256(wire(value)).hexdigest()

def unique(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('DUPLICATE_JSON_KEY')
        result[key]=value
    return result

def read(path):
    raw=Path(path).read_bytes()
    return json.loads(raw.decode('utf-8-sig'),object_pairs_hook=unique,
        parse_constant=lambda _:(_ for _ in ()).throw(ValueError('NONFINITE_JSON'))),hashlib.sha256(raw).hexdigest()

def frozen_token_policy(release):
    """Import only the source-bound read-only grant consumer and dependencies."""
    names=('cloud/grounded_generation/token_ceiling.py',
           'cloud/grounded_generation/claude_budget.py','evidence_registry.py','generation_providers.py')
    bindings=release.get('file_sha256') or {}
    for name in names:
        expected=bindings.get(name)
        if not (type(expected)is str and SHA.fullmatch(expected)) or hashlib.sha256((REPO_ROOT/name).read_bytes()).hexdigest()!=expected:
            raise ValueError('FROZEN_TOKEN_POLICY_SOURCE_CHANGED')
    from cloud.grounded_generation.token_ceiling import resolve_token_ceiling,GRANT_DOCUMENT
    return resolve_token_ceiling,GRANT_DOCUMENT


def audit_ledgers(before,after,release,*,manifest_sha,runtime_lock):
    errors=[]
    def require(ok,code):
        if not ok:errors.append(code)
    result={'passed':False,'errors':errors,'new_event_scopes_checked':0,
            'new_events_without_scope_fields':0,'event_readback_present':False}
    if type(before)is not dict or type(after)is not dict:
        errors.append('PERMANENT_LEDGER_READBACK_MISSING');return result
    try:resolve,grant_id=frozen_token_policy(release)
    except (OSError,ValueError,ImportError):
        errors.append('FROZEN_TOKEN_POLICY_SOURCE_CHANGED');return result
    primary='grounded-primary-nonrecurring-v1'
    money='owner-haiku-fallback-20261011-validation-v1'
    for name,version,limits,charges in (
        (primary,'whole-turn-capacity-v1',{'maximum_attempts':100},('reserved_attempts','reserved_tokens')),
        (money,'claude-fallback-nonrecurring-one-dollar-v1',{'maximum_nanodollars':1000000000},('reserved_nanodollars','reservation_count'))):
        prior,current=before.get(name) or {},after.get(name) or {}
        require(type(prior)is dict and type(current)is dict,'PERMANENT_LEDGER_SCHEMA_INVALID')
        if type(prior)is not dict or type(current)is not dict:continue
        require(prior.get('version')==current.get('version')==version,'PERMANENT_LEDGER_VERSION_CHANGED')
        for key,value in limits.items():
            require(type(prior.get(key))is int and type(current.get(key))is int and prior[key]==current[key]==value,'PERMANENT_LEDGER_LIMIT_CHANGED')
        for key in charges:
            require(type(prior.get(key))is int and type(current.get(key))is int and current[key]>=prior[key]>=0,'PERMANENT_CHARGES_RESET_OR_INVALID')
    try:
        prior_cap,prior_binding=resolve(before.get(primary),before.get(grant_id))
        cap,binding=resolve(after.get(primary),after.get(grant_id))
    except Exception:
        errors.append('PRIMARY_TOKEN_GRANT_INVALID');return result
    require(prior_cap==cap and prior_binding==binding,'PRIMARY_TOKEN_AUTHORITY_CHANGED_DURING_RUN')
    require(before.get(grant_id)==after.get(grant_id),'EXACT_PRIMARY_GRANT_CHANGED_DURING_RUN')
    grant=after.get(grant_id)
    if grant is not None:
        require(grant['measured']['serving_manifest_sha256']==manifest_sha and
                grant['measured']['runtime_lock']==runtime_lock,'PRIMARY_GRANT_MEASURED_RUNTIME_CHANGED')
    result.update(primary_token_ceiling=cap,token_ceiling_authorization=binding,
                  grant_sha256=digest(grant) if grant is not None else None)
    for state in (before,after):
        p=state.get(primary) or {};m=state.get(money) or {}
        for name,value,limit in (('reserved_attempts',p.get('reserved_attempts'),100),
                               ('reserved_tokens',p.get('reserved_tokens'),cap),
                               ('reserved_nanodollars',m.get('reserved_nanodollars'),1000000000)):
            require(type(value)is int and 0<=value<=limit,'PERMANENT_CHARGE_EXCEEDS_BOUND_'+name.upper())
    event_id='grounded-provider-global-v1'
    if event_id in before or event_id in after:
        result['event_readback_present']=True
        prior_doc,current_doc=before.get(event_id) or {},after.get(event_id) or {}
        prior=prior_doc.get('events',[]) if type(prior_doc)is dict else None
        current=current_doc.get('events',[]) if type(current_doc)is dict else None
        require(type(prior)is list and type(current)is list and all(type(e)is dict for e in (prior or [])+(current or [])),'PERMIT_EVENT_READBACK_INVALID')
        if type(prior)is list and type(current)is list and all(type(e)is dict for e in prior+current):
            def identity(e):return digest({key:e.get(key) for key in ('operation_id','slot','phase','phase_nonce','plan_sha256')})
            old={identity(e) for e in prior}
            for event in current:
                if identity(event) in old:continue
                if 'primary_token_ceiling' not in event and 'token_ceiling_scope_sha256' not in event:
                    result['new_events_without_scope_fields']+=1;continue
                result['new_event_scopes_checked']+=1
                require(type(event.get('primary_token_ceiling'))is int and event['primary_token_ceiling']==cap and
                        event.get('token_ceiling_scope_sha256')==(binding['scope_sha256'] if binding else None),
                        'NEW_PERMIT_EVENT_TOKEN_AUTHORITY_CHANGED')
    result['passed']=not errors
    return result


def audit_reservation_scope(row,ledger_proof):
    """Join each operation reservation to the unchanged durable token authority."""
    reservation=(row.get('saved_view') or {}).get('runtime_controls',{}).get('composition',{}).get('whole_turn_reservation') or {}
    if not reservation:return ['V13_WHOLE_TURN_SCOPE_RECEIPT_MISSING']
    if (type(reservation.get('primary_token_ceiling'))is not int or
            reservation['primary_token_ceiling']!=ledger_proof.get('primary_token_ceiling') or
            reservation.get('token_ceiling_authorization')!=ledger_proof.get('token_ceiling_authorization')):
        return ['OPERATION_RESERVATION_TOKEN_AUTHORITY_CHANGED']
    return []


def audit_case(row,release,receipt):
    errors=[]
    def require(ok,code):
        if not ok:errors.append(code)
    case=row.get('case_id','UNKNOWN')
    view=row.get('saved_view') or {}
    response=view.get('response') or {}
    composition=view.get('runtime_controls',{}).get('composition') or {}
    delivery=view.get('delivery') or {}
    verified=view.get('verified_delivery') or {}
    operation=row.get('operation_id')
    require(type(operation)is str and OP.fullmatch(operation),'OPERATION_ID_INVALID')
    require(row.get('status')=='SAVED_STREAMED_RECOVERED' and not row.get('error'),'HOSTED_CASE_INCOMPLETE')
    require(row.get('post_retries')==0 and row.get('inference_replayed') is False,'PAID_REPLAY_NOT_EXCLUDED')
    require(view.get('runtime_policy')==POLICY,'RUNTIME_POLICY_CHANGED')
    require(view.get('manual_checksum')==receipt.get('manual_checksum') and view.get('index_id')==receipt.get('index_id'),'SOURCE_INDEX_CHANGED')
    require(delivery.get('operation_id')==operation and delivery.get('runtime_lock')==receipt.get('runtime_lock'),'DELIVERY_OPERATION_RUNTIME_CHANGED')
    require(row.get('exact_saved_stream') is True and row.get('exact_recovered_view') is True,'RECORDED_SAVE_STREAM_RECOVERY_EQUALITY_MISSING')
    presentation=digest(response)
    require(row.get('response_sha256')==presentation and delivery.get('response_sha256')==presentation,'PRESENTATION_RESPONSE_HASH_CHANGED')
    require(row.get('route')==response.get('type'),'CASE_SAVED_ROUTE_CHANGED')
    attempts=composition.get('attempts',[])
    admitted_ids=sorted(view.get('runtime_controls',{}).get('source_admission',{}).get('admitted_evidence_ids',[]))
    calls=[]
    for index,attempt in enumerate(attempts):
        for field,role in (('draft_provider',ROLES[0]),('verification_provider',ROLES[1])):
            trace=attempt.get(field) or {}
            require(trace.get('model')==MODEL and trace.get('provider')=='anthropic' and trace.get('role')==role,'CURRENT_ROLE_PROVIDER_IDENTITY_CHANGED')
            require(trace.get('generation_calls')==1 and trace.get('retry_count')==0,'CURRENT_ROLE_NOT_SINGLE_GENERATION_CALL')
            require(trace.get('citable_evidence_ids_sha256')==digest(admitted_ids) and trace.get('citable_evidence_id_count')==len(admitted_ids),'EXACT_ADMITTED_ID_ENUM_BINDING_CHANGED')
            require(type(trace.get('native_role_schema_sha256'))is str and SHA.fullmatch(trace['native_role_schema_sha256']),'ACTUAL_NATIVE_ROLE_SCHEMA_HASH_MISSING')
            require(type(trace.get('role_schema_template_sha256'))is str and SHA.fullmatch(trace['role_schema_template_sha256']),'BASE_ROLE_SCHEMA_HASH_MISSING')
            prefix=trace.get('cached_prefix_sha256')
            require(type(prefix)is str and SHA.fullmatch(prefix),'ROLE_PREFIX_HASH_MISSING')
            for key in ('input_tokens_counted','input_tokens','output_tokens','uncached_input_tokens','cache_creation_input_tokens','cache_read_input_tokens'):
                require(type(trace.get(key))is int and trace[key]>=0,'ROLE_USAGE_INVALID_'+key.upper())
            if all(type(trace.get(k))is int for k in ('input_tokens','uncached_input_tokens','cache_creation_input_tokens','cache_read_input_tokens')):
                require(trace['input_tokens']==sum(trace[k] for k in ('uncached_input_tokens','cache_creation_input_tokens','cache_read_input_tokens')),'ROLE_FULL_INPUT_USAGE_INCONSISTENT')
            require(trace.get('provider_cache')=='EXPLICIT_POLICY_AND_EVIDENCE_PREFIX','ROLE_CACHE_POLICY_CHANGED')
            require(trace.get('cache_hit_observed')==(trace.get('cache_read_input_tokens',0)>0) and trace.get('cached_tokens')==trace.get('cache_read_input_tokens'),'ROLE_CACHE_READ_TRACE_INCONSISTENT')
            calls.append({'case_id':case,'attempt':index,'role':role,'prefix_sha256':prefix,
                'cache_creation_input_tokens':trace.get('cache_creation_input_tokens'),
                'cache_read_input_tokens':trace.get('cache_read_input_tokens'),
                'input_tokens_counted':trace.get('input_tokens_counted'),'input_tokens':trace.get('input_tokens')})
    require(composition.get('version')==POLICY,'COMPOSER_VERSION_CHANGED')
    require(composition.get('draft_model')==MODEL and composition.get('verifier_model')==MODEL,'COMPOSER_MODEL_CHANGED')
    require(composition.get('answer_cache')=='DISABLED' and composition.get('provider_prompt_cache')=='EXPLICIT_ROLE_PREFIX','CACHE_AUTHORITY_POLICY_CHANGED')
    require(composition.get('corrections') in (0,1) and len(attempts)<=2,'CORRECTION_BOUND_CHANGED')
    require(view.get('provider_calls')==composition.get('provider_calls')==composition.get('generation_calls')==len(calls),'RECORDED_CALL_TOTAL_CHANGED')
    plan=composition.get('model_routing') or {}
    pair=release['model_routing_contract']['roles'][ROUTE]
    require(plan.get('route')==ROUTE and plan.get('routing_contract_sha256')==digest(release['model_routing_contract']),'EXACT_ROLE_PLAN_CHANGED')
    require(plan.get('draft_model_contract_sha256')==digest(pair['draft']) and plan.get('verifier_contract_sha256')==digest(pair['verifier']),'EXACT_ROLE_CONTRACT_HASH_CHANGED')
    if response.get('release_gate_passed') is True:
        require(response.get('semantic_verification_passed') is True and response.get('semantic_support_proven') is False,'PROBABILISTIC_VERIFICATION_FLAGS_CHANGED')
        require(composition.get('verified_buffer_ready') is True,'ACCEPTED_BUFFER_NOT_READY')
        require(row.get('streamed_text')==response.get('natural_language'),'STREAMED_SAVED_TEXT_DIFFERS')
        text_sha=hashlib.sha256(response.get('natural_language','').encode()).hexdigest()
        require(verified.get('text_sha256')==text_sha,'FINALIZED_SAVED_TEXT_HASH_CHANGED')
        require(verified.get('response_sha256')==composition.get('accepted_response_sha256'),'ACCEPTED_FINALIZED_WIRE_HASH_CHANGED')
        require(verified.get('presentation_sha256')==presentation,'VERIFIED_PRESENTATION_HASH_CHANGED')
        binding=verified.get('binding_sha256')
        require(type(binding)is str and SHA.fullmatch(binding),'ACCEPTED_BINDING_HASH_INVALID')
        require(binding==composition.get('accepted_binding_sha256')==delivery.get('verification_binding_sha256')==(attempts[-1].get('binding_sha256') if attempts else None),'VERDICT_FINALIZED_SAVED_BINDING_CHANGED')
        require(verified.get('operation_id')==operation and verified.get('runtime_lock')==receipt.get('runtime_lock'),'VERIFIED_OPERATION_RUNTIME_CHANGED')
        require(verified.get('evidence_payload_sha256')==delivery.get('evidence_payload_sha256'),'VERIFIED_DELIVERY_EVIDENCE_CHANGED')
        require(verified.get('draft_model')==MODEL and verified.get('verifier_model')==MODEL and verified.get('model_route')==ROUTE,'VERIFIED_CALL_ROLE_IDENTITIES_CHANGED')
        require(verified.get('model_routing_contract_sha256')==digest(release['model_routing_contract']) and verified.get('role_plan_sha256')==digest(plan),'VERIFIED_ROLE_PLAN_HASH_CHANGED')
        require('displaying' in row.get('stream_stages',[]),'ACCEPTED_STREAM_DISPLAY_STAGE_MISSING')
    else:
        require(row.get('streamed_text')=='' and response.get('technical_content') is False,'NEUTRAL_ROUTE_RELEASED_TECHNICAL_CHUNKS')
        require(response.get('type')!='SYSTEM_ERROR','OPERATIONAL_ERROR_IS_NOT_ACCEPTANCE')
        require('displaying' not in row.get('stream_stages',[]),'NEUTRAL_ROUTE_DISPLAYED_ANSWER_STAGE')
    boundaries=row.get('completed_operation_checks')
    if boundaries:
        require(boundaries.get('duplicate_post_same_operation_and_request') is True and boundaries.get('duplicate_post_same_saved_view') is True,'COMPLETED_POST_REPLAY_CHANGED')
        require(boundaries.get('wrong_valid_visitor_get_status')==404,'OTHER_VALID_VISITOR_OWNERSHIP_NOT_404')
        require(boundaries.get('provider_reservations_unchanged') is True and boundaries.get('provider_calls')==0 and boundaries.get('new_operation_or_question_created') is False,'COMPLETED_BOUNDARIES_NEW_PROVIDER_WORK')
    return {'case_id':case,'passed':not errors,'errors':errors,'accepted':response.get('release_gate_passed') is True,
        'operation_id':operation,'text_sha256':verified.get('text_sha256'),
        'finalized_response_sha256':verified.get('response_sha256'),'presentation_response_sha256':presentation,
        'cache_calls':calls,'completed_boundary_receipt_present':bool(boundaries)}

def run(manifest_path,receipt_path):
    release,manifest_sha=read(manifest_path)
    receipt,receipt_sha=read(receipt_path)
    global_errors=[]
    def require(ok,code):
        if not ok:global_errors.append(code)
    routing=release.get('model_routing_contract') or {}
    require(set(routing.get('roles',{}))=={ROUTE},'HAIKU_ONLY_MANIFEST_REQUIRED')
    if global_errors:return {'schema':'motomedic-haiku-delivery-cache-audit-v2','passed':False,'errors':global_errors}
    require(receipt.get('schema')=='motomedic-hosted-original-page-evaluator-v1' and receipt.get('classification')=='HOSTED_REAL_PROVIDER_ENGINEERING_EVIDENCE_ONLY','REAL_HOSTED_RECEIPT_REQUIRED')
    inventory=receipt.get('client_input_inventory') or {}
    require(inventory.get('serving_manifest_sha256')==manifest_sha,'EXACT_MANIFEST_BINDING_CHANGED')
    require(inventory.get('model_routing_contract_sha256')==digest(routing) and inventory.get('model_routing_contract')==routing,'INVENTORY_ROLE_POLICY_CHANGED')
    require(receipt.get('allocation_reset') is False and receipt.get('allocation_refund') is False and receipt.get('post_retries')==0,'HISTORICAL_CHARGE_OR_RETRY_POLICY_CHANGED')
    require(receipt.get('planned_case_count')==receipt.get('case_count')==6 and receipt.get('stopped_early') is False,'SIX_CASE_RUN_INCOMPLETE')
    require(receipt.get('completed_operation_boundary_checks') is True,'COMPLETED_OWNERSHIP_BOUNDARIES_NOT_CHECKED')
    require(receipt.get('ledger_after_error') is None,'FINAL_LEDGER_READBACK_FAILED')
    before,after=receipt.get('ledger_before'),receipt.get('ledger_after')
    ledger_proof=audit_ledgers(before,after,release,manifest_sha=manifest_sha,runtime_lock=receipt.get('runtime_lock'))
    global_errors.extend(ledger_proof['errors'])
    health=receipt.get('health') or {}
    require(health.get('ready') is True and health.get('runtime_lock')==receipt.get('runtime_lock') and
        health.get('answer_provider')==health.get('verifier_provider')==MODEL and
        health.get('model_routing')==routing,'ACTUAL_BACKEND_HEALTH_ROLE_BINDING_CHANGED')
    case_rows=[]
    for case_id,expected_sha in (receipt.get('case_files') or {}).items():
        path=Path(receipt_path).parent/(case_id+'.json')
        require(re.fullmatch(r'[A-Z0-9_]{1,80}',case_id) is not None,'CASE_ID_PATH_INVALID')
        if not re.fullmatch(r'[A-Z0-9_]{1,80}',case_id):continue
        try:
            row,sha=read(path)
            require(sha==expected_sha,'CASE_FILE_HASH_CHANGED_'+case_id)
            require(row.get('case_id')==case_id,'CASE_FILE_ID_CHANGED_'+case_id)
            case_audit=audit_case(row,release,receipt)
            scope_errors=audit_reservation_scope(row,ledger_proof)
            case_audit['errors'].extend(scope_errors)
            case_audit['passed']=not case_audit['errors']
            case_rows.append(case_audit)
        except (OSError,ValueError,KeyError,TypeError):
            global_errors.append('CASE_FILE_UNREADABLE_OR_INVALID_'+case_id)
    # Numeric case suffixes record chronological order in the approved plan.
    # Cache proof may use any earlier role call, including sole correction pairs.
    calls=[call for row in sorted(case_rows,key=lambda row:int(row['case_id'].rsplit('_',1)[-1])) for call in row['cache_calls']]
    cache_proofs={}
    for role in ROLES:
        prior={};pairs=[]
        for call in calls:
            if call['role']!=role:continue
            prefix=call['prefix_sha256']
            if type(call['cache_read_input_tokens'])is int and call['cache_read_input_tokens']>0 and prefix in prior:
                pairs.append({'write':prior[prefix],'read':call})
            if type(call['cache_creation_input_tokens'])is int and call['cache_creation_input_tokens']>0:
                prior[prefix]=call
        cache_proofs[role]={'exact_role_prefix_creation_then_read_proven':bool(pairs),'pairs':pairs}
    passed=not global_errors and len(case_rows)==6 and all(row['passed'] for row in case_rows) and all(row['exact_role_prefix_creation_then_read_proven'] for row in cache_proofs.values()) and any(row['completed_boundary_receipt_present'] for row in case_rows)
    return {'schema':'motomedic-haiku-delivery-cache-audit-v2','recorded_utc':datetime.now(timezone.utc).isoformat(),
        'classification':'READONLY_ACTUAL_HOSTED_RECEIPT_AUDIT','passed':passed,'errors':global_errors,
        'serving_manifest_sha256':manifest_sha,'hosted_receipt_sha256':receipt_sha,'runtime_lock':receipt.get('runtime_lock'),
        'role_cache_proofs':cache_proofs,'permanent_ledger_proof':ledger_proof,'cases':case_rows,'provider_calls_by_auditor':0,'cloud_mutations':0,
        'source_factual_quality_acceptance':False,'public_browser_acceptance':False,
        'limits':['Exact stream/recovery/duplicate view equality is the hash-bound hosted client assertion; raw transport frames are not retained.',
            'Finalized wire hash and binding are scalar server records; the verifier prompt body is not independently reconstructed here.',
            'Completed-boundary no-call evidence uses the recorded unchanged reservation ledger assertion and idempotent response; per-provider request logs are not retained.',
            'A policy-only cache read with a changed evidence-prefix hash does not establish exact evidence-prefix reuse.',
            'Event scope checks cover supplied new event records only; standard hosted receipts omit the global event ledger. Every operation reservation scope is checked separately.']}

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--manifest',required=True)
    parser.add_argument('--receipt',required=True)
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    output=Path(args.output).resolve()
    if not output.is_relative_to(REPORT_ROOT):raise ValueError('AUDIT_OUTPUT_MUST_STAY_IN_RUNTIME_REPORT_FOLDER')
    result=run(args.manifest,args.receipt)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,indent=2,sort_keys=True,ensure_ascii=False,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps({'passed':result.get('passed'),'output':str(output),'provider_calls_by_auditor':0}))
    raise SystemExit(0 if result.get('passed') is True else 1)
