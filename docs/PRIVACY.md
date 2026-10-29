# Privacy, logging and retention

Version 1, 29 October 2026. This policy covers rider questions and everything derived from them: what is stored, what is logged, who receives it and how long it is kept. It describes the code in this repository. Where a rule needs hosted configuration that has not been applied, it says so. Nothing here is deployed: the hosted stack is offline while billing is disabled ([status](STATUS.md)).

## Rules

1. **Rider text never enters logs, traces, Git, CI or evaluations.** Questions, answers, conversation history and manual excerpts stay out of all of them.
2. **Logs describe a question by its shape only.** That is its length and word count, plus a keyed hash when `MOTOMEDIC_LOG_HMAC_KEY` is set.
3. **Rider records expire after 24 hours.** An idle session expires after 30 minutes.
4. **Logs are kept for 30 days.**
5. **Rider text goes to one outside party:** the model provider, for the single generation call of a turn.

## What is stored, and for how long

All rider records live in the project's Firestore database. The rider UI has no accounts. A visitor is identified by a signed capability, and the store keeps only a derived owner id.

| Record | Contents | Lifetime in code |
| --- | --- | --- |
| `arm_a_operations/<hash>` | The work snapshot until the turn ends: question, earlier turns, session. Then the saved answer view and its bindings. | 24 hours from creation. The work snapshot is cleared when the turn completes or fails. |
| `arm_a_sessions/<id>` | The session, the last question, the conversation (questions, answers and routes) and the latest view | 24 hours from creation; 30 minutes idle |
| `arm_a_sessions/<id>/arm_a_session_versions/<n>` | One snapshot and view per turn | Same as its session |
| `arm_a_session_operations/<id>` | The session's single-turn lock | 24 hours |
| `arm_a_usage/<owner>`, `network-<owner>`, `global`, `public-visitor-proof-<hash>` | Turn timestamps for rate limits, and single-use proof receipts. No rider text. | 24 hours, or the proof's lifetime |
| `arm_a_usage` ledger documents (the attempt allocation and the Haiku USD ledger) | Counts and money. No rider text. | Permanent by design; they carry no `expires_at` |

The Cloud Tasks body carries only the owner id, the operation id and a payload hash, never the question.

**Expiry today hides records; it does not delete them.** Every read checks `expires_at` and `idle_expires_at`, so an expired record can no longer be loaded, streamed or recovered. Deleting it needs a Firestore TTL policy on `expires_at`. No such policy is recorded as configured. Until one is, expired rider records remain in Firestore. Applying it is a hosted change that needs the owner's scope. The commands are:

```sh
for group in arm_a_operations arm_a_sessions arm_a_session_versions arm_a_session_operations arm_a_usage; do
  gcloud firestore fields ttls update expires_at --collection-group="$group" --enable-ttl --project=motomedic-ai-20261009
done
```

The ledger documents in `arm_a_usage` have no `expires_at` field, so this policy cannot delete or reset them. Firestore deletes expired documents in the background, not at the exact expiry time.

## What is sent to the model provider

The one generation call of a turn sends this to Anthropic's API under the project's API key:
- the rider question;
- up to three earlier turns, with each earlier answer cut to 600 characters;
- the retrieved manual sections.

Nothing is sent when retrieval finds nothing relevant. The provider keeps API inputs and outputs under the account's API terms. This repository does not configure zero data retention, and the trace never records prompt or answer text (`raw_content_logged: false`).

## What is logged

The answer path writes structured JSON lines to stdout ([cloud/common/telemetry.py](../cloud/common/telemetry.py)), which Cloud Run sends to Cloud Logging. Two rules are enforced in code and tested ([test_telemetry.py](../cloud/common/test_telemetry.py)):
- a field name must be on the allowlist `FIELDS`;
- a value must be a number, a boolean, an id, a code or a page, never a phrase with spaces.

Anything else is dropped and its name recorded in `redacted_fields`.

| Event | Fields |
| --- | --- |
| `answer_turn` (one per turn) | Operation id; route and reason codes; failure code. Retrieval: chunk ids, sections sent, pages sent, rerank flags, best reranker score, relevance-floor decision. Gate: version, coverage, citations, excluded warnings, dropped repeats, reworded phrases. Generation: tokens, cache reads and writes, estimated cost, ledger outcome. Stage timings. Question length and word count, and optionally `question_hmac`. |
| `span` | One per stage (retrieval, assembly, generation, gate) under the turn span. Each has a duration and an offset, and shares the turn's trace id. |
| `worker_outcome` | Operation id, outcome code (for example `COMMITTED` or `OPERATION_NOT_COMMITTED`), HTTP status and duration |
| `http_request` | Method, route template (`/v1/sessions/:session_id/questions`), status, error code, replay flag, operation id and latency. Never headers, cookies or bodies. |
| `auth_rejected` | The rejection reason code |

**Trace correlation.** The rider request's trace id (`traceparent` or `X-Cloud-Trace-Context`) is carried in the work snapshot. The API request, the worker run and the turn's spans therefore share one trace in Logs Explorer. Spans are log entries, not Cloud Trace spans.

**Keyed hash.** `question_hmac` is an HMAC-SHA-256 of the question under `MOTOMEDIC_LOG_HMAC_KEY`, cut to 32 hex characters. It links repeats of the same question without revealing the text. The key must be a managed secret. Rotating it makes old and new hashes unlinkable. Without the key, no hash is logged.

**Platform request logs.** Cloud Run also writes its own request log, which this code does not control. It includes the request URL path, the caller's IP address and the user agent. For the UI service, the caller is the rider's browser. These logs follow the same retention below.

## Log retention

Answer-path and platform logs stay in the `_Default` log bucket, whose retention is 30 days. They must not be routed to a sink with longer retention, or exported outside the project. Checking or setting this is a hosted step:

```sh
gcloud logging buckets update _Default --location=global --retention-days=30 --project=motomedic-ai-20261009
```

## Access and requests

Only the project's IAM principals can read Firestore or logs. Every rider route checks the owner, so one visitor cannot read another's session. There are no rider accounts to delete. A rider who wants their data removed before it expires can ask through the support route ([source manifest](../source/source_manifest.json)). The owner can then delete the session and operation documents by id.

## Changing this policy

A new log field must be added to `FIELDS` and checked against rule 1, with a test showing no rider text reaches the log. Any change to what is stored or sent, or for how long, needs this document updated in the same change.
