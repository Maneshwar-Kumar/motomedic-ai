# Source binding compatibility

The current approval consumer reads exact versioned source objects from [the v3 coordinator package](../human_review/agent_release_161/coordinator/release_manifest_v3.json). [The approval guide](../human_review/agent_release_161/README.md) explains its scope.

Older expanded/refined binding directories were removed from the active tree after checking current consumers. They remain in Git history. Retained root compatibility modules and tests use exact approved objects or synthetic fixtures; ordinary Q&A follows [the fresh TRD](../docs/TRD.md).
