# Owner correction: open question answering

Recorded 11 October 2026, Asia/Calcutta.

Owner instruction: "There is no symptom routing. The rider asks questions. If the agent can answer good, else move on." The owner also clarified that the agent is supposed to accept any query, rather than support only the 30 deployed benchmark questions.

The product accepts arbitrary rider questions for the selected bike/manual. It retrieves relevant evidence and answers when the approved source and applicable release gates support the answer. Otherwise it states that it cannot support an answer; it must not require a predefined symptom, record ID or diagnostic branch to accept a question. There is no mandatory symptom-routing or troubleshooting wizard. Clarification is appropriate only when needed to answer the rider's actual question.

The 30 cases remain evaluation data. They are not the production question catalogue. The currently deployed initial API loads reports/ab30_v1_cases.json and requires an exact normalized query/record match; it therefore does not fulfill this open-question product requirement.

Next integration work: replace the benchmark allowlist at the rider boundary with raw-question retrieval and supported-answer selection, preserving source applicability, warnings, dependencies, claim support, citations, durable save, authenticated ownership, complete-unit streaming, recovery and the 24-hour retention policy. Retrieval relevance alone cannot authorize an answer. Arm A exact reviewed wording and scope bindings remain enforced; this correction does not approve free generation or carry old source approval onto new answer objects.

Session history supplies conversational context and request recovery. It does not require issued symptom branches or action feedback for ordinary questions. Existing adaptive-flow code and historical benchmark evidence remain preserved.

Status: product/integration requirement recorded; open-question backend and UI connection are not yet installed. No deployment or new provider calls were performed by recording this decision.
