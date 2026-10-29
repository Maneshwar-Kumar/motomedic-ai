"""Replay the 90 saved v3 drafts through the current gate, on the exact inputs they were written for.

Shows what the new composition steps change on development data, with no model calls: which
sentences are dropped as near-duplicates, which meta phrases are rewritten, and whether any
release outcome changes. Usage (project root): python evals/20261025_quality_round_v1/replay_v3_drafts.py
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
V3 = ROOT / 'evals/20261025_answer_release_v3'
from cloud.grounded_generation import template_answer as ta

SUPPORT = 'mailto:support@royalenfield.com'


def main():
    cases = {c['case_id']: c for c in json.loads((ROOT / 'evals/20261023_stage_replay_v1/cases.json').read_text(encoding='utf-8'))['cases']}
    aliases = json.loads((ROOT / 'evals/20261024_sonnet_generation_v1/alias_mapping.json').read_text())
    rows, summary = [], {}
    for arm in ('haiku', 'haiku_high', 'sonnet'):
        before = {r['alias']: r for r in json.loads((V3 / f'gate_results_{arm}.json').read_text(encoding='utf-8'))['rows']}
        counts = {'released_v3': 0, 'released_now': 0, 'outcome_changed': 0, 'answers_with_dropped_duplicates': 0,
                  'dropped_duplicates': 0, 'answers_with_rewrites': 0}
        for alias, cid in sorted(aliases.items()):
            assembled = json.loads((V3 / 'retrieval' / f'{alias}.json').read_text(encoding='utf-8'))['assembled']
            draft = json.loads((V3 / f'drafts_{arm}' / f'{alias}.json').read_text(encoding='utf-8'))
            old = before[alias]
            try:
                new = ta.gate(draft, assembled, cases[cid]['question'], SUPPORT)
                outcome = 'RELEASED'
            except ta.ReleaseRejected as exc:
                new, outcome = None, exc.code
            old_outcome = old['rejection_code'] or 'RELEASED'
            counts['released_v3'] += old_outcome == 'RELEASED'
            counts['released_now'] += outcome == 'RELEASED'
            counts['outcome_changed'] += outcome != old_outcome
            if new:
                counts['dropped_duplicates'] += new['suppressed_duplicates']
                counts['answers_with_dropped_duplicates'] += bool(new['suppressed_duplicates'])
                counts['answers_with_rewrites'] += bool(new['rewritten_phrases'])
                if new['suppressed_duplicates'] or new['rewritten_phrases'] or outcome != old_outcome:
                    rows.append({'arm': arm, 'case_id': cid, 'v3_outcome': old_outcome, 'now_outcome': outcome,
                                 'dropped_duplicates': new['suppressed_duplicates'],
                                 'rewritten_phrases': new['rewritten_phrases'],
                                 'v3_text': old['released_text'], 'now_text': new['text']})
            elif outcome != old_outcome:
                rows.append({'arm': arm, 'case_id': cid, 'v3_outcome': old_outcome, 'now_outcome': outcome})
        summary[arm] = counts
    result = {'label': 'LOCAL_REPLAY_OF_SAVED_V3_DRAFTS_NO_MODEL_CALLS', 'gate': ta.VERSION, 'summary': summary, 'rows': rows}
    (HERE / 'replay_v3_drafts.json').write_bytes((json.dumps(result, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))
    print(json.dumps(summary, indent=1))


if __name__ == '__main__':
    main()
