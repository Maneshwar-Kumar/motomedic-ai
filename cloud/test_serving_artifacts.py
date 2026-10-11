"""Synthetic provider-free artifact integrity, confinement and startup checks."""
import hashlib
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch
import cloud.serving_artifacts as artifacts

from cloud.serving_artifacts import (ArtifactError, GCSReader, ObjectReference,
    confined, digest, extract_snapshot, load_index, verify_index)


class Response(io.BytesIO):
    def __init__(self, body, generation='123'):
        super().__init__(body)
        self.headers = {'x-goog-generation': generation}


class Opener:
    def __init__(self, body, generation='123'):
        self.body, self.generation, self.requests = body, generation, []

    def open(self, request, timeout):
        self.requests.append(request)
        return Response(self.body, self.generation)


def reference(raw, **changes):
    value = dict(uri='gs://private-test-bucket/index/snapshot.tar.gz', generation='123',
        sha256=hashlib.sha256(raw).hexdigest(), maximum_bytes=1024 * 1024)
    value.update(changes)
    return ObjectReference(**value)


def archive(members):
    output = io.BytesIO()
    with tarfile.open(fileobj=output, mode='w:gz') as target:
        for name, raw, kind in members:
            item = tarfile.TarInfo(name)
            item.size = len(raw)
            if kind == 'link':
                item.type, item.linkname, item.size = tarfile.SYMTYPE, '../escape', 0
                target.addfile(item)
            elif kind == 'directory':
                item.type, item.size = tarfile.DIRTYPE, 0
                target.addfile(item)
            else:
                target.addfile(item, io.BytesIO(raw))
    return output.getvalue()


