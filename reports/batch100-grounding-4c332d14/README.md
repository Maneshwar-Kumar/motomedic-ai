# Completed batch grounding handoff

The producer's 100-record completion manifest was independently checked against the reserved IDs, latest ledger versions, all author/reviewer/judge byte hashes, frozen objects, independent actor/context bindings, original manual checksum and final catalogue bindings. Completion digest: `4c332d1441417fe25caeadc3b0a83768f32622fd777f7cc9815ed3dca7111590`.

`fixtures.json` contains 100 private engineering regression fixtures. It preserves authored questions/answers/turns, warnings, conditions, forbidden claims, stopping rules, source references and feedback verbatim. Page-associated immutable index objects are candidates only; no new claim support, dependencies, outcome enums or source approval were inferred. The 161-entry catalogue was verified, but this export covers only the new 100 records. The refinement chat owns the expanded 161-case controller evaluation and human_review files.

All 100 records' referenced pages have index objects. All 100 still contain source references without exact evidence IDs. Six new records carry explicit underlying scope/rights blocker cards; those cards remain open. Expected authored routes: 36 SUPPORTED, 29 UNSUPPORTED, 10 AMBIGUOUS, 10 SAFETY_STOP and 15 SYSTEM_ERROR. These are candidate expectations, not measured runtime success rates. Safety, abstention and synthetic outage routes must remain distinct when compiled into typed controller fixtures.

`existing-controller-gates.json` records the real-index offline check: all 11 existing draft source gates rejected generation correctly. It does not measure runtime grounding of the 100 new records. No provider calls, semantic-verifier calibration, retrieval ranking/recall measurement, formal source approvals, cache promotion, deployment, re-embedding or billing change occurred. Semantic accuracy remains NOT_EVALUATED.

Next: the refinement owner must establish exact claim spans and reviewed warning/prerequisite/dependency/figure associations, then compile typed session fixtures and run the expanded controller baseline. Formal source/step/rule/dependency approval is needed before eligible live Gemma evaluation. Draft regression fixtures must never be treated as held-out evaluation data or public repair instructions.

Reproduce from the workspace root:

```text
python audit_gemma_batch_grounding.py --index build/index-bge-final --output reports/batch100-grounding-4c332d14
python verify_gemma_grounding.py --index build/index-bge-final --output reports/batch100-grounding-4c332d14/existing-controller-gates.json
```
