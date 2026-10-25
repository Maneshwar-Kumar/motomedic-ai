# V8 UI connection handover

Prepared integration only. No deployment, billing change, live model request or secret read was performed for this handover. The existing deployed backend may still serve the retired pipeline; strict v8 UI checks intentionally reject it.

The Streamlit app constructs RiderAPI from server-side configuration. New input posts to `/v1/sessions`; ordinary follow-ups post to `/v1/sessions/{id}/questions`. Both request SSE and render only backend progress followed by the exact saved accepted response. Recovery reads `/v1/operations/{id}` without repeating inference. No browser provider calls or model selector are introduced.

## Configuration prepared for the authorized deployment step

| Service | Setting | Required value/source |
| --- | --- | --- |
| UI | MOTOMEDIC_RIDER_API_URL | HTTPS base URL of the current rider session backend, not Qdrant |
| Private UI | MOTOMEDIC_RIDER_AUTH | cloud_run; dedicated UI service account with invocation rights |
| UI and backend | MOTOMEDIC_VISITOR_SECRET | Same managed signing secret; preserve existing identity/edge configuration |
| UI | MOTOMEDIC_CACHE_MODE | bypass |
| Backend | MOTOMEDIC_CLAUDE_FALLBACK_ENABLED | true only when the fallback allocation and secrets are authorized; otherwise disabled |
| Backend | ANTHROPIC_API_KEY | Managed server-side secret, never UI/browser configuration |
| Backend | ClaudeBudget and ProviderAdmission | Transactional non-recurring cost and token/call reservations |

Keep the existing private IAM or separately managed anonymous edge configuration intact. Do not enable the engineering loopback switch in deployment. Do not place secret values in commands, files, screenshots or routine logs.

## Connection checks

1. Build the backend and UI from the same reviewed v8 serving freeze. Verify Git blobs as well as local file hashes before producing images; a correct local file omitted from a commit cannot appear in a hosted build.
2. Under existing authenticated server access, inspect `/healthz`: architecture must be `DRAFT_VERIFY_STREAM_OPEN_MANUAL_QA`, streaming must be `DRAFT_VERIFY_STREAM`, and answer_provider must identify the configured Gemma primary and Haiku chain when enabled. This is configuration evidence, not proof of successful provider calls.
3. Inspect `/v1/catalogue`: question_input=open, diagnostic_wizard=false, streaming=DRAFT_VERIFY_STREAM and the immutable manual/index must match. The current catalogue answer_provider identifies the primary; health is the chain metadata check.
4. Use the real RiderAPI path with a fresh question. All returned views, including neutral responses, must carry runtime_policy=open-manual-draft-verify-v8. An accepted answer needs current operation/runtime/source/evidence/presentation bindings. The displaying stage and chunks must follow durable commit. Fixed fallback/error use neutral completion with no verified label or chunks.
5. Disconnect and recover the original operation. Compare the entire saved view and response hash with the accepted stream; recovery and replay must make no new provider request. Record actual browser/service timing and cited-page presentation separately from offline software results.

Do not weaken policy checks to connect to an old deployment. A current backend revision, its managed settings and authenticated UI URL connection are required before a rider-facing live acceptance claim.

## Offline integration evidence

`cloud/grounded_generation/test_ui_fallback_wiring.py` exercises real open Questions, Composer, FallbackProvider, ClaudeProvider, backend handlers, transactional store fixture and strict production RiderAPI/SSE/recovery validation. Only retrieval selection and provider HTTP responses are scripted; immutable source authority is real. It covers accepted delivery, semantic rejection and malformed verifier output. Earlier delivery tests separately block verification and durable save to check that content cannot arrive early.

Provider quality and deployed browser behavior require actual acceptance evidence. Synthetic outcomes cannot establish semantic accuracy or provider availability.
