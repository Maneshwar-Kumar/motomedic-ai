"""Structural document QA, explicitly distinct from rendered all-page inspection."""
from pathlib import Path
import hashlib,json,zipfile
from docx import Document
from lxml import etree
from tools.reconcile_draft_verify_stream_documents import NAMES,MAPS,OUT,FALLBACK_TEXT,SYSTEM_ERROR_TEXT

def main():
 records=[]
 for name in NAMES:
  path=Path(name);prior=OUT/'prior_documents'/name;doc=Document(path);old=Document(prior);skip=set(MAPS.get(name,{}))
  if name=='03_TRD_Architecture_Decision_Note.docx':skip.update({1,2});skip.update(i for i,p in enumerate(old.paragraphs) if p.style.name.startswith('Heading') and i>=3)
  if name=='04_To_Build_Evaluation_Decisions.docx':skip.update(i for i,p in enumerate(old.paragraphs) if p.text in ('Reconciliation change record 9 October 2026','Rider UI and safeguards reconciliation 11 October 2026'))
  retained=[p.text for i,p in enumerate(old.paragraphs) if i not in skip and p.text];missing=[p for p in retained if p not in [x.text for x in doc.paragraphs]]
  texts='\n'.join(p.text for p in doc.paragraphs)+'\n'+'\n'.join(c.text for t in doc.tables for r in t.rows for c in r.cells)
  required=['DRAFT','VERIFY','STREAM','separate','actual question','partial','operation ID','durable save','ACTION_COMPLETED_UNRESOLVED','SYSTEM_ERROR','No predefined question','private drafting tokens','at most one','not authorize new spending']
  required+=['RELEASE_COMPLETE','RELEASE_PARTIAL','SHOW_FALLBACK','RELEASE_CLARIFICATION','RELEASE_SAFETY_STOP','IRRELEVANT_ANSWER','MISSING_SUPPORT','CORRECTION_UNSUCCESSFUL',FALLBACK_TEXT,SYSTEM_ERROR_TEXT,'partial-answer limitation before verification','require no successful LLM','source_manifest.json','AMBIGUOUS','SAFETY_STOP','not a verified technical answer']
  absent=[x for x in required if x not in texts]
  with zipfile.ZipFile(path) as z:
   for n in z.namelist():
    if n.endswith('.xml'):etree.fromstring(z.read(n))
   media={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('word/media/')}
  with zipfile.ZipFile(prior) as z:oldmedia={n:hashlib.sha256(z.read(n)).hexdigest() for n in z.namelist() if n.startswith('word/media/')}
  result={'file':name,'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'prior_sha256':hashlib.sha256(prior.read_bytes()).hexdigest(),'unrelated_existing_nonempty_paragraphs_checked':len(retained),'missing_unrelated_paragraphs':missing,'missing_current_requirements':absent,'original_tables_preserved':len(doc.tables)==len(old.tables),'original_media_byte_identical':media==oldmedia,'ooxml_parse_ok':True,'structural_result':'PASS' if not missing and not absent and media==oldmedia else 'FAIL','visual_qa':'PENDING_MANAGED_RENDER_AND_ALL_PAGE_INSPECTION'}
  if name=='03_TRD_Architecture_Decision_Note.docx':result['historical_numeric_comparison_table_content_identical']=[[c.text for c in r.cells] for r in doc.tables[1].rows]==[[c.text for c in r.cells] for r in old.tables[1].rows]
  footer_text=' '.join(p.text for sec in doc.sections for footer in (sec.footer,sec.first_page_footer,sec.even_page_footer) for p in footer.paragraphs)
  result['current_footer_revision']=('TRD v0.6' in footer_text and 'DRAFT VERIFY STREAM' in footer_text and '09 OCTOBER 2026' not in footer_text and 'OWNER A B DECISION' not in footer_text)
  result['footer_page_fields_not_duplicated']=all(len(f._element.xpath('.//w:fldSimple'))+len(f._element.xpath('.//w:instrText'))==1 for sec in doc.sections for f in (sec.footer,sec.first_page_footer,sec.even_page_footer))
  result['all_table_rows_prevent_split']=all(bool(row._tr.xpath('./w:trPr/w:cantSplit')) for t in doc.tables for row in t.rows)
  result['historical_captions_keep_next']=all(p.paragraph_format.keep_with_next for p in doc.paragraphs if p.text.startswith('Historical flow illustration retained'))
  if not all(result[k] for k in ('current_footer_revision','footer_page_fields_not_duplicated','all_table_rows_prevent_split','historical_captions_keep_next')):result['structural_result']='FAIL'
  if name=='04_To_Build_Evaluation_Decisions.docx':
   result['g04_reference_restored']=any(p.text.startswith('G-04') for p in doc.paragraphs)
   result['obsolete_empty_page_breaks_removed']=not any(p._p.xpath('.//w:br[@w:type="page"]') for p in doc.paragraphs if not p.text)
   result['table_body_fonts_consistent']=all(len({run.font.size.pt for row in table.rows for c in row.cells for p in c.paragraphs for run in p.runs if run.font.size})<=1 for table in doc.tables)
   if not all(result[k] for k in ('g04_reference_restored','obsolete_empty_page_breaks_removed','table_body_fonts_consistent')):result['structural_result']='FAIL'
  if name=='03_TRD.docx':
   verdict=[r.cells[1].text for r in doc.tables[1].rows if r.cells[0].text=='VerificationVerdict']
   schema_fields=['binding_sha256','decision','question_coverage','per_claim_support','omissions','conflicts','coverage_limitation_clear','clarification_is_rider_resolvable','release_eligible','correction_possible']
   result['verifier_schema_fields_match_current_contract']=len(verdict)==1 and all(f in verdict[0] for f in schema_fields) and 'Application metadata separately records fallback reason' in verdict[0]
   if not result['verifier_schema_fields_match_current_contract']:result['structural_result']='FAIL'
  if name=='02_PRD.docx':
   ids=[r.cells[0].text for r in doc.tables[1].rows[1:]];result['unique_functional_ids']=len(ids)==len(set(ids))
   compact=[r.cells[2].text for r in doc.tables[1].rows if r.cells[0].text.split(' /')[0] in ('FR-07','FR-20','FR-27')]
   result['compact_policy_acceptance_cells']=len(compact)==3 and all(len(v)<=210 for v in compact)
   if not result['compact_policy_acceptance_cells']:result['structural_result']='FAIL'
  records.append(result)
 passed=all(x['structural_result']=='PASS' for x in records)
 (OUT/'structural_qa.json').write_text(json.dumps({'checks':records,'all_structural_checks_pass':passed,'not_visual_acceptance':True},indent=2),encoding='utf-8');print(json.dumps(records,indent=2));return 0 if passed else 1
if __name__=='__main__':raise SystemExit(main())
