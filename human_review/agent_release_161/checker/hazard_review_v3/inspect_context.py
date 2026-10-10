"""Inspect immutable inputs without printing unrelated full case plans."""
from pathlib import Path
import hashlib
import json

ROOT = Path(__file__).resolve().parents[4]
OUT = Path(__file__).resolve().parent
BASE = ROOT / 'human_review/agent_release_161'

def read(path):
    return json.loads(path.read_text(encoding='utf-8'))

def rawh(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    manifest_path = BASE / 'coordinator/release_manifest_v2.json'
    manifest = read(manifest_path)
    assert rawh(manifest_path) == '8d9330c551777f764d35f01b05ab9822db208abd6ba3cda618ec3fe35121554f'
    original_hashes = {name: rawh(ROOT / name) for name in manifest['outputs']}
    assert original_hashes == manifest['outputs']
    original_hashes[str(manifest_path.relative_to(ROOT)).replace('\\', '/')] = rawh(manifest_path)
    for path in (BASE / 'planner/plans').glob('*.json'):
        original_hashes[path.relative_to(ROOT).as_posix()] = rawh(path)
    for path in (ROOT / 'human_review/llm_judge_161').rglob('*'):
        if path.is_file():
            original_hashes[path.relative_to(ROOT).as_posix()] = rawh(path)
    original_hashes['source_manifest.json'] = rawh(ROOT / 'source_manifest.json')
    baseline = {
        'schema_version': 'independent-hazard-preservation-baseline-v3',
        'reviewer': '/root/hazard_checker',
        'source_release_manifest_sha256': rawh(manifest_path),
        'source_release_file_count': len(manifest['outputs']),
        'unchanged_history_file_hashes': original_hashes,
    }
    (OUT / 'preservation_baseline.json').write_text(json.dumps(baseline, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    corpus = read(ROOT / 'human_review/llm_judge_161/corpus.json')
    results = read(ROOT / 'human_review/llm_judge_161/results.json')
    print('Corpus keys:', list(corpus) if isinstance(corpus, dict) else 'list')
    print('Results keys:', list(results) if isinstance(results, dict) else 'list')
    for record_id in ('EXP001', 'EXP002'):
        plan = read(BASE / 'planner/plans' / f'{record_id}.json')
        case = plan['candidate_case']
        print(json.dumps({
            'record_id': record_id,
            'question': case.get('question'),
            'canonical_answer': case['canonical_answer'],
            'branch_context': case.get('branch_context'),
            'plan_keys': list(plan),
            'case_keys': list(case),
        }, ensure_ascii=True, indent=2))
    print('Preserved baseline files:', len(original_hashes))

if __name__ == '__main__':
    main()
