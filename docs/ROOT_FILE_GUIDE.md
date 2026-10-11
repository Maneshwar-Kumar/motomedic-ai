# Compatibility-root file guide

These paths remain stable for hosted workflows, approved bindings and active chats. Use the topic guides first. This list makes the remaining root files visible by purpose.

## Planning and handoffs

- [01_Concept_Architecture.docx](../01_Concept_Architecture.docx)
- [02_PRD.docx](../02_PRD.docx)
- [03_TRD.docx](../03_TRD.docx)
- [03_TRD_Architecture_Decision_Note.docx](../03_TRD_Architecture_Decision_Note.docx)
- [04_To_Build_Evaluation_Decisions.docx](../04_To_Build_Evaluation_Decisions.docx)
- [GEMMA26B_ARCHITECTURE_RERUN_HANDOFF.md](../GEMMA26B_ARCHITECTURE_RERUN_HANDOFF.md)
- [GEMMA_CONTROLLER_HANDOFF.md](../GEMMA_CONTROLLER_HANDOFF.md)
- [IMPLEMENTATION_PROGRESS.md](../IMPLEMENTATION_PROGRESS.md)
- [NEXT_CHAT_HANDOFF.txt](../NEXT_CHAT_HANDOFF.txt)
- [NEXT_CHAT_HANDOFF_RECEIPT.json](../NEXT_CHAT_HANDOFF_RECEIPT.json)
- [TRD_UI_FOLLOWUP_HANDOFF.md](../TRD_UI_FOLLOWUP_HANDOFF.md)

## Implementation

- [approved_registry.py](../approved_registry.py)
- [approved_runner.py](../approved_runner.py)
- [approved_text_journeys.py](../approved_text_journeys.py)
- [architecture_benchmark.py](../architecture_benchmark.py)
- [architecture_measurement.py](../architecture_measurement.py)
- [benchmark_pacing.py](../benchmark_pacing.py)
- [benchmark_stream_transport.py](../benchmark_stream_transport.py)
- [constrained_generator.py](../constrained_generator.py)
- [controller_contracts.py](../controller_contracts.py)
- [CONTROLLER_INTEGRATION.md](../CONTROLLER_INTEGRATION.md)
- [diagnose.py](../diagnose.py)
- [evidence_registry.py](../evidence_registry.py)
- [gemini_transport.py](../gemini_transport.py)
- [gemma_api_smoke.py](../gemma_api_smoke.py)
- [GEMMA_OBSERVABILITY.md](../GEMMA_OBSERVABILITY.md)
- [generation_contracts.py](../generation_contracts.py)
- [generation_providers.py](../generation_providers.py)
- [GENERATOR_INTEGRATION.md](../GENERATOR_INTEGRATION.md)
- [index_manual.py](../index_manual.py)
- [online_ingest.py](../online_ingest.py)
- [online_retrieve.py](../online_retrieve.py)
- [provider_response_probe.py](../provider_response_probe.py)
- [provider_shape_probe.py](../provider_shape_probe.py)
- [reconcile_accepted_examples.py](../reconcile_accepted_examples.py)
- [registry_source_candidates.py](../registry_source_candidates.py)
- [registry_workflow.py](../registry_workflow.py)
- [render_docx_word.ps1](../render_docx_word.ps1)
- [requirements-ingest.txt](../requirements-ingest.txt)
- [retrieval_policy.py](../retrieval_policy.py)
- [retrieve_evidence.py](../retrieve_evidence.py)
- [reviewed_cache.py](../reviewed_cache.py)
- [reviewed_controller.py](../reviewed_controller.py)
- [semantic_candidate_cache.py](../semantic_candidate_cache.py)
- [session_store.py](../session_store.py)
- [update_conditional_trd.py](../update_conditional_trd.py)
- [update_guardrail_docs.py](../update_guardrail_docs.py)
- [verified_delivery_stream.py](../verified_delivery_stream.py)

## Tests and verification

- [audit_a_semantic.py](../audit_a_semantic.py)
- [audit_architecture_v3.py](../audit_architecture_v3.py)
- [audit_architecture_v4.py](../audit_architecture_v4.py)
- [audit_gemma_batch_grounding.py](../audit_gemma_batch_grounding.py)
- [test_a_semantic_audit.py](../test_a_semantic_audit.py)
- [test_accepted_reconciliation.py](../test_accepted_reconciliation.py)
- [test_approved_integration.py](../test_approved_integration.py)
- [test_architecture_benchmark.py](../test_architecture_benchmark.py)
- [test_architecture_features.py](../test_architecture_features.py)
- [test_architecture_measurement.py](../test_architecture_measurement.py)
- [test_benchmark_pacing.py](../test_benchmark_pacing.py)
- [test_budget_guard.py](../test_budget_guard.py)
- [test_conditional_retrieval.py](../test_conditional_retrieval.py)
- [test_constrained_generator.py](../test_constrained_generator.py)
- [test_diagnose.py](../test_diagnose.py)
- [test_gemini_provider.py](../test_gemini_provider.py)
- [test_gemini_transport_bytes.py](../test_gemini_transport_bytes.py)
- [test_gemma_api_smoke.py](../test_gemma_api_smoke.py)
- [test_online_assembly.py](../test_online_assembly.py)
- [test_retrieve_evidence.py](../test_retrieve_evidence.py)
- [test_reviewed_controller.py](../test_reviewed_controller.py)
- [test_text_journeys.py](../test_text_journeys.py)
- [verify_approved_integration.py](../verify_approved_integration.py)
- [verify_controller.py](../verify_controller.py)
- [verify_gemma_grounding.py](../verify_gemma_grounding.py)
- [verify_generation.py](../verify_generation.py)

## Source and evaluation data

- [diagnosis_flow.json](../diagnosis_flow.json)
- [golden_dialogues.json](../golden_dialogues.json)
- [golden_dialogues.md](../golden_dialogues.md)
- [golden_qa.json](../golden_qa.json)
- [golden_qa.md](../golden_qa.md)
- [index_benchmark.json](../index_benchmark.json)
- [provisional_golden_cache.json](../provisional_golden_cache.json)
- [reviewed_graph_links.json](../reviewed_graph_links.json)
- [royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf](../royal-enfield-new-himalayan-450-owners-manual-bs-six-english.pdf)
- [source_manifest.json](../source_manifest.json)
- [source_review_notes.json](../source_review_notes.json)

## Repository configuration and entry points

- [.gitattributes](../.gitattributes)
- [.gitignore](../.gitignore)
- [AGENTS.md](../AGENTS.md)
- [CONTRIBUTING.md](../CONTRIBUTING.md)
- [README.md](../README.md)
- [TODO.md](../TODO.md)

## Temporary owner review input

- [motomedic-edited.html](../motomedic-edited.html)

The saved owner HTML is an active UI-review input. The UI chat owns its preservation; the monitor should relocate it only after confirming the chat no longer depends on its root path.

## Files observed during concurrent work

- [TODO.md](../TODO.md): current human task register owned by the UI work.
- [audit_a_semantic.py](../audit_a_semantic.py): active audit executable, retain its reviewed workflow path.
- [test_a_semantic_audit.py](../test_a_semantic_audit.py): active audit tests, retain current imports/discovery.
