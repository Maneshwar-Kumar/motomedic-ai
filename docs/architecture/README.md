# Architecture and implementation

## Retrieval

- [Hosted index decision](HOSTED_INDEX_DECISION.md): selected BGE M3 snapshot and measured alternatives.
- [Evidence assembly decision](RETRIEVAL_ASSEMBLY_DECISION.md): provisional candidate boundary and dependencies.
- [Local index baseline](LOCAL_INDEX_BASELINE.md): historical Python/NumPy development baseline, not the deployment architecture.
- [Index comparison data](../../index_benchmark.json): draft in-sample comparisons, not release accuracy.

## Runtime code map

| Layer | Main files |
| --- | --- |
| Hosted ingestion and retrieval | [online_ingest.py](../../online_ingest.py), [online_retrieve.py](../../online_retrieve.py), [retrieval_policy.py](../../retrieval_policy.py) |
| Typed state and eligibility | [controller_contracts.py](../../controller_contracts.py), [reviewed_controller.py](../../reviewed_controller.py), [session_store.py](../../session_store.py) |
| Reviewed source and approvals | [evidence_registry.py](../../evidence_registry.py), [approved_registry.py](../../approved_registry.py), [registry](../../registry/README.md) |
| Answer composition and delivery | [constrained_generator.py](../../constrained_generator.py), [generation_contracts.py](../../generation_contracts.py), [verified_delivery_stream.py](../../verified_delivery_stream.py) |
| Provider transport | [generation_providers.py](../../generation_providers.py), [gemini_transport.py](../../gemini_transport.py) |
| Integration and journeys | [diagnose.py](../../diagnose.py), [approved_runner.py](../../approved_runner.py), [approved_text_journeys.py](../../approved_text_journeys.py) |
| UI | [rider_ui](../../rider_ui/README.md) |
| Hosted infrastructure | [cloud](../../cloud/README.md) |

## Integration history

[Controller integration](../../CONTROLLER_INTEGRATION.md), [generator integration](../../GENERATOR_INTEGRATION.md) and [Gemma observability](../../GEMMA_OBSERVABILITY.md) preserve earlier implementation contracts and updates. Their paths are referenced by review packets and are retained. Later [v3 approvals](../../human_review/agent_release_161/README.md) and [TRD v0.5](../../03_TRD.docx) govern their exact superseded scopes. Older model names are historical; continuation selects explicit Gemma 26B.


## Later question-scope record

The [open-question scope correction, 11 October 2026](OPEN_QUESTION_SCOPE_20261011.md) records the later owner direction for accepting rider questions. Read it alongside the earlier TRD and exact evidence/release scopes; the document separates the new requirement from the implementation status at the time it was recorded. The integration continuation owns behavior changes and acceptance evidence.

The [private question UI wiring](UI_WIRING_20261011.md) describes the implemented connection, conservative answer coverage, identity, retention, verification and rollback. Live deployment/acceptance receipts are maintained separately.


The [policy-caveat validation record, 11 October 2026](POLICY_CAVEAT_VALIDATION_20261011.md) documents later claim/policy separation, exact runtime bindings and evaluation limits. Its linked baseline and targeted reports are retained in separate versioned work areas. This is a dated design/evaluation record; consult deployment receipts for installed runtime status.
