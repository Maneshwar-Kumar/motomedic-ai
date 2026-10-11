"""Provider-free projection preservation and immutable version-bound tests."""
from copy import deepcopy
import json
import os
from pathlib import Path
import tempfile
import unittest
from cloud.grounded_generation.serving_context import project, decode_table
from cloud.grounded_generation.context import project as legacy_project
from cloud.grounded_generation.test_context import decode_content, expected_content
from cloud.grounded_generation.serving_baseline import validate_index
from online_retrieve import RetrievalSystemError

ROOT = Path(__file__).resolve().parents[2]
INDEX = Path(os.environ.get('MOTOMEDIC_TEST_INDEX', str(ROOT / 'build/index-bge-final')))


class Tests(unittest.TestCase):
    def test_every_index_table_preserves_cell_content_and_missing_vs_null(self):
        evidence = map(json.loads, (INDEX / 'evidence.jsonl').read_text(encoding='utf-8').splitlines())
        tables = [row['raw_object'] for row in evidence if row['raw_object'].get('label') == 'table']
        self.assertTrue(tables)
        for raw in tables:
            projected = project(raw)['content']
            original = expected_content(raw)
            for field in ('table_cells', 'grid'):
                value = projected['data'].get(field)
                if not isinstance(value, dict) or 'rows' not in value:
                    continue
                decoded = decode_table(value)
                expected = original['data'][field]
                if field == 'grid': expected = [cell for row in expected for cell in row]
                self.assertEqual(decoded, expected)
            for key in ('captions', 'references', 'footnotes', 'annotations'):
                self.assertEqual(projected.get(key), original.get(key))

    def test_missing_null_false_and_distinct_original_text_survive(self):
        raw = {'label': 'table', 'text': 'rendered', 'orig': 'distinct original',
            'data': {'table_cells': [{'text': 'a', 'nullable': None, 'flag': False}, {'text': 'b'}]}}
        value = project(raw)['content']
        self.assertEqual(decode_table(value['data']['table_cells']), raw['data']['table_cells'])
        self.assertEqual(value['orig'], 'distinct original')

    def test_project_does_not_mutate_original(self):
        raw = {'self_ref': '#/texts/1', 'meta': None, 'children': [], 'label': 'text',
            'text': 'warning', 'orig': 'warning', 'references': [{'cref': '#/texts/2'}]}
        before = deepcopy(raw)
        result = project(raw)
        self.assertEqual(raw, before)
        self.assertTrue(result['content']['orig_same_as_text'])
        self.assertEqual(result['content']['references'], raw['references'])

    def test_pinned_index_manifest_and_explicit_page103_gap(self):
        receipt = validate_index(INDEX)
        self.assertEqual(receipt['parser_gap_pages'], [103])
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'manifest.json'
            path.write_bytes((INDEX / 'manifest.json').read_bytes() + b' ')
            with self.assertRaisesRegex(RetrievalSystemError, 'MANIFEST_CHANGED'):
                validate_index(path.parent)

    def test_real_object_table_projection_reduces_wire_without_losing_cells(self):
        objects = [json.loads(line)['raw_object'] for line in (INDEX / 'evidence.jsonl').read_text(encoding='utf-8').splitlines()]
        tables = [raw for raw in objects if raw.get('label') == 'table']
        old = sum(len(json.dumps(legacy_project(raw), ensure_ascii=False)) for raw in tables)
        new = sum(len(json.dumps(project(raw), ensure_ascii=False)) for raw in tables)
        self.assertLess(new, old)


if __name__ == '__main__': unittest.main()
