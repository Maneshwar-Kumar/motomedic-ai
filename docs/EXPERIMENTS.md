# Local experiments with Claude Code as the generator

The hosted service is not deployed, so experiments run here. [tools/local_answer.py](../tools/local_answer.py) runs the serving modules on the pinned section index. Only the single Haiku API call is replaced: a Claude Code subagent (Haiku, effort high) reads the same input and writes the draft.

The stages run as follows:

| Stage | In serving | In a local experiment |
| --- | --- | --- |
| Index | `build/section-index`, verified against the release | `build/index-v3-sections`, verified against [release v11.1](../releases/serving_manifest_v11_1.json) |
| Retrieval | BGE-M3 + BM25, RRF top 5, conditional rerank | Same code, exact search over the pinned vectors |
| Model input, system prompt, schema | `section_assembly`, `template_answer` | Same code, written to `model_input.txt`, `instructions.md`, `schema.json` |
| Generation | One `claude-haiku-5-5` API call, effort high, native JSON schema | One Claude Code subagent, `model: haiku`, `effort: high`, told to match `schema.json` |
| Gate | `template_answer.gate` | Same code |
| Ledger, Firestore, Cloud Tasks | Used | Not used; no API key or spend |

One difference matters when you read results. The API call enforces the JSON schema natively, so field names, enums and required fields cannot be wrong. The subagent is only told the schema, so a structural slip that the API would prevent can still fail the gate locally.

## Setup

1. Use Python 3.12 or newer with NumPy and `sentence-transformers==6.1.0` (CPU PyTorch is enough).
2. Build the section index at `build/index-v3-sections` ([SETUP](SETUP.md#rebuild-the-section-index)).
3. Download BGE-M3 at revision `5617a9f61b028005a4858fdac845db406aefb181`, keeping `pytorch_model.bin`. `prepare` checks the weights' SHA-256 against the index before it runs.

   ```python
   from huggingface_hub import snapshot_download
   snapshot_download('BAAI/bge-m3', revision='5617a9f61b028005a4858fdac845db406aefb181',
                     allow_patterns=['*.json', '*.txt', '*.model', 'pytorch_model.bin', '1_Pooling/*'])
   ```

   Pass the directory with `--model`, or set `MOTOMEDIC_BGE_M3`.

## Ask a question

In Claude Code, type `/motomedic-answer <question>`. The [skill](../.claude/skills/motomedic-answer/SKILL.md) runs the three steps below. To run them by hand:

```sh
python tools/local_answer.py prepare --question "Can I charge my phone from the USB port while riding in the rain?" --out build/local_answers/usb_rain
```

Then spawn one Claude Code subagent with `model: haiku` and `effort: high`. It reads `instructions.md`, `model_input.txt` and `schema.json` in that folder and writes `draft.json`. Finally, release:

```sh
python tools/local_answer.py release --out build/local_answers/usb_rain
```

For a follow-up, pass `--history <file>` with `[{"question": ..., "response": ...}]` for the earlier turns. When nothing is retrieved, `prepare` prints the fixed message and support route itself and no draft is needed. A bad draft is a `SYSTEM_ERROR (GATE_<code>)`; do not edit it or retry, because the runtime makes one attempt.

## Example run (25 October 2026, local)

The question "Can I charge my phone from the USB port while riding in the rain?" ran as follows:
- **Retrieval.** It kept 5 chunks, 3 sections, 36 lines and 11 warnings to decide, and reranked them because the dense and BM25 tops disagreed.
- **Generation.** A Haiku subagent at high effort wrote the draft.
- **Gate.** The gate released this:

> ROUTE: SAFETY_STOP — The manual recommends not using the USB charging port in rainy conditions. This is to avoid damage to your smartphone and the charger. The USB charger works only when the engine is running. Only mobile phones may be charged, and only one at a time. Watch out: The manual recommends against using the USB port in rainy conditions to avoid damage to your smartphone and the charger. Watch out: Do not leave the USB port cap open or partly closed when the port is not in use, to avoid a short circuit. Watch out: Keep the USB port cap closed and locked properly when not in use; the warranty does not apply if the cap is damaged and not sealed properly. The manual gives no rain rating for the USB port. It only recommends not using it in rainy conditions. (Pages 64, 65)

It included 3 warnings and marked 8 not applicable, each with a reason. The rain point is said twice, once as an answer sentence and once as a watchout; that is the known restatement weakness ([TODO](TODO.md)).

## Running a set of questions

For a batch, prepare one folder per question, run one subagent per folder (isolated, so no answer sees another), then release each. To score a batch against canonical answers, follow the [v3 evaluation](../evals/20261025_answer_release_v3/README.md). Its inputs, drafts, gate results and judgments show the format, and new runs belong in `evals/<date>_<name>/`. The 30 existing questions are development cases; a claim about quality needs new held-out questions.
