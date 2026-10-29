"""Hosted-only bridge from the existing GitHub Anthropic key secret to the managed secret the
generation call reads (resource name motomedic-evaluator-anthropic-v1, kept from its first use).

The restricted federated service account can add versions to this exact secret;
it cannot read secret values, deploy services, change billing or run providers.
"""
import base64
import json
import os
from pathlib import Path
import google.auth
from google.auth.transport.requests import AuthorizedSession

SECRET = 'projects/motomedic-ai-20261009/secrets/motomedic-evaluator-anthropic-v1'
CANONICAL_SECRET = 'projects/279945185781/secrets/motomedic-evaluator-anthropic-v1'


def main():
    if (os.environ.get('GITHUB_ACTIONS') != 'true' or
            os.environ.get('GITHUB_REPOSITORY') != 'Maneshwar-Kumar/motomedic-ai' or
            os.environ.get('GITHUB_REF') not in ('refs/heads/codex/public-evaluator', 'refs/heads/main')):
        raise RuntimeError('Exact hosted repository scope required')
    key = os.environ.get('ANTHROPIC_API_KEY', '')
    if not key or len(key) > 4096:
        raise RuntimeError('Existing Anthropic repository secret is required')
    credentials, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
    with AuthorizedSession(credentials) as session:
        response = session.post('https://secretmanager.googleapis.com/v1/' + SECRET + ':addVersion',
            json={'payload': {'data': base64.b64encode(key.encode()).decode()}}, timeout=25)
        if response.status_code != 200:
            raise RuntimeError('Managed secret write failed HTTP_' + str(response.status_code))
        result = response.json()
    name = result.get('name', '')
    if (not any(name.startswith(prefix + '/versions/') for prefix in (SECRET, CANONICAL_SECRET)) or
            result.get('state') != 'ENABLED'):
        raise RuntimeError('Managed secret receipt mismatch')
    receipt = {'schema_version': 'hosted-managed-verifier-secret-v1',
        'secret_version': name, 'source': 'EXISTING_GITHUB_ANTHROPIC_SECRET',
        'git_commit': os.environ['GITHUB_SHA'], 'run_id': os.environ['GITHUB_RUN_ID'],
        'key_logged_or_saved_to_workspace': False, 'provider_calls': 0,
        'billing_changed': False}
    target = Path('build/public-evaluator-secret-receipt.json')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt))


if __name__ == '__main__':
    main()
