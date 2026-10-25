"""LOOPBACK ENGINEERING FIXTURE. No retrieval, provider, or motorcycle advice."""
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from rider_ui.client import MANUAL_SHA, INDEX_ID

BASE={'schema_version':'motomedic-rider-api-v1','manual_checksum':MANUAL_SHA,'index_id':INDEX_ID}
operations={}
sessions={}
requests=[]
class Handler(BaseHTTPRequestHandler):
    fail_next_response=False
    def log_message(self,*args): pass
    def reply(self, data, status=200):
        stream=status==200 and self.command=='POST' and 'text/event-stream' in self.headers.get('Accept','')
        raw=(('event: complete\ndata: '+json.dumps(data)+'\n\n').encode() if stream else json.dumps(data).encode())
        self.send_response(status);self.send_header('Content-Type','text/event-stream' if stream else 'application/json')
        self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        if self.headers.get('Authorization')!='Bearer ui-test-only':
            self.reply({},401);return
        if self.path=='/v1/catalogue':
            self.reply({**BASE,'question_input':'open'});return
        if self.path.startswith('/v1/operations/'):
            v=operations.get(self.path.rsplit('/',1)[1]);self.reply(v or {},200 if v else 404);return
        v=sessions.get(self.path.rsplit('/',1)[1]);self.reply(v or {},200 if v else 404)
    def do_POST(self):
        if self.headers.get('Authorization')!='Bearer ui-test-only':
            self.reply({},401);return
        raw=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
        op=self.headers.get('Idempotency-Key')
        requests.append({'path':self.path,'operation_id':op,'payload':raw})
        if op in operations: self.reply(operations[op]);return
        v={**BASE,'session_id':'f'*32,'version':1,'history':[],
           'response':{'type':'AMBIGUOUS','natural_language':'Engineering fixture: confirm this test observation?',
                       'technical_content':False,'cited_pages':[],'trace_id':'ui-fixture-response'},
           'choices':[]}
        sessions[v['session_id']]=v;operations[op]=v
        if Handler.fail_next_response:
            Handler.fail_next_response=False;self.reply({},500)
        else:
            self.reply(v)

def serve(port=8766):
    return ThreadingHTTPServer(('127.0.0.1',port),Handler)
if __name__=='__main__': serve().serve_forever()

