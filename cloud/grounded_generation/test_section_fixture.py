"""SYNTHETIC TEST FIXTURE (no tests here): a tiny section index with the real file layout. Not manual content.

Three sections: RUNNING IN (two lines), CHARGER PORT (a line, a WARNING box and a NOTE box) and
SPECIFICATIONS (a two-row table). Vectors are keyword features, so dense ranking is predictable.
"""
import hashlib
import json
from pathlib import Path

# Loaded at import: tests that patch sys.modules must not first import NumPy inside the patch.
import numpy as np
from online_ingest import build_bm25
from rider_ui.client import INDEX_ID, MANUAL_SHA

TOPICS = (('running', 'engine', 'rpm', 'throttle', 'km'), ('charger', 'port', 'usb', 'rain', 'cap'),
          ('compression', 'ratio', 'bore', 'specification'), ())
SECTIONS = (
    ('RUNNING IN', 40, [('text', 'During the first 500 km keep the engine below 6000 rpm and avoid full throttle.', None),
                        ('text', 'From 500 km to 1500 km keep the engine below 7000 rpm.', None)]),
    ('CHARGER PORT', 64, [('text', 'Charger port is located on the centre of the handlebar.', None),
                          ('text', 'Do not use the charger port in rain or while washing the motorcycle.', 'WARNING'),
                          ('text', 'Close the charger port cap after use.', 'NOTE')]),
    ('SPECIFICATIONS', 140, [('table', [('Compression ratio', '11.5:1'), ('Bore', '84 mm')], None)]),
)


def features(text):
    words = text.lower()
    vector = [float(sum(words.count(k) for k in topic)) for topic in TOPICS[:3]] + [0.1]
    norm = sum(v * v for v in vector) ** 0.5
    return [v / norm for v in vector]


class Embedder:
    """Keyword-feature query encoder; `forced` maps an exact query to a chosen vector."""
    def __init__(self, forced=None):
        self.forced = forced or {}

    def encode(self, text, normalize_embeddings=True):
        return np.array(self.forced.get(text, features(text)), dtype='float32')


class CrossEncoder:
    def __init__(self, scores=None):
        self.calls, self.scores = [], scores or {}

    def predict(self, pairs):
        self.calls.append(pairs)
        return [self.scores.get(text.split('\n')[0], 0.0) for _query, text in pairs]


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    chunks, sections, evidence = [], [], []
    for s_at, (heading, page, rows) in enumerate(SECTIONS):
        sid = f'section_synthetic_{s_at}'
        section = {'id': sid, 'heading': heading, 'chunk_ids': [], 'evidence_ids': [], 'box_of': {}, 'pdf_pages': [page]}
        for r_at, (kind, value, box) in enumerate(rows):
            eid = f'evidence_synthetic_{s_at}_{r_at}'
            if kind == 'table':
                cells = [{'start_row_offset_idx': 0, 'start_col_offset_idx': 0, 'text': 'Item', 'column_header': True},
                         {'start_row_offset_idx': 0, 'start_col_offset_idx': 1, 'text': 'Value', 'column_header': True}]
                for i, (a, b) in enumerate(value, 1):
                    cells += [{'start_row_offset_idx': i, 'start_col_offset_idx': 0, 'text': a},
                              {'start_row_offset_idx': i, 'start_col_offset_idx': 1, 'text': b}]
                raw, text = {'data': {'table_cells': cells}}, ' '.join(a + ' ' + b for a, b in value)
            else:
                raw, text = {'text': value}, value
            evidence.append({'id': eid, 'type': kind, 'raw_object': raw, 'provenance': [{'page_no': page}]})
            cid = f'chunk_synthetic_{s_at}_{r_at}'
            chunks.append({'id': cid, 'section_id': sid, 'section_heading': heading, 'box': box,
                           'evidence_ids': [eid], 'text': text, 'source_sha256': MANUAL_SHA,
                           'index_text': heading + '\n' + (box + '\n' if box else '') + text})
            section['chunk_ids'].append(cid)
            section['evidence_ids'].append(eid)
            section['box_of'][eid] = box
        sections.append(section)
    for name, rows in (('chunks.jsonl', chunks), ('sections.jsonl', sections), ('evidence.jsonl', evidence),
                       ('pages.jsonl', [])):
        (root / name).write_text(''.join(json.dumps(r) + '\n' for r in rows), encoding='utf-8')
    np.save(root / 'embeddings.npy', np.array([features(c['index_text']) for c in chunks], dtype='float32'))
    (root / 'bm25.json').write_text(json.dumps(build_bm25(chunks)), encoding='utf-8')
    names = ('chunks.jsonl', 'sections.jsonl', 'embeddings.npy', 'bm25.json', 'evidence.jsonl', 'pages.jsonl')
    manifest = {'index_id': INDEX_ID, 'source_sha256': MANUAL_SHA, 'label': 'SYNTHETIC_TEST_FIXTURE',
                'embedding': {'model': 'synthetic-keyword-features', 'dimensions': 4},
                'sectioning': {'version': 'section-index-v1'}, 'file_sha256': {n: _sha(root / n) for n in names},
                'qa': {'chunks': len(chunks), 'sections': len(sections)}}
    (root / 'manifest.json').write_text(json.dumps(manifest, indent=1) + '\n', encoding='utf-8')
    return root


SOURCE_MANIFEST = {'manual_id': 'synthetic-manual', 'sha256': MANUAL_SHA.upper(), 'variant': 'Himalayan BS6',
                   'edition': 'synthetic-test-edition',
                   'oem_service_route': {'url': 'mailto:support@royalenfield.com', 'email': 'support@royalenfield.com',
                                         'verified': True, 'market': 'India'}}
