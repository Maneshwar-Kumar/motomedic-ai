# Approved scope caveat frequency

Owner clarification: approved scope caveats are acceptable in answers; measure where they appear. A caveat alone is not a correctness defect. This measurement adds no provider calls and does not change the historical gate-failure results.

| Method | Delivered answers containing a scope caveat | Frequency among delivered | Frequency among all 30 attempted |
|---|---:|---:|---:|
| A | 5/23 | 21.7% | 16.7% |
| B | 1/11 | 9.1% | 3.3% |
| Combined | 6/34 | 17.6% | 6/60 = 10.0% |

Counted by the frozen approved claim roles `OEM_FACT_WITH_POLICY_SCOPE_LIMIT` and `APPROVED_PRODUCT_POLICY_SCOPE_LIMIT`, then checked for the meaning in actual retained output using the independent output assessment. Ordinary manual safety warnings, operating conditions and approximate specifications are excluded. Count is per answer, not per sentence. Five unique cases produced these six answer occurrences.

Five actual examples from A:

1. GEN007, E20 fuel: “That does not establish approval for fuel above E20.”
2. GEN009, low-fuel figures: “These approximate figures do not guarantee usable range or tell you how far it is safe to ride.”
3. GEN011, seat heights: “These are specification values for guidance, not confirmation of the seat fitted to your bike.”
4. GEN014, fork oil: “This is a specification lookup; it does not supply a fork-service procedure.”
5. GEN033, iOS music: “It does not establish compatibility for other iOS music apps.” B also delivered this meaning as “Compatibility for other iOS music applications is not established.”

The frozen answer definitions included scope caveats in 11/30 cases (36.7%). Six of those cases—GEN025, GEN027, GEN030, GEN039, EXP024 and EXP010—failed the runtime gate in both methods, so their caveats were never shown. Their authored caveats are not included in the delivered-frequency numerator. B's lower observed caveat rate partly reflects its lower delivery coverage; it does not demonstrate a preference to omit caveats.

See `CAVEAT_FREQUENCY.json` for exact case/method records and `ALL_OUTPUTS.md` for the full delivered wording. Existing source/support gates still apply. This clarification does not authorize changing gate behavior or rerunning the benchmark.
