"""Collect hosted golden regression metadata; no credentials recorded."""
import json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tools.connect_arm_a_ui import document,REGION
OUT=Path(__file__).resolve().parents[1]/'reports/arm_a/policy_caveats_v2'
def collect():
 submission=json.loads((OUT/'build_submission.json').read_text(encoding='utf-8'));bid=submission['id']
 build=document(['builds','describe',bid,'--region='+REGION]);(OUT/'build_result.json').write_text(json.dumps(build,indent=2)+'\n',encoding='utf-8')
 logs=document(['logging','read','resource.type="build" AND resource.labels.build_id="'+bid+'" AND textPayload:"golden161_"','--limit=200','--order=asc'])
 events=[]
 for row in logs:
  text=row.get('textPayload','');pos=text.find('{"event":')
  if pos<0:continue
  try:event=json.JSONDecoder().raw_decode(text[pos:])[0]
  except ValueError:continue
  if event.get('run_id')=='golden161-policy-caveats-20261011-v2':events.append(event)
 rows=[e for e in events if e['event']=='golden161_case'];byid={r['record_id']:r for r in rows};rows=sorted(byid.values(),key=lambda r:r['ordinal'])
 (OUT/'partial_results.json').write_text(json.dumps({'build_id':bid,'build_status':build['status'],'events':events,'cases':rows},indent=2)+'\n',encoding='utf-8')
 summary=next((e for e in events if e['event']=='golden161_summary'),None)
 if summary:(OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8')
 progress={'build_id':bid,'status':build['status'],'completed':len(rows),'total':len(json.loads((OUT/'preparation.json').read_text(encoding='utf-8'))['target_records']),'passed':sum(r['passed'] for r in rows),'last_record':rows[-1]['record_id'] if rows else None,'summary_present':summary is not None}
 print(json.dumps(progress));return progress
if __name__=='__main__':collect()
