# Releases

A serving manifest freezes exactly what the runtime may run:
- the SHA-256 of every serving code, UI and workflow file;
- the manual and its source manifest;
- the section index identity;
- the generation contract;
- the owner decisions and the evaluation behind it.

A manifest is never edited after it is committed; a changed input needs a new version. Freezing authorizes no deployment.

| File | Status |
| --- | --- |
| [serving_manifest_v11_3.json](serving_manifest_v11_3.json) | **Current.** The v11.2 answer path, plus the answer-quality regression gate (the receipt is bound, and a freeze needs it to pass) and observability. [`.sha256`](serving_manifest_v11_3.sha256). |
| [serving_manifest_v11_2.json](serving_manifest_v11_2.json) | The quality round: section index `index_f768fbb216836c003701079e` with related warnings, the relevance floor and gate v5 (repeats left out, internal wording checked). Kept byte for byte and bound by v11.3 as history; [`.sha256`](serving_manifest_v11_2.sha256). |
| [serving_manifest_v11_1.json](serving_manifest_v11_1.json) | The section-template answer path with no token ceiling, in this repository layout. 81 inputs. Kept byte for byte and bound by v11.2 and v11.3 as history. |
| [serving_manifest_v11.json](serving_manifest_v11.json) | The first v11 release, with the same answer path but the 2,000,000-token ceiling and the pre-reorganization paths. It is kept byte for byte and bound by every later v11 release as history. |
| [owner_decision_v5.json](owner_decision_v5.json) | The decision behind v11.1: merge to `main`, remove the token ceiling, run experiments locally with Claude Code, reorganize the repository |
| [owner_decision_v6.json](owner_decision_v6.json) | The decision behind v11.2: suggestions 2–6 of the quality review, tested on held-out questions |
| [owner_decision_v7.json](owner_decision_v7.json) | The decision behind v11.3: regression gate, published index, observability and privacy, offline setup on `main` |
| [section_index_asset_v1.json](section_index_asset_v1.json) | Receipt for the published section index: release tag, asset hash, per-file hashes and the round-trip check |

To verify the current release, run `python tools/serving_release.py verify`. Add `--committed-revision $(git rev-parse HEAD)` to also check the committed blobs.

Manifests v8 to v10.14 belong to the retired draft-then-verify runtime and are kept in [archive/](../archive/README.md). Their bindings were last verified in their original layout at commit `7c412369f055b4d0ee747501e6b026f5987d1564`.
