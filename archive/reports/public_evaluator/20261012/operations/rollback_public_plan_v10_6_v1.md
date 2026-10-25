# v10_6 compatible rollback and UI opening preparation

This is a prepared procedure, not cloud execution evidence. The ignored helper is
`tmp/rollback_public_v10_6.py`. No cloud request, provider call, secret payload
read, IAM change, traffic change, billing change or allocation write was performed
while preparing it. The 20 local checks use synthetic fixtures and mocked cloud,
health and SDK calls.

The helper requires the immutable `serving_manifest_v10_6.json` and its SHA-256
sidecar, `hosted_image_binding_v10_6.json`, and
`expected_runtime_lock_v10_6.json`. A missing index generation is an error. It
does not infer an expected lock from changing local code. Actual image digests
and revision names remain pending until the coordinator's hosted build and
private deployment finish.

The current expected authentication mode is `MOTOMEDIC_RIDER_AUTH=cloud_run`.
The rider UI runs as its existing service account, uses the private backend,
and receives only managed visitor-secret references. The backend and worker
retain their exact Gemini, verifier and visitor-secret references, fallback
disabled, current queue and task identity, and current resource bounds. The
worker's only explicit invoker is the task service account; Qdrant's is the
backend service account. The backend retains the UI and backend service account
invokers. Every core service must keep its IAM invoker check enabled.

The private console may expose these fixed actions in order:

1. `create`: read current service and revision metadata, authenticate health,
   verify the current runtime lock, snapshot configuration and private IAM
   hashes, then create compatible candidate revisions. Images, environment,
   secret references, resource bounds and runtime policy remain identical.
   Only the candidate revision label changes. Traffic stays explicitly at
   100% on the original, actually served revision.
2. `poll`: verify all creation operations finish successfully and save exact
   candidate revisions. Polling does not replace an existing successful
   receipt.
3. `route_candidate`, then `health_candidate`: explicitly route each service
   to its saved candidate revision and confirm actual resolved traffic and
   authenticated health. This establishes a real transition before rollback.
4. `route_rollback`, then `health_rollback`: explicitly restore the original
   saved revision, verify all traffic operations, and confirm actual health.
5. `route_restore`, then `health_restore`: explicitly route the identical
   candidate again, verify all traffic operations, and confirm actual health.

Every stage uses explicit revision targets. The helper rejects changing images,
environment, template configuration, runtime locks, source/index identity,
private invokers, disabled IAM checks, or unexpected actual traffic. It saves
receipts under `operations/rollback_v10_6_*.json`. Initial and per-service
mutation journals are written before or immediately after each operation so a
partial failure remains inspectable. Existing receipts cannot be overwritten;
an uncertain mutation is not silently repeated.

`public_open` remains a separate coordinator action. The private console does
not expose it. Before granting access it requires:

- The existing owner authorization with its exact recorded file hash.
- `operations/semantic_acceptance_v10_6.json`, schema
  `motomedic-six-case-semantic-acceptance-v1`, with decision `ACCEPTED`, the exact
  manifest hash, runtime lock and actual evaluator build ID. Its six unique
  records bind the independently reviewed original-PDF assessment to the exact
  local case artifact hashes and expected/actual routes. Human signoff is
  explicitly false and source-display authorization remains unchanged.
- The actual client `hosted_runs/<build-id>/receipt.json` for that same build,
  bound through `evaluator_client_submission_v3.json` and source receipt v4.
  The evaluator plan's pinned SHA-256 is
  `a7dc784be633c14accdff256e57abb784a486076da07b149c6f2e04096ee5541`.
  The plan has a separate evaluation binding: its exact bytes must match
  source-v4 file inventory and the actual hosted client inventory. The raw
  source `client_inputs.json` must match its archived hash and the hosted
  parsed inventory; its complete file hash map must match source v4.
  All six cases must have saved, exact streamed and recovered views. Engineering
  route checks alone cannot replace semantic acceptance.
- An actual nested `completed_operation_checks` record proving duplicate POST
  returns the same operation and saved view, a different valid visitor receives
  404, reservations remain unchanged, no provider call occurs, and no new
  question or operation is created. The aggregate boundary flag alone is
  insufficient.
- Retained primary/verifier reservation scalars within unchanged permanent
  allocation maxima, and successful compatible rollback and restore receipts.
- Fresh ready service metadata and actual health on the restored exact image,
  template and traffic revisions, with private core IAM unchanged.

The semantic template beside this plan is deliberately `PENDING`; it cannot
satisfy the gate. The retrieval reviewer creates the actual independently
adjudicated receipt only after the six hosted case outputs exist. The
coordinator confirms final artifact byte hashes.

The only public mutation adds `allUsers` to the UI service's unconditioned
`roles/run.invoker` binding, preserving unrelated IAM rows and using the policy
etag. Backend, worker and Qdrant IAM remain private and unchanged. This does not
disable Cloud Run's IAM check, create resources, read secret payloads, change
billing, change model allocations, or authorize source display.

After the IAM readback, `public_health` performs read-only checks. A 403 or 503
during propagation returns `verification_pending=true` and does not write a
successful opening receipt. The coordinator may later invoke `public_health`
again; it performs no IAM mutation. Successful anonymous GET of the exact public
UI `/health` produces `operations/public_open_v10_6_v1.json`. That receipt keeps
`public_browser_acceptance=false` until the coordinator separately performs and
records the actual browser interaction. Health and IAM success do not establish
rider-flow or factual acceptance.

The inference project remains billing-disabled. No helper action restarts it.
Historical v10_4 failed acceptance and rollback receipts and the v10_5 freeze
with missing generation remain preserved.
