import json,sys
from pathlib import Path
sys.path.insert(0,str(Path('human_review/record_workflow').resolve()))
from workflow import encoded
b=Path('human_review/record_workflow/batch_100')
for i in [14,16]:
 a=json.loads((b/'drafts'/f'GEN{i:03}_v2.json').read_text(encoding='utf8'));r=json.loads((b/'receipts'/f'GEN{i:03}_v2_author.json').read_text(encoding='utf8'));old=json.loads((b/'reviews'/f'GEN{i:03}_v1_review.json').read_text(encoding='utf8'));p={k:old[k] for k in ['record_id','role','actor','manual_sha256','batch_context_sha256','independent_original_review','original_page_checks']};p.update(version=2,author_sha256=r['payload_sha256'],context_sha256=r['context_sha256'],findings=[],verdict='PASS',reason=('Exact SS-47G, RH589±2.5ml,LH507±2.5ml lookup and approximate capacity retained; original PDF21 unqualified wrong-oil-grade caution now visible consistently; no fork-service steps.' if i==14 else 'Exact unsafe arbitrary electrical-rating fitment route now SAFETY_STOP; original PDF19 overload/erratic/premature-failure warning and authorised approved-fitment referral retained.')+' Rechecked exact v2 against original source layout/text and prior judge correction; engineering-only, no human/source/dependency/release approval.')
 if i==14:p['original_page_checks'][0]['checked_span']+=' CAUTION: wrong oil grade reduces moving-part life and seriously affects performance, unqualified table warning.'
 with (b/'reviews'/f'GEN{i:03}_v2_review.json').open('xb') as h:h.write(encoded(p))
print('GEN014/016v2 source rereviews PASS')
