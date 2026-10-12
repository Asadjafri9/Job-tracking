# Three-provider BYOK and fallback

## Initial adapters

| Provider | Initial model | Adapter boundary |
| --- | --- | --- |
| OpenRouter | `deepseek/deepseek-v4-flash` | fixed OpenRouter API origin, explicit evaluated model/endpoints and supported output mode |
| xAI Grok | `grok-4.7` | fixed xAI API origin; evaluated structured-output schema |
| Google Gemini | `gemini-3.8-flash` | Google GenAI SDK/fixed API origin; supported schema subset |

The owner's spoken “DeepSeek before flash” is interpreted as DeepSeek V4 Flash, verified in the [OpenRouter catalog](https://openrouter.ai/deepseek/deepseek-v4-flash). Grok means xAI. Recheck availability/capabilities before enabling an adapter; UI can select only evaluated server-catalog models, not arbitrary endpoints. Provider keys are optional individually: one valid enabled key is sufficient; three can form a chain.

Contract operations: extract_profile_candidates, analyze_job_context, draft_form_answers, draft_email, classify_job_openings. Every adapter normalizes outcome/schema/usage/error metadata. Use supported structured output where available, then authoritative Pydantic validation. If a chosen OpenRouter endpoint lacks the required schema mode, select an allowed schema-capable endpoint or use a separately evaluated JSON/validation strategy; never assume OpenAI-compatible HTTP means identical schema support. No tools, URL browsing, application actions or credentials in prompts.

References: [OpenRouter structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs), [xAI structured outputs](https://docs.x.ai/developers/model-capabilities/text/structured-outputs), [Gemini structured outputs](https://ai.google.dev/gemini-api/docs/generate-content/structured-output?hl=en).

## Key storage and consent

Saved mode: per-credential AES-256-GCM data key, random nonce, AAD `user_id/provider/credential_id`; wrap DEK using versioned Key Vault KEK. Store ciphertext/nonce/wrapped DEK/KEK version/status/last4 metadata, never plaintext. Worker/API unwrap only within an authenticated owner job/request, and hold plaintext for the outbound request only. Key material cannot be returned by GET, placed in provider prompts, traces, outbox or exports. Rotate by rewrapping DEKs; deletion destroys ciphertext/wrapped key immediately and disables all associated jobs. Never send one vendor's key to another.

Credential disable/delete/replacement writes an independent content-free revocation entry (account/credential/version IDs and time) before acknowledgement; failure disables use and reports pending repair. Replaying these entries after restore must prevent an older credential version from being re-enabled.

Session-only mode: key entered in trusted UI memory and supplied for interactive requests; not persisted by server. It cannot support unattended monitoring. Explain saved-key background use and provider/downstream processing, model/order/cost limits. Fallback requires a separate explicit consent from using a provider interactively: the settings record stores its consent revision, and routes after the first are rejected unless that consent is current. Switching must be visible in results/usage. Background consent covers job-text/preferences only, not full personal details or original documents; background routes likewise require the shared background-consent revision and each credential's own background-purpose permission. User can revoke background permission without deleting interactive credentials.

OpenRouter downstream providers must satisfy the configured privacy routing policy; default disallow endpoints marked as collecting/training on submitted data. Do not claim that this setting covers all vendor policies or guarantees zero retention. An unavailable policy-compatible endpoint is an explicit failure/fallback condition, never an excuse to relax privacy silently. See [OpenRouter provider routing](https://openrouter.ai/docs/guides/routing/provider-selection).

## Outcome state machine

| Outcome | Action |
| --- | --- |
| Success with valid safe output | return/save the intended result once; record actual provider/model and usage |
| Explicit exhausted credit/quota | mark cooldown/exhausted for this request; try next enabled consented provider |
| Definitive 429 | bounded Retry-After once only if short and within deadline; otherwise next eligible provider; distinguish daily exhaustion from transient rate limit |
| Definitive unavailable/model-capacity error before a result | next provider, with bounded attempt budget |
| Invalid/revoked key (401/403) | mark credential needs_attention, notify settings; use next provider only if fallback consent permits; no repeated bad-key loop |
| Bad input/schema capability mismatch | stop and fix input/adapter; do not keep charging all providers |
| Refusal, missing facts, unsafe/unsupported claim | surface refusal/needs_information; no provider switching to bypass it |
| Timeout, connection loss after dispatch, ambiguous 5xx/completion | UNKNOWN; stop automatic retry/fallback; possible charge warning; explicit user new request only |
| All eligible providers exhausted/unavailable | PROVIDERS_UNAVAILABLE; preserve draft/facts, pause affected monitor AI, show actionable notification |

At most one normal attempt per provider plus one permitted short 429 retry overall, all within one 60-second interactive deadline. Disable SDK retries unless explicitly accounted for. Cancelation is not proof the provider stopped. Background jobs may reschedule a definitive no-result outage at most twice within their run window; UNKNOWN is not replayed automatically.

Limits: ≤12,000 input tokens/request; output ≤4,000 tokens for a bounded form batch of at most ten open questions (larger forms chunk explicitly), ≤1,500 for email, ≤2,000 for extraction/classification. Each answer respects actual field limits and 200-word default. Daily usage counters reset at 00:00 UTC and display their reset time; local monitoring dates remain independent. User limit 50 interactive operations/day and five source-classification operations/day; provider attempts tracked separately, with a total ceiling of 150/day/account. These ceilings prevent unlimited fallback but are not dollar-spend guarantees. Show usage and optionally user-configured estimated budget from verified pricing metadata; never claim provider balance knowledge unless its API supplies it.

## Idempotency and quality

One active interactive operation/account; request state and attempt records created transactionally before dispatch. Fingerprint input without key material; stable idempotency key never creates a second result/charge automatically within its retained window. User explicitly regenerating creates a new operation. Form/email output persists only in the owner-scoped draft/session selected by the feature; sources/claim anchors recorded with it. Background job classification persists normalized posting evidence, never raw credential/content logs.

Test every adapter and enabled fallback path against shared source-reference/factuality/option/email/extraction corpora. Track prompt/model version per result. A failed provider can be disabled independently; core tracker/no-AI factual fill and copy-email paths continue. Periodic model availability changes create an actionable configuration issue, not an automatic unevaluated model upgrade.
