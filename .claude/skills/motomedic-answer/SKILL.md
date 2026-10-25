---
name: motomedic-answer
description: Answer a MotoMedic rider question locally with the real answer path. It runs real retrieval and the release gate on the pinned section index, with a Claude Code Haiku subagent (effort high) writing the draft instead of the Anthropic API. Use when asked to try, test, demo or compare a MotoMedic question. Needs no API key, ledger or cloud service.
---

# Answer a MotoMedic question locally

The runtime makes one Haiku call per turn. Here, that call is a Claude Code subagent, and everything else is the serving code ([docs/EXPERIMENTS.md](../../../docs/EXPERIMENTS.md)).

## Inputs

The question comes from the user's request. Prior turns are optional: when it is a follow-up, write the earlier turns to `build/local_answers/<name>/history.json` as `[{"question": ..., "response": ...}]`.

The command needs Python with `sentence-transformers` and NumPy. It also needs a BGE-M3 directory at revision `5617a9f61b028005a4858fdac845db406aefb181`, given with `--model` or the `MOTOMEDIC_BGE_M3` environment variable. If either is missing, stop and point the user to docs/EXPERIMENTS.md.

## Steps

1. Pick a short folder name, then run from the project root:

   ```sh
   python tools/local_answer.py prepare --question "<question>" --out build/local_answers/<name> [--history build/local_answers/<name>/history.json]
   ```

   If it prints `NO_MODEL_CALL`, nothing was retrieved. Report the fixed message and support route it printed, and stop.
2. Spawn exactly one subagent with `model: haiku` and `effort: high` (the runtime's effort). Pass it the absolute folder path and this prompt:

   > You are the answer generator for MotoMedic. Work only in this folder: `<absolute folder>`.
   > 1. Read instructions.md in that folder and follow its system prompt exactly.
   > 2. Read model_input.txt (the rider question, earlier conversation, manual sections and WARNINGS TO DECIDE) and schema.json (the exact JSON schema your answer must match).
   > 3. Write only the single JSON object to draft.json in that folder with the Write tool.
   >
   > Do not open any other file, the repository or the web. Do not explain your answer outside the JSON. Reply with just "written" when done.

   Do not edit draft.json yourself, and do not retry. The runtime makes one attempt, and a bad draft is a SYSTEM_ERROR.
3. Run:

   ```sh
   python tools/local_answer.py release --out build/local_answers/<name>
   ```

   Show the user what it prints, unchanged:
   - the route;
   - the rider text;
   - the pages and the support route;
   - the warning decisions.

   A `SYSTEM_ERROR (GATE_...)` line is a gate failure; report its code.

Label the result as a local Claude Code run, not a hosted or API answer.
