# Start here

MotoMedic answers questions about the Himalayan BS6 owner's manual. The answer path works as follows:
- **Retrieval.** Top-5 hybrid retrieval over a section index; the whole section of each chunk is sent as plain text.
- **Generation.** One Haiku call (effort high) fills the answer template.
- **Gate.** A deterministic gate releases the answer or fails closed.
- **No review layer and no verifier.**

It is implemented and frozen as serving manifest v11, but **not deployed**.

Read these first:
1. [STATUS](STATUS.md): what is built, tested, frozen and still open.
2. [Section answer path v3](../reports/evals/20261025_answer_release_v3/README.md): the evaluation and owner decision behind the design.
3. [PRD](PRD.md), [TRD](TRD.md) and [architecture](ARCHITECTURE.md): the specification.
4. [TODO](../TODO.md), [AGENTS](../AGENTS.md) and [CONTRIBUTING](../CONTRIBUTING.md): what to do next and how to work.

[Reports](../reports/README.md) keep the exact evidence of earlier versions and failures. They are history, not the current design.
