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
| [serving_manifest_v11_1.json](serving_manifest_v11_1.json) | **Current.** It covers the section-template answer path with no token ceiling, in this repository layout. 81 inputs; [`.sha256`](serving_manifest_v11_1.sha256). |
| [serving_manifest_v11.json](serving_manifest_v11.json) | The previous release, with the same answer path but the 2,000,000-token ceiling and the pre-reorganization paths. It is kept byte for byte and bound by v11.1 as history. |
| [owner_decision_v5.json](owner_decision_v5.json) | The decision behind v11.1: merge to `main`, remove the token ceiling, run experiments locally with Claude Code, reorganize the repository |

To verify the current release, run `python tools/serving_release.py verify`. Add `--committed-revision $(git rev-parse HEAD)` to also check the committed blobs.

Manifests v8 to v10.14 belong to the retired draft-then-verify runtime and are kept in [archive/](../archive/README.md). Their bindings were last verified in their original layout at commit `7c412369f055b4d0ee747501e6b026f5987d1564`.
