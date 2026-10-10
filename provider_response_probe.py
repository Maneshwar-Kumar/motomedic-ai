"""One authorized synthetic Gemma26B response-structure diagnostic."""
from dataclasses import replace
import json
from pathlib import Path
from approved_text_journeys import require_live_preflight
from generation_providers import GeminiJSONProvider, ProviderFailure, gemma_runtime_config


def evaluate(output):
    model = 'gemma-4-26b-a4b-it'
    preflight = require_live_preflight(model)
    config = replace(gemma_runtime_config(model), max_output_tokens=64)
    provider = GeminiJSONProvider(model, config, enabled=True, authorized_calls=1)
    try:
        result = provider.complete('Return exactly one JSON object {"ready":true}.',
                                   {'request': 'synthetic response structure control'},
                                   {'type': 'object', 'properties': {'ready': {'type': 'boolean'}}})
        reason = 'SYNTHETIC_READY' if result.output == {'ready': True} else 'UNEXPECTED_JSON'
    except ProviderFailure as exc:
        reason = str(exc)
    report = {'schema_version': 'synthetic-response-structure-probe-v1',
              'execution': 'SYNTHETIC_NOT_GROUNDED_OR_RELEASE_ACCEPTANCE',
              'preflight': preflight, 'model': model, 'maximum_requests': 1,
              'reserved_requests': 1 - provider.remaining_calls,
              'max_output_tokens': 64, 'reason': reason,
              'telemetry': provider.last_telemetry, 'automatic_retries': 0,
              'raw_content_logged': False, 'mechanical_claims_sent': False}
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'reason': reason, 'requests': report['reserved_requests']}))
    return report


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    evaluate(parser.parse_args().output)
