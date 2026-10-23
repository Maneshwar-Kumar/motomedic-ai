"""Section index: the manual's Docling chunks regrouped into real content sections.

Built from the cached Docling parse and the HybridChunker chunks of index_a3282c4d98cf54595e4ba168
(no re-parse, no review layer):
- WARNING / CAUTION / NOTE boxes join the content section they follow in reading order;
- running chapter headers (one section-header text on 3+ pages, always in the page's top band) do
  not start a new section after their first appearance, so page-break continuations stay in one
  section;
- each chunk's search text is "<content heading>\n[<box label>\n]<text>" and is re-embedded.

Usage (project root): python section_index.py <source_index_dir> <out_dir> <bge_m3_dir>
"""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import shutil
import sys

VERSION = 'section-index-v1'
BOXES = ('WARNING', 'CAUTION', 'NOTE')
RUNNING_MIN_PAGES = 3
RUNNING_TOP_BAND = 0.12


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as handle:
        for block in iter(lambda: handle.read(1 << 20), b''):
            digest.update(block)
    return digest.hexdigest()


def stable_id(kind, source, value):
    encoded = json.dumps([source, value], sort_keys=True, ensure_ascii=False).encode()
    return kind + '_' + hashlib.sha256(encoded).hexdigest()[:24]


def read_jsonl(path):
    with Path(path).open(encoding='utf-8') as handle:
        return [json.loads(line) for line in handle]


def write_jsonl(path, rows):
    Path(path).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows), encoding='utf-8')


def running_headers(doc):
    """Section-header texts printed as page headers: on RUNNING_MIN_PAGES+ pages, always near the top."""
    seen = defaultdict(list)
    for item in doc['texts']:
        if item['label'] != 'section_header' or not item.get('prov'):
            continue
        prov = item['prov'][0]
        height = doc['pages'][str(prov['page_no'])]['size']['height']
        top = prov['bbox']['t'] if prov['bbox']['coord_origin'] == 'TOPLEFT' else height - prov['bbox']['t']
        seen[item['text'].strip()].append((prov['page_no'], top / height))
    return {text: sorted({page for page, _ in rows}) for text, rows in seen.items()
            if text.upper() not in BOXES and len({page for page, _ in rows}) >= RUNNING_MIN_PAGES
            and all(fraction <= RUNNING_TOP_BAND for _, fraction in rows)}


def _search_text(chunk, heading, box):
    prefix = heading + '\n' + (box + '\n' if box else '')
    if chunk['id'].startswith('chunk_fallback'):
        return chunk['index_text']
    if chunk['retrieval_window'] or chunk['requires_full_source_context']:
        old = '\n'.join(chunk['section_path']) + '\n'
        body = chunk['index_text'][len(old):] if chunk['index_text'].startswith(old) else chunk['index_text']
        return prefix + body
    return prefix + chunk['text']


def regroup(chunks, running):
    """Assign every chunk, in reading order, to one content section and an optional box label."""
    sections, out, current, opened = [], [], None, set()
    stats = Counter()
    for chunk in chunks:
        heading = (chunk['section_path'] or [''])[0].strip()
        box = None
        if chunk['id'].startswith('chunk_fallback'):
            current = None
            stats['page_fallback_chunks'] += 1
        elif heading.upper() in BOXES:
            box = heading.upper()
            stats['box_chunks'] += 1
            if current is not None:
                stats['box_chunks_attached'] += 1
        elif heading in running and heading in opened and current is not None:
            stats['page_break_continuations'] += 1
            heading = current['heading']
        elif current is not None and heading == current['heading']:
            pass
        else:
            current = None
        if heading in running:
            opened.add(heading)
        if current is None:
            current = {'id': stable_id('section', chunk['source_sha256'], [heading, chunk['id']]),
                       'heading': heading, 'chunk_ids': [], 'evidence_ids': [],
                       'box_of': {}, 'pdf_pages': []}
            sections.append(current)
        current['chunk_ids'].append(chunk['id'])
        for eid in chunk['evidence_ids']:
            if eid not in current['box_of']:
                current['evidence_ids'].append(eid)
                current['box_of'][eid] = box
        current['pdf_pages'] = sorted(set(current['pdf_pages']) | {c['pdf_page'] for c in chunk['citations']})
        out.append({**chunk, 'section_id': current['id'], 'section_heading': current['heading'], 'box': box,
                    'source_index_text': chunk['index_text'],
                    'index_text': _search_text(chunk, current['heading'], box)})
    return out, sections, stats


