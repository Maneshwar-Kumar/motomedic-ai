# Optional GitHub identity setup for immutable artifact validation

Recorded 12 October 2026. This report contains sanitized, read-only GCP and GitHub metadata and proposed owner/admin setup commands. **No IAM, repository variable, credential, bucket, billing or deployment changes were executed.** The current machine-authenticated hosted image build does not depend on this optional workflow setup.

## Findings

| Item | Observed value |
| --- | --- |
| Project | `motomedic-ai-20261009`, number `279945185781` |
| Repository | `Maneshwar-Kumar/motomedic-ai`, immutable repository ID `1410890968` |
| Owner | `Maneshwar-Kumar`, immutable owner ID `215264495` |
| Default branch | `main` |
| Current validation workflow | `.github/workflows/serving-artifact-validation.yml`; manual dispatch, GitHub-hosted Ubuntu runner, `contents: read` and `id-token: write` |
| Required repository variables | `MOTOMEDIC_GCP_WORKLOAD_IDENTITY_PROVIDER` and `MOTOMEDIC_GCP_READONLY_SERVICE_ACCOUNT`; neither is configured |
| Existing Workload Identity pool | `projects/279945185781/locations/global/workloadIdentityPools/motomedic-secret-loader`; state `ACTIVE`, **disabled: true** |
| Existing GitHub provider | That pool's `providers/github`; issuer `https://token.actions.githubusercontent.com` |
| Existing impersonation | Repository-scoped `roles/iam.workloadIdentityUser` binding on `motomedic-secret-loader@motomedic-ai-20261009.iam.gserviceaccount.com` |
| Existing artifact reader | `motomedic-qdrant@motomedic-ai-20261009.iam.gserviceaccount.com`; bucket-level `roles/storage.objectViewer`, no service-account impersonation bindings |
| Artifact bucket | `motomedic-ai-20261009-indices`; uniform bucket-level access enabled, public access prevention enforced |

The existing provider accepts only this retired branch and workflow:

```text
assertion.repository=='Maneshwar-Kumar/motomedic-ai' &&
assertion.ref=='refs/heads/codex/reviewed-evidence-controller' &&
assertion.workflow_ref=='Maneshwar-Kumar/motomedic-ai/.github/workflows/provision-serving-secret.yml@refs/heads/codex/reviewed-evidence-controller'
```

It cannot authenticate the current artifact-validation workflow: the pool is disabled and the accepted workflow/ref differ. Leave the existing pool, provider and secret-loader binding unchanged.

The inspected scope included global pool/provider metadata, all seven project service accounts and their IAM policies, project IAM, the index bucket's metadata/IAM, and repository metadata/variables. No secret values or credentials were read. Other resource-level permissions of existing service accounts were not exhaustively audited. The two existing provider-key secret names are unrelated to GCP federation and provide no GCP authentication.

## Dedicated read-only identity

