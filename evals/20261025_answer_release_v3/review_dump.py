"""Print each case for the main agent's review: released text, every cited item beside the exact
lines it cites, and the canonical answer.  Usage: python review_dump.py <arm> [case_id ...]
"""
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
arm, only = sys.argv[1], set(sys.argv[2:])
rows = json.loads((HERE / f'gate_results_{arm}.json').read_text(encoding='utf-8'))['rows']
for r in rows:
    if only and r['case_id'] not in only:
        continue
    objects = json.loads((HERE / 'retrieval' / f"{r['alias']}.json").read_text(encoding='utf-8'))['assembled']['objects']
    gold = set(r['gold_evidence_ids'])
    gold_labels = [l for l, o in objects.items() if o['evidence_id'] in gold]
    print('=' * 90)
    print(f"{r['case_id']} [{r['group']}] {r['gate']} {r['released_route'] or ''}/{r['draft_coverage']} "
          f"{r['rejection_code'] or ''} {r['rejection_detail'] or ''}")
    print('Q:', r['question'])
    print('CANON:', r['canonical_answer'] or r['absence_check'])
    print('GOLD LABELS:', gold_labels, '| WATCHOUTS INCLUDED:', r['watchouts_included'], 'of', r['warnings_sent'])
    for section, items in r['sections'].items():
        for item in items or []:
            print(f'  [{section}] {item.get("text")}')
            for label in item.get('evidence_ids') or []:
                obj = objects.get(label)
                print(f'      {label}: {obj["text"][:300] if obj else "NOT SENT"}')
    if r['clarification_question']:
        print('  [clarification]', r['clarification_question'])
    print('SHOWN:', r['released_text'])
