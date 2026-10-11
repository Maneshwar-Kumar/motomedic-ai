"""Generation-pinned private GCS snapshots, loaded once before serving requests.

No ingestion, embedding, provider calls or rider-facing source delivery occurs here.
The REST transport uses workload ADC; tokens and raw remote errors are never logged.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
import tempfile
from urllib.parse import quote, urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler


class ArtifactError(RuntimeError):
    pass


ORIGINAL_INDEX_MANIFEST_SHA256 = '665121e286a22881803ec181597e860cdec8024412dbd334b2774b509cbabfde'
QDRANT_LOCK_PATH = 'qdrant/.lock'
QDRANT_LOCK_BYTES = b'tmp lock file'
QDRANT_LOCK_SHA256 = '67a987c432005e3afcc13a871b3ddabaeee0f4504058da65b0769016d3083b44'


def qdrant_lock_policy():
    return {'schema_version':'qdrant-client-1.19.1-exact-lock-recovery-v1',
        'path':QDRANT_LOCK_PATH, 'sha256':QDRANT_LOCK_SHA256,
        'utf8_content':'tmp lock file', 'byte_length':12,
        'dependency':{'qdrant-client':'1.19.1'},
        'original_manifest_sha256':ORIGINAL_INDEX_MANIFEST_SHA256,
        'origin_receipt':'reports/build/20261012/qdrant_lock_recovery.json',
        'scope':'Only missing deterministic process-lock bytes; never source/index content or a checksum exclusion.'}


def digest(path):
    checksum = hashlib.sha256()
    with Path(path).open('rb') as source:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            checksum.update(block)
    return checksum.hexdigest()


def confined(root, name):
    """Portable names reject traversal, Windows drive paths and separator tricks."""
    if (not isinstance(name, str) or not name or '\\' in name or ':' in name
            or name.startswith('/') or any(p in ('', '.', '..') for p in name.split('/'))):
        raise ArtifactError('UNSAFE_ARTIFACT_PATH')
    result = Path(root) / name
    if not result.resolve().is_relative_to(Path(root).resolve()):
        raise ArtifactError('UNSAFE_ARTIFACT_PATH')
    return result


@dataclass(frozen=True)
class ObjectReference:
    uri: str
    generation: str
    sha256: str
    maximum_bytes: int

    def __post_init__(self):
        parsed = urlsplit(self.uri)
        if (parsed.scheme != 'gs' or not parsed.netloc or not parsed.path.strip('/')
                or parsed.query or parsed.fragment or '@' in parsed.netloc
                or not re.fullmatch(r'[a-z0-9][a-z0-9._-]{1,221}[a-z0-9]', parsed.netloc)):
            raise ArtifactError('INVALID_GCS_REFERENCE')
        if not isinstance(self.generation, str) or not re.fullmatch(r'[1-9][0-9]{0,24}', self.generation):
            raise ArtifactError('MISSING_OR_INVALID_OBJECT_GENERATION')
        if not isinstance(self.sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', self.sha256):
            raise ArtifactError('INVALID_ARTIFACT_SHA256')
        if type(self.maximum_bytes) is not int or not 0 < self.maximum_bytes <= 4 * 1024**3:
            raise ArtifactError('INVALID_ARTIFACT_SIZE_BOUND')

    def url(self, *, media=False):
        parsed = urlsplit(self.uri)
        query = {'generation': self.generation, 'ifGenerationMatch': self.generation}
        if media:
            query['alt'] = 'media'
        return ('https://storage.googleapis.com/storage/v1/b/' + quote(parsed.netloc, safe='')
                + '/o/' + quote(parsed.path.lstrip('/'), safe='') + '?' + urlencode(query))


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ArtifactError('ARTIFACT_REDIRECT_REJECTED')


def workload_token():
    import google.auth
    from google.auth.transport.requests import Request as AuthRequest
    credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/devstorage.read_only'])
    credentials.refresh(AuthRequest())
    return credentials.token


class GCSReader:
    def __init__(self, token=workload_token, opener=None):
        self.token = token
        self.opener = opener or build_opener(NoRedirect())

    def open(self, url):
        try:
            token = self.token()
            if not isinstance(token, str) or not token or '\r' in token or '\n' in token:
                raise ArtifactError('ARTIFACT_AUTH_UNAVAILABLE')
            return self.opener.open(Request(url, headers={'Authorization': 'Bearer ' + token}), timeout=60)
        except ArtifactError:
            raise
        except Exception:
            raise ArtifactError('ARTIFACT_STORE_UNAVAILABLE') from None

    def fetch(self, reference, destination):
        """Hash and bound the full generation before atomic installation; no retries."""
        if not isinstance(reference, ObjectReference):
            raise ArtifactError('BOUND_OBJECT_REFERENCE_REQUIRED')
        destination = Path(destination)
        if destination.exists():
            if destination.is_file() and destination.stat().st_size <= reference.maximum_bytes and digest(destination) == reference.sha256:
                return destination
            raise ArtifactError('EXISTING_ARTIFACT_CHANGED')
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as target:
                temporary = Path(target.name)
                checksum, total = hashlib.sha256(), 0
                with self.open(reference.url(media=True)) as response:
                    reported_generation = response.headers.get('x-goog-generation')
                    if reported_generation is not None and reported_generation != reference.generation:
                        raise ArtifactError('OBJECT_GENERATION_MISMATCH')
                    while True:
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        total += len(block)
                        if total > reference.maximum_bytes:
                            raise ArtifactError('ARTIFACT_SIZE_BOUND_EXCEEDED')
                        checksum.update(block)
                        target.write(block)
                if checksum.hexdigest() != reference.sha256:
                    raise ArtifactError('ARTIFACT_SHA256_MISMATCH')
                target.flush()
                os.fsync(target.fileno())
            # Hard-link refuses to replace a concurrently installed destination.
            try:
                os.link(temporary, destination)
            except FileExistsError:
                if digest(destination) != reference.sha256:
                    raise ArtifactError('CONCURRENT_ARTIFACT_CHANGED')
            return destination
        except ArtifactError:
            raise
        except Exception:
            raise ArtifactError('ARTIFACT_LOAD_FAILED') from None
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)


def extract_snapshot(archive, destination, *, maximum_files=20000, maximum_expanded_bytes=4 * 1024**3):
    """All members checked before extraction; no links, devices or overwrites."""
    destination = Path(destination)
    if destination.exists():
        raise ArtifactError('SNAPSHOT_DESTINATION_ALREADY_EXISTS')
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='index-stage-', dir=destination.parent))
    try:
        with tarfile.open(archive, 'r:gz') as source:
            members = source.getmembers()
            if len(members) > maximum_files:
                raise ArtifactError('SNAPSHOT_FILE_BOUND_EXCEEDED')
            names, total = set(), 0
            for member in members:
                # Historical GNU archives may prefix their portable paths with ./.
                name = member.name.removeprefix('./').rstrip('/')
                if name in ('', '.') and member.isdir():
                    continue
                confined(staging, name)
                if name in names or not (member.isdir() or member.isfile()):
                    raise ArtifactError('SNAPSHOT_UNSAFE_OR_DUPLICATE_MEMBER')
                names.add(name)
                total += member.size
                if total > maximum_expanded_bytes:
                    raise ArtifactError('SNAPSHOT_EXPANSION_BOUND_EXCEEDED')
            for member in members:
                name = member.name.removeprefix('./').rstrip('/')
                if name in ('', '.'):
                    continue
                target = confined(staging, name)
                if member.isdir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    stream = source.extractfile(member)
                    if stream is None:
                        raise ArtifactError('SNAPSHOT_FILE_UNREADABLE')
                    with stream, target.open('xb') as output:
                        shutil.copyfileobj(stream, output)
        staging.rename(destination)
        return destination
    except ArtifactError:
        raise
    except Exception:
        raise ArtifactError('SNAPSHOT_EXTRACTION_FAILED') from None
    finally:
        if staging.exists():
            shutil.rmtree(staging)


def verify_index_metadata(index, expected):
    """Verify the exact original manifest before any declared recovery or use."""
    index = Path(index)
    if digest(index / 'manifest.json') != expected['manifest_sha256']:
        raise ArtifactError('INDEX_MANIFEST_CHANGED')
    manifest = json.loads((index / 'manifest.json').read_bytes())
    if (manifest['index_id'] != expected['index_id']
            or manifest['source_sha256'] != expected['manual_sha256']
            or manifest['embedding'] != expected['embedding']
            or manifest['chunker'] != expected['chunker']
            or manifest['counts']['chunks'] != expected['chunks']
            or manifest['counts']['parent_sections'] != expected['parents']):
        raise ArtifactError('INDEX_IDENTITY_MISMATCH')
    if manifest['file_checksums'] != expected['file_sha256']:
        raise ArtifactError('INDEX_INVENTORY_CHANGED')
    return manifest


def restore_qdrant_lock(index, expected):
    """Recover just the pinned client's known literal, retaining all original hashes."""
    if expected.get('deterministic_file_recovery') != qdrant_lock_policy():
        raise ArtifactError('QDRANT_LOCK_RECOVERY_POLICY_CHANGED')
    if expected.get('manifest_sha256') != ORIGINAL_INDEX_MANIFEST_SHA256:
        raise ArtifactError('QDRANT_LOCK_ORIGINAL_MANIFEST_REQUIRED')
    manifest = verify_index_metadata(index, expected)
    if (manifest.get('dependencies', {}).get('qdrant-client') != '1.19.1'
            or manifest['file_checksums'].get(QDRANT_LOCK_PATH) != QDRANT_LOCK_SHA256
            or hashlib.sha256(QDRANT_LOCK_BYTES).hexdigest() != QDRANT_LOCK_SHA256):
        raise ArtifactError('QDRANT_LOCK_ORIGINAL_BINDING_CHANGED')
    # Missing or changed source/index files can never trigger a reconstruction.
    for name, checksum in expected['file_sha256'].items():
        if name == QDRANT_LOCK_PATH:
            continue
        target = confined(index, name)
        if not target.is_file() or digest(target) != checksum:
            raise ArtifactError('INDEX_FILE_MISSING_OR_CHANGED:' + name)
    target = confined(index, QDRANT_LOCK_PATH)
    if target.exists():
        if not target.is_file() or digest(target) != QDRANT_LOCK_SHA256:
            raise ArtifactError('EXISTING_QDRANT_LOCK_CHANGED')
        return False
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        with target.open('xb') as output:
            output.write(QDRANT_LOCK_BYTES)
    except FileExistsError:
        if not target.is_file() or digest(target) != QDRANT_LOCK_SHA256:
            raise ArtifactError('EXISTING_QDRANT_LOCK_CHANGED') from None
    if digest(target) != QDRANT_LOCK_SHA256:
        raise ArtifactError('QDRANT_LOCK_RECOVERY_FAILED')
    return True


def verify_index(index, expected):
    """Check identity and every expected sparse/source/model artifact before startup."""
    manifest = verify_index_metadata(index, expected)
    for name, checksum in expected['file_sha256'].items():
        if digest(confined(index, name)) != checksum:
            raise ArtifactError('INDEX_FILE_CHANGED:' + name)
    return manifest


def load_index(release, cache, reader=None):
    """Call only at worker startup, before request handling and provider creation."""
    index_policy = release['index']
    reference = ObjectReference(**index_policy['snapshot'])
    cache = Path(cache)
    archive = cache / ('snapshot-' + reference.sha256 + '.tar.gz')
    (reader or GCSReader()).fetch(reference, archive)
    index = cache / index_policy['index_id']
    if not index.exists():
        extract_snapshot(archive, index)
    # Never trust an existing local directory merely because its name matches.
    try:
        restore_qdrant_lock(index, index_policy)
        verify_index(index, index_policy)
    except (OSError, ValueError, KeyError, TypeError):
        raise ArtifactError('INDEX_VALIDATION_FAILED') from None
    return index
