"""Hosted image build: package pinned model assets, never re-embed manual text."""
import json
from pathlib import Path
from sentence_transformers import SentenceTransformer, CrossEncoder

index = Path('/app/build/index')
manifest = json.loads((index/'manifest.json').read_text())
model = manifest['embedding']
SentenceTransformer(model['model'], revision=model['revision'], device='cpu').save(str(index/'embedding_model'))
if not (index/'reranker_model').exists():
    reranker = json.loads((index/'reranker_manifest.json').read_text())
    CrossEncoder(reranker['model'], revision=reranker['revision'], device='cpu').save(str(index/'reranker_model'))
print('Pinned query and reranker assets packaged; document embeddings unchanged.')
