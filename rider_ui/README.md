# MotoMedic rider UI

A Streamlit interface built separately from the ongoing controller/model experiments. It uses a server-to-server hosted API, with no manual, index, embedding model, provider key or local authoritative session store in the UI image.

Implemented: Himalayan BS6 confirmation and manual identity; symptom text and hosted topic selection; one server-issued clarification/action at a time; full gated text and warnings; structured server-issued feedback; five distinct response states; citation metadata; remembered outcomes; verified support link; safe operation recovery after transport failures; desktop/mobile layout.

Photos remain disabled under the required text-first acceptance sequence. Optional voice is not implemented. Citation expansion shows metadata because end-user PDF/excerpt/crop display is prohibited. Topic coverage and adaptive transitions are supplied by the installed hosted controller, not enlarged by the UI.

## Status

UI code, contract tests and container packaging are implemented. Hosted session API integration and shareable deployment are pending. No live rider/provider call, source approval, index rebuild, billing change or production deployment follows from this UI work.

Read [API_CONTRACT.md](API_CONTRACT.md) for the exact required endpoints and integration obligations. It includes transaction/idempotency, per-session authorization, rate/spending and full browser acceptance requirements. The authenticated candidate Qdrant service is not a compatible rider API.

## Hosted configuration

Supply these **server-side** environment variables or Streamlit secrets:
- MOTOMEDIC_RIDER_API_URL: HTTPS base URL for the hosted session API.
- MOTOMEDIC_RIDER_API_TOKEN: credential for the UI server to authenticate to that API.

No API keys are requested from riders or entered in browser fields. Do not set MOTOMEDIC_UI_ENGINEERING_LOOPBACK in deployment. No env file, secret value or raw rider media belongs in Git.

Build from the project root using `docker build -f rider_ui/Dockerfile -t motomedic-rider-ui .`. The image copies only rider_ui, copies only its presentation/client/safeguard runtime files and excludes tests and project source assets, and listens on PORT (8080 by default). Deploy with XSRF/CORS protections enabled, an access-controlled smoke environment first, managed secrets, appropriate Streamlit websocket routing and existing approved project resource/spending limits. Inspect current billing/guard state before deployment; never re-enable stopped billing automatically.

No deployment command is automated by this package. A new hosted service and budget preflight need to be implemented alongside the backend's current runtime allocation. The UI container alone cannot turn a candidate retrieval service into a rider assistant.

## Engineering checks

Install `rider_ui/requirements.txt` in an isolated environment; run `python -m unittest discover -s rider_ui/tests -p 'test_*.py' -v`. The dedicated Verify rider UI GitHub workflow runs the same tests in a hosted build environment.

Local preview: `python -m streamlit run rider_ui/app.py`. Unconfigured preview disables symptom submission. The owner removed the disconnected-service notice.

Loopback fixture: `python -m rider_ui.tests.fixture_api` plus explicit engineering-only loopback URL/token settings. It serves neutral **engineering fixture** text, no motorcycle instructions, retrieval or provider calls. Its passes establish UI behavior only.

## Runtime connection checklist

1. Install the API contract over the existing reviewed service using durable managed sessions, source/model/version locks, actual retrieval and required answer gates.
2. Issue only reviewed, version-bound choices; retain unresolved outcomes and immutable corrections.
3. Enable secret-backed UI-to-API connection, authenticated session ownership, idempotent operation recovery, upload/rate/spending controls and redacted traces.
4. Smoke-test the deployed text interface with a fresh browser and real provider/retrieval execution, with cache bypassed and citations displayed.
5. Record a live acceptance report. Only then extend to evaluated photo observations and optional voice.

Rollback: disable the new UI connection or revert its container revision; preserve managed session histories and immutable backend source/index versions. Never roll back source approval bindings by changing UI configuration.


The symptom input sits inside the entry card. Text maximum is 2,000 characters in both the widget and client. Photo support remains disabled with a visible one-photo/5-MB/three-per-conversation policy. Read SERVICE_SAFEGUARDS.md for the implemented validators and required managed enforcement, context admission, prompt versioning and retention. TODO.md tracks remaining live release gates.
