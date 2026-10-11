# Repository organization decision

Recorded 11 October 2026 in response to the owner's request for human navigation.

## Applied practices

[GitHub's repository guidance](https://docs.github.com/en/repositories/creating-and-managing-repositories/best-practices-for-repositories) recommends a README that explains and helps people navigate the project. [README guidance](https://docs.github.com/en/repositories/managing-your-repositorys-settings-and-features/customizing-your-repository/about-readmes) recommends relative links and an entry point covering purpose, use and help. [Contributor guidance](https://docs.github.com/en/communities/setting-up-your-project-for-healthy-contributions/setting-guidelines-for-repository-contributors) supports a discoverable CONTRIBUTING file and review templates.

The resulting layout groups material by purpose, gives each major area an explanation and separates current entry points from historical evidence. GitHub does not prescribe one universal `src/` layout. MotoMedic's exact-version path bindings make a wholesale runtime move inappropriate during concurrent work.

## Folder contract

| Folder | Put here |
| --- | --- |
| `docs/planning/` | Planning navigation; current Word documents remain at their compatibility paths |
| `docs/architecture/` | Technical design and decision narratives |
| `docs/source/` | Source navigation and permission explanations |
| `docs/evaluation/` | Evaluation navigation and methodology |
| `docs/history/` | Superseded human narratives and conversation context |
| `rider_ui/` | Rider application, UI contracts and UI tests |
| `cloud/` | Deployment/infrastructure code and resource records |
| `registry/`, `grounding_bindings/`, `human_review/` | Version-bound evidence and approval objects; retain paths/bytes |
| `reports/<work-area>/<version-or-run>/` | New evidence, measurements, screenshots and validation results |
| `experiments/<name>/` | Active isolated experiments with a README and exit decision |
| `outdated_design_choices/<name>/` | Retired alternatives with their decision record |
| `tools/` | Maintenance, validation and document utilities |
| `tmp/`, `build/` | Ignored temporary/generated artifacts |

Do not add routine outputs, saved HTML reviews or generic new handoffs to the root. Existing compatibility-root files are listed in [ROOT_FILE_GUIDE.md](ROOT_FILE_GUIDE.md). Frozen reports and bindings are not tidied by moving them.

## Changes and verification

Four safe Markdown documents moved to `docs/architecture/` and `docs/history/`; relative Markdown links were repaired. The previous root README is retained. [Move record](../reports/repository_organization/moves.json) records old/new paths and hashes. Runtime code, tests, approved objects, source files, active Word files and handoffs retain their paths.

`python tools/check_repository_structure.py` checks the navigation links and unexpected root files against the baseline in `docs/repository_layout.json`. Run it from the repository root. A recurring chat monitor checks new files and relevant chat progress; an alert is a finding to inspect, not permission to change exact approvals or runtime paths.

## Later runtime migration

Once active work is stable, plan a versioned migration of application modules into a package and tests into `tests/`. Update imports, Docker/build contexts, workflows, test discovery and content/path-bound approvals together. Verify preserved source IDs and byte hashes, exact approval-consumer tests, subsystem regressions and hosted reproducibility. Do not represent this staged documentation organization as a completed runtime migration.
