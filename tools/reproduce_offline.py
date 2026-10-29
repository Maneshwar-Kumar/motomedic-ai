"""Reproduce a saved local evaluation run with a checkout's code: retrieval, model input and gate.

For every saved turn of a run (<run>/runs/<arm>/<id>/), this re-runs retrieval and assembly on
the pinned section index and compares the chunk IDs, the model input, the answer schema and
the system prompt with the saved files, byte for byte. It then passes the saved draft through
the checkout's gate and compares the route and text with the saved release. No model is called.

  python tools/reproduce_offline.py --root <checkout> --run evals/20261025_heldout_v1 \\
      --index <section_index_dir> --model <bge_m3_dir> --out <report.json> \\
      [--expected-gate-changes evals/20261025_heldout_v1/regate_current.json]

It exits non-zero on any mismatch, except gate changes listed in a documented re-gate file.
--root selects whose code is reproduced (default: this checkout). The report also records the
Python version, platform and package versions, so a reproduction names its setup.
"""
import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import sys

PACKAGES = ('numpy', 'torch', 'sentence-transformers', 'transformers', 'tokenizers', 'huggingface_hub',
            'safetensors', 'Flask')


def environment():
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    return {'python': platform.python_version(), 'platform': platform.platform(), 'packages': versions}


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--root', default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument('--run', required=True, help='evaluation folder, relative to --root')
    parser.add_argument('--index', required=True)
    parser.add_argument('--model', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--expected-gate-changes', help='re-gate JSON whose changed turns are documented')
    args = parser.parse_args()
    root = Path(args.root).resolve()
    sys.path.insert(0, str(root))
    from cloud.grounded_generation import section_assembly as sa
    from cloud.grounded_generation import section_retrieval as sr
    from cloud.grounded_generation import template_answer as ta
    from cloud.grounded_generation.section_questions import ManualSource, earlier_turns
    from tools import local_answer

    identity = local_answer.pinned_index_identity(args.index)
    embedding, reranker = local_answer.load_models(args.index, args.model, identity['embedding']['weights_sha256'])
    retriever, index = sr.SectionRetriever(args.index, embedding, reranker), sa.SectionIndex(args.index)
    support = ManualSource.load(root, identity).support_uri
    rows = []
    for turn in sorted((root / args.run / 'runs').glob('*/*/question.json')):
        out = turn.parent
        asked = json.loads(turn.read_text(encoding='utf-8'))
        saved = json.loads((out / 'retrieval.json').read_text(encoding='utf-8'))
        found = retriever.search(sr.retrieval_query(asked['question'], asked['history']))
        assembled = sa.assemble(index, found['chunk_ids'])
        row = {'arm': out.parent.name, 'id': out.name,
               'chunk_ids_match': found['chunk_ids'] == saved['retrieval']['chunk_ids'],
               'floor_match': found['below_relevance_floor'] == saved['retrieval']['below_relevance_floor'],
               'cross_score_delta': (None if found['max_cross_score'] is None else
                                     abs(found['max_cross_score'] - saved['retrieval']['max_cross_score'])),
               'assembly_match': json.loads(json.dumps(assembled)) == saved['assembled']}
        if (out / 'model_input.txt').exists():
            text = sa.model_input(asked['question'], assembled, earlier_turns(asked['history']))
            row['model_input_match'] = text.encode('utf-8') == (out / 'model_input.txt').read_bytes()
            row['schema_match'] = (json.dumps(ta.answer_schema(assembled), indent=1).encode('utf-8')
                                   == (out / 'schema.json').read_bytes())
            row['system_prompt_match'] = ta.SYSTEM_PROMPT in (out / 'instructions.md').read_text(encoding='utf-8')
        release = json.loads((out / 'release.json').read_text(encoding='utf-8'))
        if (out / 'draft.json').exists():
            try:
                now = ta.gate(json.loads((out / 'draft.json').read_text(encoding='utf-8')), saved['assembled'],
                              asked['question'], support)
                route, text = now['route'], now['text']
            except ta.ReleaseRejected as exc:
                route, text = 'SYSTEM_ERROR', 'GATE_' + exc.code
            row['gate_match'] = (route, text) == (release['route'], release['text'] if route != 'SYSTEM_ERROR'
                                                  else release.get('reason'))
        rows.append(row)
    checks = ('chunk_ids_match', 'floor_match', 'assembly_match', 'model_input_match', 'schema_match',
              'system_prompt_match', 'gate_match')
    summary = {check: '%d/%d' % (sum(r[check] for r in rows if check in r), sum(check in r for r in rows))
               for check in checks}
    deltas = [r['cross_score_delta'] for r in rows if r['cross_score_delta'] is not None]
    expected = set()
    if args.expected_gate_changes:
        documented = json.loads((root / args.expected_gate_changes).read_text(encoding='utf-8'))
        expected = {(row['arm'], row['id']) for row in documented['changed']}
    for row in rows:
        row['documented_gate_change'] = row.get('gate_match') is False and (row['arm'], row['id']) in expected
    unexplained = [r for r in rows if not all(r.get(c, True) for c in checks if c != 'gate_match')
                   or (r.get('gate_match') is False and not r['documented_gate_change'])]
    report = {'label': 'OFFLINE_REPRODUCTION_NO_MODEL_CALLS', 'run': args.run, 'index_id': identity['index_id'],
              'code_root_commit': (root / '.git').exists() and _head(root), 'environment': environment(),
              'max_cross_score_delta': max(deltas) if deltas else None, 'summary': summary,
              'mismatches': [r for r in rows if not all(r.get(c, True) for c in checks)],
              'unexplained_mismatches': len(unexplained), 'reproduced': not unexplained}
    Path(args.out).write_bytes((json.dumps(report, indent=1) + '\n').encode('utf-8'))
    print(json.dumps({k: report[k] for k in ('index_id', 'code_root_commit', 'environment', 'max_cross_score_delta',
                                              'summary')}, indent=1))
    print('mismatches:', [(r['arm'], r['id'], r['documented_gate_change']) for r in report['mismatches']])
    print('reproduced:', report['reproduced'])
    raise SystemExit(0 if report['reproduced'] else 1)


def _head(root):
    import subprocess
    try:
        return subprocess.run(['git', '-C', str(root), 'rev-parse', 'HEAD'], capture_output=True, text=True,
                              check=True).stdout.strip()
    except Exception:
        return None


if __name__ == '__main__':
    main()
