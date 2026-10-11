"""Render the five current planning documents with an explicitly managed renderer.

Never discovers the user's desktop LibreOffice. Pass the absolute bundled/managed
build executable and its runtime root. Can run on an authorized Linux build host.
"""
import argparse,hashlib,importlib.util,json,os,sys,traceback
from pathlib import Path
NAMES=['01_Concept_Architecture.docx','02_PRD.docx','03_TRD.docx','03_TRD_Architecture_Decision_Note.docx','04_To_Build_Evaluation_Decisions.docx']

def main():
 p=argparse.ArgumentParser();p.add_argument('--renderer',required=True);p.add_argument('--soffice',required=True);p.add_argument('--runtime-root',required=True);p.add_argument('--output-dir',required=True);a=p.parse_args()
 root=Path(__file__).resolve().parents[1];out=Path(a.output_dir);out.mkdir(parents=True,exist_ok=True)
 executable=Path(a.soffice).resolve();runtime=Path(a.runtime_root).resolve()
 results=[]
 if not executable.is_relative_to(runtime):raise RuntimeError('LibreOffice must stay within explicitly configured managed document runtime')
 spec=importlib.util.spec_from_file_location('packaged_document_renderer',a.renderer);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
 def resolve_managed():
  if not executable.is_file():raise FileNotFoundError('Bundled LibreOffice unavailable at '+str(executable))
  return str(executable)
 module._resolve_soffice=resolve_managed
 for name in NAMES:
  path=root/name;folder=out/path.stem
  record={'document':name,'document_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'renderer':str(Path(a.renderer).resolve()),'managed_libreoffice':str(executable),'runtime_root':str(runtime),'pngs':[],'visual_inspection':'PENDING'}
  try:
   record['pngs']=list(module.rasterize(str(path),str(folder),150,True,True));record['render_status']='RENDERED_PENDING_VISUAL_INSPECTION'
  except Exception as exc:
   record['render_status']='FAILED';record['failure']=str(exc);(out/(path.stem+'-render.log')).write_text(traceback.format_exc(),encoding='utf-8')
  results.append(record)
 (out/'render_results.json').write_text(json.dumps(results,indent=2),encoding='utf-8')
 print(json.dumps(results,indent=2))
 return 0 if all(x['render_status']=='RENDERED_PENDING_VISUAL_INSPECTION' for x in results) else 2
if __name__=='__main__':raise SystemExit(main())
