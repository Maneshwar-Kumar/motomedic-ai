# v7 client copy and runtime verification

66 private software tests pass: 60 UI/client tests and six backend/client integration tests. Exact commands, complete outputs, durations and file hashes are in [validation.json](validation.json).

The client error literal and synthetic error/fallback fixtures now use ASCII Unicode escapes for the owner's U+2019 apostrophe. Independent literal assertions verify exact copy and source encoding. The UI/client literals were already correct before this change; the malformed backend v6 copy is preserved in its historical execution artifact.

Production delivery requires open-manual-draft-verify-v7 on every route, including neutral fallback/error and JSON recovery. A retired runtime cannot display a verified block or neutral completion before the policy check. Explicit engineering loopback compatibility remains isolated. Existing exact chunk/accepted/saved equality, truthful progress, commit barrier, disconnect recovery and source/runtime receipt tests remain passing.

No provider calls, real retrieval, deployment or spending occurred. The frozen v6 reports are unchanged. These tests do not establish real v7 semantic quality or successful-answer latency; no v7 model execution was performed.
