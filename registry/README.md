# Runtime source registry

These are evidence/rule/dependency objects consumed by controller and source-review tooling. File presence does not establish approval.

- [candidate_registry.json](candidate_registry.json): original candidate records.
- [review_decisions.json](review_decisions.json): original review ledger.
- [acceptance_scenarios.json](acceptance_scenarios.json): original engineering gate scenarios.
- [reconciled-accepted-eleven](reconciled-accepted-eleven/): versioned reconciled objects.

Current exact approval authority is described in the [161-case v3 package](../human_review/agent_release_161/README.md). Preserve paths and byte hashes. Do not approve candidates by changing a status string or repurpose legacy human signoff fields.
