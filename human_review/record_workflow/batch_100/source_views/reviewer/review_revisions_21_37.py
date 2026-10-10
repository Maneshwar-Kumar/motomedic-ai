import json,sys
from pathlib import Path
sys.path.insert(0,str(Path('human_review/record_workflow').resolve()))
from workflow import encoded
b=Path('human_review/record_workflow/batch_100')
for i in [21,37]:
 a=json.loads((b/'drafts'/f'GEN{i:03}_v2.json').read_text(encoding='utf8'));r=json.loads((b/'receipts'/f'GEN{i:03}_v2_author.json').read_text(encoding='utf8'));old=json.loads((b/'reviews'/f'GEN{i:03}_v1_review.json').read_text(encoding='utf8'));p={k:old[k] for k in ['record_id','role','actor','manual_sha256','batch_context_sha256','independent_original_review','original_page_checks']};p.update(version=2,author_sha256=r['payload_sha256'],context_sha256=r['context_sha256'],findings=[],verdict='PASS',reason=('Exact splitter-use proposal now SAFETY_STOP with original PDF64 one-mobile/no-other-device charging WARNING preserved in answer/turn; no connector/current compatibility inference.' if i==21 else 'Exact owner-reset request now UNSUPPORTED; original PDF60 only authorised personnel after service rule and service referral retained, no workaround.')+' Independently rechecked corrected v2 plus immutable prior feedback against original page and TRD canonical route. Engineering-only; no source/human/release approval.')
 with (b/'reviews'/f'GEN{i:03}_v2_review.json').open('xb') as h:h.write(encoded(p))
print('GEN021/037v2 re-reviews PASS')
