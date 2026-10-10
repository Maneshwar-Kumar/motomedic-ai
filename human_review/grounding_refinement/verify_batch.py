"""Read-only producer-gate verification; hashes identify content, not human approval."""
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from human_review.record_workflow.workflow import Store

def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def load(path):
    return json.loads(Path(path).read_text(encoding='utf-8-sig'))

def verify(root=ROOT):
    root = Path(root).resolve()
    manifest_path = root/'human_review/record_workflow/batch_100_completion.json'
    m = load(manifest_path)
    assert m['status'] == 'COMPLETE_AGENT_LOOP' and m['all_terminal'] is True
    rows = m['records']
    assert len(rows) == 100 and {r['record_id'] for r in rows} == {f'GEN{i:03}' for i in range(1,101)}
    store = Store(root)
    events = store.ledger()
    for obj in (store.home/'objects').iterdir():
        if obj.is_file():
            store.object(obj.name)
    submissions = [e['payload'] for e in events if e['kind'] == 'SUBMISSION']
    audit = load(store.home/'batch_100/judgments/judge_closure_audit.json')
    audited = {r['record_id']: r for r in audit['records']}
    questions = set()
    for row in rows:
        rid, version = row['record_id'], row['version']
        assert version == max(s['version'] for s in submissions if s['record_id'] == rid)
        roles = {}
        for role, key in [('author','draft'),('reviewer','review'),('judge','judge')]:
            path = (root/row[key+'_path']).resolve()
            assert path.is_relative_to(store.home)
            digest = sha(path)
            assert digest == row[key+'_sha256']
            payload = load(path)
            assert (payload['record_id'], payload['version'], payload['role']) == (rid,version,role)
            assert payload['manual_sha256'].lower() == m['manual_sha256'].lower()
            assert payload['batch_context_sha256'] == m['batch_context_sha256']
            bindings = [s for s in submissions if s['record_id']==rid and s['version']==version and s['role']==role]
            assert len(bindings) == 1 and bindings[0]['payload_sha256'] == digest
            assert store.object(digest) == path.read_bytes()
            audit_key = 'author' if key=='draft' else key
            assert audited[rid][audit_key+'_sha256'] == digest
            roles[role] = payload
        a,r,j = (roles[k] for k in ('author','reviewer','judge'))
        assert len({a['actor'],r['actor'],j['actor']}) == 3
        assert r['author_sha256'] == j['author_sha256'] == row['draft_sha256']
        assert j['review_sha256'] == row['review_sha256']
        assert r['context_sha256'] == j['context_sha256'] == m['batch_context_sha256']
        assert r['independent_original_review'] is True and j['independent_original_review'] is True
        assert r['verdict']=='PASS' and j['verdict']==row['terminal_disposition']=='PASS_AGENT_REVIEW'
        assert not r['findings'] and not j['findings']
        required_pages = {x['pdf_page'] for x in a['source_refs']}
        for reviewer in (r,j):
            assert required_pages <= {x['pdf_page'] for x in reviewer['original_page_checks']}
        q = ' '.join(a['question'].casefold().split())
        assert q not in questions
        questions.add(q)
        for card in row['blocker_card_paths']:
            p = (root/card).resolve()
            assert p.is_relative_to(root/'human_review/blockers') and p.is_file()
        assert row['runtime_authorized'] is False and row['formal_source_approval']=='PENDING'
    assert sha(root/m['catalogue_path']) == m['catalogue_sha256']
    original_ids = load(root/'registry/candidate_registry.json')['steps']
    legacy = load(store.home/'inventory.json')['records']
    all_ids = set(original_ids)|{r['record_id'] for r in legacy}|{r['record_id'] for r in rows}
    assert len(all_ids)==161
    catalogue=(root/m['catalogue_path']).read_text(encoding='utf-8')
    assert all(rid in catalogue for rid in all_ids)
    for row in legacy:
        for key in ('draft','review','judgment'):
            assert sha(root/row[key+'_path']) == row[key+'_sha256']
    manual=load(root/'source_manifest.json')
    assert sha(root/manual['file']).lower()==m['manual_sha256'].lower()
    return {'gate_verified':True,'manifest_sha256':sha(manifest_path),
            'catalogue_sha256':m['catalogue_sha256'],'records':161,
            'ledger_events':len(events),'human_source_approval_inferred':False}

if __name__=='__main__':
    print(json.dumps(verify(),indent=2))
