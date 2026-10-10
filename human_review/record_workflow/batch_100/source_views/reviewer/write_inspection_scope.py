from pathlib import Path
import json
p=Path('human_review/record_workflow/batch_100');pages={}
for f in sorted((p/'reviews').glob('GEN*_review.json')):
 x=json.loads(f.read_text(encoding='utf8'))
 for z in x['original_page_checks']:pages[z['pdf_page']]=z['printed_page']
lines=['# Independent reviewer inspection scope','', 'Actor: batch100-source-reviewer. Original manual SHA-256 cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89 verified against actual PDF bytes.', '', 'Original-page text extraction covered149 pages as a locator; this is not exhaustive manual QA. Actual case source checks use the original PDF text plus independently rendered full-page layout/footers. Full-page montages are engineering-only. A MuPDF zlib warning occurred during the bulk locator extraction; subsequently cited source pages were readable in original text and render. No repaired text or missing-page fact was invented.', '', 'Synthetic policy fixtures refer to TRDv0.4 as product authority. Their manual pages are topic anchors, not OEM rules about caches, ranking, privacy, state storage, index corruption or model failures. These tests do not assert real outages occurred. Original manual absence, evidence assembly/review gaps and actual operational failure are separate.', '', 'The passing verdict assesses exact candidate wording and fixture route only. It never records human acceptance, formal source/rule/dependency approval, display rights or release.', '', '| Original PDF page | Actual printed label |','|---|---|']
lines += [f'|{i}|{pages[i]}|' for i in sorted(pages)]
lines += ['', 'Frozen exact review files preserve initial feedback and all revised checks. audit_review_bindings.py checks actual author receipt/context/manual bindings.']
out=p/'reviews/REVIEWER_INSPECTION_SCOPE.md'
with out.open('x',encoding='utf8') as h:h.write('\n'.join(lines)+'\n')
print('Reviewer scope inventory written for',len(pages),'cited pages')
