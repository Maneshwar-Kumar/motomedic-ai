"""Two synthetic transport probes; never a grounding or release evaluation."""
from dataclasses import replace
import json
from pathlib import Path
from approved_text_journeys import require_live_preflight
from generation_providers import GeminiJSONProvider, ProviderFailure, gemma_runtime_config
from gemini_transport import stream_request


def evaluate(output):
    preflight = require_live_preflight()
    rows = []
    for role in ('user', 'system'):
        def transport(model, key, body, timeout):
            body['systemInstruction']['role'] = role
            return stream_request(model, key, body, timeout)
        config = replace(gemma_runtime_config(), max_output_tokens=64)
        provider = GeminiJSONProvider(config.generator_model, config, enabled=True,
                                      authorized_calls=1, transport=transport)
        try:
            result = provider.complete('Reply with exactly the JSON object {"ready":true}.',
                                       {'request': 'transport control'},
                                       {'type': 'object', 'properties': {'ready': {'type': 'boolean'}}})
            reason = 'SYNTHETIC_READY' if result.output == {'ready': True} else 'UNEXPECTED_JSON'
        except ProviderFailure as exc:
            reason = str(exc)
        rows.append({'system_content_role': role, 'reason': reason,
                     'reserved_requests': 1 - provider.remaining_calls,
                     'telemetry': provider.last_telemetry})
    report = {'schema_version': 'synthetic-provider-shape-probe-v1',
              'preflight': preflight, 'model': GeminiJSONProvider.MODEL,
              'max_output_tokens_per_request': 64, 'automatic_retries': 0,
              'execution': 'SYNTHETIC_TRANSPORT_CONTROL_NOT_GROUNDING',
              'maximum_requests': 2, 'rows': rows, 'release_or_grounding_claimed': False,
              'production_role_changed': False, 'source_or_rider_media_sent': False}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'report': str(output), 'reasons': [r['reason'] for r in rows]}))
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    evaluate(parser.parse_args().output)
