"""Create an isolated byte-bound production build context; no model inference."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import sys
import subprocess

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from human_review.agent_release_161.approval_consumer import ApprovalConsumer

ROOT = Path(__file__).resolve().parents[1]
MODULES = ('approved_registry.py approved_runner.py reviewed_controller.py controller_contracts.py '
           'diagnose.py session_store.py constrained_generator.py generation_contracts.py '
           'generation_providers.py evidence_registry.py online_retrieve.py online_ingest.py '
           'retrieval_policy.py reviewed_cache.py gemini_transport.py '
           'human_review/agent_release_161/approval_consumer.py').split()

def sha(path):
    return hashlib.file_digest(path.open('rb'), 'sha256').hexdigest()

def prepare(destination):
    destination = destination.resolve()
    if not destination.is_relative_to(ROOT/'build') or destination.exists():
        raise ValueError('Use a new directory under workspace build/')
    old = json.loads((ROOT/'reports/ab30_v2_review.json').read_text())
    for name, digest in old['source_sha256'].items():
        if sha(ROOT/name) != digest:
            raise ValueError('Frozen source binding changed: '+name)
    names = set(old['source_sha256']) | set(MODULES)
    consumer=ApprovalConsumer(ROOT,'human_review/agent_release_161/coordinator/release_manifest_v3.json')
    for row in consumer.records.values():
        name=row['artifact_bindings']['planner_case_locator']['file']
        if sha(ROOT/name) != row['planner_file_sha256']:
            raise ValueError('Bound planner changed: '+name)
        names.add(name)
    names.update(str(p.relative_to(ROOT)).replace('\\','/') for p in (ROOT/'cloud/arm_a').glob('*')
                 if p.is_file() and not p.name.startswith('test_'))
    bindings = {}
    for name in sorted(names):
        target = destination/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT/name,target)
        bindings[name] = sha(target)
    index = ROOT/'build/index-bge-final'
    manifest = json.loads((index/'manifest.json').read_text())
    index_names = {'chunks.jsonl','parents.jsonl','evidence.jsonl','graph.json','bm25.json',
                   'embeddings.npy','manifest.json','reranker_manifest.json'}
    index_names.update(name for name in manifest['file_checksums'] if name.startswith('reranker_model/'))
    for name in sorted(index_names):
        origin = index/name
        if not origin.is_file():
            raise ValueError('Missing immutable index asset: '+name)
        if name in manifest['file_checksums'] and sha(origin) != manifest['file_checksums'][name]:
            raise ValueError('Immutable index mismatch: '+name)
        target = destination/'build/index'/name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origin,target)
        bindings['build/index/'+name] = sha(target)
    # Only manifest-bound reranker assets are reused. Query model assets are
    # downloaded at the pinned revision during the hosted image build.
    lock = {'schema_version':'arm-a-release-v1', 'created_at':datetime.now(timezone.utc).isoformat(),
            'source_authority':'OWNER_DELEGATED_AGENT_COORDINATOR_V3',
            'scope':'30 explicit reviewed initial LOOKUP routes; no adaptive UI',
            'architecture':'A_DETERMINISTIC_CANONICAL', 'provider_calls':0,
            'benchmark_pacing':False, 'streaming':'VERIFIED_COMPLETE_UNIT_SSE',
            'reranking':'conditional-rerank-v1', 'index_id':manifest['index_id'],
            'file_sha256':bindings}
    (destination/'arm_a_release.json').write_text(json.dumps(lock,indent=2)+'\n',encoding='utf-8')
    subprocess.run([sys.executable,'-B','-c',
        "from pathlib import Path; from approved_registry import ApprovedEvidenceRegistry; "
        "from online_retrieve import Retriever; r=Path.cwd(); "
        "registry=ApprovedEvidenceRegistry.load(r,r/'build/index'); "
        "retriever=Retriever(r/'build/index',embedding_model=object()); "
        "assert registry.source_ready() and len(retriever.chunks)==532; "
        "print('Isolated source and index preflight passed; zero inference.')"],
        cwd=destination,check=True)
    print(json.dumps({'context':str(destination),'bound_files':len(bindings),
                      'release_sha256':sha(destination/'arm_a_release.json')}))
    return lock

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('destination',type=Path)
    prepare(parser.parse_args().destination)
