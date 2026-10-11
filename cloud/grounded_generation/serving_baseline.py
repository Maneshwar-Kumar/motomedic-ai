"""Deterministic immutable source/index identity before model loading or requests."""
import hashlib
import json
from pathlib import Path
from online_retrieve import RetrievalSystemError

VERSION = 'immutable-selected-baseline-v1'
MANUAL_SHA = 'cf221a29e2f9cd5af6e80a99774a697c814e8eda661c27d72e519d8a7e80da89'
INDEX_ID = 'index_a3282c4d98cf54595e4ba168'
INDEX_MANIFEST_SHA = '665121e286a22881803ec181597e860cdec8024412dbd334b2774b509cbabfde'


def validate_index(index_dir):
    root = Path(index_dir)
    raw = (root / 'manifest.json').read_bytes()
    if hashlib.sha256(raw).hexdigest() != INDEX_MANIFEST_SHA:
        raise RetrievalSystemError('IMMUTABLE_INDEX_MANIFEST_CHANGED')
    manifest = json.loads(raw)
    embedding = manifest['embedding']
    if (manifest['index_id'] != INDEX_ID or manifest['source_sha256'] != MANUAL_SHA
            or manifest['counts']['chunks'] != 532 or manifest['counts']['parent_sections'] != 277
            or manifest['counts']['pdf_pages'] != 149 or manifest['counts']['parser_gap_pages'] != [103]
            or manifest['parser'] != 'Docling' or manifest['chunker']['max_tokens'] != 1024
            or embedding['model'] != 'BAAI/bge-m3' or embedding['dimensions'] != 1024
            or embedding['revision'] != '5617a9f61b028005a4858fdac845db406aefb181'):
        raise RetrievalSystemError('IMMUTABLE_SOURCE_INDEX_VERSION_MISMATCH')
    return {'version': VERSION, 'index_id': INDEX_ID, 'manual_sha256': MANUAL_SHA,
            'index_manifest_sha256': INDEX_MANIFEST_SHA, 'parser_gap_pages': [103],
            'document_parse_calls': 0, 'document_embedding_calls': 0}
