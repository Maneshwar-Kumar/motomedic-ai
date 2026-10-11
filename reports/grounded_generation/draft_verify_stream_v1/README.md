# Draft, verify, stream integration

Status: implemented with software boundary tests; real-output review is in progress. No deployment or semantic acceptance claimed.

[Owner architecture decision](../../../docs/architecture/DRAFT_VERIFY_STREAM_DECISION_20261011.md) is authoritative for this work. Frozen v5 remains historical. Its hosted run 38155908875 stopped before provider calls because source-authority tests used a local-only index path. No real model quality result was produced by that run.

The new runtime uses the same immutable source-authority package and index. Original 161-case approvals and source-object bytes remain unchanged. Source-context gaps continue to limit coverage; open Q&A does not authorize unreviewed source bodies.

New reports will distinguish local synthetic boundary checks, hosted real-output measurements, original-page review and deployment state. Provider calls must remain within existing authorized allowances. Document layout verification is recorded separately from structural editing.

The strict verifier result carries RELEASE_COMPLETE, RELEASE_PARTIAL or SHOW_FALLBACK for ordinary answers, with separate clarification and safety decisions. Application code owns final validation, durable save and accepted-buffer delivery. A limitation must be in the proposed response before verification. One correction and verification are permitted; transport, schema, quota and integrity failures remain SYSTEM_ERROR. Fixed fallback/error responses make no additional model call.

Frozen v6 passed 16 verifier/controller tests and 64 UI/client integration tests. Hosted run 38158688412 evaluates its actual outputs within the existing provider allowance. An independent exact-copy inspection subsequently found a corrupted apostrophe in its two fixed messages; v6 is preserved as failed for that requirement. The corrective v7 uses ASCII source escapes and independent expected-string tests. Its copy correction does not inherit a claim of real-model acceptance.

Current software review records: [v6 boundaries](../v6/verified_qa_review.json), [delivery and recovery](../v6/ui_streaming/REPORT.md), and [v6 fixed-copy defect](../v7/v6_encoding_defect.json). Actual hosted latency, question coverage and original-page claim support will be reported separately. The real-output harness uses the existing hosted immutable BGE/BM25 index snapshot and fsync operation files; it does not certify deployed Qdrant request latency, production Firestore or Cloud Run disconnection behavior.
