# Rider interface

The frontend is a public gateway around Streamlit. Signed cookies and a browser proof challenge lead to a private IAM-authenticated backend; provider keys stay server-side. The backend retrieves the top-5 manual sections and makes one Haiku call per turn, released by a deterministic gate; there is no verifier. The UI shows real progress (`retrieving`, `drafting`, `checking`, `displaying`), then the exact saved text, and checks every binding during streaming, follow-ups and recovery.

Requirements: [PRD](../docs/PRD.md), [TRD](../docs/TRD.md), [architecture](../docs/ARCHITECTURE.md), [API contract](API_CONTRACT.md) and [safeguards](SERVICE_SAFEGUARDS.md).

## Connection

Backend configuration stays server-side:
- `MOTOMEDIC_RIDER_API_URL`;
- `MOTOMEDIC_RIDER_AUTH=cloud_run`;
- the managed visitor-signing secret.

Direct public mode uses `MOTOMEDIC_RIDER_ACCESS=public_gateway` and `MOTOMEDIC_EDGE_POLICY=gcp-public-cloud-run-cookie-v2`, with the exact configured Cloud Run host. Only the gateway listens publicly; Streamlit is loopback. Visitor reservation requires the exact UI service identity and persistent proof and issuance quotas. No client IP is trusted, and provider keys never belong in browser fields. Engineering loopback stays disabled in deployment.

The client accepts only:
- runtime policy `open-manual-section-template-v1`;
- the manual SHA `cf221a29…7e80da89`;
- index `index_f768fbb216836c003701079e`;
- a catalogue reporting `streaming: SAVED_RELEASE_STREAM`.

Saved views from earlier runtimes are rejected before display or continuation. The UI displays released paraphrases and page references only, never the PDF, excerpts or figure crops. Photo and voice stay disabled.

## Checks

Provider-free CI covers the client, the stream decoder, progress and recovery, the gateway and the Streamlit app (`python -m unittest discover -s rider_ui/tests -p 'test_*.py'`). It uses an engineering loopback fixture server. Hosted browser-to-backend answering, Firestore persistence, worker lifetime and disconnect recovery need a hosted run under a new owner scope; see [TODO](../docs/TODO.md).
