# Hosted preparation and identity requirements

12 October 2026. This is a reviewable configuration checklist for the implemented candidate. The requested hosted backend/UI builds completed using the owner's existing machine login and the already used default compute build identity. [Exact receipts](hosted_image_binding_v9_1.json) preserve both images; the full build results record that identity. No identity, IAM grant, queue, service setting, deployment or billing change has been applied; no model/provider run occurred.

The coordinator resolved the machine credential path after the owner clarified that GCP was already configured: the existing gcloud installation has an active login. The authenticated read-only capture verified snapshot generation `1791537775184836` and complete SHA-256 `4248b6f21bede82375a2aceda2205ad8abb63a061abf18c30e9686cd82bba6bc`; [the exact reference](index_snapshot_reference.json) is a serving input. Existing Cloud Build history is readable and the project's recorded billing is enabled; neither setting was changed. Earlier Python ADC attempts returned `ARTIFACT_STORE_UNAVAILABLE`, which did not establish absence of the machine's separate gcloud login.

The coordinator's read-only GitHub inspection found two provider-key secret names and no repository variables. Neither provider key authenticates GCP. GitHub's read-only WIF workflow therefore still lacks its configured variables, but the existing machine gcloud login can submit the owner's requested hosted image builds. Source freezing, committed byte checks, prepared contexts and successful exact build receipts remain required. Build authorization grants no provider activation, deployment, traffic, IAM or billing change.

## Read-only artifact validation

The existing manual workflow is [.github/workflows/serving-artifact-validation.yml](../../../.github/workflows/serving-artifact-validation.yml). It requires these already-configured variables:

| Variable | Exact configured value required |
| --- | --- |
| `MOTOMEDIC_GCP_WORKLOAD_IDENTITY_PROVIDER` | `projects/<number>/locations/global/workloadIdentityPools/<pool>/providers/<provider>` |
| `MOTOMEDIC_GCP_READONLY_SERVICE_ACCOUNT` | The dedicated, approved read-only service-account email. |

An authorized administrator would bind GitHub OIDC to this repository's immutable numeric repository/owner IDs and the approved branch/workflow. Service-account impersonation requires the appropriate federated principal's `roles/iam.workloadIdentityUser` binding on that account. The workflow asks for `id-token: write` and `contents: read`; the auth action produces an ephemeral ADC configuration. It does not create keys or grant roles. [Google's pipeline federation guide](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines) describes these bindings and restrictions.

The read-only account needs `storage.objects.get` on the existing snapshot, typically a bucket-scoped Storage Object Viewer role or narrower custom permission. The capture reads object metadata, fetches the selected generation and verifies the complete SHA-256. `generation` and `ifGenerationMatch` bind the object revision; `alt=media` retrieves its bytes. [GCS object GET contract](https://docs.cloud.google.com/storage/docs/json_api/v1/objects/get).

The workflow then runs real-source/index integration checks with synthetic providers. It obtains no provider secrets, invokes no models and performs no cloud write. Its short-lived receipt artifact is evidence, not a durable serving input.

## Hosted image build

The [release preparer](../../../tools/serving_release.py) requires exact committed inputs and a generation/hash-pinned snapshot. It creates separate canonical backend/UI archives and `cloudbuild.json` recipes. Only those contexts are valid build inputs. The historical `cloud/arm_a/cloudbuild.yaml` path explicitly refuses a raw repository submission, which lacks the installed release lock and generation-pinned archive provenance.

Before a separately authorized build, identify the build submitter, dedicated build service account, source bucket/object generation and destination image repository. The submitter needs `cloudbuild.builds.create` and permission to use the chosen service account; broad project Owner/Editor grants are unnecessary. [Cloud Build permissions](https://docs.cloud.google.com/build/docs/iam-roles-permissions).

For future separately approved identity changes, select the build account explicitly through the API `serviceAccount` field or the submit command's service-account option and preserve it in the resulting build receipt. These builds reused `279945185781-compute@developer.gserviceaccount.com`, as recorded by existing history and the new full API responses, without changing roles. The generated recipe uses `CLOUD_LOGGING_ONLY`, so the selected account needs permission to write the selected Cloud Logging destination. [User-managed build accounts](https://docs.cloud.google.com/build/docs/securing-builds/configure-user-specified-service-accounts), [build log permissions](https://docs.cloud.google.com/build/docs/securing-builds/store-manage-build-logs).

The build account needs read access to the generation-pinned source archive and the recorded private backend base image, plus push access only to the approved output repository. Artifact Registry Reader/Writer permissions can be scoped to repositories. The build identity has no need for provider keys or deployment/traffic privileges. [Artifact Registry access control](https://docs.cloud.google.com/artifact-registry/docs/access-control).

The backend overlay inherits the exact recorded image's dependencies, manual and local model files. Its installed checker validates the original approval package and manual hash; startup verifies inherited embedding identity and passes local model paths with network download disabled. All new serving, safety, durable-operation and artifact-loader modules are included by the current freeze inventory. The UI's 41 complete Linux/amd64 Python 3.12 package pins and wheel hashes are in [the lock](../../../rider_ui/requirements-linux-amd64-py312.lock.txt); Docker and ordinary CI require those same hashes. [Dependency resolution receipt](ui_dependency_lock.json).

Both hosted build outputs must pass [image/provenance binding](../../../tools/bind_serving_images.py) in `--mode build-only`; this mode verifies source, recipe, uploaded archive generation/hash and both immutable image digests without claiming a rollout or inventing historical service revisions. Build success does not authorize promotion. The default promotion mode additionally requires a compatible digest-addressed backend/UI rollback pair with exact service revisions, session schema and runtime lock. Independent original-source/model acceptance, hosted service/recovery checks and exact deployment authority remain separate requirements.

## Durable backend dispatch

The implemented runtime requires all three settings together:

| Setting | Required configuration |
| --- | --- |
| `MOTOMEDIC_TASK_QUEUE` | Existing authorized `projects/<project>/locations/<region>/queues/<queue>` resource. |
| `MOTOMEDIC_TASK_WORKER_URL` | Approved private HTTPS backend origin followed by `/internal/operations/run`; no query or fragment. |
| `MOTOMEDIC_TASK_SERVICE_ACCOUNT` | Dedicated OIDC task identity in the queue's project. |

The runtime enqueuer needs task-create permission on that queue and `iam.serviceAccounts.actAs` on the chosen task identity. That task identity needs `roles/run.invoker` on the exact private backend service. Verify the Cloud Tasks primary service agent retains `roles/cloudtasks.serviceAgent` and the documented Service Account User binding on the task identity. Queue-level OIDC overrides must preserve the exact identity and audience. [Authenticated Cloud Tasks contract](https://docs.cloud.google.com/tasks/docs/creating-http-target-tasks), [Cloud Run service authentication](https://docs.cloud.google.com/run/docs/authenticating/service-to-service).

The audience is the backend service origin. The application additionally verifies issuer, audience, verified email and exact configured identity; a Cloud Tasks header alone grants nothing. Task bodies contain only owner/operation/payload hashes; rider questions and history remain in the owned Firestore work snapshot. Four Gunicorn threads allow an authenticated worker request to progress while SSE reads its stored state. Its 1,200-second deadline remains bounded by the existing whole-turn quota and pacing policy.

Confirm queue retry duration covers the operation deadline and choose queue concurrency consistent with the existing provider ledger before activation. Verify the runtime's existing GCS, private Qdrant, Firestore and selected server-secret access with the approved service identity. These deployed permission/configuration checks have not run, and this checklist creates no new authority to provision or activate them.
