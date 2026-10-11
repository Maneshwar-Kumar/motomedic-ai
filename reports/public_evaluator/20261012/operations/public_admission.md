# Private public-visitor admission implementation

12 October 2026. Additive candidate code only; cloud resources, IAM, secret payloads, billing and frozen manifests were not changed by this work. See [the pre-promotion inventory](inventory.md) for observed managed dependencies.

`POST /internal/visitors/reserve` is installed alongside the rider API. The existing `create_app.before_request` establishes the platform-authenticated owner. The endpoint additionally requires `MOTOMEDIC_EDGE_SERVICE_ACCOUNT` to match the selected trusted token's exact service-account email, `email_verified=true`, valid Google issuer/expiry and the platform owner's subject hash. It consistently prefers `X-Serverless-Authorization` when present. Task and other IAM callers cannot issue visitors. This restriction assumes the backend remains Cloud Run IAM-protected; it is not independent JWT signature verification.

Required backend environment:

```text
MOTOMEDIC_EDGE_SERVICE_ACCOUNT=motomedic-rider-ui@motomedic-ai-20261009.iam.gserviceaccount.com
```

No `app.py` edit or UI Firestore role is needed. The endpoint requires exactly `{"proof_sha256":"<64 lowercase hexadecimal characters>"}` and responds with exactly `{"ready":true}` on success. It sends no capability, cookie or secret. Invalid identity returns 403, malformed payload 400, proof replay 409, exhausted creation quota 429, and store/integrity outage 503. JSON response failures remain typed `SYSTEM_ERROR`.

The backend transaction reads both records before writing and atomically reserves one creation with one spent proof. Records live in the already-TTL-enabled `arm_a_usage` collection group:

| Record | Content | Expiry |
| --- | --- | --- |
| `public-visitor-global-v1` | Version, immutable 10/minute and 60/rolling-day limits, bounded creation timestamps | 24 hours from latest reservation |
| `public-visitor-proof-<sha256>` | Version, spent flag | 3 minutes |

Quota persists across instances and revisions. No raw proof token, cookie, IP, network, caller subject or rider text is stored or logged by this module. The public gateway owns challenge validation/signing and requires this managed reservation before issuing a cookie. The spent-proof TTL exceeds its 120-second challenge validity; asynchronous TTL cleanup can extend replay rejection. Public request/provider limits remain separate persistent controls.

Provider-free synthetic verification passed **44 tests in 10.780 seconds** across `cloud.arm_a.test_public_admission`, `cloud.arm_a.test_store`, `cloud.arm_a.test_durable_operations` and `cloud.grounded_generation.test_open_wiring`. The ten new checks cover exact UI identity and missing configuration, task rejection, trusted-header precedence, owner mismatch, strict payload/size validation, concurrent same-proof replay, concurrent unique-proof minute enforcement, rolling-day persistence/expiry, store outage and changed quota binding. Existing save/stream/recover and worker fencing checks remain passing. `git diff --check` passed.

Owned file SHA-256 values at handoff:

```text
cloud/arm_a/public_admission.py
b024c46e6213b0551790e00eb2d42d3236ddec35b3343d84be0a2b5c1621407e

cloud/arm_a/rider_api.py
8069423e232ba051f1735528d841028a869bf7ddfb9901a9e4046193cddcd28a

cloud/arm_a/test_public_admission.py
f875b3966bfca251b7ef80f1e4ba2df6870df34c576135246d52aad861b4e360
```

The coordinator must bind these bytes in the new scoped candidate release and test the deployed managed identity/transaction path before treating it as hosted evidence.
