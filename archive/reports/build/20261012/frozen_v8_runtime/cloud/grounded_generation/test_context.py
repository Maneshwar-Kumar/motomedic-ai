"""Complete-content projection checks over immutable approved evidence.

These prove preservation of content fields under the frozen Docling schema,
not correct OCR/table interpretation or semantic support of generated claims.
"""
from copy import deepcopy
from pathlib import Path
import unittest
import os
from approved_registry import ApprovedEvidenceRegistry
from evidence_registry import content_hash
from cloud.grounded_generation.context import project,VERSION

ROOT=Path(__file__).resolve().parents[2]

def decode_content(value):
    content=deepcopy(value)
    def cells(encoded):
        fields=encoded['fields'];result=[]
        for entries in encoded['cells']:
            assert len({i for i,v in entries})==len(entries)
            assert all(type(i) is int and 0<=i<len(fields) for i,v in entries)
            result.append({fields[i]:v for i,v in entries})
        return result
    if content.get('label')=='table' and 'table_cells' in content.get('data',{}):
        data=content['data'];data['table_cells']=cells(data['table_cells'])
        if 'grid' in data:
            encoded=data['grid'];flat=cells(encoded);rows=[];at=0
            for length in encoded['row_lengths']:
                rows.append(flat[at:at+length]);at+=length
            assert at==len(flat)
            data['grid']=rows
    return content

def expected_content(raw):
    result=deepcopy(raw);result.pop('prov',None)
    if result.get('label')=='table' and 'table_cells' in result.get('data',{}):
        data=result['data'];grid=data.get('grid')
        if grid is not None:
            if all(cell in data['table_cells'] for row in grid for cell in row):data.pop('grid')
            else:
                for row in grid:
                    for cell in row:cell.pop('bbox',None)
        for cell in data['table_cells']:cell.pop('bbox',None)
    return result
class Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.registry=ApprovedEvidenceRegistry.load(ROOT,Path(os.environ.get('MOTOMEDIC_TEST_INDEX',str(ROOT/'build/index-bge-final'))))
        cls.approved={eid:e for eid,e in cls.registry.evidence.items() if cls.registry.evidence_ready(eid)}
        cls.tables={eid:e for eid,e in cls.approved.items() if e['raw_object'].get('label')=='table'}
        assert cls.approved and cls.tables
    def test_removed_provenance_is_identical_to_separate_runtime_provenance(self):
        for eid,evidence in self.approved.items():
            with self.subTest(evidence_id=eid):
                raw=evidence['raw_object']
                if 'prov' in raw:self.assertEqual(raw['prov'],evidence['provenance'])
    def test_every_approved_object_retains_complete_content_except_declared_duplicates(self):
        for eid,evidence in self.approved.items():
            with self.subTest(evidence_id=eid):
                raw=evidence['raw_object'];expected=expected_content(raw)
                actual=project(raw)
                self.assertEqual(decode_content(actual['content']),expected)
                self.assertEqual(actual['original_object_sha256'],content_hash(raw))
                self.assertEqual(actual['content_projection'],VERSION)
    def test_projection_cannot_mutate_source_or_return_shared_mutable_content(self):
        for eid,evidence in self.approved.items():
            raw=evidence['raw_object'];before=deepcopy(raw);result=project(raw)
            result['content']['test_injected_field']='test only'
            self.assertEqual(raw,before)
            self.assertNotIn('test_injected_field',project(raw)['content'])
    def test_every_table_cell_text_span_and_header_field_preserved(self):
        fields={'row_span','col_span','start_row_offset_idx','end_row_offset_idx',
            'start_col_offset_idx','end_col_offset_idx','text','column_header','row_header','row_section'}
        for eid,evidence in self.tables.items():
            with self.subTest(table=eid):
                raw=evidence['raw_object'];result=decode_content(project(raw)['content'])
                original=raw['data']['table_cells'];cells=result['data']['table_cells']
                self.assertEqual(len(cells),len(original))
                for before,after in zip(original,cells):
                    self.assertTrue(fields<=set(before))
                    self.assertEqual(after,{k:v for k,v in before.items() if k!='bbox'})
                self.assertEqual(result.get('data'),expected_content(raw).get('data'))
    def test_images_references_annotations_captions_and_footnotes_preserved(self):
        for eid,evidence in self.approved.items():
            raw=evidence['raw_object'];result=decode_content(project(raw)['content'])
            for field in ('image','annotations','captions','footnotes','references','meta','children','parent'):
                if field in raw:
                    with self.subTest(evidence_id=eid,field=field):self.assertEqual(result[field],raw[field])
    def test_grid_with_additional_content_and_empty_rows_is_retained(self):
        raw={'label':'table','data':{'table_cells':[{'text':'approved cell'}],
            'grid':[[{'text':'unbound additional fact'}],[],[{'text':'','row_span':1}]]}}
        self.assertEqual(decode_content(project(raw)['content']),raw)
    def test_columnar_missing_null_and_false_fields_remain_distinct(self):
        raw={'label':'table','data':{'table_cells':[{'text':'a','flag':False,'optional':None},
            {'text':'b','nested':{'reference':'r'},'spans':[1,2]}]}}
        self.assertEqual(decode_content(project(raw)['content']),raw)
    def test_non_table_nested_layout_fields_are_not_removed(self):
        raw={'label':'text','text':'warning text','bbox':[1,2,3,4],
            'data':{'table_cells':[{'bbox':[5,6,7,8],'text':'not a table'}],'grid':[['value']]}}
        self.assertEqual(project(raw)['content'],raw)

if __name__=='__main__':unittest.main()
