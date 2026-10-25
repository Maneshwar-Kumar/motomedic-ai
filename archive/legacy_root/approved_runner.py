"""Shared approved retrieval/controller/composer factory.

Explicit record selection is a bounded intent contract, not semantic permission.
No case fixture seeds rider observations and no approval implies provider spending.
"""
from dataclasses import replace
from pathlib import Path

from approved_registry import ApprovedEvidenceRegistry
from constrained_generator import build_generator
from generation_providers import gemma_runtime_config
from online_retrieve import Retriever
from reviewed_controller import ReviewedController, start_session
from cloud.arm_a.composer import ArmAComposer


def build_approved_runner(index, *, root=None, retriever=None, generator=None,
                          live=False, calls_per_adapter=0, audience="end_user", runtime_config=None):
    root = Path(root or Path(__file__).parent).resolve()
    registry = ApprovedEvidenceRegistry.load(root, index)
    if generator is not None and runtime_config is not None and generator.config != runtime_config:
        raise ValueError("Supplied generator and selected runtime configuration differ")
    if generator is None and runtime_config is not None:
        raise ValueError('Provider configuration requires an explicitly supplied historical generator')
    pipeline = generator or ArmAComposer()
    controller = ReviewedController(registry, retriever or Retriever(index),
                                    response_generator=pipeline)
    controller.audience = audience
    return controller


def confirmed_session(controller, record_id, variant):
    registry = controller.registry
    if record_id not in registry._consumer.records:
        raise ValueError("Unknown approved record selection")
    # Only intent and the rider's explicit bike choice enter this session.
    # Step facts from session_fixtures.json are intentionally never consumed.
    return replace(start_session(registry, [record_id], variant),
                   generation_lock=controller.response_generator.config.lock)


if __name__ == "__main__":
    import argparse
    import json
    from verify_controller import NoInferenceEncoder
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--index", type=Path, required=True)
    args = parser.parse_args()
    # Source/index integration preflight performs no query embedding/inference.
    controller = build_approved_runner(args.index,
                                      retriever=Retriever(args.index, embedding_model=NoInferenceEncoder()))
    registry = controller.registry
    print(json.dumps({"authority": "OWNER_DELEGATED_AGENT_COORDINATOR",
                      "registry_lock": registry.lock, "index_id": registry.index_id,
                      "source_ready": registry.source_ready(),
                      "ready_text_steps": sum(registry.step_ready(sid) for sid in registry.candidate["steps"]),
                      "provider_calls": 0, "index_rebuilt": False}))