class ArtifactTests(unittest.TestCase):
    def test_exact_generation_hash_download_and_reuse(self):
        raw = b'immutable-index'
        opener = Opener(raw)
        reader = GCSReader(token=lambda: 'synthetic-token', opener=opener)
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'snapshot'
            self.assertEqual(reader.fetch(reference(raw), destination).read_bytes(), raw)
            reader.fetch(reference(raw), destination)
            self.assertEqual(len(opener.requests), 1)
            self.assertIn('generation=123', opener.requests[0].full_url)
            self.assertIn('ifGenerationMatch=123', opener.requests[0].full_url)
            self.assertIn('alt=media', opener.requests[0].full_url)
            destination.write_bytes(b'changed')
            with self.assertRaisesRegex(ArtifactError, 'EXISTING_ARTIFACT_CHANGED'):
                reader.fetch(reference(raw), destination)

    def test_wrong_generation_hash_or_size_never_installed(self):
        for raw, generation, changes, reason in (
                (b'changed', '123', {}, 'SHA256_MISMATCH'),
                (b'index', '124', {}, 'GENERATION_MISMATCH'),
                (b'index', '123', {'maximum_bytes': 4}, 'SIZE_BOUND_EXCEEDED')):
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as directory:
                destination = Path(directory) / 'snapshot'
                reader = GCSReader(token=lambda: 'synthetic-token', opener=Opener(raw, generation))
                with self.assertRaisesRegex(ArtifactError, reason):
                    reader.fetch(reference(b'index', **changes), destination)
                self.assertFalse(destination.exists())
                self.assertEqual(list(Path(directory).iterdir()), [])

    def test_generation_required_and_no_alternate_protocol(self):
        for changes in ({'generation': None}, {'generation': 'latest'}, {'generation': '0'},
                {'uri': 'https://attacker.test/snapshot'}, {'uri': 'gs://private-test-bucket/index#123'}):
            with self.subTest(changes=changes), self.assertRaises(ArtifactError):
                reference(b'index', **changes)

    def test_safe_archive_and_exact_bound_inventory(self):
        raw = archive([('.', b'', 'directory'), ('./a/data.json', b'{}', 'file')])
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / 'source.tar.gz'
            source.write_bytes(raw)
            destination = Path(directory) / 'index'
            extract_snapshot(source, destination)
            self.assertEqual((destination / 'a/data.json').read_bytes(), b'{}')
            with self.assertRaisesRegex(ArtifactError, 'ALREADY_EXISTS'):
                extract_snapshot(source, destination)

    def test_traversal_link_duplicate_and_expansion_rejected(self):
        for members, limits in (
                ([('../escape', b'bad', 'file')], {}),
                ([('a\\escape', b'bad', 'file')], {}),
                ([('C:/escape', b'bad', 'file')], {}),
                ([('link', b'', 'link')], {}),
                ([('x', b'a', 'file'), ('x', b'b', 'file')], {}),
                ([('x', b'12345', 'file')], {'maximum_expanded_bytes': 4}),
                ([('x', b'a', 'file'), ('y', b'b', 'file')], {'maximum_files': 1})):
            with self.subTest(members=members), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / 'source.tar.gz'
                source.write_bytes(archive(members))
                destination = Path(directory) / 'index'
                with self.assertRaises(ArtifactError):
                    extract_snapshot(source, destination, **limits)
                self.assertFalse(destination.exists())
                self.assertEqual([p.name for p in Path(directory).iterdir()], ['source.tar.gz'])

    def test_index_manifest_source_version_and_each_file_checked(self):
        with tempfile.TemporaryDirectory() as directory:
            index = Path(directory)
            (index / 'bm25.json').write_bytes(b'{}')
            manifest = {'index_id': 'synthetic-index', 'source_sha256': 'a' * 64,
                'embedding': {'model': 'synthetic-model', 'revision': 'frozen'},
                'chunker': {'max_tokens': 1024}, 'counts': {'chunks': 2, 'parent_sections': 1},
                'file_checksums': {'bm25.json': digest(index / 'bm25.json')}}
            (index / 'manifest.json').write_text(json.dumps(manifest), encoding='utf-8')
            expected = {'index_id': 'synthetic-index', 'manual_sha256': 'a' * 64,
                'embedding': manifest['embedding'], 'chunker': manifest['chunker'],
                'chunks': 2, 'parents': 1, 'manifest_sha256': digest(index / 'manifest.json'),
                'file_sha256': manifest['file_checksums']}
            verify_index(index, expected)
            (index / 'bm25.json').write_bytes(b'changed')
            with self.assertRaisesRegex(ArtifactError, 'INDEX_FILE_CHANGED'):
                verify_index(index, expected)
            (index / 'bm25.json').write_bytes(b'{}')
            (index / 'manifest.json').write_bytes(b'changed')
            with self.assertRaisesRegex(ArtifactError, 'INDEX_MANIFEST_CHANGED'):
                verify_index(index, expected)

    def test_unbound_generation_prevents_startup_before_network(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ArtifactError, 'GENERATION'):
                load_index({'index': {'snapshot': {'uri': 'gs://private-test-bucket/index',
                    'generation': None, 'sha256': 'a' * 64, 'maximum_bytes': 100}}}, directory)
            self.assertEqual(list(Path(directory).iterdir()), [])

    def recovery_fixture(self, index, *, version='1.19.1', lock_sha=None):
        (index/'qdrant').mkdir()
        (index/'bm25.json').write_bytes(b'{}')
        manifest={'index_id':'synthetic-index','source_sha256':'a'*64,
            'dependencies':{'qdrant-client':version},'embedding':{'revision':'synthetic'},
            'chunker':{'max_tokens':1024},'counts':{'chunks':2,'parent_sections':1},
            'file_checksums':{'bm25.json':digest(index/'bm25.json'),
                'qdrant/.lock':lock_sha or artifacts.QDRANT_LOCK_SHA256}}
        (index/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
        sha=digest(index/'manifest.json')
        expected={'index_id':'synthetic-index','manual_sha256':'a'*64,
            'embedding':manifest['embedding'],'chunker':manifest['chunker'],
            'chunks':2,'parents':1,'manifest_sha256':sha,'file_sha256':manifest['file_checksums']}
        return expected,sha

    def test_exact_deterministic_lock_recovery_retains_every_original_hash(self):
        with tempfile.TemporaryDirectory() as directory:
            index=Path(directory)
            expected,sha=self.recovery_fixture(index)
            original=(index/'manifest.json').read_bytes()
            with patch.object(artifacts,'ORIGINAL_INDEX_MANIFEST_SHA256',sha):
                expected['deterministic_file_recovery']=artifacts.qdrant_lock_policy()
                self.assertTrue(artifacts.restore_qdrant_lock(index,expected))
                self.assertEqual((index/'qdrant/.lock').read_bytes(),b'tmp lock file')
                self.assertEqual((index/'manifest.json').read_bytes(),original)
                verify_index(index,expected)
                self.assertFalse(artifacts.restore_qdrant_lock(index,expected))

    def test_recovery_rejects_missing_source_altered_existing_lock_or_policy(self):
        for change in ('missing-source','changed-source','nonempty-lock','empty-lock','policy','version','expected-hash','manifest'):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                index=Path(directory)
                expected,sha=self.recovery_fixture(index,
                    version='1.19.2' if change=='version' else '1.19.1',
                    lock_sha='b'*64 if change=='expected-hash' else None)
                with patch.object(artifacts,'ORIGINAL_INDEX_MANIFEST_SHA256',sha):
                    expected['deterministic_file_recovery']=artifacts.qdrant_lock_policy()
                    if change=='missing-source':
                        (index/'bm25.json').unlink()
                    elif change=='changed-source':
                        (index/'bm25.json').write_bytes(b'changed')
                    elif change in ('nonempty-lock','empty-lock'):
                        (index/'qdrant/.lock').write_bytes(b'changed' if change=='nonempty-lock' else b'')
                    elif change=='policy':
                        expected['deterministic_file_recovery']['path']='different.lock'
                    elif change=='manifest':
                        (index/'manifest.json').write_bytes(b'changed')
                    with self.assertRaises(ArtifactError):
                        artifacts.restore_qdrant_lock(index,expected)
                    if change not in ('nonempty-lock','empty-lock'):
                        self.assertFalse((index/'qdrant/.lock').exists())

    def test_startup_recovers_lock_only_after_snapshot_and_manifest_verification(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            source=root/'source'
            source.mkdir()
            expected,sha=self.recovery_fixture(source)
            raw=archive([('manifest.json',(source/'manifest.json').read_bytes(),'file'),
                         ('bm25.json',b'{}','file'),('qdrant',b'','directory')])
            expected['snapshot']=reference(raw).__dict__
            with patch.object(artifacts,'ORIGINAL_INDEX_MANIFEST_SHA256',sha):
                expected['deterministic_file_recovery']=artifacts.qdrant_lock_policy()
                for failure in ('archive','manifest','none'):
                    cache=root/failure
                    policy=dict(expected)
                    if failure=='manifest':
                        policy['manifest_sha256']='0'*64
                    reader=GCSReader(token=lambda:'synthetic-token',
                        opener=Opener(b'altered' if failure=='archive' else raw))
                    if failure=='none':
                        loaded=load_index({'index':policy},cache,reader)
                        self.assertEqual((loaded/'qdrant/.lock').read_bytes(),b'tmp lock file')
                        verify_index(loaded,policy)
                    else:
                        with self.assertRaises(ArtifactError):
                            load_index({'index':policy},cache,reader)
                        self.assertFalse((cache/'synthetic-index/qdrant/.lock').exists())


if __name__ == '__main__':
    unittest.main()
