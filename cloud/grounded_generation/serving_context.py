"""Compact complete object projection; originals remain immutable and server bound.

Only redundant layout and empty parser metadata are omitted. Source text, distinct
orig text, units, table positions/spans/header flags, captions and references stay.
Table cells use fields + rows; missing fields are recorded separately from null.
"""
from copy import deepcopy
from cloud.grounded_generation.context import project as complete_project

VERSION = 'complete-reviewed-object-projection-v2'


def project(raw):
    value = complete_project(raw)
    content = value['content']
    # These are parser object identity/layout fields, not source content. The
    # original hash and registry preserve them for exact binding/inspection.
    content.pop('self_ref', None)
    for key in ('meta', 'formatting', 'hyperlink'):
        if content.get(key, object()) is None:
            content.pop(key)
    if content.get('children') == []:
        content.pop('children')
    if content.get('orig') == content.get('text') and 'orig' in content:
        content.pop('orig')
        content['orig_same_as_text'] = True
    if content.get('label') == 'table':
        data = content.get('data', {})
        for key in ('table_cells', 'grid'):
            encoded = data.get(key)
            if not isinstance(encoded, dict) or not {'fields', 'cells'} <= encoded.keys():
                continue
            fields = encoded['fields']
            rows, missing = [], {}
            for at, cells in enumerate(encoded.pop('cells')):
                cell = dict(cells)
                rows.append([cell.get(i) for i in range(len(fields))])
                absent = [i for i in range(len(fields)) if i not in cell]
                if absent:
                    missing[str(at)] = absent
            encoded['rows'] = rows
            if missing:
                encoded['missing'] = missing
    value['content_projection'] = VERSION
    return value


def decode_table(encoded):
    """Inspection/test helper proving field absence remains distinct from null."""
    fields = encoded['fields']
    return [{field: deepcopy(row[i]) for i, field in enumerate(fields)
             if i not in encoded.get('missing', {}).get(str(at), [])}
            for at, row in enumerate(encoded['rows'])]
