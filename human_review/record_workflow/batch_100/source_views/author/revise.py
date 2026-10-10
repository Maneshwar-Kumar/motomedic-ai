from pathlib import Path
import sys,json,hashlib
ROOT=Path(__file__).resolve().parents[5]
sys.path.insert(0,str(ROOT/'human_review/record_workflow'))
import workflow
HOME=ROOT/'human_review/record_workflow/batch_100'
def revision(rid,answer,changes,dispositions,extra=None):
    old=sorted((HOME/'drafts').glob(rid+'_v*.json'))[-1]
    p=json.loads(old.read_bytes()); v=p['version']
    judge=json.loads((HOME/'receipts'/f'{rid}_v{v}_judge.json').read_bytes())
    author=json.loads((HOME/'receipts'/f'{rid}_v{v}_author.json').read_bytes())
    assert judge['verdict']=='NEEDS_REVISION' and v<4
    p.update(version=v+1,answer=answer,previous_author_sha256=author['payload_sha256'],feedback_judgment_sha256=judge['payload_sha256'],changes=changes,feedback_disposition=dispositions)
    p['turns'][1]['text']=answer
    if extra:p.update(extra)
    dst=HOME/'drafts'/f'{rid}_v{v+1}.json'
    with dst.open('xb') as f:f.write(workflow.encoded(p))
    print(dst.name,hashlib.sha256(dst.read_bytes()).hexdigest())
if __name__=='__main__':
    revision('GEN008','No. The listed 17.0 L tank capacity is approximate; actual filling capacity varies. If refuelling, first turn the engine and handheld electronic devices OFF, use a well-ventilated area with no smoking, flames or sparks, and open the cap slowly. Gasoline vapour is highly explosive. Fill only to the bottom of the anti-splash plate to leave expansion space; overfilling can damage the evaporative-emission system. Avoid spills on painted surfaces and wipe any spill off immediately to prevent a permanent stain.',['Added source-backed compact refuelling setup and explosive-vapour/spill cautions to the actual answer and assistant turn; retained approximate-capacity distinction.'],{'GEN008-F1':'ACCEPTED and implemented in visible answer/turn against original PDF8/27; metadata alone is insufficient for a filling instruction.'})
