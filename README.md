# MotoMedic AI

A motorcycle troubleshooting assistant that offers a concise next step only when the selected Royal Enfield owner's manual supports it.

**[Start here: product, code, source and results](docs/START_HERE.md)**

## Find your way

| What you need | Where to go |
| --- | --- |
| Product design and build checklist | [Planning](docs/planning/README.md), [current TODO](TODO.md) |
| System architecture and code map | [Architecture](docs/architecture/README.md) |
| Rider interface | [Rider UI](rider_ui/README.md) |
| Manual, applicability and permissions | [Source](docs/source/README.md) |
| Cases, approvals and evaluation | [Evaluation](docs/evaluation/README.md) |
| Hosted resources and spending controls | [Cloud](cloud/README.md) |
| Benchmark results and screenshots | [Reports](reports/README.md) |
| Active chats and continuation handoffs | [Current work](docs/CURRENT_WORK.md) |
| Older decisions and retired alternatives | [History](docs/history/README.md) |

## Current design and release status

The [11 October owner amendment](docs/architecture/TRD_V05_GROUNDED_GENERATION_AMENDMENT_20261011.md) supersedes TRD v0.5 section 14's exact-wording-only restriction: versioned Docling/BGE M3 + BM25 retrieval and deterministic evidence/state gates feed a grounded answer LLM. Unseen questions are admitted by applicable evidence; canonical wording is only eligible for exact response-cache hits. Citation/step/warning checks are deterministic, with no separate final semantic-verifier call. The retired full-manual Claude design stays archived.

The hosted candidate index is `index_a3282c4d98cf54595e4ba168`. Ingestion runs once per source/pipeline/model version; rider requests reuse its evidence and vectors. The exact 161-case v3 approval covers defined source-content and initial-response scopes, including selected-manual Himalayan + BS6 applicability. It does not establish blanket adaptive, vision or public deployment acceptance. See the [approval scope](human_review/agent_release_161/README.md).

The rider UI is under active development; live browser-to-hosted acceptance remains a release gate. End-user PDF, excerpts and figure delivery are prohibited by the current display policy. This is an advisory prototype, not proof of a verified repair.

## Working on the project

Use [CONTRIBUTING.md](CONTRIBUTING.md) for file placement and concurrent work, and [AGENTS.md](AGENTS.md) for detailed project contracts. Root runtime/test files and current Word documents retain compatibility paths; the [file guide](docs/ROOT_FILE_GUIDE.md) groups them by purpose.

Run the read-only organization check from the repository root:

```bash
python tools/check_repository_structure.py
```

Use the relevant existing private GitHub verification workflow for implementation changes. Builds and provider runs remain hosted; credentials stay server-side. Organization work does not authorize deployment or billing changes. See the [organization decision and references](docs/REPOSITORY_ORGANIZATION.md).
