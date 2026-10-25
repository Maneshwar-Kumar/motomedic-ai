"""Model input: the whole content section of each retrieved chunk, as plain labelled text.

No review gate, parser JSON, server-added warning displays or source-gap IDs. Each manual object
becomes one line with a short label ([E1], [E2], ...); the server keeps the label -> evidence ID and
page map. WARNING and CAUTION lines are the warnings the model must decide on.
"""
import json
from pathlib import Path
import re

VERSION = 'section-plain-text-v1'
WARNING_BOXES = ('WARNING', 'CAUTION')
_PRIVATE_USE = re.compile('[-]')
_SKIP = {'section_header', 'picture', 'page_header', 'page_footer'}


def clean(text):
    text = _PRIVATE_USE.sub('', text or '')
    text = re.sub(r'^\s*-\s+', '', text)
    return re.sub(r'[ \t]+', ' ', text).strip()


def table_lines(raw):
    """Rows as 'header: value' pairs when the table has column headers, else 'a: b' / 'a | b | c'."""
    data = raw.get('data') or {}
    grid = {}
    headers = {}
    for cell in data.get('table_cells', []):
        row, col, text = cell['start_row_offset_idx'], cell['start_col_offset_idx'], clean(cell.get('text'))
        if cell.get('column_header'):
            headers[col] = (headers.get(col, '') + ' ' + text).strip()
        elif text:
            grid.setdefault(row, {})[col] = text
    lines = []
    for row in sorted(grid):
        cells = grid[row]
        if headers:
            parts = [f'{headers[c]}: {v}' if headers.get(c) else v for c, v in sorted(cells.items())]
            lines.append('; '.join(parts))
        else:
            values = [v.rstrip(' .') for _, v in sorted(cells.items())]
            lines.append(': '.join(values) if len(values) == 2 else ' | '.join(values))
    return lines


def render(row):
    """Plain text for one manual object, or None when it carries no readable text."""
    if row['type'] in _SKIP:
        return None
    raw = row.get('raw_object') or {}
    if row['type'] == 'table':
        lines = table_lines(raw)
        return '\n    '.join(lines) if lines else None
    text = clean(raw.get('text'))
    return text or None


class SectionIndex:
    def __init__(self, index_dir):
        root = Path(index_dir)
        self.manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
        def read(name):
            with (root / name).open(encoding='utf-8') as handle:
                return [json.loads(line) for line in handle]
        self.chunks = {c['id']: c for c in read('chunks.jsonl')}
        self.sections = {s['id']: s for s in read('sections.jsonl')}
        self.evidence = {e['id']: e for e in read('evidence.jsonl')}


def assemble(index, chunk_ids):
    """Sections in retrieval order, each sent whole; returns text, label map and warning labels."""
    order = []
    for cid in chunk_ids:
        sid = index.chunks[cid]['section_id']
        if sid not in order:
            order.append(sid)
    objects, warnings, blocks = {}, [], []
    for sid in order:
        section = index.sections[sid]
        pages = section['pdf_pages']
        span = f'page {pages[0]}' if len(pages) == 1 else f'pages {pages[0]}-{pages[-1]}'
        lines = [f'## {clean(section["heading"]) or "Untitled section"} ({span})']
        for eid in section['evidence_ids']:
            row = index.evidence[eid]
            text = render(row)
            if text is None:
                continue
            label = f'E{len(objects) + 1}'
            box = section['box_of'].get(eid)
            obj_pages = sorted({p['page_no'] for p in row['provenance']})
            objects[label] = {'evidence_id': eid, 'text': text, 'pages': obj_pages, 'box': box,
                              'section': section['heading'], 'type': row['type']}
            if box in WARNING_BOXES:
                warnings.append(label)
            lines.append(f'[{label}] ' + (f'({box}) ' if box else '') + text)
        if len(lines) > 1:
            blocks.append('\n'.join(lines))
    return {'version': VERSION, 'index_id': index.manifest['index_id'], 'sections': order,
            'objects': objects, 'warnings': warnings, 'text': '\n\n'.join(blocks)}


def model_input(question, assembled, history=()):
    earlier = '\n'.join(f'- {h}' for h in history) if history else 'none'
    warnings = ', '.join(assembled['warnings']) or 'none'
    return (f'RIDER QUESTION: {question}\n\nEARLIER CONVERSATION: {earlier}\n\n'
            f'MANUAL SECTIONS:\n\n{assembled["text"]}\n\nWARNINGS TO DECIDE: {warnings}\n')
