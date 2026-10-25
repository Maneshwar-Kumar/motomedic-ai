"""Synthetic maintainer receipt checks; no real approval, SDK or cloud actions."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
import tempfile
import types
import unittest
from unittest.mock import patch

from evidence_registry import content_hash
from tools import manage_primary_token_ceiling as tool
from cloud.grounded_generation.test_token_ceiling import fixtures, synthetic_owner_evidence
from cloud.grounded_generation.test_whole_turn_admission import Client, atomic
from cloud.grounded_generation.token_ceiling import ALLOCATION, GRANT_DOCUMENT, HAIKU_ALLOCATION, make_proposal


class MaintainerReceiptTests(unittest.TestCase):
    def test_timestamp_events_and_metadata_have_json_safe_complete_digests_without_raw_events(self):
        timestamp = datetime(2026, 10, 12, 12, 30, 1, 123456, tzinfo=timezone.utc)
        document = {'reserved_tokens': 123, 'created_at': timestamp, 'events': [
            {'at': timestamp, 'operation_id': 'synthetic-private-event', 'tokens': 7}],
            'unknown_metadata': {'bytes': b'\x00\xff', 'nonfinite': float('nan')}}
        before = deepcopy(document)
        audit = tool.document_audit(document, ('reserved_tokens',))
        encoded = json.dumps(audit, allow_nan=False)
        self.assertEqual(audit['event_count'], 1)
        self.assertTrue(audit['all_document_fields_in_digest'])
        self.assertEqual(audit['complete_document_sha256'], content_hash(tool.audit_value(document)))
        self.assertEqual(audit['complete_events_sha256'], content_hash(tool.audit_value(document['events'])))
        self.assertNotIn('synthetic-private-event', encoded)
        self.assertNotIn('created_at', encoded)
        self.assertEqual(document['created_at'], before['created_at'])
        self.assertEqual(document['events'], before['events'])

    def hosted_fixture(self, root):
        budget, ledgers = fixtures()
        proposal = make_proposal(budget, ledgers)
        owner_raw = synthetic_owner_evidence(proposal)
        owner = root / 'reports/public_evaluator/20261012/haiku_v10_13/synthetic_owner_approval.json'
        owner.parent.mkdir(parents=True);owner.write_bytes(owner_raw)
        proposal_path = root / 'proposal.json';proposal_path.write_text(json.dumps(proposal), encoding='utf-8')
        output = root / 'application.json'
        client = Client();client.documents = deepcopy(ledgers)
        timestamp = datetime(2026, 10, 12, tzinfo=timezone.utc)
        client.documents[ALLOCATION]['created_at'] = timestamp
        client.documents[HAIKU_ALLOCATION]['observed_at'] = timestamp
        client.documents['grounded-provider-global-v1'] = {'events': [{
            'at': timestamp, 'operation_id': 'synthetic-private-event', 'tokens': 9}], 'expires_at': timestamp}
        google = types.ModuleType('google');cloud = types.ModuleType('google.cloud')
        cloud.firestore = types.SimpleNamespace(transactional=atomic, Client=lambda project: client)
        google.cloud = cloud
        arguments = ['manage_primary_token_ceiling.py', 'apply-owner-approved', '--proposal', str(proposal_path),
            '--owner-evidence', str(owner), '--output', str(output)]
        return client, output, arguments, {'google': google, 'google.cloud': cloud}

    def test_timestamp_readbacks_cannot_fail_json_after_an_authorized_synthetic_transaction(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve();client, output, arguments, modules = self.hosted_fixture(root)
            before = deepcopy(client.documents)
            with patch.object(tool, 'ROOT', root), patch.dict('os.environ',
                    {'MOTOMEDIC_HOSTED_TOKEN_LIMIT_MAINTENANCE': 'true'}), \
                    patch('sys.argv', arguments), patch.dict('sys.modules', modules):
                tool.main()
            result = json.loads(output.read_bytes())
            pending = output.with_name('application_application_pending.json')
            self.assertTrue(pending.exists());self.assertTrue(result['owner_approved'])
            self.assertEqual(result['primary_readback']['scalars']['maximum_tokens'], 1050000)
            self.assertEqual(result['primary_readback']['scalars']['reserved_tokens'], 357663)
            self.assertEqual(result['shared_haiku_readback']['scalars']['reserved_nanodollars'], 28975875)
            self.assertEqual(result['rolling_usage_readback']['event_count'], 1)
            self.assertNotIn('synthetic-private-event', output.read_text())
            self.assertEqual(client.documents[HAIKU_ALLOCATION], before[HAIKU_ALLOCATION])
            self.assertEqual(client.documents['grounded-provider-global-v1'], before['grounded-provider-global-v1'])
            self.assertEqual(client.documents[ALLOCATION]['created_at'], before[ALLOCATION]['created_at'])
            self.assertIn(GRANT_DOCUMENT, client.documents)

    def test_pending_journal_retains_exact_action_if_unexpected_readback_type_prevents_final_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve();client, output, arguments, modules = self.hosted_fixture(root)
            client.documents[ALLOCATION]['synthetic_unsupported_metadata'] = object()
            with patch.object(tool, 'ROOT', root), patch.dict('os.environ',
                    {'MOTOMEDIC_HOSTED_TOKEN_LIMIT_MAINTENANCE': 'true'}), \
                    patch('sys.argv', arguments), patch.dict('sys.modules', modules):
                with self.assertRaisesRegex(ValueError, 'FIRESTORE_AUDIT_VALUE_UNSUPPORTED'):tool.main()
            self.assertFalse(output.exists())
            pending = json.loads(output.with_name('application_application_pending.json').read_bytes())
            self.assertEqual(pending['intended_maximum_tokens'], 1050000)
            self.assertEqual(client.documents[GRANT_DOCUMENT]['scope_sha256'], pending['grant_scope_sha256'])
            self.assertEqual(client.documents[ALLOCATION]['maximum_tokens'], 1050000)


if __name__ == '__main__':unittest.main()
