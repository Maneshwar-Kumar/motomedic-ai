"""Bounded progress and accepted-buffer SSE reader; private drafts never render.

Production mutation streams bind every event to their requested operation. The
legacy complete-unit mode is retained only for isolated engineering fixtures.
"""
import codecs
import hashlib
import json
from rider_ui.client import APIError, MAX_BYTES, validate_view, CHECK_ERROR_COPY

PROGRESS_LABELS={
    'retrieving':'Retrieving manual information.',
    'drafting':'Drafting your answer.',
    'verifying':'Checking the answer against the manual.',
    'displaying':'Displaying the verified answer.',
}

def response_hash(view):
    return hashlib.sha256(json.dumps(view['response'],sort_keys=True,
        separators=(',',':'),ensure_ascii=False,allow_nan=False).encode('utf-8')).hexdigest()

def read_verified_stream(chunks,on_verified=None,*,operation_id=None,on_progress=None,on_chunk=None,expected_policy=None):
    """Publish only an accepted whole view and slices of that exact saved text.

    A disconnect preserves the complete accepted view through on_verified;
    callers recover the same operation, never automatically repeat inference.
    Progress contains known stage IDs only, with no draft or source content.
    """
    decoder=codecs.getincrementaldecoder('utf-8')('strict')
    text,total,verified,complete='',0,None,None
    digest,streamed,displaying=None,'',False
    frames=0

    def fail(message='The service stream could not be verified. Retrieve the saved result.'):
        raise APIError(message)

    def bound(data,keys):
        if type(data) is not dict or set(data)!=keys or data.get('operation_id')!=operation_id:
            fail()

    def event(frame):
        nonlocal verified,complete,digest,streamed,displaying,frames
        fields={}
        for line in frame.splitlines():
            if not line or line.startswith(':'):continue
            name,separator,value=line.partition(':')
            if not separator or name not in ('event','data') or name in fields:fail()
            fields[name]=value.lstrip(' ')
        if not fields:return
        frames+=1
        if frames>300 or set(fields)!={'event','data'} or complete is not None:fail()
        try:data=json.loads(fields['data'])
        except (ValueError,RecursionError):fail()
        kind=fields['event']
        if kind=='progress':
            bound(data,{'operation_id','stage'})
            stage=data['stage']
            if type(stage) is not str or stage not in PROGRESS_LABELS or verified is not None:fail()
            if displaying:fail()
            displaying=stage=='displaying'
            if on_progress:on_progress(stage)
        elif kind=='verified_block':
            if verified is not None:fail()
            if operation_id is not None:
                bound(data,{'view','operation_id','response_sha256'})
                if not displaying:fail()
                verified=validate_view(data['view'],expected_policy=expected_policy)
                digest=response_hash(verified)
                if data['response_sha256']!=digest:fail()
            else:
                if type(data) is not dict or set(data)!={'view'}:fail()
                verified=validate_view(data['view'],expected_policy=expected_policy)
            response=verified['response']
            if operation_id is not None:
                if response['type']=='SYSTEM_ERROR' or response.get('release_gate_passed') is not True:
                    fail('The streamed answer has not passed the display gate.')
                binding=verified.get('delivery')
                if not binding or binding['operation_id']!=operation_id or binding['response_sha256']!=digest:fail()
            elif (response['type'] not in {'SUPPORTED','SAFETY_STOP'} or
                    response.get('release_gate_passed') is not True or
                    response.get('technical_content') is not True):
                fail('The streamed answer has not passed the display gate.')
            if on_verified:on_verified(verified)
        elif kind=='answer_chunk':
            bound(data,{'operation_id','response_sha256','offset','text'})
            if (verified is None or digest is None or data['response_sha256']!=digest or
                    type(data['offset']) is not int or data['offset']!=len(streamed) or
                    type(data['text']) is not str or not data['text']):fail()
            accepted=verified['response']['natural_language']
            if accepted[len(streamed):len(streamed)+len(data['text'])]!=data['text']:fail()
            streamed+=data['text']
            if on_chunk:on_chunk(data['text'])
        elif kind=='complete':
            complete=validate_view(data,expected_policy=expected_policy)
            if verified is not None:
                if verified!=complete:fail('The service stream changed. Retrieve the saved result.')
                if operation_id is not None and (response_hash(complete)!=digest or
                        streamed!=complete['response']['natural_language']):fail()
            response=complete['response']
            if (response['type'] in {'SUPPORTED','SAFETY_STOP'} and
                    response.get('technical_content') is True and verified is None):
                fail('The service did not deliver a verified answer unit.')
        elif kind=='error':
            fail(CHECK_ERROR_COPY)
        else:fail('The service returned an unsupported stream event.')

    try:
        for chunk in chunks:
            if type(chunk) is not bytes or not chunk:fail('The service stream was interrupted. Retrieve the saved result.')
            total+=len(chunk)
            if total>MAX_BYTES:fail('The service stream exceeded the display limit.')
            text=(text+decoder.decode(chunk)).replace('\r\n','\n')
            while '\n\n' in text:
                frame,text=text.split('\n\n',1);event(frame)
        text+=decoder.decode(b'',final=True)
    except UnicodeError:fail('The service stream was interrupted. Retrieve the saved result.')
    if text.strip() or complete is None:fail('The service stream was interrupted. Retrieve the saved result.')
    return complete
