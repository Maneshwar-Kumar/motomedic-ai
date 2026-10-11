# Owner-approved separation of technical claims and policy caveats

On 11 October 2026, the owner approved policy caveats using approved policy references without manual citations, while retaining technical evidence gates. Preserve the complete 161-case UI question-core run as the baseline; rerun the failures attributable to caveat rejection with 5-7-second intervals.

Arm A now accepts a policy-only caveat only when its complete claim exactly matches the selected approved step, its record scope remains intact, its wording has no unreviewed variants, and every policy reference is bound to an unchanged PRODUCT_POLICY object in that same record. Only FACT and WARNING caveats qualify. Changed content, ACTION claims, PREREQUISITE claims, unbound policy sources and cross-record substitutions fail closed.

Claims with OEM evidence IDs retain the original required-evidence and citation checks. Policy caveats do not contribute IDs to mandatory manual warning or prerequisite coverage. Product-policy IDs are retained separately in the internal response mapping and are never emitted as OEM page citations. The rider presentation rechecks those policy bindings and exact wording. Technical retrieval, source identity, applicability, eligibility, dependency, warning, figure and quality holds remain enforced. The generic B generation path keeps its original strict contract.

The exact approved source package is unchanged. The runtime receives a new composer version, rider contract version and frozen build manifest, so baseline sessions cannot silently acquire the new generation lock.

Evidence: [preserved baseline](../../reports/arm_a/golden161_validation_v1/README.md) and [targeted candidate report](../../reports/arm_a/policy_caveats_v2/README.md). This implementation and hosted evaluation do not change the deployed service or establish full-corpus, browser, Gemma, vision or adaptive-flow acceptance.
