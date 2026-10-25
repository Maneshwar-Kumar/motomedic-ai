# Hosted verifier probe IAM plan

This is a plan, not an IAM change. No probe source object has been supplied yet. The private worker task-invoker binding is separately pending worker deployment in `setup_v1.json`.

Use `projects/motomedic-ai-20261009/serviceAccounts/motomedic-arm-a@motomedic-ai-20261009.iam.gserviceaccount.com` as the build execution identity. The authenticated owner submits the build and already has the caller permissions. The execution identity does not need `roles/cloudbuild.builds.builder` merely to run its build steps; assign only the resources used by the selected steps. [Google's user-managed build account guidance](https://docs.cloud.google.com/build/docs/securing-builds/configure-user-specified-service-accounts).

| Resource | Minimal planned grant | Condition |
| --- | --- | --- |
| Main project Cloud Logging | `roles/logging.logWriter` to the backend service account | Build config uses `options.logging: CLOUD_LOGGING_ONLY`; no default Google-owned GCS log bucket. |
| Probe source archive | Existing custom role `projects/motomedic-ai-20261009/roles/motomedicSnapshotObjectGet`, containing only `storage.objects.get` | Bucket policy condition equals the exact supplied `projects/_/buckets/BUCKET/objects/OBJECT` resource name. Confirm source archive before granting. |
| Private build-step container image | `roles/artifactregistry.reader` on the exact repository | Required only if the probe uses a private Artifact Registry image and access is not already sufficient. No image push or repository writer grant. |
| Backend account ID-token generation | `roles/iam.serviceAccountOpenIdTokenCreator` on the backend service account, member equal to that same service account | Required only if the probe calls private Qdrant or another authenticated service from Cloud Build. The permission is `iam.serviceAccounts.getOpenIdToken`; no project-wide token creator. |

Google documents that a custom build account needs ID-token permission for both the gcloud and metadata-server ID-token methods. [Cloud Build service-to-service authorization](https://docs.cloud.google.com/build/docs/securing-builds/authorize-service-to-service-access). Repository reader permission covers private image pulls; writer permission is unnecessary for a read-only probe. [Artifact Registry access control](https://docs.cloud.google.com/artifact-registry/docs/access-control).

Existing backend permissions already cover its Firestore data access, exact serving-index object read, private Qdrant invocation and managed secrets assigned to it. Preserve those scopes. Do not give the default Compute Engine or Cloud Build account secret access. Do not add deploy, image-write, public backend, UI datastore, fallback activation or billing permissions.

After the exact source archive and probe image/authentication method are known, read the existing bindings, apply only missing grants, then read back the precise bindings. Record command arguments and sanitized metadata without credential values. If a build fails for another permission, assess that concrete operation before expanding access.
