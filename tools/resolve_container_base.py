"""Resolve an official public Docker Hub image tag to an immutable OCI digest.

Only anonymous public registry reads occur. The registry token is not persisted.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def resolve(repository, tag):
    if not re.fullmatch(r'library/[a-z0-9._-]+', repository) or not re.fullmatch(r'[A-Za-z0-9._-]+', tag):
        raise ValueError('OFFICIAL_PUBLIC_IMAGE_REQUIRED')
    token_url = 'https://auth.docker.io/token?' + urlencode({
        'service': 'registry.docker.io', 'scope': 'repository:' + repository + ':pull'})
    with urlopen(token_url, timeout=30) as response:
        token = json.loads(response.read(65536))['token']
    request = Request('https://registry-1.docker.io/v2/' + repository + '/manifests/' + tag,
        headers={'Authorization': 'Bearer ' + token,
            'Accept': 'application/vnd.oci.image.index.v1+json, application/vnd.docker.distribution.manifest.list.v2+json'})
    with urlopen(request, timeout=30) as response:
        raw = response.read(1024 * 1024)
        advertised = response.headers['Docker-Content-Digest']
    actual = 'sha256:' + hashlib.sha256(raw).hexdigest()
    if actual != advertised:
        raise ValueError('REGISTRY_MANIFEST_HASH_MISMATCH')
    return {'schema_version': 'public-container-base-resolution-v1',
        'tag': repository + ':' + tag, 'image': 'docker.io/' + repository + '@' + actual,
        'registry_manifest_sha256': actual.removeprefix('sha256:'),
        'platform': 'linux/amd64', 'authenticated_account_used': False,
        'registry_reads_only': True, 'build_executed': False, 'provider_calls': 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', default='library/python')
    parser.add_argument('--tag', default='3.12-slim')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    result = resolve(args.repository, args.tag)
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError('NEVER_OVERWRITE_BASE_IMAGE_RECEIPT')
    target.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'image': result['image'], 'provider_calls': 0, 'cloud_mutations': 0}))


if __name__ == '__main__':
    main()
