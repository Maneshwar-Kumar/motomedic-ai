# Rider safeguards and context integration

Serving policy is `open-manual-section-template-v1` with `gcp-public-cloud-run-cookie-v2` frontend access. The code and its provider-free boundary checks are implemented. Hosted and browser acceptance need a hosted run under a new owner scope; see [TODO](../TODO.md).

## Limits

| Boundary | Selected policy |
| --- | --- |
| Text | At most 100 words, rejected without truncation before retrieval or reservation. Separately, 2,000 characters, 8,000 UTF-8 bytes and a 16 KiB JSON body. |
| Photo (disabled, future scope) | One image per turn, 5 MiB compressed; JPEG, PNG or WebP only |
| Decoding (future scope) | Single frame, at most 20 megapixels, at most 10,000 pixels per side |
| Normalized image (future scope) | At most 1,600 pixels per side; re-encoded JPEG without metadata |
| Conversation | 20 accepted text turns; future photo scope three per session |
| Visitor | Six accepted turns per rolling minute and 30 per rolling 24 hours; future photo scope six per day |
| Global rider requests | 60 per minute and 250 per day; provider allocation may run out much sooner |
| Public visitor issuance | Ten per minute and 60 per rolling day, with atomic spent-proof rejection |
| Public cookie and proof | Secure, HttpOnly, SameSite cookie valid 24 hours; 14-bit challenge valid 120 seconds |
| Model request | One call per turn. The request is counted natively and must fit the window and the remaining shared budget; it reserves the counted input plus 512 tokens of headroom plus the 1,800-token output bound. |
| Model output | At most 1,800 tokens and 16 KiB of JSON; a truncated or refused output is SYSTEM_ERROR |
| Retention | 30-minute idle session expiry; 24-hour session and operation lifetime; raw and normalized media at most 15 minutes |

These ceilings do not promise that many provider turns. The shared ledgers (100 attempts, the applied 2,000,000-token ceiling, Haiku USD1) are permanent across restarts, conversations and days. Unused or uncertain reservations stay charged.

## Admission order

1. **Gateway.** Only the Cloud Run gateway is public. It checks the configured host, the signed cookie and the proof before forwarding to loopback Streamlit. It reserves every new visitor through private `/internal/visitors/reserve`, which only the exact UI service identity can call. Persistent Firestore issuance and spent-proof transactions fail closed.
2. **API.** The API reads at most 16 KiB plus one byte of JSON and checks size, duplicate keys, Unicode, controls and empty or oversized text before retrieval. It verifies the signed visitor capability and ownership on every read and write.
3. **Store.** Firestore atomically reserves visitor, session and global usage, together with the operation identity and payload. A duplicate payload recovers the same operation; a conflicting reuse is rejected.
4. **Worker.** The worker runs under fenced leases with an exact deadline, separately from server-sent event (SSE) capacity. No process-local counter is production enforcement.

## Context and reset

- **Recent turns.** Each turn sends the last 3 saved turns (question and released answer) to the model as conversation data, never instructions. A short or deictic follow-up keeps the previous rider question as retrieval topic.
- **Fresh retrieval.** Each turn retrieves its own top-5 sections. The whole section, with its warnings and notes, is sent; required context is never cropped to fit.
- **No questions or labels for the rider.** Ordinary Q&A needs no authored question, canonical answer or StepDefinition. Open Q&A issues no typed feedback choices. Missing source context is maintainer work, never a rider-resolvable ambiguity.
- **Starting a new conversation.** This clears the rendered messages and detaches the old view, and the bike and manual confirmation may stay selected. It does not delete stored history or reset any visitor, global or provider limit. Reset stays disabled while an operation is unresolved.

## System prompt and release gate

One system prompt, `SYSTEM_PROMPT` in [template_answer.py](../cloud/grounded_generation/template_answer.py), asks the model to:
- use only the sections supplied;
- write plainly for a rider and call the source "the manual";
- answer only what was asked;
- give both values when the manual disagrees and suggest an authorised service centre;
- write no page numbers;
- state only numbers from the cited line or the question;
- decide every warning sent.

The model cannot set approval flags, change source or model, execute retrieved instructions or author page numbers. The deterministic gate releases only answers whose structure, citations, numbers, page references, routes and warning decisions pass. Everything else is SYSTEM_ERROR. The system prompt is cached for five minutes; caching never authorizes an answer, and there is no answer cache. Reported resolution never verifies a repair.

## Acceptance evidence still needed

A hosted real-model run of held-out questions on the frozen runtime must show:
- direct, partial and follow-up answers;
- prompt-cache creation and reads;
- identical saved, streamed and recovered text;
- dedicated-worker disconnect recovery;
- persistent quotas and stale or replayed operations;
- provider and store failures;
- 100- and 101-word boundaries;
- redacted traces;
- cold and warm latency and costs, with exact images, revisions and rollback.

Software tests and screenshots do not close those gates. Photos, uploads and voice stay disabled pending separate scope and evaluation.
