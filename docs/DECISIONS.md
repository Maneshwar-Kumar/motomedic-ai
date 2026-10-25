# Decision log

These are the owner's decisions that shaped the current design, oldest first. Each links to the record that holds the exact instruction. Earlier designs and their evidence are in [archive/](../archive/README.md).

| Date (2026) | Decision | Record |
| --- | --- | --- |
| 9 Oct | Use the supplied Himalayan 450 BS6 owner's manual, RAM00818/A, as the only source. The rider confirms Himalayan + BS6, and no model-year question is asked. | [source_manifest.json](../source/source_manifest.json) |
| 11 Oct | Reset the repository to one current specification. Earlier competing designs were removed and kept in Git history. | [reset receipt](../archive/reports/reset/20261011/README.md) |
| 12 Oct | Build a public evaluator URL that a human reviewer can use. | [owner_scope_v1](../archive/reports/public_evaluator/20261012/owner_scope_v1.json) |
| 12 Oct | Use Claude Haiku as the only model and drop Gemini. | [owner_model_scope_v3](../archive/reports/public_evaluator/20261012/owner_model_scope_v3.json) |
| 12 Oct | Publish the repository, the manual and the original index for reviewers. | [public review](../archive/reports/public_evaluator/20261012/public_review/owner_public_review_scope_v1.json), [index release](../archive/reports/public_evaluator/20261012/public_review/owner_index_release_scope_v1.json) |
| 12 Oct | Waive independent manual answer review for the functional demo; prove that the agent retrieves and answers. | [functional acceptance](../archive/reports/public_evaluator/20261012/public_review/owner_functional_acceptance_scope_v1.json) |
| 12 Oct | Raise the token ceiling to 2,000,000 (superseded on 25 Oct). | [token ceiling approval](../archive/reports/public_evaluator/20261012/haiku_v10_13/admission/owner_token_ceiling_approval_v1.json) |
| 23 Oct | Run a private hosted evaluation; billing was re-linked for it and disabled again afterwards. | [private hosted v5 scope](../evals/20261023_private_hosted_v5/owner_scope_v1.json) |
| 24 Oct | Remove the separate verifier. One generation call fills an answer template, and a deterministic gate releases it. | [owner_decision_v1](../evals/20261024_answer_release_v1/owner_decision_v1.json) |
| 24 Oct | Settled the template details:<br>- empty sections may be omitted;<br>- disclaimers stating a value or page must cite;<br>- page references must belong to cited objects;<br>- nothing retrieved means the fixed message and support route with no model call. | [owner_decision_v2](../evals/20261024_answer_release_v1/owner_decision_v2.json) |
| 24–25 Oct | Changed the design:<br>- no review layer;<br>- top-5 retrieval, with the reranker ordering the 5 only when the searches disagree;<br>- whole sections as plain text, with warnings attached at index time;<br>- one system prompt;<br>- test Haiku, Haiku at high effort and Sonnet on the same 30 questions;<br>- retire draft-then-verify in the repository. | [owner_decision_v3](../evals/20261025_answer_release_v3/owner_decision_v3.json) |
| 25 Oct | Integration bar: Haiku at default effort scored 24/30, below the 27/30 bar, so the integration was stopped and reverted. The owner then accepted Haiku at high effort (30/30) and had it merged. | [owner_decision_v4](../evals/20261025_answer_release_v3/owner_decision_v4.json) |
| 25 Oct | Changes to code and the repository:<br>- merge to `main`;<br>- remove the token ceiling;<br>- keep the current build for experiments, with Claude Code generating answers locally;<br>- reorganize the repository for an external reviewer. | [owner_decision_v5](../releases/owner_decision_v5.json) |

## What did not change

- **No deployment.** No decision since 23 October authorizes deployment, public opening, billing restart or extra provider spending.
- **Hosted ledgers.** The Firestore ledger documents are unchanged. The token ceiling is gone from the code only; the 100-attempt allocation and the shared Haiku USD1 ledger still bind.
- **Budget guard.** The lifetime budget stays at INR3,120, with the billing-disconnect guard at INR2,960. Billing is disabled.
- **Signoff.** No decision is a human factual signoff of the answers.
