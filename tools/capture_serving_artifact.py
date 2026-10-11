"""Read-only hosted capture of the already-recorded GCS snapshot generation.

Writes a new local receipt only after the selected generation's full SHA matches.
Uses managed ADC, not command-line access tokens. No providers or cloud mutations.
"""
import argparse
import json
from pathlib import Path
import sys
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from cloud.serving_artifacts import GCSReader, ObjectReference
from tools.serving_release import dump


def capture(root, destination, cache, reader=None):
    recorded = json.loads((Path(root) / 'cloud/deployment_status.json').read_bytes())
    parsed = urlsplit(recorded['snapshot_uri'])
    if parsed.scheme != 'gs' or parsed.query or parsed.fragment:
        raise ValueError('INVALID_RECORDED_GCS_URI')
    url = ('https://storage.googleapis.com/storage/v1/b/' + quote(parsed.netloc, safe='')
        + '/o/' + quote(parsed.path.lstrip('/'), safe=''))
    reader = reader or GCSReader()
    with reader.open(url) as response:
        metadata = json.loads(response.read(65537))
    reference = {'uri': recorded['snapshot_uri'], 'generation': metadata['generation'],
        'sha256': recorded['snapshot_sha256'], 'maximum_bytes': 1024**3}
    selected = ObjectReference(**reference)
    if int(metadata['size']) > selected.maximum_bytes:
        raise ValueError('RECORDED_SNAPSHOT_EXCEEDS_SIZE_BOUND')
    reader.fetch(selected, Path(cache) / ('snapshot-' + selected.sha256 + '.tar.gz'))
    dump(destination, reference)
    return reference


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True)
    parser.add_argument('--cache', default='build/serving-artifacts')
    args = parser.parse_args()
    result = capture(ROOT, Path(args.out), Path(args.cache))
    print(json.dumps({'generation': result['generation'], 'sha256_verified': result['sha256'],
        'provider_calls': 0, 'cloud_mutations': 0}))


if __name__ == '__main__':
    main()
