# Scoped source-structure review v2 (candidate)

**Status: approved exact-scope agent review, consumed only by the candidate v5 loader. Not wired into production, not deployed, and no human signoff.** Frozen v10.14 serving bytes and every earlier approval are unchanged.

## Why

The [stage replay](../../evals/20261023_stage_replay_v1/README.md) found that retrieval and reranking delivered the answer chunk for all 20 answerable test questions. The v10.14 serving gate admitted the answer evidence for only 8 of them, because it admits only reviewed objects (199 of 1,691). This package reviews the sections holding the blocked answers, plus the warning, note and caution context those sections need.

## What it approves

| File | Purpose |
|---|---|
| [proposal.json](proposal.json) | Revision 4, SHA-256 `38dc0709…a1cc3d`. Contains 12 components, 25 sections, 1 unparented footnote and 79 exact immutable objects, with links, mandatory reviewed displays and review notes. Built by [build_proposal.py](build_proposal.py). |
| [independent_review.json](independent_review.json) | SHA-256 `d7dfdc6e…bc58c8`. Decision `APPROVED_EXACT_SOURCE_OBJECT_CONTEXT_ONLY`, no open findings, 12 approved components, 3 accepted residual limitations. |
| [review_round1_findings.json](review_round1_findings.json), [round2](review_round2_findings.json), [round3](review_round3_findings.json) | Retained findings from rounds 1–3. |

Components: luggage and accessory loading (p14–15), RE app phone compatibility (p54), display language menu (p50–51), compass note (p57), tell-tales (p62), battery handling notes (p104/105/107), headlight beam adjustment (p109), tail and licence-plate lamp (p110), brake-pad wear check (p90–91), rear-suspension preload (p116–117), storage precautions (p120), and the lubricant-table footnote (p21). The page-21 lubricants table also gains its numbered notes and its DOT 4 footnote.

Every object was checked against the rendered original PDF pages (manual SHA `cf221a29…`). The two lone "0" objects on page 51 are speedometer digits in a figure, so they are excluded and stay gaps. No figure objects are approved. The approval grants no parent-text, action, diagnosis or OEM-sequence authority.

## Review history

The proposer was this session's main agent. The reviewer was a separate-context subagent that rendered pages itself and simulated the loader without any provider calls.

| Round | Proposal SHA | Verdict | Main findings |
|---|---|---|---|
| 1 | `874473f1…` | Changes required | F1 blocking: the parser lost the merged 32 psi cell on p117. Major: missing p14 luggage body (110 km/h), p63 ABS conditions, p91 pad criterion, battery warnings, fuel warnings, DOT 4 footnote. Also display wording and section paths. |
| 2 | `52867152…` | Changes required | R2-N1 blocking: links to p63 and p8/27 objects pulled their broad v4 closures, so 18 unrelated warnings appeared in a turn-signal answer. |
| 3 | `df2200c8…` | Changes required | Two one-string fixes: the ABS check-up qualifier and a stale role name in a note. |
| 4 | `38dc0709…` | **Approved** | Byte diff is exactly the two strings. The closure/display simulation was re-run, and no answer pulls in unrelated warnings. |

## Accepted residual limitations

- **R2-N2:** fuel no-flame warnings for draining fuel are carried as a review note only. Linking them would import their broad v4 closure.
- **R2-N7:** two brake-pad objects keep their earlier v4 contexts, because v2 never rebinds an existing approval.
- **R2-N3:** the merged-cell FACT display has not been exercised by the hosted verifier. A rejection fails closed. Run a hosted probe before any live use.

## Use

[serving_source_authority_v5.py](candidate/serving_source_authority_v5.py) subclasses the v4 serving authority. It is kept outside the bound serving tree so the frozen v10.14 serving inventory stays unchanged. It pins both hashes and fails closed on any change. Tests: [test_serving_source_authority_v5.py](candidate/test_serving_source_authority_v5.py).

Promoting it would need, as a separate scope: a new serving manifest, hosted CI and build, a hosted verifier probe, and owner deployment authorization. Hosted billing is currently disabled by the budget guard.
