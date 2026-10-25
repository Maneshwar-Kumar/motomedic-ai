# Existing worker OIDC canary result

The existing Cloud Tasks canary reached the private worker and returned the expected HTTP 400 at `2026-10-11T21:06:17.303081Z` (recorded latency `0.061053464s`). Its configured caller was `motomedic-answer-tasks@motomedic-ai-20261009.iam.gserviceaccount.com`; the token audience matched the worker origin. The handler authenticates that identity before its invalid-body rejection, so this establishes access to the authenticated worker route. The submission records zero provider calls and no raw rider data.

Observed and current ready revision: `motomedic-answer-worker-00002-fbw`. Exact v10_3 image: `us-central1-docker.pkg.dev/motomedic-ai-20261009/motomedic/arm-a@sha256:0a6d142b18962854824205b0bcc89bf9ce4f973e01bd8cb00fa7dbe98386ed5c`. Current IAM permits only the task service account; invoker checking is enabled. No new task or application request was made for this report. Technical-answer acceptance is evaluated separately.

The exact submitted task, saved log entry, source-record hashes and ten binding checks are in [worker_oidc_canary_result_v1.json](worker_oidc_canary_result_v1.json). Current billing, allocation maxima, service images and IAM are in [current_readback_v1.json](current_readback_v1.json).
