# MotoMedic rider UI

A Streamlit interface built separately from the ongoing controller/model experiments. It uses a server-to-server hosted API, with no manual, index, embedding model, provider key or local authoritative session store in the UI image.

Implemented: Himalayan BS6 confirmation and manual identity; free-text questions and ordinary follow-up questions; source-grounded answers, including partial answers and rider-resolvable clarifications; full checked text and warnings; structured server-issued feedback; five distinct response states; citation metadata; remembered outcomes; verified support link; safe operation recovery after transport failures; desktop/mobile layout.

Photos remain disabled under the required text-first acceptance sequence. Optional voice is not implemented. Citation expansion shows metadata because end-user PDF/excerpt/crop display is prohibited. The backend supplies source-grounded answers and retains relevant typed outcomes; the UI adds no technical advice.

## Status

The latest [draft–verify–stream decision](../docs/architecture/DRAFT_VERIFY_STREAM_DECISION_20261011.md) governs the client. Backend progress stages show retrieval, private drafting, separate checking and display. The complete answer must pass verification and durable save before accepted wording is delivered. Each displayed chunk must match the saved response, operation and response hash. Recovery retrieves that same answer without repeating inference. Private software checks are recorded in [the v8 UI streaming report](../reports/grounded_generation/v8/ui_streaming/REPORT.md). The production client requires `open-manual-draft-verify-v8` on accepted and neutral responses; a retired backend cannot supply current answers or recovery. Real-model quality, hosted browser acceptance and deployment remain pending. Historical hosted wiring receipts remain in reports/arm_a/ui_wiring_v1/.

Read [API_CONTRACT.md](API_CONTRACT.md) for the exact required endpoints and integration obligations. It includes transaction/idempotency, per-session authorization, rate/spending and full browser acceptance requirements. The authenticated candidate Qdrant service is not a compatible rider API.

## Hosted configuration

Supply these **server-side** environment variables or Streamlit secrets:
- MOTOMEDIC_RIDER_API_URL: HTTPS base URL for the hosted session API.
- MOTOMEDIC_RIDER_AUTH=cloud_run: fresh audience-bound tokens from the dedicated UI service account.
- MOTOMEDIC_VISITOR_SECRET: managed shared signing secret.

The hosted UI requires Cloud Run IAM. Its verified browser principal binds visitor ownership and quotas across refresh/new conversations. Anonymous public deployment is outside this identity design. MOTOMEDIC_RIDER_API_TOKEN remains an engineering fixture option.

No API keys are requested from riders or entered in browser fields. Do not set MOTOMEDIC_UI_ENGINEERING_LOOPBACK in deployment. No env file, secret value or raw rider media belongs in Git.

The UI uses the backend session API for both new questions and follow-ups. Haiku availability fallback is configured only on that backend, through `MOTOMEDIC_CLAUDE_FALLBACK_ENABLED=true` and the managed server-side `ANTHROPIC_API_KEY`. It is off by default. One fallback attempt is permitted after primary HTTP 500/502/503/504 or an unconfigured primary; quota, schema, source/integrity failures and semantic rejection do not select fallback. Drafting and checking retain the same evidence and delivery gates. The backend reserves the maximum permitted request cost against the non-recurring allocation; no rider model selector is needed.

Use [the v8 connection handover](../reports/grounded_generation/v8/ui_wiring/CONNECTION_HANDOVER.md) to check the backend health, capability, policy and saved-response bindings before connecting a UI revision. Setting a URL to the old deployed backend does not upgrade that backend. No deployment or billing change is implied by this wiring preparation.

Build from the project root using `docker build -f rider_ui/Dockerfile -t motomedic-rider-ui .`. The verified build stage includes software test fixtures; the final image contains only presentation/client/identity/safeguard runtime files and excludes tests and project source assets, and listens on PORT (8080 by default). Deploy with XSRF/CORS protections enabled, an access-controlled smoke environment first, managed secrets, appropriate Streamlit websocket routing and existing approved project resource/spending limits. Inspect current billing/guard state before deployment; never re-enable stopped billing automatically.

The private deployment utility is tools/connect_arm_a_ui.py, with budget/guard preflight, exact reviewed contexts and immutable image checks. The UI container alone cannot turn a candidate retrieval service into a rider assistant.

## Engineering checks

Install `rider_ui/requirements.txt` in an isolated environment; run `python -m unittest discover -s rider_ui/tests -p 'test_*.py' -v`. The dedicated Verify rider UI GitHub workflow runs the same tests in a hosted build environment.

Local preview: `python -m streamlit run rider_ui/app.py`. Unconfigured preview disables symptom submission. The owner removed the disconnected-service notice.

Loopback fixture: `python -m rider_ui.tests.fixture_api` plus explicit engineering-only loopback URL/token settings. It serves neutral **engineering fixture** text, no motorcycle instructions, retrieval or provider calls. Its passes establish UI behavior only.

## Runtime connection checklist

1. Install the API contract over the existing reviewed service using durable managed sessions, source/model/version locks, actual retrieval and required answer gates.
2. Issue only reviewed, version-bound choices; retain unresolved outcomes and immutable corrections.
3. Enable secret-backed UI-to-API connection, authenticated session ownership, idempotent operation recovery, upload/rate/spending controls and redacted traces.
4. Smoke-test the deployed text interface with a fresh browser, real retrieval, separate drafting/verification, truthful progress, committed answer streaming and citations. Incompatible answer-cache shortcuts stay disabled.
5. Record a live acceptance report. Only then extend to evaluated photo observations and optional voice.

Rollback: disable the new UI connection or revert its container revision; preserve managed session histories and immutable backend source/index versions. Never roll back source approval bindings by changing UI configuration.


The symptom input sits inside the entry card. Text maximum is 2,000 characters in both the widget and client. Photo support remains disabled with a visible one-photo/5-MB/three-per-conversation policy. Read SERVICE_SAFEGUARDS.md for the implemented validators and required managed enforcement, context admission, prompt versioning and retention. TODO.md tracks remaining live release gates.

## Saved UI chat outcome

Read [CHAT_OUTCOME_20261011.md](CHAT_OUTCOME_20261011.md) for the owner-approved copy/layout, reset and privacy decisions. Its Arm A and exact-response method descriptions are historical; the later draft–verify–stream decision supersedes them. Provider prompt caching remains distinct from answer authorization, with no established savings for the current exact model. Existing public/private deployment records are historical receipts, not approval to release this changed pipeline.
