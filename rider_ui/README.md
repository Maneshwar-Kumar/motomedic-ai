# Rider interface

The Streamlit interface sends text questions and follow-ups to an authenticated backend. The backend owns retrieval, private drafting, separate verification and durable response storage. The client displays truthful progress and checks saved response bindings before showing accepted text.

Current product and technical requirements: [PRD](../docs/PRD.md), [TRD](../docs/TRD.md), [architecture](../docs/ARCHITECTURE.md) and [TODO](../TODO.md).

## Connection

Backend configuration stays server-side: MOTOMEDIC_RIDER_API_URL, MOTOMEDIC_RIDER_AUTH=cloud_run and a managed visitor-signing secret. Provider keys never belong in browser fields. Do not enable engineering loopback in deployment. Claude fallback is configured only on the backend and remains disabled until authorized activation.

The candidate backend and UI must have compatible runtime, policy, operation and response bindings. A URL pointing to an older service does not install the new pipeline. Use [the v8 connection handover](../reports/grounded_generation/v8/ui_wiring/CONNECTION_HANDOVER.md) as a dated preparation receipt; the current TODO defines remaining hosted acceptance.

Photo and voice remain disabled pending scoped evaluation. Display only supported paraphrases and authorized evidence/page metadata; never serve the PDF, excerpts or figure crops.

## Checks and release

Provider-free CI covers the client, stream decoder and progress/recovery behavior using software doubles. Real browser-to-hosted retrieval, supported/partial answering, Firestore persistence, worker lifetime and disconnect recovery remain release gates.

Build/deployment requires the accepted exact input manifest, compatible backend/UI images, managed identity/secrets, rate/spend/retention enforcement and recorded rollback. [Current status](../docs/STATUS.md) identifies the failed answer-coverage baseline.
