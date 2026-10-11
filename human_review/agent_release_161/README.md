# Exact owner-delegated source approval

Current authority: [release_manifest_v3.json](coordinator/release_manifest_v3.json), SHA-256 b8f8c7b5a9e1a299f0a90eecbf10127779b62b35fc105f0cd587de433e235298. The owner delegated final approval to the coordinator agent; independent agents checked original manual pages and exact source/runtime objects.

The package approves 161 exact source-content and initial-response scopes, conditional on applicable typed facts, plus selected Himalayan + BS6 applicability. No additional human-only signoff is required for these scopes. Never represent agent inspection as human approval.

The consumer verifies all 187 signed output files and source/step/rule/dependency/parent bindings. [root_validation_v3.json](root_validation_v3.json) is the retained validation receipt. Source-content authority is consumed by the current open-Q&A source assembler; it does not make authored question or StepDefinition catalogs general answer gates.

Version 3 corrects the two exact hazard-button identification scopes against PDF pages 23, 29 and 30. The ten recorded unrelated quality holds remain scoped limitations. Approval does not cover all adaptive transitions, general vision, public PDF/excerpt/crop delivery or deployment. Changed source/runtime objects require a new scoped version.

Run from the project root:

```sh
python human_review/agent_release_161/approval_consumer.py
python -m unittest discover -s human_review/agent_release_161 -p 'test_approval_consumer.py' -v
```

Required approved artifacts retain their original paths and bytes. Obsolete approval attempts and generated page duplicates are recoverable from Git history and the local reset snapshot. Follow [the current TRD](../../docs/TRD.md) and [TODO](../../TODO.md) for subsequent integration.
