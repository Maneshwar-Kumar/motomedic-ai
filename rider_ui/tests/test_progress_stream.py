"""Private synthetic progress/delivery checks; no provider or manual correctness claim."""
import copy
import unittest
from rider_ui.client import APIError
from rider_ui.verified_sse import read_verified_stream,response_hash,PROGRESS_LABELS
from rider_ui.tests.test_client import view
from rider_ui.tests.test_verified_sse import frame

OP='c'*32

def accepted_frames(v,key=OP,stages=('retrieving','drafting','verifying','displaying')):
    digest=response_hash(v);text=v['response']['natural_language']
    v['delivery']={'operation_id':key,'response_sha256':digest,'runtime_lock':'e'*64,
        'manual_checksum':v['manual_checksum'],'index_id':v['index_id']}
    frames=[frame('progress',{'operation_id':key,'stage':stage}) for stage in stages]
    frames.append(frame('verified_block',{'view':v,'operation_id':key,'response_sha256':digest}))
    offset=0
    for part in (text[:5],text[5:]):
        if part:
            frames.append(frame('answer_chunk',{'operation_id':key,'response_sha256':digest,'offset':offset,'text':part}))
            offset+=len(part)
    return frames+[frame('complete',v)]

class ProgressStreamTests(unittest.TestCase):
    def test_prompt_progress_has_zero_answer_leakage_until_accepted(self):
        v=view();v['response']['natural_language']='Synthetic accepted text: café.'
        received=[];stages=[];chunks=[]
        frames=accepted_frames(v)
        def source():
            for data in frames[:4]:
                yield data
                self.assertEqual(received,[]);self.assertEqual(chunks,[])
            yield frames[4]
            self.assertEqual(received,[v]);self.assertEqual(chunks,[])
            yield from frames[5:]
        result=read_verified_stream(source(),received.append,operation_id=OP,on_progress=stages.append,on_chunk=chunks.append)
        self.assertEqual(result,v)
        self.assertEqual(stages,list(PROGRESS_LABELS))
        self.assertEqual(''.join(chunks),v['response']['natural_language'])

    def test_byte_splits_preserve_accepted_streamed_recovered_equality(self):
        v=view();v['response']['natural_language']='Synthetic — café exact text.'
        raw=b''.join(accepted_frames(v));chunks=[]
        result=read_verified_stream((raw[i:i+1] for i in range(len(raw))),operation_id=OP,on_chunk=chunks.append)
        recovered=copy.deepcopy(v)
        self.assertEqual(result,recovered)
        self.assertEqual(''.join(chunks),recovered['response']['natural_language'])
        self.assertEqual(response_hash(result),response_hash(recovered))

    def test_private_text_and_unbound_progress_rejected_before_callbacks(self):
        for data in ({'operation_id':OP,'stage':'drafting','text':'private draft'},
                     {'operation_id':'d'*32,'stage':'drafting'},
                     {'operation_id':OP,'stage':'99 percent complete'},
                     {'operation_id':OP,'stage':'verifying','confidence':1}):
            seen=[]
            with self.assertRaises(APIError):
                read_verified_stream([frame('progress',data)],operation_id=OP,on_progress=seen.append)
            self.assertEqual(seen,[])
        with self.assertRaises(APIError):
            read_verified_stream([frame('answer_chunk',{'operation_id':OP,'response_sha256':'0'*64,'offset':0,'text':'unchecked'})],operation_id=OP)

    def test_wrong_hash_offset_content_or_operation_never_displays_bad_slice(self):
        v=view();base=accepted_frames(v)
        for change in ({'response_sha256':'0'*64},{'offset':1},{'text':'Changed advice.'},{'operation_id':'d'*32}):
            seen=[]
            import json
            data=json.loads(base[5].decode().split('data: ')[1])
            data.update(change)
            with self.assertRaises(APIError):
                read_verified_stream(base[:5]+[frame('answer_chunk',data)],operation_id=OP,on_chunk=seen.append)
            self.assertEqual(seen,[])

    def test_revised_draft_progress_allowed_without_private_answer_tokens(self):
        v=view();stages=[]
        sequence=('retrieving','drafting','verifying','drafting','verifying','displaying')
        self.assertEqual(read_verified_stream(accepted_frames(v,stages=sequence),operation_id=OP,on_progress=stages.append),v)
        self.assertEqual(stages,list(sequence))

    def test_accepted_view_hash_and_terminal_full_text_checked(self):
        v=view();frames=accepted_frames(v);received=[]
        import json
        data=json.loads(frames[4].decode().split('data: ')[1]);data['response_sha256']='0'*64
        with self.assertRaises(APIError):
            read_verified_stream(frames[:4]+[frame('verified_block',data)],received.append,operation_id=OP)
        self.assertEqual(received,[])
        with self.assertRaises(APIError):
            read_verified_stream(frames[:5]+[frames[-1]],operation_id=OP)
        changed=copy.deepcopy(v);changed['response']['natural_language']='Changed recovery.'
        with self.assertRaises(APIError):
            read_verified_stream(frames[:-1]+[frame('complete',changed)],operation_id=OP)

    def test_disconnect_retains_complete_accepted_view_for_operation_recovery(self):
        v=view();received=[];parts=[]
        with self.assertRaises(APIError):
            read_verified_stream(accepted_frames(v)[:6],received.append,operation_id=OP,on_chunk=parts.append)
        self.assertEqual(received,[v])
        self.assertEqual(''.join(parts),v['response']['natural_language'][:5])

    def test_migration_old_technical_units_cannot_bypass_production_envelope(self):
        v=view();seen=[]
        with self.assertRaises(APIError):
            read_verified_stream([frame('verified_block',{'view':v}),frame('complete',v)],seen.append,operation_id=OP)
        self.assertEqual(seen,[])

    def test_all_verified_nonerror_routes_may_stream_without_answer_catalogue(self):
        for route in ('SUPPORTED','AMBIGUOUS','UNSUPPORTED','SAFETY_STOP'):
            v=view();v['response']['type']=route
            v['response']['technical_content']=route in ('SUPPORTED','SAFETY_STOP')
            if not v['response']['technical_content']:v['response']['cited_pages']=[]
            self.assertEqual(read_verified_stream(accepted_frames(v),operation_id=OP)['response']['type'],route)

    def test_json_recovery_requires_unchanged_bound_response_and_operation(self):
        import json
        from rider_ui.client import RiderAPI,validate_view
        from rider_ui.tests.test_client import Transport
        v=view();accepted_frames(v)
        for patch in ({'response_sha256':'0'*64},{'runtime_lock':'bad'},
                      {'manual_checksum':'other'},{'index_id':'other'},{'operation_id':123}):
            changed=copy.deepcopy(v);changed['delivery'].update(patch)
            with self.assertRaises(APIError):validate_view(changed)
        changed=copy.deepcopy(v);changed['response']['natural_language']='Changed saved response.'
        with self.assertRaises(APIError):validate_view(changed)
        api=RiderAPI('https://example.com','synthetic-test')
        api.opener=Transport(result=json.dumps(v).encode())
        self.assertEqual(api.recover_operation(OP),v)
        with self.assertRaises(APIError):api.recover_operation('d'*32)

    def test_persisted_verification_receipt_metadata_is_bound(self):
        import hashlib
        from rider_ui.client import validate_view
        v=view();accepted_frames(v)
        v['delivery'].update(evidence_payload_sha256='1'*64,verification_binding_sha256='2'*64)
        v['verified_delivery']={'operation_id':OP,'runtime_lock':'e'*64,'manual_checksum':v['manual_checksum'],
            'index_id':v['index_id'],'presentation_sha256':response_hash(v),'evidence_payload_sha256':'1'*64,
            'binding_sha256':'2'*64,'text_sha256':hashlib.sha256(v['response']['natural_language'].encode()).hexdigest()}
        self.assertEqual(validate_view(v),v)
        for key in v['verified_delivery']:
            changed=copy.deepcopy(v);changed['verified_delivery'][key]='changed'
            with self.assertRaises(APIError):validate_view(changed)
        changed=copy.deepcopy(v);changed['delivery']['verification_binding_sha256']='invalid'
        with self.assertRaises(APIError):validate_view(changed)

    def test_fixed_fallback_is_neutral_complete_only_with_no_verified_label_or_chunks(self):
        v=view();v['response'].update(type='UNSUPPORTED',technical_content=False,release_gate_passed=False,cited_pages=[])
        v['response']['natural_language']='I couldn’t find relevant information in the selected manual to answer your question. Please contact Royal Enfield or an authorised service centre.'
        v['escalation_uri']='mailto:support@royalenfield.com'
        received=[];parts=[];stages=[]
        frames=[frame('progress',{'operation_id':OP,'stage':stage}) for stage in ('retrieving','drafting','verifying')]+[frame('complete',v)]
        result=read_verified_stream(frames,received.append,operation_id=OP,on_chunk=parts.append,on_progress=stages.append)
        self.assertEqual(result,v);self.assertEqual(received,[]);self.assertEqual(parts,[])
        self.assertNotIn('displaying',stages)

    def test_uncommitted_error_uses_fixed_check_error_copy(self):
        from rider_ui.client import CHECK_ERROR_COPY
        with self.assertRaises(APIError) as raised:
            read_verified_stream([frame('error',{'type':'SYSTEM_ERROR','error':'OPERATION_NOT_COMMITTED','operation_id':OP})],operation_id=OP)
        self.assertEqual(str(raised.exception),CHECK_ERROR_COPY)

    def test_failure_progress_then_system_error_releases_no_technical_text(self):
        v=view();v['response'].update(type='SYSTEM_ERROR',technical_content=False,release_gate_passed=False,cited_pages=[])
        seen=[];parts=[]
        result=read_verified_stream([frame('progress',{'operation_id':OP,'stage':'verifying'}),frame('complete',v)],seen.append,operation_id=OP,on_chunk=parts.append)
        self.assertEqual(result['response']['type'],'SYSTEM_ERROR')
        self.assertEqual(seen,[]);self.assertEqual(parts,[])

if __name__=='__main__':unittest.main()
