"""Read-only producer audit and engineering-only grounding fixture export.

This does not adjudicate OEM claims, approve evidence, or call a provider.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys


def sha(data):
    return hashlib.sha256(data).hexdigest()


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def read(root, relative):
    path = (root / relative).resolve()
    require(path.is_relative_to(root), "Path escapes workspace")
    data = path.read_bytes()
    return json.loads(data), sha(data)


def audit(root, index):
    root = root.resolve()
    sys.path.insert(0, str(root / 'human_review/record_workflow'))
    from batch_loop import Batch, ACTORS, TERMINAL
    from workflow import encoded
    batch = Batch(root)
    spec = batch.spec()
    state = batch.status()
    current = {r['record_id']: r for r in state['records']}
    manifest, manifest_sha = read(root, 'human_review/record_workflow/batch_100_completion.json')
    require(manifest['schema_version'] == 1 and manifest['all_terminal'] is True, 'Invalid completion schema')
    require(manifest['expected_count'] == manifest['actual_unique_count'] == 100, 'Invalid batch count')
    require(manifest['status'] in ('COMPLETE_AGENT_LOOP', 'COMPLETE_AGENT_LOOP_WITH_EXPLICIT_BLOCKS'), 'Batch not complete')
    records = manifest['records']
    require(len(records) == len({r['record_id'] for r in records}) == 100, 'Duplicate or missing record')
    require({r['record_id'] for r in records} == set(spec['ids']), 'Reserved IDs mismatch')
    require(manifest['batch_context_sha256'] == spec['batch_context_sha256'], 'Context mismatch')
    catalogue = (root / manifest['catalogue_path']).read_bytes()
    require(sha(catalogue) == manifest['catalogue_sha256'], 'Catalogue changed')
    catalogue_text = catalogue.decode('utf-8')
    counts = [sum(line.startswith(prefix) for line in catalogue_text.splitlines())
              for prefix in ('### Original ', '### EXP', '### GEN')]
    require(counts == [11, 50, 100] and manifest['total_catalogue_record_count'] == 161, 'Catalogue count mismatch')
    source, source_sha = read(root, 'source_manifest.json')
    require(source['sha256'].lower() == manifest['manual_sha256'] == spec['manual_sha256'], 'Manual version mismatch')
    require(sha((root / source['file']).read_bytes()) == manifest['manual_sha256'], 'Manual bytes changed')
    # Check every current index file, using the same manifest integrity contract as Retriever.
    index_manifest = json.loads((index / 'manifest.json').read_bytes())
    require(index_manifest['index_id'] == 'index_a3282c4d98cf54595e4ba168', 'Unexpected index')
    require(index_manifest['source_sha256'] == manifest['manual_sha256'], 'Index/manual mismatch')
    for name in ('chunks.jsonl', 'parents.jsonl', 'evidence.jsonl', 'graph.json', 'bm25.json', 'embeddings.npy'):
        expected = index_manifest['file_checksums'][name]
        path = (index / name).resolve()
        require(path.is_relative_to(index.resolve()), 'Index path escapes snapshot')
        require(sha(path.read_bytes()) == expected, 'Index integrity failure: ' + name)
    by_page = defaultdict(list)
    for line in (index / 'evidence.jsonl').read_text(encoding='utf-8').splitlines():
        obj = json.loads(line)
        require(obj['source_sha256'] == manifest['manual_sha256'], 'Evidence checksum mismatch')
        for page in {p['page_no'] for p in obj.get('provenance', [])}:
            by_page[page].append({'evidence_id': obj['id'], 'type': obj['type'],
                                  'review_status': obj.get('review_status', 'MISSING')})
    fixtures, diagnostic_rows, intents = [], [], set()
    for record in records:
        rid, version = record['record_id'], record['version']
        latest = current[rid]
        require(latest['version'] == version and latest['state'] == record['terminal_disposition']
                and latest['state'] in TERMINAL, rid + ': stale/nonterminal version')
        require(set(latest['roles']) == set(ACTORS), rid + ': missing independent role')
        payloads = {}
        for role, prefix in (('author', 'draft'), ('reviewer', 'review'), ('judge', 'judge')):
            payload, digest = read(root, record[prefix + '_path'])
            require(digest == record[prefix + '_sha256'] == latest['roles'][role]['payload_sha256'], rid + ': hash mismatch')
            require(batch.store.object(digest) == (root / record[prefix + '_path']).read_bytes(), rid + ': frozen object mismatch')
            require(payload['record_id'] == rid and payload['version'] == version
                    and payload['actor'] == ACTORS[role] and payload['role'] == role, rid + ': actor/version mismatch')
            require(payload['manual_sha256'].lower() == manifest['manual_sha256']
                    and payload['batch_context_sha256'] == spec['batch_context_sha256'], rid + ': context/source mismatch')
            payloads[role] = payload
        author, review, judge = (payloads[r] for r in ('author', 'reviewer', 'judge'))
        require(review['author_sha256'] == judge['author_sha256'] == record['draft_sha256']
                and judge['review_sha256'] == record['review_sha256'], rid + ': judgement binding mismatch')
        require(review['independent_original_review'] is True and judge['independent_original_review'] is True,
                rid + ': independent agent inspection missing')
        require(judge['verdict'] == record['terminal_disposition'], rid + ': disposition mismatch')
        require(author['expected_route'] == record['expected_route'], rid + ': route changed')
        intent = author['distinctive_intent'].strip().casefold()
        require(intent and intent not in intents, rid + ': duplicate intent label')
        intents.add(intent)
        require(f'### {rid} v{version}' in catalogue_text and record['judge_sha256'] in catalogue_text,
                rid + ': catalogue binding missing')
        require(record['formal_source_approval'] == 'PENDING' and record['runtime_authorized'] is False,
                rid + ': unexpected approval; separate review needed')
        for card in record['blocker_card_paths']:
            path = (root / card).resolve()
            require(path.is_relative_to((root / 'human_review/blockers').resolve()) and path.is_file(),
                    rid + ': blocker handoff missing')
        pages = sorted({ref['pdf_page'] for ref in author.get('source_refs', [])})
        candidates = {str(page): by_page.get(page, []) for page in pages}
        missing_pages = [page for page in pages if not candidates[str(page)]]
        unresolved_ids = [ref['pdf_page'] for ref in author.get('source_refs', []) if not ref.get('evidence_ids')]
        # Copy authored fields verbatim into private fixtures. No inferred outcome enum, warning or dependency.
        fixture = {k: author.get(k) for k in ('record_id', 'version', 'question', 'answer', 'turns',
                    'scenario_setup', 'case_type', 'expected_route', 'conditions', 'warnings',
                    'source_refs', 'policy_refs', 'forbidden_claims', 'stopping_rules', 'source_limits',
                    'changes', 'feedback_disposition')}
        fixture.update(manual_sha256=manifest['manual_sha256'], index_id=index_manifest['index_id'],
                       batch_completion_sha256=manifest_sha, draft_sha256=record['draft_sha256'],
                       review_sha256=record['review_sha256'], judge_sha256=record['judge_sha256'],
                       blocker_card_paths=record['blocker_card_paths'], candidate_objects_by_page=candidates,
                       page_mapping_authorizes_claims=False, formal_source_approval=False,
                       runtime_authorized=False, dataset_partition='FEEDBACK_TUNED_REGRESSION_NOT_HELD_OUT',
                       typed_session_fixture_status='NOT_COMPILED_OR_APPROVED')
        fixtures.append(fixture)
        diagnostic_rows.append({'record_id': rid, 'version': version, 'expected_route': author['expected_route'],
            'required_source_pages': pages, 'pages_without_candidate_objects': missing_pages,
            'source_refs_without_exact_evidence_ids': unresolved_ids,
            'candidate_object_count': sum(map(len, candidates.values())),
            'blocker_card_paths': record['blocker_card_paths'],
            'grounding_readiness': 'BLOCKED_PENDING_FORMAL_SOURCE_AND_DEPENDENCY_REVIEW',
            'live_calls': 0})
    require(dict(Counter(r['terminal_disposition'] for r in records)) == manifest['counts'], 'Terminal counts changed')
    events = batch.store.ledger()
    require(any(e['kind'] == 'BATCH_COMPLETED' and e['payload']['manifest_sha256'] == sha(encoded(manifest))
                for e in events), 'Completion is not bound to ledger')
    context_files = ['AGENTS.md', 'source_manifest.json', 'GEMMA_CONTROLLER_HANDOFF.md',
                     'human_review/subagent_feedback.md', 'human_review/record_id_verification.md',
                     'human_review/blockers/WORKFLOW_INDEX.md',
                     '01_Concept_Architecture.docx', '02_PRD.docx', '03_TRD.docx',
                     '04_To_Build_Evaluation_Decisions.docx',
                     'registry/review_decisions.json', 'registry/reconciled-accepted-eleven/review_decisions.json']
    report = {'schema_version': 'batch-grounding-readiness-v1', 'checked_at_utc': datetime.now(timezone.utc).isoformat(),
              'completion_verified': True, 'completion_manifest_sha256': manifest_sha,
              'catalogue_sha256': manifest['catalogue_sha256'], 'catalogue_record_count': 161,
              'grounding_fixture_count': len(fixtures), 'agent_terminal_counts': manifest['counts'],
              'expected_route_counts': dict(Counter(f['expected_route'] for f in fixtures)),
              'manual_sha256': manifest['manual_sha256'], 'index_id': index_manifest['index_id'],
              'source_manifest_sha256': source_sha,
              'input_context_hashes': {p: sha((root / p).read_bytes()) for p in context_files},
              'audit_code_sha256': sha(Path(__file__).read_bytes()),
              'records': diagnostic_rows, 'provider_calls': 0, 'formal_approvals_created': 0,
              'semantic_accuracy': 'NOT_EVALUATED', 'complete_evidence_recall': 'NOT_EVALUATED',
              'retrieval_ranking': 'NOT_EVALUATED_PAGE_OBJECT_MAPPING_ONLY',
              'controller_grounding_for_new_ids': 'PENDING_REFINEMENT_CHAT_TYPED_FIXTURES',
              'release_approved': False, 'index_rebuilt': False,
              'billing_or_deployment_changed': False, 'selected_model': 'gemma-4-31b-it'}
    # Fail closed if the producer changed during this audit.
    require(sha((root / 'human_review/record_workflow/batch_100_completion.json').read_bytes()) == manifest_sha,
            'Completion changed during audit')
    require(sha((root / manifest['catalogue_path']).read_bytes()) == manifest['catalogue_sha256'],
            'Catalogue changed during audit')
    return fixtures, report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--index', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    fixtures, report = audit(root, args.index.resolve())
    args.output.mkdir(parents=True, exist_ok=True)
    for name, payload in (('fixtures.json', {'schema_version': 'batch-grounding-fixtures-v1', 'records': fixtures}),
                          ('readiness.json', report)):
        (args.output / name).write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False)+'\n', encoding='utf-8')
    print(json.dumps({'completion_verified': True, 'fixtures': len(fixtures), 'provider_calls': 0,
                      'routes': report['expected_route_counts']}))


if __name__ == '__main__':
    main()
