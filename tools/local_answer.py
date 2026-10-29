"""Answer a question locally with the serving answer path, using Claude Code as the generator.

For experimentation. Retrieval, assembly and the release gate are the serving modules, run on
the pinned section index. The one difference from serving is the generation call: instead of
the Anthropic API (and its ledger), a Claude Code subagent (Haiku, effort high) reads the
prepared input and writes the draft JSON. No Firestore, Cloud Tasks, API key or ledger is used.

  python tools/local_answer.py prepare --question "..." --out build/local_answers/<name>
      [--history turns.json] [--index build/index-v4-sections] [--model <bge_m3_dir>]
  -> writes instructions.md, model_input.txt and schema.json for the subagent, which writes draft.json
  python tools/local_answer.py release --out build/local_answers/<name>
  -> runs the gate on draft.json and prints the rider answer, or the SYSTEM_ERROR code

When nothing is retrieved, or the best reranker score is below the relevance floor, prepare
writes the fixed fallback directly and no draft is needed. The API's structured output enforces
the answer schema; a subagent's draft has no such guarantee, so release also records any schema
errors (schema_errors) to separate slips the API would have refused from real gate failures.
The `/motomedic-answer` Claude Code skill (.claude/skills/motomedic-answer) runs all three steps.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from cloud.grounded_generation import section_assembly as sa
from cloud.grounded_generation import section_index as si
from cloud.grounded_generation import section_retrieval as sr
from cloud.grounded_generation import template_answer as ta
from cloud.grounded_generation.section_questions import ManualSource, earlier_turns

DEFAULT_INDEX = ROOT / 'build/index-v4-sections'
DRAFT_RULES = '''Your input is model_input.txt in this folder: the rider question, the earlier conversation, the
manual sections and the warnings to decide. Read all of it. Write only the JSON object, matching
schema.json in this folder, to draft.json in this folder with the Write tool. Do not open any other
file, the repository or the web, and do not explain your answer outside the JSON.'''


def strict_json(raw):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError('DUPLICATE_JSON_KEY')
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=unique)


def schema_errors(value, schema, path='$'):
    """Where a draft breaks the answer schema (types, enums, required and extra keys)."""
    kinds = {'object': dict, 'array': list, 'string': str}
    expected = kinds.get(schema.get('type'))
    if expected and type(value) is not expected:
        return [path + ': not ' + schema['type']]
    if 'enum' in schema and value not in schema['enum']:
        return [path + ': not in enum']
    errors = []
    if expected is dict:
        props = schema.get('properties', {})
        errors += [path + '.' + key + ': missing' for key in schema.get('required', []) if key not in value]
        if schema.get('additionalProperties') is False:
            errors += [path + '.' + key + ': not allowed' for key in value if key not in props]
        for key, item in value.items():
            if key in props:
                errors += schema_errors(item, props[key], path + '.' + key)
    elif expected is list and 'items' in schema:
        for at, item in enumerate(value):
            errors += schema_errors(item, schema['items'], f'{path}[{at}]')
    return errors


def pinned_index_identity(index_dir):
    """The section index must be the one the current serving release pins."""
    from tools.serving_release import CURRENT
    release = json.loads((ROOT / CURRENT).read_text(encoding='utf-8'))
    return si.verify(index_dir, release['index'])


def load_models(index_dir, model_dir, expected_weights_sha256):
    from sentence_transformers import CrossEncoder, SentenceTransformer
    weights = Path(model_dir) / 'pytorch_model.bin'
    if not weights.is_file():
        raise SystemExit('BGE-M3 directory must hold pytorch_model.bin at the index revision: ' + str(model_dir))
    digest = hashlib.sha256()
    with weights.open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 22), b''):
            digest.update(block)
    if digest.hexdigest() != expected_weights_sha256:
        raise SystemExit('BGE-M3 weights differ from the ones the index was built with')
    embedding = SentenceTransformer(str(model_dir), device='cpu', local_files_only=True)
    reranker = CrossEncoder(str(Path(index_dir) / 'reranker_model'), device='cpu', local_files_only=True)
    return embedding, reranker


def prepare(args):
    index_dir = Path(args.index)
    identity = pinned_index_identity(index_dir)
    model_dir = args.model or os.environ.get('MOTOMEDIC_BGE_M3')
    if not model_dir:
        raise SystemExit('Pass --model <bge_m3_dir> or set MOTOMEDIC_BGE_M3 (see docs/EXPERIMENTS.md)')
    embedding, reranker = load_models(index_dir, model_dir, identity['embedding']['weights_sha256'])
    history = json.loads(Path(args.history).read_text(encoding='utf-8')) if args.history else []
    retriever = sr.SectionRetriever(index_dir, embedding, reranker)
    prepare_one(args.question, history, Path(args.out), retriever, sa.SectionIndex(index_dir), ManualSource.load(ROOT, identity))


def prepare_one(question, history, out, retriever, index, source):
    """Retrieve and assemble one turn into out/ (models already loaded, for batch runs)."""
    out.mkdir(parents=True, exist_ok=True)
    for stale in ('draft.json', 'release.json'):
        (out / stale).unlink(missing_ok=True)
    found = retriever.search(sr.retrieval_query(question, history))
    assembled = sa.assemble(index, found['chunk_ids'])
    (out / 'question.json').write_bytes(json.dumps({'question': question, 'history': history},
                                                   indent=1, ensure_ascii=False).encode('utf-8'))
    (out / 'retrieval.json').write_bytes(json.dumps({'retrieval': found, 'assembled': assembled},
                                                    indent=1, ensure_ascii=False).encode('utf-8'))
    if not assembled['objects'] or found['below_relevance_floor']:
        release = ta.no_evidence_release(source.support_uri,
                                         'BELOW_RELEVANCE_FLOOR' if assembled['objects'] else 'NOTHING_RETRIEVED')
        (out / 'release.json').write_bytes(json.dumps(release, indent=1, ensure_ascii=False).encode('utf-8'))
        print('NO_MODEL_CALL\n' + release['text'] + '\nSupport: ' + source.support_uri)
        return
    text = sa.model_input(question, assembled, earlier_turns(history))
    (out / 'model_input.txt').write_bytes(text.encode('utf-8'))
    (out / 'schema.json').write_bytes(json.dumps(ta.answer_schema(assembled), indent=1).encode('utf-8'))
    (out / 'instructions.md').write_bytes(('# MotoMedic answer generator\n\nFollow this system prompt exactly:\n\n'
        '```text\n' + ta.SYSTEM_PROMPT + '\n```\n\n' + DRAFT_RULES + '\n').encode('utf-8'))
    print(json.dumps({'status': 'READY_FOR_DRAFT', 'out': str(out), 'sections': len(assembled['sections']),
                      'lines': len(assembled['objects']), 'warnings_to_decide': len(assembled['warnings']),
                      'reranked': found['reranked'], 'model_input_chars': len(text)}, indent=1))


def release(args):
    out = Path(args.out)
    done = out / 'release.json'
    if not (out / 'draft.json').exists() and done.exists():
        print(json.loads(done.read_text(encoding='utf-8'))['text'])
        return
    question = json.loads((out / 'question.json').read_text(encoding='utf-8'))['question']
    assembled = json.loads((out / 'retrieval.json').read_text(encoding='utf-8'))['assembled']
    source = ManualSource.load(ROOT, si.identity(Path(args.index)))
    errors = None
    try:
        draft = strict_json((out / 'draft.json').read_text(encoding='utf-8'))
        errors = schema_errors(draft, ta.answer_schema(assembled))
        result = ta.gate(draft, assembled, question, source.support_uri)
    except (ValueError, ta.ReleaseRejected) as exc:
        code = getattr(exc, 'code', 'INVALID_DRAFT_JSON')
        result = {'route': 'SYSTEM_ERROR', 'text': 'I couldn’t check the answer right now. Please try again shortly.',
                  'reason': 'GATE_' + code, 'detail': getattr(exc, 'detail', str(exc))}
    result['schema_errors'] = errors
    done.write_bytes(json.dumps(result, indent=1, ensure_ascii=False).encode('utf-8'))
    print('ROUTE: ' + result['route'] + (' (' + result['reason'] + ')' if 'reason' in result else ''))
    if errors:
        print('SCHEMA ERRORS (the API would have refused this draft): ' + '; '.join(errors[:5]))
    print(result['text'])
    if result.get('cited_pages'):
        print('Pages: ' + ', '.join(map(str, result['cited_pages'])))
    if result.get('escalation_uri'):
        print('Support: ' + result['escalation_uri'])
    for row in result.get('watchout_review', []):
        print('  warning ' + row['display_id'] + ': ' + row['decision'] + ' (' + row['reason'] + ')')


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest='command', required=True)
    for name in ('prepare', 'release'):
        p = sub.add_parser(name)
        p.add_argument('--out', required=True)
        p.add_argument('--index', default=os.environ.get('MOTOMEDIC_SECTION_INDEX', str(DEFAULT_INDEX)))
    sub.choices['prepare'].add_argument('--question', required=True)
    sub.choices['prepare'].add_argument('--history', help='JSON list of {"question", "response"} earlier turns')
    sub.choices['prepare'].add_argument('--model', help='BGE-M3 directory (or MOTOMEDIC_BGE_M3)')
    args = parser.parse_args()
    (prepare if args.command == 'prepare' else release)(args)


if __name__ == '__main__':
    main()
