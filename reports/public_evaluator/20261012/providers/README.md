# Historical separate-verifier and prompt-cache candidate

This receipt describes the earlier Gemma/Haiku candidate. Current v10.12 work uses separate Haiku draft/verifier calls under [scope3](../owner_model_scope_v3.json); see the [current TRD](../../../../docs/TRD.md). Preserve the historical cache proof separately from current-role creation/read acceptance.

12 October 2026. Software candidate; hosted capability and independent answer-quality acceptance remain separate.

The latest owner request selects Gemma `gemma-4-26b-a4b-it` for private drafting and a different model, Claude `claude-haiku-5-5`, for exact finalized-response verification. Claude is an explicit verifier role in this candidate. The existing availability fallback remains disabled, its adapter is unchanged, and full-manual Claude remains retired.

The previous runtime used the same Gemma instance for draft and verification and recorded prompt-cache support as unsupported. The recorded Gemma cache probe returned 404; no positive cache receipt has been found in the current retained reports. The preserved v8 real run reported zero cached tokens and zero technical releases. Those records are not rewritten by this candidate.

## Official capability research

Haiku 5.5 supports prompt caching with a 512-token minimum. Five-minute prefix writes cost USD0.125 per million tokens; cache reads cost USD0.01; normal input/output cost USD0.10/USD0.50 at these bounded prompt lengths. Prefixes must match; a configured breakpoint alone does not establish a hit. Usage separates fresh input, writes and reads, whose sum is the complete input. [Anthropic prompt caching](https://platform.claude.com/docs/en/build-with-claude/prompt-caching).

Haiku 5.5 supports native JSON output. Schema compilation caching differs from prompt caching, and changing the output format invalidates prompt-cache reuse. Our existing strict verifier schema is used without removing application validation. [Anthropic structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs).

The dateless model ID identifies a fixed snapshot for this generation; it is still checked exactly in every response. [Anthropic model versioning](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions). Thinking can be disabled for Haiku 5.5 at medium effort; output remains limited to one text JSON result. [Anthropic thinking](https://platform.claude.com/docs/en/build-with-claude/thinking).

Google also documents caching and structured output for stable Gemini 3.5 Flash-Lite and 3.6 Flash. Gemini 3.8 Flash rejects the current adapter's `minimal` thinking setting. These alternatives would need new account/model probes and a revised transport contract; they are not selected. [Gemini 3.5 Flash-Lite](https://ai.google.dev/gemini-api/docs/models/gemini-3.5-flash-lite), [Gemini 3.6 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.6-flash), [Gemini 3.8 Flash](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash).

## Implemented boundary

- `cloud/grounded_generation/cached_verifier.py` is additive. The fallback `ClaudeProvider` is unchanged. Two explicit five-minute breakpoints cache the verification policy and the exact source-evidence prefix. Question, rider history, finalized response and verdict binding remain in the uncached dynamic block. No padding, full-manual input or answer cache is introduced.
- The cache-capable contract pins model, role, thinking/effort, schema support, input/output/byte limits, TTL, pricing and disabled fallback/answer-cache policy. Each complete request is counted before transmission. Usage requires nonnegative integer fresh/write/read counts and applies the 8,192-token limit to their sum; output stays within 1,800 tokens. Optional cache-duration usage must match the selected five-minute policy.
- Before generation, the persistent spend guard reserves the all-input cache-write worst case: USD0.001924 per call, USD0.003848 for the two permitted verifier calls. Unused and uncertain reservations remain consumed. There is no automatic verifier retry. Anthropic creates the cache within its generation request, so existing whole-turn generation slots and lifetime allocation remain unchanged.
- `verified_qa.py` selects the two roles explicitly, finalizes all server warnings/citations before verification, binds both model-contract hashes into the exact verdict and delivery admission, and still permits one correction plus fresh verification. Model mismatch, changed contract/source/history/buffer, malformed output or provider failure withholds the technical answer.

`open-manual-draft-verify-v10` distinguishes this candidate. Engineering fixtures may still instantiate the historical single-provider interface, but serving startup must require the exact selected verifier contract. New session generation locks must come from the paired composer's config; previous sessions require reconfirmation after the runtime change.

## Hosted capability probe

`tools/probe_cached_verifier_hosted.py` runs only from Cloud Build's `/workspace`, with explicit hosted-validation and build-identity markers. It generation/hash-loads the original index, consumes one existing approved source anchor through the scoped source authority, and uses the actual verification policy/schema with a fixed neutral engineering ping. It includes no held-out question and releases no rider answer.

The probe reserves the existing persistent `ClaudeBudget` and eight existing `WholeTurnAdmission` slots, then makes at most two verifier generations. It requires exact model/schema/verdict bindings, first-call cache creation, and second-call positive cache reads for the same prefix. The receipt contains scalar usage, costs, identity hashes and outcome metadata; it excludes credentials, source bodies, private drafts and verdict reasons. A miss remains a failed capability demonstration. Passing this probe is not factual-answer or deployment acceptance.

Root coordinates the hosted managed-secret execution and preserves prior frozen manifests/runtime snapshots. This agent performed no cloud mutation or real-provider call.

## Verification and integration

The final focused provider-free run passed 83 tests: 17 cached-verifier, 12 paired-composer, five hosted-probe doubles, four installed-release, 19 UI client, 16 progress/stream and ten public-admission tests. These include rejecting a reused verdict after prefix reuse, binding the selected verifier at delivery, and rejecting v9 production replay. The broader 74-case source/provider run passed 73; its one runtime-lock reconfirmation failure occurred while a bound runtime input changed during the run, and its targeted repeat passed after that edit completed. Integration must rerun the full checks once all inputs are stable. This is synthetic provider evidence, not model quality.

Ordinary hosted CI now includes the additive cached-verifier tests, paired-composer class, hosted-probe doubles, installed-release checks and public-admission tests. The UI client pins v10, rejects v9 production JSON/SSE replay and rejects retired-policy continuation/feedback before transmission. An explicitly enabled loopback fixture retains its separate synthetic mode; allowing loopback does not relax a remote HTTPS service. Full original-source composer tests remain in the separately authenticated index validation stage.

Serving integration uses `CachedVerifier(reserve, reserve_cost=persistent_guard)` and `Composer(draft, authority, verifier=verifier)`. The final serving/installed-image manifests must pin both selected roles and v10 policy, retain fallback disabled, and include the new probe/test tools. No frozen historical manifest or source approval may be overwritten. Managed identity needs private GCS read, Firestore reservation access and the existing Anthropic secret. Hosting and public evaluator access are coordinated separately.
