# Start here

MotoMedic helps a rider take a concise next step supported by the selected Royal Enfield owner's manual. This repository contains the product design, implementation and evidence for that promise. It does not yet establish public release acceptance.

## Choose what you need

| I want toâ€¦ | Open | What it contains |
| --- | --- | --- |
| Understand the product | [Planning documents](planning/README.md) | Concept, requirements, authoritative TRD and build checklist |
| See the rider interface | [Rider UI](../rider_ui/README.md) | UI setup, API boundary and design review |
| Understand how it works | [Architecture guide](architecture/README.md) | Retrieval, controller, generator and code map |
| Check the source and permissions | [Source guide](source/README.md) | Exact manual, metadata, applicability and display limits |
| See what has been verified | [Evaluation guide](evaluation/README.md) | Scope-bound approvals, golden cases and benchmark results |
| Check hosting and costs | [Cloud guide](../cloud/README.md) | Deployment records, smoke checks and budget guard |
| Resume current work | [Current work](CURRENT_WORK.md) | Active chats and durable handoffs |
| Look up an older decision | [History](history/README.md) | Conversation context and retired designs |
| Find a particular root file | [File guide](ROOT_FILE_GUIDE.md) | Every compatibility-root file grouped by purpose |

## Read the status correctly

The current [draft, verify, stream decision](architecture/DRAFT_VERIFY_STREAM_DECISION_20261011.md) supersedes the earlier exact-wording and no-online-verifier methods. Consult the [integration report](../reports/grounded_generation/draft_verify_stream_v1/README.md) for validation and implementation status. Earlier descriptions remain dated history.

The selected pipeline reuses versioned Docling ingestion and BGE M3 plus BM25 retrieval, drafts privately, then verifies the proposed response against source evidence before streaming. Source integrity, applicability, citations and session controls remain enforced. Architecture decisions and passing software checks do not establish deployed acceptance.

The 161-case v3 approval covers exact source-content and initial-response scopes, including selected-manual Himalayan + BS6 applicability. It does not approve every adaptive transition, general vision performance, public source display or deployment. Older integration notes preserve their original draft/human-review terminology; the later scope-bound approval and TRD v0.5 take precedence. Do not infer current status from an old report's filename alone.

## Why some files remain at the root

Executable imports, hosted workflows and exact-version approval records depend on current paths. The Word planning files and handoffs are also being used by active chats. Moving them now would break reproducibility or concurrent work. Their locations are explicit in the guides; new work belongs in the named folders. A later runtime migration requires updated imports/workflows and new exact bindings, followed by relevant verification.

## Owner decision: draft, verify, stream (11 October 2026)

The current open manual Q&A method is [draft, verify, stream](../docs/architecture/DRAFT_VERIFY_STREAM_DECISION_20261011.md). It supersedes exact-answer-only, catalogue/action allowlists and the no-online-verifier amendment. Implementation and test status are recorded in [the integration report](../reports/grounded_generation/draft_verify_stream_v1/README.md). Existing source restrictions, model and spending/deployment authorizations still apply. No public release follows from the decision.

