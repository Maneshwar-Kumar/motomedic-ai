"""Run the 33 held-out questions through the local answer path, one arm at a time.

Retrieval, assembly and the gate are the serving modules on the pinned section index. The one
generation call per turn is a Claude Code Haiku subagent (docs/EXPERIMENTS.md), which reads a
prepared folder and writes draft.json. A follow-up is prepared after its first turn is released,
with that turn's rider text as history. The questions were written by an independent subagent
and their hash recorded before any run; nothing in the answer path was tuned on them.

Usage (project root):
  python evals/20261025_heldout_v1/run_heldout.py prepare --arm haiku_high --turn 1 --model <bge_m3_dir>
  (one subagent per folder that printed READY_FOR_DRAFT writes draft.json)
  python evals/20261025_heldout_v1/run_heldout.py prepare --arm haiku_high --turn 2 --model <bge_m3_dir>
  python evals/20261025_heldout_v1/run_heldout.py release --arm haiku_high
"""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
HERE = Path(__file__).resolve().parent
from cloud.grounded_generation import section_assembly as sa
from cloud.grounded_generation import section_retrieval as sr
from cloud.grounded_generation.section_questions import ManualSource
from tools import local_answer

ARMS = ('haiku_high', 'haiku_default')
INDEX = ROOT / 'build/index-v4-sections'


def questions():
    return json.loads((HERE / 'questions.json').read_text(encoding='utf-8'))['questions']


def folder(arm, qid):
    return HERE / 'runs' / arm / qid


def prepare(args):
    identity = local_answer.pinned_index_identity(INDEX)
    embedding, reranker = local_answer.load_models(INDEX, args.model, identity['embedding']['weights_sha256'])
    retriever, index = sr.SectionRetriever(INDEX, embedding, reranker), sa.SectionIndex(INDEX)
    source = ManualSource.load(ROOT, identity)
    by_id = {q['id']: q for q in questions()}
    for q in by_id.values():
        if (q['follow_up_of'] is None) != (args.turn == 1):
            continue
        history = []
        if q['follow_up_of']:
            first = by_id[q['follow_up_of']]
            done = json.loads((folder(args.arm, first['id']) / 'release.json').read_text(encoding='utf-8'))
            history = [{'question': first['question'], 'response': done['text']}]
        print(q['id'], end=' ')
        local_answer.prepare_one(q['question'], history, folder(args.arm, q['id']), retriever, index, source)


def release(args):
    rows = []
    for q in questions():
        out = folder(args.arm, q['id'])
        if not out.is_dir():  # a follow-up not yet prepared
            continue
        with contextlib.redirect_stdout(io.StringIO()):
            local_answer.release(argparse.Namespace(out=str(out), index=str(INDEX)))
        result = json.loads((out / 'release.json').read_text(encoding='utf-8'))
        found = json.loads((out / 'retrieval.json').read_text(encoding='utf-8'))
        retrieval, assembled = found['retrieval'], found['assembled']
        sent_pages = sorted({p for o in assembled['objects'].values() for p in o['pages']})
        rows.append({'id': q['id'], 'category': q['category'], 'expected_route': q['expected_route'],
            'route': result['route'], 'reason': result.get('reason'), 'coverage': result.get('coverage'),
            'model_called': (out / 'draft.json').exists(), 'schema_errors': result.get('schema_errors'),
            'text': result['text'], 'cited_pages': result.get('cited_pages', []),
            'suppressed_duplicates': result.get('suppressed_duplicates'),
            'rewritten_phrases': result.get('rewritten_phrases'),
            'watchout_review': result.get('watchout_review', []),
            'max_cross_score': retrieval['max_cross_score'], 'below_relevance_floor': retrieval['below_relevance_floor'],
            'reranked': retrieval['reranked'], 'sections_sent': list(dict.fromkeys(o['section'] for o in assembled['objects'].values())),
            'warnings_to_decide': len(assembled['warnings']), 'model_input_chars': len(assembled['text']),
            'reference_pages': q['pages'], 'reference_pages_sent': [p for p in q['pages'] if p in sent_pages]})
    summary = {'arm': args.arm, 'label': 'LOCAL_CLAUDE_CODE_SUBAGENT_RUN_NOT_HOSTED_NOT_API',
               'questions_sha256': hashlib.sha256((HERE / 'questions.json').read_bytes()).hexdigest(),
               'released': sum(r['route'] != 'SYSTEM_ERROR' for r in rows),
               'system_errors': [r['id'] + ':' + r['reason'] for r in rows if r['route'] == 'SYSTEM_ERROR'],
               'drafts_with_schema_errors': [r['id'] for r in rows if r['schema_errors']],
               'model_calls': sum(r['model_called'] for r in rows),
               'below_floor': [r['id'] for r in rows if r['below_relevance_floor']], 'rows': rows}
    (HERE / f'gate_results_{args.arm}.json').write_bytes(
        (json.dumps(summary, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))
    print(json.dumps({k: v for k, v in summary.items() if k != 'rows'}, indent=1))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('command', choices=('prepare', 'release'))
    parser.add_argument('--arm', choices=ARMS, required=True)
    parser.add_argument('--turn', type=int, choices=(1, 2), default=1)
    parser.add_argument('--model', help='BGE-M3 directory (prepare only)')
    args = parser.parse_args()
    (prepare if args.command == 'prepare' else release)(args)


if __name__ == '__main__':
    main()