def build(source_dir, out_dir, model_dir):
    import numpy as np
    from sentence_transformers import SentenceTransformer
    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    from online_ingest import build_bm25

    source_dir, out_dir = Path(source_dir), Path(out_dir)
    if (out_dir / 'manifest.json').exists():
        raise SystemExit('Output already holds an index; use a fresh directory')
    out_dir.mkdir(parents=True, exist_ok=True)
    base = json.loads((source_dir / 'manifest.json').read_text(encoding='utf-8'))
    parse = source_dir / 'docling_document.json'
    if sha256(parse) != base['cached_parse_sha256']:
        raise SystemExit('Cached Docling parse does not match the source index manifest')
    doc = json.loads(parse.read_text(encoding='utf-8'))
    running = running_headers(doc)
    chunks, sections, stats = regroup(read_jsonl(source_dir / 'chunks.jsonl'), running)
    evidence = read_jsonl(source_dir / 'evidence.jsonl')
    owners = Counter(eid for s in sections for eid in s['evidence_ids'])
    if any(n != 1 for n in owners.values()):
        raise SystemExit('An evidence object belongs to more than one section')
    model = SentenceTransformer(str(model_dir), device='cpu', local_files_only=True)
    vectors = model.encode([c['index_text'] for c in chunks], normalize_embeddings=True,
                           batch_size=16, show_progress_bar=False).astype('float32')
    weights = next(p for p in (Path(model_dir) / n for n in ('model.safetensors', 'pytorch_model.bin')) if p.exists())
    config = {'version': VERSION, 'boxes': BOXES, 'running_min_pages': RUNNING_MIN_PAGES,
              'running_top_band': RUNNING_TOP_BAND, 'search_text': '<content heading>\\n[<box label>\\n]<text>'}
    embedding = {**base['embedding'], 'weights_file': weights.name, 'weights_sha256': sha256(weights)}
    code = sha256(__file__)
    index_id = stable_id('index', base['source_sha256'], [base['cached_parse_sha256'], config, embedding, code])
    write_jsonl(out_dir / 'chunks.jsonl', chunks)
    write_jsonl(out_dir / 'sections.jsonl', sections)
    np.save(out_dir / 'embeddings.npy', vectors)
    (out_dir / 'bm25.json').write_text(json.dumps(build_bm25(chunks)), encoding='utf-8')
    for name in ('evidence.jsonl', 'pages.jsonl'):
        shutil.copy2(source_dir / name, out_dir / name)
    shutil.copytree(source_dir / 'reranker_model', out_dir / 'reranker_model')
    covered = {p['page_no'] for e in evidence for p in e['provenance'] if e['id'] in owners}
    qa = {'chunks': len(chunks), 'sections': len(sections), 'evidence_objects_in_sections': len(owners),
          'source_parent_sections': base['counts']['parent_sections'], **stats,
          'box_chunks_unattached': stats['box_chunks'] - stats['box_chunks_attached'],
          'running_headers': running, 'pages_covered': len(covered), 'pdf_pages': base['counts']['pdf_pages'],
          'parser_gap_pages': base['counts']['parser_gap_pages']}
    manifest = {'index_id': index_id, 'built_from_index_id': base['index_id'], 'source_sha256': base['source_sha256'],
                'cached_parse_sha256': base['cached_parse_sha256'], 'chunker': base['chunker'], 'sectioning': config,
                'embedding': embedding, 'code_sha256': code, 'review_layer': 'NONE',
                'file_sha256': {n: sha256(out_dir / n) for n in ('chunks.jsonl', 'sections.jsonl', 'embeddings.npy',
                                                                  'bm25.json', 'evidence.jsonl', 'pages.jsonl')},
                'qa': qa}
    (out_dir / 'manifest.json').write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + '\n', encoding='utf-8')
    return manifest


if __name__ == '__main__':
    result = build(*sys.argv[1:4])
    print(json.dumps({k: result[k] for k in ('index_id', 'built_from_index_id')} | {'qa': result['qa']}, indent=1)[:3000])
