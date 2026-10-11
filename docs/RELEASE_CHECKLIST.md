# Three-pillar private beta release checklist

Every box is unchecked. Attach observed evidence, release commit/image digest, extension checksum/ID, versions and reviewer before checking. Planning readiness satisfies none of these runtime gates. Future Azure tasks are specifications; this planning turn uses no connected Azure.

- [ ] FR-001–013/applicable tasks implemented with evidence; all three pillars demonstrated and exclusions retained.
- [ ] Fresh locked JS/Python install, lint/types/unit/API/build/generated-contract checks pass.
- [ ] Fresh/upgrade migrations, actual runtime-role RLS, owner FKs, two-user/pool isolation pass.
- [ ] Actual signup/login/reset/fresh authentication, CSRF/expiry/logout and extension one-use PKCE grant pass with exact origins/IDs.
- [ ] Rich profile/documents, bounded parsing/conflicts/confirmation/source revisions and sensitive-purpose controls work.
- [ ] Every enabled OpenRouter/Grok/Gemini adapter passes quality/schema/reference gates with model/prompt versions and opted-in live evidence.
- [ ] Saved-key encryption/session-only mode, masked metadata, purpose/fallback/background consent, rotation/revocation and secret canaries pass; no plaintext durable key/log/export/prompt.
- [ ] Exhaustion/429/unavailability follows bounded consented fallback; input/refusal/unsupported claims stop; unknown completion never automatically redispatches.
- [ ] At least 100 labeled controls meet detection/fill gates; zero wrong field/manual overwrite/guessed sensitive choice/extension submission.
- [ ] Ordinary facts/options fill then user reviews; stale page/field/value/profile/account and late results rejected; attachments/attestations manual.
- [ ] Passive trusted submit observations, validation failures/unknown/site signals and same-account offline replay correctly distinguished/deduplicated.
- [ ] Click creates SubmissionAttempted, never confirmed Applied alone; dashboard evidence, confirmation and immutable correction history work.
- [ ] Empty dashboard, filters/date reminders/timezone rules and separate drafts/discovered-job counts work.
- [ ] Email drafting factual/editable/versioned; Gmail has no OAuth/connect prompt, correct encoding and long/failed-prefill copy fallback without truncation.
- [ ] Manual email attachment/send clear; opening compose never means Applied; explicit sent/date confirmation creates one USER_CONFIRMED_EMAIL record.
- [ ] Five-source HTTPS/robots/DNS/redirect/byte/time bounds pass SSRF checks; denied/unsupported/partial results visible.
- [ ] Daily 09:00 IANA-timezone runs with browser closed; DST/edit/restart/catch-up/lease uniqueness and dispatch/completion targets pass.
- [ ] First-scan/new-match notifications/read badge deduplicated; no-key/error/unchanged/closure paths correct; no invented jobs.
- [ ] Export v2 complete with originals/safe ZIP/CSV/checksums/private 24-hour expiry; no credential key material.
- [ ] Deletion revokes sessions/keys/schedules, blocks late results and survives retries; independent journal/receipt/operator identity cleanup pass with 24-hour coverage.
- [ ] Keyboard/screen-reader/360px UI, offline/partial states and worker/API resource/performance gates pass.
- [ ] Current/previous Chrome/compatible API clients pass; installation/manual fallbacks documented; two permitted controlled form environments demonstrated.
- [ ] Future Azure quote/quotas/roles/network/crypto/identity reviewed; no fake production auth/provider/public database/files; deployment/redacted alerts work.
- [ ] Prior-image rollback/isolated restore measured; deletion/revocation replay and queued-job reconciliation prevent resurrection/uncertain provider replay; RPO/RTO recorded.
- [ ] Zero open P0/P1 defects; P2 exceptions record impact/workaround/owner/follow-up.
- [ ] Runbooks/reviewer and owner release decision recorded; ten-user private invitations only.

Release record: commit/version, container digest, extension checksum/ID, environment, runtime/browser/provider/prompt versions, evidence links, P2 risks, reviewer/date and owner decision. Public launch needs separate licensing/store/privacy/support/capacity planning.
