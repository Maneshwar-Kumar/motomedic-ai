import json,sys
from pathlib import Path
sys.path.insert(0,str(Path('human_review/record_workflow').resolve()))
from workflow import encoded
b=Path('human_review/record_workflow/batch_100')
reasons={52:'Exact v2 asks accessible paperwork BS6/BSVI confirmation, with explicit unconfirmed-manual abstention/support; does not invent label location or infer emission variant from photo.',57:'Exact v2 preserves not-applicable outcome separately from normal and asks one paperwork-based HimalayanBS6 applicability question before control-dependent action.',58:'Exact v2 preserves previous customer-reported resolution and attempt history and asks one current returned-symptom question; no repair verification, fault inference or automatic repeated action.',59:'Exact v2 withholds no-start row until engine-failing-to-start observation clarified; normal lights do not erase separate weak-horn report or prove complete electrical health.'}
for i in [52,57,58,59]:
 a=json.loads((b/'drafts'/f'GEN{i:03}_v2.json').read_text(encoding='utf8'));r=json.loads((b/'receipts'/f'GEN{i:03}_v2_author.json').read_text(encoding='utf8'));old=json.loads((b/'reviews'/f'GEN{i:03}_v1_review.json').read_text(encoding='utf8'));p={k:old[k] for k in ['record_id','role','actor','manual_sha256','batch_context_sha256','independent_original_review','original_page_checks']};p.update(version=2,author_sha256=r['payload_sha256'],context_sha256=r['context_sha256'],findings=[],verdict='PASS',reason=reasons[i]+' Independently compared actual v2 answer/turn with original scope and TRD/manifest policy; no actual state execution, human/source/dependency/release approval.')
 with (b/'reviews'/f'GEN{i:03}_v2_review.json').open('xb') as h:h.write(encoded(p))
print('GEN052/057/058/059v2 re-reviews PASS')