The proposed identity uses a new pool and service account. It accepts only the exact repository and immutable owner/repository IDs, the validation workflow on `main`, manual dispatch, and a GitHub-hosted runner. Numeric IDs avoid repository or owner-name reuse; the provider checks the workflow and ref in addition to repository ownership. See [Google's deployment-pipeline federation guide](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines) and [GitHub's OIDC claims reference](https://docs.github.com/en/actions/reference/security/oidc).

The new service account receives a custom role containing **only `storage.objects.get`**, conditionally bound to the exact snapshot object name. Existing Qdrant access stays unchanged. `roles/storage.objectViewer` also permits object listing, so reusing that account would not provide the same get-only boundary. See [Cloud Storage IAM permissions](https://docs.cloud.google.com/storage/docs/access-control/iam-permissions) and [object-name conditions](https://docs.cloud.google.com/storage/docs/access-control/iam).

The immutable snapshot remains:

```text
gs://motomedic-ai-20261009-indices/index_a3282c4d98cf54595e4ba168/index_snapshot.tar.gz
generation: 1791537775184836
sha256: 4248b6f21bede82375a2aceda2205ad8abb63a061abf18c30e9686cd82bba6bc
```

IAM restricts the object name; the existing loader independently requires the pinned generation, archive SHA-256 and complete frozen inventory. These commands do not change the snapshot, workflow, release manifest or source approvals.

## Optional owner/admin commands

These are **proposed commands, not executed commands**. Run them only if the owner authorizes this separate IAM/repository setup. They are written for Bash/Cloud Shell with an already-authenticated administrator. The operator needs permission to create federation resources, create and bind a service account, create a project custom role, and update this bucket's IAM. The IAM, Resource Manager, IAM Credentials and Security Token Service APIs must already be available or be enabled under separately approved scope; this report does not authorize API or billing changes.

First create the dedicated service account, pool and exact provider condition:

```bash
MM_PROJECT='motomedic-ai-20261009'
MM_NUMBER='279945185781'
MM_POOL='motomedic-github-readonly'
MM_PROVIDER='github-artifact-validation'
MM_SA_NAME='motomedic-gh-artifact-reader'
MM_SA="${MM_SA_NAME}@${MM_PROJECT}.iam.gserviceaccount.com"
MM_REPO='Maneshwar-Kumar/motomedic-ai'

gcloud iam service-accounts create "${MM_SA_NAME}" \
  --project="${MM_PROJECT}" \
  --display-name='GitHub immutable artifact reader'

gcloud iam workload-identity-pools create "${MM_POOL}" \
  --project="${MM_PROJECT}" --location=global \
  --display-name='MotoMedic GitHub artifact reader'

MM_MAPPING='google.subject=assertion.sub,attribute.repository_id=assertion.repository_id,attribute.repository_owner_id=assertion.repository_owner_id,attribute.repository=assertion.repository,attribute.ref=assertion.ref,attribute.workflow_ref=assertion.workflow_ref,attribute.event_name=assertion.event_name,attribute.runner_environment=assertion.runner_environment'
MM_CONDITION="assertion.repository_id == '1410890968' && assertion.repository_owner_id == '215264495' && assertion.repository == '${MM_REPO}' && assertion.ref == 'refs/heads/main' && assertion.workflow_ref == '${MM_REPO}/.github/workflows/serving-artifact-validation.yml@refs/heads/main' && assertion.event_name == 'workflow_dispatch' && assertion.runner_environment == 'github-hosted'"

gcloud iam workload-identity-pools providers create-oidc "${MM_PROVIDER}" \
  --project="${MM_PROJECT}" --location=global \
  --workload-identity-pool="${MM_POOL}" \
  --issuer-uri='https://token.actions.githubusercontent.com' \
  --attribute-mapping="${MM_MAPPING}" \
  --attribute-condition="${MM_CONDITION}"
```

The default canonical provider audience is retained, matching the existing `google-github-actions/auth@v3` workflow configuration. No keys or audience overrides are required. See [provider creation](https://docs.cloud.google.com/sdk/gcloud/reference/iam/workload-identity-pools/providers/create-oidc) and the [authentication action's documentation](https://github.com/google-github-actions/auth).

Create the get-only custom role, bind it to the exact object, and permit repository-scoped impersonation of this new service account:

```bash
gcloud iam roles create motomedicSnapshotObjectGet \
  --project="${MM_PROJECT}" \
  --title='MotoMedic exact snapshot object get' \
  --description='Read the immutable serving snapshot object only' \
  --permissions=storage.objects.get --stage=GA

gcloud storage buckets add-iam-policy-binding \
  gs://motomedic-ai-20261009-indices \
  --member="serviceAccount:${MM_SA}" \
  --role="projects/${MM_PROJECT}/roles/motomedicSnapshotObjectGet" \
  --condition="title=motomedic-exact-index-snapshot,expression=resource.name == 'projects/_/buckets/motomedic-ai-20261009-indices/objects/index_a3282c4d98cf54595e4ba168/index_snapshot.tar.gz'"

gcloud iam service-accounts add-iam-policy-binding "${MM_SA}" \
  --project="${MM_PROJECT}" \
  --role=roles/iam.workloadIdentityUser \
  --member="principalSet://iam.googleapis.com/projects/${MM_NUMBER}/locations/global/workloadIdentityPools/${MM_POOL}/attribute.repository_id/1410890968"
```

The federation provider's full condition applies before that repository principal can impersonate the account. No project-wide storage role, service-account key, broad token-creator role or access to serving/provider secrets is added. Command references: [custom roles](https://docs.cloud.google.com/sdk/gcloud/reference/iam/roles/create), [conditional bucket binding](https://docs.cloud.google.com/sdk/gcloud/reference/storage/buckets/add-iam-policy-binding), and [service-account impersonation through federation](https://docs.cloud.google.com/iam/docs/workload-identity-federation-with-deployment-pipelines).

Configure the two nonsecret repository variables after IAM readback confirms the exact resources and conditions:

```bash
gh variable set MOTOMEDIC_GCP_WORKLOAD_IDENTITY_PROVIDER \
  --repo "${MM_REPO}" \
  --body "projects/${MM_NUMBER}/locations/global/workloadIdentityPools/${MM_POOL}/providers/${MM_PROVIDER}"

gh variable set MOTOMEDIC_GCP_READONLY_SERVICE_ACCOUNT \
  --repo "${MM_REPO}" --body "${MM_SA}"
```

These are repository variables, not credentials. See [`gh variable set`](https://cli.github.com/manual/gh_variable_set).

Read back the resulting configuration:

```bash
gcloud iam workload-identity-pools describe "${MM_POOL}" \
  --project="${MM_PROJECT}" --location=global --format=json
gcloud iam workload-identity-pools providers describe "${MM_PROVIDER}" \
  --project="${MM_PROJECT}" --location=global \
  --workload-identity-pool="${MM_POOL}" --format=json
gcloud iam roles describe motomedicSnapshotObjectGet \
  --project="${MM_PROJECT}" --format=json
gcloud iam service-accounts get-iam-policy "${MM_SA}" \
  --project="${MM_PROJECT}" --format=json
gcloud storage buckets get-iam-policy gs://motomedic-ai-20261009-indices \
  --format=json
gh variable list --repo "${MM_REPO}"
gcloud iam workload-identity-pools describe motomedic-secret-loader \
  --project="${MM_PROJECT}" --location=global --format=json
```

Confirm that the custom role has just `storage.objects.get`, its bucket binding has the exact object-name condition, impersonation names the new pool and numeric repository ID, the provider enforces every listed constraint, and the retired pool remains disabled.

## Optional hosted validation after integration

The proposed provider accepts `main` only. Integrate the reviewed build and the existing workflow on `main` before dispatching; the current `codex/complete-text-build` ref will be rejected. Supporting another ref would require a separately scoped provider-condition change with both the exact ref and exact workflow reference, without wildcards.

After the owner chooses to configure this identity, dispatch the existing read-only workflow once and inspect its exact committed SHA and receipt:

```bash
gh workflow run serving-artifact-validation.yml --repo "${MM_REPO}" --ref main
gh run list --repo "${MM_REPO}" \
  --workflow serving-artifact-validation.yml --limit 5 \
  --json databaseId,headSha,status,conclusion,url
# Substitute the dispatched run's actual numeric ID, then inspect its receipt artifact.
gh run view RUN_ID --repo "${MM_REPO}" --json headSha,status,conclusion,jobs,url
```

A successful receipt must bind the dispatched commit and frozen snapshot generation/hash/inventory, with `provider_calls: 0` and `cloud_mutations: 0`. This validates hosted immutable artifact loading and synthetic boundaries; it does not establish real-provider factual acceptance, latency or deployment readiness. No workflow dispatch was performed as part of this metadata investigation.
