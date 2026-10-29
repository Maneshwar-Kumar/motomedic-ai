"""The answer-quality regression gate: a fixed question set, deterministic checks and a pass bar.

CI cannot call the model, so answer quality is held in two steps:
1. Run. Before a prompt, model, index, retrieval or assembly change ships, the changed path
   answers the regression set (locally with one Claude Code subagent per turn, as in
   docs/EXPERIMENTS.md) and `score` writes a receipt bound to that path's answer identity.
2. Check, in CI and in every serving freeze:
   - the receipt must name the current answer identity: index, retrieval constants, assembly
     version and generation contract, including the system prompt hash;
   - every saved model input and answer schema is rebuilt from the saved sections and must match;
   - every saved draft goes through the current gate and is rescored with the current set;
   - the totals must meet the set's thresholds.

A gate-only change is therefore re-checked in CI without a model call. A prompt, model, index,
retrieval or assembly change makes the receipt stale until a new passing run is committed.

  python tools/regression.py prepare --run evals/<date>_regression_<n> --model <bge_m3_dir> [--turn 2]
  (one generator per folder that printed READY_FOR_DRAFT writes draft.json)
  python tools/regression.py score --run evals/<date>_regression_<n>
  python tools/regression.py check [--run evals/<date>_regression_<n>]
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

SET = 'evals/regression/set_v1.json'
CURRENT = 'evals/20261029_regression_v1'
INDEX_DIR = ROOT / 'build/index-v4-sections'
CONTRACT_KEYS = ('provider', 'model', 'version', 'effort', 'thinking', 'output_tokens', 'native_json_schema',
                 'system_prompt_sha256')
_PLAIN = str.maketrans({'–': '-', '—': '-', '−': '-', '‐': '-', '‑': '-', ' ': ' ',
                        '‘': "'", '’': "'", '“': '"', '”': '"'})


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def answer_identity():
    """Everything that shapes a model input or the generation call; the gate is re-run instead."""
    from cloud.grounded_generation import section_assembly as sa
    from cloud.grounded_generation import section_retrieval as sr
    from cloud.grounded_generation.haiku_answer import CONTRACT
    from tools.check_installed_serving_release import INDEX
    return {'index_id': INDEX,
            'retrieval': {'version': sr.VERSION, 'top_k': sr.TOP_K, 'rrf_k': sr.RRF_K, 'dense_limit': sr.DENSE_LIMIT,
                          'fuse_depth': sr.FUSE_DEPTH, 'disagreement_top': sr.DISAGREEMENT_TOP,
                          'max_query_tokens': sr.MAX_QUERY_TOKENS, 'relevance_floor': sr.RELEVANCE_FLOOR},
            'assembly_version': sa.VERSION,
            'generation': {key: CONTRACT[key] for key in CONTRACT_KEYS}}


def load_set(root=ROOT):
    path = Path(root) / SET
    return json.loads(path.read_text(encoding='utf-8')), sha256(path.read_bytes())


def normalize(text):
    return re.sub(r'\s+', ' ', (text or '').translate(_PLAIN).lower()).strip()


def score_case(case, route, text, assembled):
    norm = normalize(text)
    missing = [group for group in case['require'] if not any(re.search(p, norm) for p in group)]
    forbidden = [p for p in case['forbid'] if re.search(p, norm)]
    shown = [any(re.search(p, norm) for p in group) for group in case['warnings']]
    sent = {p for obj in (assembled or {}).get('objects', {}).values() for p in obj['pages']}
    released = route != 'SYSTEM_ERROR'
    return {'id': case['id'], 'route': route, 'released': released, 'route_allowed': route in case['routes'],
            'missing': [group[0] for group in missing], 'forbidden': forbidden,
            'warnings_shown': sum(shown), 'warnings': len(shown),
            'pages_sent': sum(p in sent for p in case['pages']), 'pages': len(case['pages']),
            'passed': released and route in case['routes'] and not missing and not forbidden}


def totals(rows):
    return {'cases': len(rows), 'passed': sum(r['passed'] for r in rows),
            'system_errors': sum(not r['released'] for r in rows),
            'forbidden_matches': sum(len(r['forbidden']) for r in rows),
            'warnings_shown': sum(r['warnings_shown'] for r in rows), 'warnings': sum(r['warnings'] for r in rows),
            'reference_pages_sent': sum(r['pages_sent'] for r in rows),
            'reference_pages': sum(r['pages'] for r in rows)}


def shortfalls(total, thresholds):
    """Names of the thresholds the totals miss; empty means the bar is met."""
    if not thresholds:
        return ['THRESHOLDS_NOT_SET']
    checks = [('PASSED_BELOW_MIN', total['passed'] < thresholds['passed_min']),
              ('SYSTEM_ERRORS_ABOVE_MAX', total['system_errors'] > thresholds['system_errors_max']),
              ('FORBIDDEN_MATCHES_ABOVE_MAX', total['forbidden_matches'] > thresholds['forbidden_max']),
              ('WARNINGS_SHOWN_BELOW_MIN', total['warnings_shown'] < thresholds['warnings_shown_min']),
              ('REFERENCE_PAGES_BELOW_MIN', total['reference_pages_sent'] < thresholds['reference_pages_sent_min'])]
    return [name for name, failed in checks if failed]


def support_uri(root):
    manifest = json.loads((Path(root) / 'source/source_manifest.json').read_text(encoding='utf-8-sig'))
    return manifest['oem_service_route']['url']


def release_turn(folder, question, support):
    """(route, text, assembled) for a saved turn, re-released with the current gate."""
    from cloud.grounded_generation import template_answer as ta
    from tools.local_answer import strict_json
    saved = json.loads((folder / 'retrieval.json').read_text(encoding='utf-8'))
    assembled = saved['assembled']
    if not assembled['objects'] or saved['retrieval']['below_relevance_floor']:
        return 'UNSUPPORTED', ta.FALLBACK_TEXT, assembled
    if not (folder / 'draft.json').exists():
        raise ValueError('REGRESSION_DRAFT_MISSING:' + folder.name)
    try:
        released = ta.gate(strict_json((folder / 'draft.json').read_text(encoding='utf-8')), assembled, question, support)
        return released['route'], released['text'], assembled
    except (ValueError, ta.ReleaseRejected):
        return 'SYSTEM_ERROR', None, assembled


def evaluate(run, root=ROOT):
    """Rebuild, re-gate and rescore every saved turn of a run; returns problems and totals."""
    from cloud.grounded_generation import section_assembly as sa
    from cloud.grounded_generation import template_answer as ta
    from cloud.grounded_generation.section_questions import earlier_turns
    run, root = Path(run), Path(root)
    regression, set_sha = load_set(root)
    support = support_uri(root)
    problems, rows = [], []
    for case in regression['cases']:
        folder = run / 'runs' / case['id']
        if not (folder / 'question.json').exists():
            problems.append('CASE_NOT_RUN:' + case['id'])
            continue
        asked = json.loads((folder / 'question.json').read_text(encoding='utf-8'))
        if asked['question'] != case['question'] or bool(asked['history']) != bool(case['follow_up_of']):
            problems.append('QUESTION_CHANGED:' + case['id'])
        assembled = json.loads((folder / 'retrieval.json').read_text(encoding='utf-8'))['assembled']
        if (folder / 'model_input.txt').exists():
            text = sa.model_input(asked['question'], assembled, earlier_turns(asked['history']))
            if text.encode('utf-8') != (folder / 'model_input.txt').read_bytes():
                problems.append('MODEL_INPUT_CHANGED:' + case['id'])
            if json.dumps(ta.answer_schema(assembled), indent=1).encode('utf-8') != (folder / 'schema.json').read_bytes():
                problems.append('ANSWER_SCHEMA_CHANGED:' + case['id'])
            if ta.SYSTEM_PROMPT not in (folder / 'instructions.md').read_text(encoding='utf-8'):
                problems.append('SYSTEM_PROMPT_CHANGED:' + case['id'])
        try:
            route, text, assembled = release_turn(folder, asked['question'], support)
        except ValueError as exc:
            problems.append(str(exc))
            continue
        rows.append(score_case(case, route, text, assembled))
    total = totals(rows)
    return {'set': SET, 'set_sha256': set_sha, 'problems': problems, 'totals': total,
            'thresholds': regression['thresholds'], 'shortfalls': shortfalls(total, regression['thresholds']),
            'rows': rows}


def check(run=None, root=ROOT):
    """The CI and freeze gate. Returns the result; raises nothing; `passed` is the verdict."""
    root = Path(root)
    run = root / (run or CURRENT)
    receipt_path = run / 'receipt.json'
    if not receipt_path.exists():
        return {'passed': False, 'problems': ['REGRESSION_RECEIPT_MISSING:' + str(run)]}
    receipt = json.loads(receipt_path.read_text(encoding='utf-8'))
    identity = answer_identity()
    problems = ['REGRESSION_RECEIPT_STALE:' + key for key in identity
                if receipt.get('answer_identity', {}).get(key) != identity[key]]
    generator = receipt.get('generator') or {}
    if (generator.get('model') != identity['generation']['model']
            or generator.get('effort') != identity['generation']['effort']):
        problems.append('REGRESSION_GENERATOR_DIFFERS_FROM_CONTRACT')
    result = evaluate(run, root)
    result['problems'] = problems + result['problems']
    result.update(receipt=str(receipt_path.relative_to(root)).replace('\\', '/'),
                  receipt_sha256=sha256(receipt_path.read_bytes()), answer_identity=identity,
                  passed=not result['problems'] and not result['shortfalls'])
    return result


def prepare(args):
    from cloud.grounded_generation import section_assembly as sa
    from cloud.grounded_generation import section_retrieval as sr
    from cloud.grounded_generation.section_questions import ManualSource
    from tools import local_answer
    index_dir = Path(args.index)
    identity = local_answer.pinned_index_identity(index_dir)
    embedding, reranker = local_answer.load_models(index_dir, args.model, identity['embedding']['weights_sha256'])
    retriever, index = sr.SectionRetriever(index_dir, embedding, reranker), sa.SectionIndex(index_dir)
    source = ManualSource.load(ROOT, identity)
    regression, _ = load_set()
    by_id = {case['id']: case for case in regression['cases']}
    for case in regression['cases']:
        if (case['follow_up_of'] is None) != (args.turn == 1):
            continue
        history = []
        if case['follow_up_of']:
            first = by_id[case['follow_up_of']]
            done = json.loads((Path(args.run) / 'runs' / first['id'] / 'release.json').read_text(encoding='utf-8'))
            history = [{'question': first['question'], 'response': done['text']}]
        print(case['id'], end=' ')
        local_answer.prepare_one(case['question'], history, Path(args.run) / 'runs' / case['id'], retriever, index, source)


def release(args):
    """Write release.json for each drafted turn (needed before follow-ups are prepared)."""
    import argparse as _argparse
    import contextlib
    import io
    from tools import local_answer
    for folder in sorted((Path(args.run) / 'runs').iterdir()):
        if (folder / 'draft.json').exists():
            with contextlib.redirect_stdout(io.StringIO()):
                local_answer.release(_argparse.Namespace(out=str(folder), index=args.index))


def score(args):
    from tools.reproduce_offline import environment
    run = Path(args.run)
    result = evaluate(run)
    receipt = {'schema': 'motomedic-regression-receipt-v1', 'label': 'LOCAL_CLAUDE_CODE_SUBAGENT_RUN_DETERMINISTIC_SCORE',
               'answer_identity': answer_identity(),
               'generator': {'kind': args.generator_kind, 'model': args.generator_model, 'effort': args.generator_effort},
               'environment': environment(), **{k: result[k] for k in ('set', 'set_sha256', 'problems', 'totals',
                                                                         'thresholds', 'shortfalls', 'rows')}}
    (run / 'receipt.json').write_bytes((json.dumps(receipt, indent=1, ensure_ascii=False) + '\n').encode('utf-8'))
    print(json.dumps({k: receipt[k] for k in ('totals', 'shortfalls', 'problems')}, indent=1))


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'release', 'score', 'check'):
        p = sub.add_parser(name)
        p.add_argument('--run', required=name != 'check')
        p.add_argument('--index', default=str(INDEX_DIR))
    sub.choices['prepare'].add_argument('--model', required=True, help='BGE-M3 directory at the index revision')
    sub.choices['prepare'].add_argument('--turn', type=int, choices=(1, 2), default=1)
    sub.choices['score'].add_argument('--generator-kind', default='CLAUDE_CODE_SUBAGENT')
    sub.choices['score'].add_argument('--generator-model', default='claude-haiku-5-5')
    sub.choices['score'].add_argument('--generator-effort', default='high')
    args = parser.parse_args()
    if args.command == 'check':
        result = check(args.run)
        print(json.dumps({k: result.get(k) for k in ('receipt', 'totals', 'thresholds', 'shortfalls', 'problems',
                                                      'passed')}, indent=1))
        raise SystemExit(0 if result['passed'] else 1)
    {'prepare': prepare, 'release': release, 'score': score}[args.command](args)


if __name__ == '__main__':
    main()
