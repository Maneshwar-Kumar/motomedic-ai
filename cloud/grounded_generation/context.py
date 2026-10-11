"""Complete content projection: remove duplicated layout coordinates, not text.

Original source objects and bounding boxes stay immutable in the registry. Every
projected object includes its full-object hash. Table cells retain every content
field, span and header flag; redundant grid copies and per-cell bboxes are removed.
Images, annotations, warnings, footnote/caption references are retained unchanged.
"""
from copy import deepcopy
from evidence_registry import content_hash

VERSION='complete-content-projection-v1'

def project(value):
    raw=deepcopy(value)
    raw.pop('prov',None) # Separate immutable server-owned provenance accompanies it.
    if raw.get('label')=='table':
        data=raw.get('data',{})
        if 'table_cells' in data:
            # Grid is the same cells expanded by row/column span, not extra facts.
            grid=data.get('grid')
            if grid is not None:
                cells=data['table_cells']
                if all(cell in cells for row in grid for cell in row): data.pop('grid')
                else:
                    # Retain unmatched cells, including parser-inserted empties.
                    for row in grid:
                        for cell in row: cell.pop('bbox',None)
            for cell in data['table_cells']: cell.pop('bbox',None)
            def columnar(cells):
                fields=sorted({key for cell in cells for key in cell})
                return {'fields':fields,'cells':[[[i,cell[key]] for i,key in enumerate(fields) if key in cell] for cell in cells]}
            data['table_cells']=columnar(data['table_cells'])
            if 'grid' in data:
                lengths=[len(row) for row in data['grid']]
                data['grid']={'row_lengths':lengths,**columnar([cell for row in data['grid'] for cell in row])}
    return {'content_projection':VERSION,'original_object_sha256':content_hash(value),'content':raw}
