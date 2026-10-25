"""Retrieve, assemble and write the blind plain-text model inputs for the 30 questions.

Usage (project root): python build_inputs.py <section_index_dir> <bge_m3_dir>
Writes inputs/Qnn.txt (what the model reads), retrieval/Qnn.json (trace and label map, server side)
and retrieval_summary.json (recall against the gold evidence; agent-authored gold, not human review).
"""
import json
from pathlib import Path
import statistics
import sys

HERE = Path(__file__).resolve().parent
EVALS = HERE.parent
sys.path.insert(0, str(HERE / 'candidate'))
import section_assembly as sa  # noqa: E402
import section_retrieval as sr  # noqa: E402


def main(index_dir, model_dir):
    from sentence_transformers import CrossEncoder, SentenceTransformer
    index_dir = Path(index_dir)
    embed = SentenceTransformer(str(model_dir), device='cpu', local_files_only=True)
    cross = CrossEncoder(str(index_dir / 'reranker_model'), device='cpu', local_files_only=True)
    retriever, index = sr.SectionRetriever(index_dir, embed, cross), sa.SectionIndex(index_dir)
    mapping = json.loads((EVALS / '20261024_sonnet_generation_v1/alias_mapping.json').read_text())
    cases = {c['case_id']: c for c in json.loads((EVALS / '20261023_stage_replay_v1/cases.json').read_text(encoding='utf-8'))['cases']}
    (HERE / 'inputs').mkdir(exist_ok=True)
    (HERE / 'retrieval').mkdir(exist_ok=True)
    from template_answer import SYSTEM_PROMPT
    (HERE / 'ANSWER_INSTRUCTIONS_v3.md').write_text(
        '# MotoMedic answer generator (v3)\n\nFollow this system prompt exactly:\n\n```text\n' + SYSTEM_PROMPT +
        '\n```\n\nYour input is a plain-text file holding the rider question, the earlier conversation, the manual '
        'sections and the warnings to decide. Read all of it. Write only the JSON object, with the Write tool, to '
        'the output path you were given. Do not open any other file, the repository or the web.\n', encoding='utf-8')
    rows = []
    for alias, cid in sorted(mapping.items()):
        case = cases[cid]
        found = retriever.search(case['question'])
        assembled = sa.assemble(index, found['chunk_ids'])
        text = sa.model_input(case['question'], assembled)
        (HERE / 'inputs' / f'{alias}.txt').write_text(text, encoding='utf-8')
        (HERE / 'retrieval' / f'{alias}.json').write_text(json.dumps({'retrieval': found, 'assembled': assembled},
                                                                      indent=1, ensure_ascii=False), encoding='utf-8')
        gold = set(case['gold_evidence_ids'])
        sent = {o['evidence_id'] for o in assembled['objects'].values()}
        in_chunks = {e for c in found['chunk_ids'] for e in index.chunks[c]['evidence_ids']}
        rows.append({'alias': alias, 'case_id': cid, 'group': case['group'], 'gold': len(gold),
                     'answer_chunk_in_top5': bool(gold & in_chunks) if gold else None,
                     'gold_sent': len(gold & sent), 'all_gold_sent': gold <= sent if gold else None,
                     'sections_sent': len(assembled['sections']), 'lines_sent': len(assembled['objects']),
                     'warnings_sent': len(assembled['warnings']), 'input_chars': len(text),
                     'reranked': found['reranked']})
        print(alias, cid, 'sections', rows[-1]['sections_sent'], 'lines', rows[-1]['lines_sent'],
              'warnings', rows[-1]['warnings_sent'], 'chars', len(text), 'gold', f"{rows[-1]['gold_sent']}/{len(gold)}")
    answerable = [r for r in rows if r['gold']]
    summary = {'label': 'LOCAL_RETRIEVAL_DIAGNOSTIC_NOT_ACCEPTANCE', 'index_id': index.manifest['index_id'],
               'retrieval_version': sr.VERSION,
               'assembly_version': sa.VERSION,
               'answerable': len(answerable),
               'answer_chunk_in_top5': sum(r['answer_chunk_in_top5'] for r in answerable),
               'all_gold_sent': sum(r['all_gold_sent'] for r in answerable),
               'reranked': sum(r['reranked'] for r in rows),
               'input_chars_median': statistics.median(r['input_chars'] for r in rows),
               'input_chars_max': max(r['input_chars'] for r in rows),
               'lines_sent_median': statistics.median(r['lines_sent'] for r in rows),
               'warnings_sent_median': statistics.median(r['warnings_sent'] for r in rows),
               'warnings_sent_max': max(r['warnings_sent'] for r in rows), 'rows': rows}
    (HERE / 'retrieval_summary.json').write_text(json.dumps(summary, indent=1) + '\n', encoding='utf-8')
    print(json.dumps({k: v for k, v in summary.items() if k != 'rows'}, indent=1))


if __name__ == '__main__':
    main(*sys.argv[1:3])
