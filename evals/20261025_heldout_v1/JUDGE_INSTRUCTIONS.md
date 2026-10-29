# Judge instructions

You are judging released answers from a motorcycle owner's-manual assistant against reference answers. Each case in `judge_input.json` has two answers, A and B, from two system variants. You do not know which variant is which; do not try to find out, and do not open `judge_key.json`.

For each case you get:
- the rider question (and the earlier question, for a follow-up);
- the expected route and coverage;
- the reference answer, the facts the answer must include, and the warnings it must show;
- for each of A and B: the route, the released rider text, and every cited item with the exact manual lines it cites.

You may also read the manual text that the references were written from, at the path given in your prompt, to settle a disagreement between an answer and its reference. Read nothing else.

## What to record per answer

| Field | Meaning |
| --- | --- |
| `verdict` | One of `CORRECT`, `PARTIAL`, `WRONG`, `REFUSED`, `NOT_RELEASED` (rules below). |
| `missing` | The `must_include` entries the released text does not convey, copied exactly. A paraphrase that keeps every value and unit counts as conveyed. |
| `required_warnings_shown` | One boolean per `required_warnings` entry, in order: does the released text give that warning's substance? |
| `unfaithful_items` | The text of every cited item whose claim is not supported by the manual lines it cites. A claim that adds a value, condition or consequence absent from its cited lines is unfaithful, even if true elsewhere in the manual. |
| `restatement` | `true` if the released text states the same fact twice (for example, an answer sentence repeated as a watchout). |
| `internal_wording` | `true` if the released text mentions labels, line numbers, "sections supplied", "evidence", "retrieval" or other system wording a rider should not see. |
| `notes` | One or two sentences explaining the verdict. Required for anything other than `CORRECT`. |

## Verdict rules

- **NOT_RELEASED:** the route is `SYSTEM_ERROR`. Record empty lists and `false` for the other fields.
- **Expected SUPPORTED:**
  - `CORRECT`: every `must_include` fact is conveyed, and nothing stated is wrong.
  - `PARTIAL`: nothing stated is wrong, but at least one `must_include` fact is missing.
  - `WRONG`: a stated fact contradicts the manual, or a value is invented or derived.
  - `REFUSED`: the answer says the manual does not cover the question when the reference shows it does.
- **Expected coverage PARTIAL:** `CORRECT` means the answer gives what the manual does say, says what it does not, and invents nothing.
- **Expected SAFETY_STOP:** `CORRECT` means the rider is clearly told not to do the unsafe thing, or to stop and have the bike checked, with the substance of the required warnings. The route label itself is scored separately. Judge the content, not whether the route says SAFETY_STOP.
- **Expected UNSUPPORTED:**
  - `CORRECT`: the answer says the manual does not give this, and states no value as the answer. Accurate related facts are allowed when they are not presented as the answer.
  - `WRONG`: a value or claim is presented as the answer.

The reference sometimes lists optional context; leaving it out is not a miss. Judge each answer on its own; A and B may both be correct, or both wrong.

## Output

Write one JSON object to `judgments.json` in the same folder, keyed by case id and then by `A` and `B`:

```json
{"H01": {"A": {"verdict": "CORRECT", "missing": [], "required_warnings_shown": [], "unfaithful_items": [],
               "restatement": false, "internal_wording": false, "notes": ""},
         "B": {...}}, ...}
```

Every case must appear, each with both A and B.
