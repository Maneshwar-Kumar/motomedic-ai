"""Compare an immutable runtime freeze to Git HEAD and the actual checkout."""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def check(path):
    manifest=json.loads(path.read_bytes());bindings=manifest['file_sha256'];names=list(bindings)
    result=subprocess.run(['git','cat-file','--batch'],input=''.join('HEAD:'+n+'\n'for n in names).encode(),
        capture_output=True,check=True,cwd=ROOT)
    wire=result.stdout;offset=0;errors=[]
    for name in names:
        end=wire.index(b'\n',offset);header=wire[offset:end].split();offset=end+1
        if header[-1]==b'missing':errors.append({'path':name,'error':'NOT_COMMITTED'});continue
        size=int(header[2]);body=wire[offset:offset+size];offset+=size+1
        if header[1]!=b'blob' or hashlib.sha256(body).hexdigest()!=bindings[name]:
            errors.append({'path':name,'error':'COMMITTED_BYTES_DIFFER_FROM_FREEZE'})
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=bindings[name]:
            errors.append({'path':name,'error':'CHECKOUT_BYTES_DIFFER_FROM_FREEZE'})
    return {'schema_version':'frozen-git-checkout-binding-v1','files':len(names),'ok':not errors,'errors':errors}
if __name__=='__main__':
    result=check(ROOT/sys.argv[1]);print(json.dumps(result,indent=2));sys.exit(0 if result['ok'] else 1)
