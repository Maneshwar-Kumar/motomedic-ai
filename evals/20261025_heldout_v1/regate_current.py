"""Post-hoc: gate the saved held-out drafts again with the current gate and list what changes.

The held-out run used gate template-answer-v4. It showed that v4's repeat rule could drop an
answer step that shares its words with another but reverses their order (H18, default effort).
Gate v5 never drops answer items. This replays the same drafts, on the same inputs, through the
current gate. Because the fix was made after seeing held-out output, this is not held-out evidence.
Usage (project root): python evals/20261025_heldout_v1/regate_current.py
"""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
from cloud.grounded_generation import template_answer as ta

SUPPORT = 'mailto:support@royalenfield.com'


def main():
    rows = []
    for arm in ('haiku_high', 'haiku_default'):
        for out in sorted((HERE / 'runs' / arm).iterdir()):
            if not (out / 'draft.json').exists():
                continue
            before = json.loads((out / 'release.json').read_text(encoding='utf-8'))
            question = json.loads((out / 'question.json').read_text(encoding='utf-8'))['question']
            assembled = json.loads((out / 'retrieval.json').read_text(encoding='utf-8'))['assembled']
            draft = json.loads((out / 'draft.json').read_text(encoding='utf-8'))
            try:
                now = ta.gate(draft, assembled, question, SUPPORT)
            except ta.ReleaseRejected as exc:
                now = {'route': 'SYSTEM_ERROR', 'text': None, 'reason': 'GATE_' + exc.code}
            if (now['route'], now['text']) != (before['route'], before['text'] if before['route'] != 'SYSTEM_ERROR' else None):
                rows.append({'arm': arm, 'id': out.name, 'as_run_route': before['route'], 'now_route': now['route'],
                             'as_run_text': before['text'], 'now_text': now['text']})
    result = {'label': 'POST_HOC_REGATE_NOT_HELD_OUT_EVIDENCE', 'as_run_gate': 'template-answer-v4',
              'current_gate': ta.VERSION, 'changed': rows}
    (HERE / 'regate_current.json').write_bytes((json.dumps(result, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))
    print(json.dumps(result, indent=1, ensure_ascii=False))


if __name__ == '__main__':
    main()
