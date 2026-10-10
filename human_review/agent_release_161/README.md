# Owner-delegated 161-case release review

Current version: **v3**, completed 10 October 2026. The owner delegated final approval to the coordinator agent and removed the human-only review requirement. The planner supplied case-specific check plans, independent agents checked the original manual and exact runtime objects, and the coordinator signed version-bound decisions.

Use [release_manifest_v3.json](coordinator/release_manifest_v3.json) and [RELEASE_REPORT_v3.md](coordinator/RELEASE_REPORT_v3.md). All 161 retain APPROVED_AGENT_RELEASE for source content and their reviewed initial response, conditional on applicable typed facts. The selected immutable manual is approved under the owner's Himalayan + BS6 selection policy. No further human review is required for these scopes. Historical human-only fields are not this version's approval authority; never represent agent review as human inspection.

## Two hazard corrections

EXP001 now identifies the triangle-marked hazard button on the **right-hand handlebar control** and uses StepDefinition `EXP001:candidate-v4`. EXP002's retained authored unsure branch uses the same corrected right-hand location; its current initial runtime response is unchanged. Independent review checked complete original PDF pages 23, 29 and 30. Conditions, warnings, conditional 30-minute operation and source citations are preserved. The coordinator also approved these two exact static authored identification scopes. All 159 unaffected case versions remain unchanged.

The current approval consumer verified all **187** signed output files and every case/source/step/rule/dependency/parent-boundary binding. All **17** tests passed, including rejection of the retired release and regression checks for both corrected authored identifications. See [root_validation_v3.json](root_validation_v3.json). The consumer pins the exact v3 manifest, rejects changed artifacts and unknown/coerced facts, and does not read secrets or construct a provider.

## History and scope

Version 1 and [version 2](coordinator/release_manifest_v2.json) remain unchanged as audit history. Version 2 grouped 22 standalone Yes/No claims with their reviewed cited explanation and retained the answer meanings. Its validation is preserved in [root_validation.json](root_validation.json), and its consumer is preserved as [approval_consumer_v2.py](approval_consumer_v2.py). Version 3 adds the two hazard corrections without rewriting the frozen [LLM judge report](../llm_judge_161/REPORT.md) or original planner records.

The ten other quality revisions recorded by that judge remain open: GEN043, GEN053, GEN056, EXP030, EXP044, EXP049, a_switches_on, a_refuel, a_reconnect and a_cool_engine. This correction does not assert a new whole-corpus quality score. Those revisions can be addressed alongside integration of the affected flows.

The shared generator/controller has not installed this package. Integration must consume the scoped agent approvals and exact bindings rather than demand new human review or flip legacy human_signoff flags. Full adaptive transitions, general rider-image verification, public source-image delivery and deployment remain separate scopes. No provider call, billing operation or index rebuild occurred in this correction. The concrete integration sequence is in [next_steps/README.md](next_steps/README.md).

Reproduce the current approval verification and tests from the project root:

```text
python human_review/agent_release_161/approval_consumer.py
python -m unittest discover -s human_review/agent_release_161 -p 'test_approval_consumer.py' -v
```
