# Owned implementation risks

Planning controls are specified; every risk remains OPEN until implementation evidence demonstrates its mitigation. Technical owner: maintainer, operational owner: operator, scope/cost owner: project owner.

| ID | Risk / severity | Planned control and trigger | Owner / verification |
| --- | --- | --- | --- |
| R-01 | Arbitrary forms exceed supported controls / High | Early browser prototype, native control matrix, manual fallback; no unsupported site claim | Maintainer / EXT-003, EXT-006, BETA-001 |
| R-02 | Cross-user profile/document/key exposure / Critical | API ownership, RLS, owner FKs, private storage, AAD-bound encryption and secret canaries; disclosure stops beta | Maintainer / DB-002, KEY-001, QA-001 |
| R-03 | Stale writes or accidental site action / Critical | Bind selected account/document/field/revision/value, preserve edits; no automatic Submit/Next/attestation/attachment | Maintainer / EXT-005–006, TRACK-001 |
| R-04 | False application confirmation / High | Separate click/native submit/site-reported/user evidence; Gmail opening never proves send; immutable correction history | Maintainer / TRACK-001–003, MAIL-003 |
| R-05 | Fabricated achievements, answers or vacancies / High | Confirmed facts/anchors, option validation, reviewed style, bounded extraction and factuality corpus | Maintainer / DOC-003, AI-004, MON-003 |
| R-06 | Provider drift or uncertain charges / High | Evaluated three-adapter catalog, consented fallback/attempt caps; UNKNOWN stops retries; no silent model upgrade | Maintainer / AI-002–004 |
| R-07 | Saved-key compromise or revoked permission still used / Critical | Wrapped per-key DEK, no plaintext persistence/log/export, purpose checks, disable/delete/cancel guards and restore journal | Maintainer/operator / KEY-001–002, DATA-003, AZ-004 |
| R-08 | Source fetching reaches internal services / Critical | Separate pinned-public HTTPS/DNS/IPv6/redirect transport, metadata denial and robots/access rules | Maintainer / MON-002, QA-001 |
| R-09 | Source changes, partial scans or duplicate schedules / High | Stable identities/completeness, no false closure, local-date unique runs/DST/leases/catch-up and deduplicated alerts | Maintainer / MON-003–004 |
| R-10 | Parser workload exhausts runtime / High | Ten 5 MiB documents, bounded subprocess/ZIP/pages/time, API priority and worker limits; revise topology if gates fail | Maintainer / DOC-002, QA-002 |
| R-11 | Gmail prefill fails or message is long / Medium | Best-effort compose link, copy controls/unprefilled Gmail/mailto, no truncation, manual attachment/send | Maintainer / MAIL-002 |
| R-12 | Identity/extension setup unavailable / High | Local fake contract checks; later real signup/reset/exact-ID smoke; production rejects fakes | Maintainer / AUTH-004, AZ-003 |
| R-13 | Partial deletion or restored data/jobs resurrect access / Critical | Immediate revocation, independent journal, durable stages/operator identity cleanup; isolate restore and reconcile jobs | Operator / DATA-003, AZ-004 |
| R-14 | Cloud cost/capacity/availability misses beta needs / High | Future quote/quota review, ten-user caps, limited availability, measured recovery; USD 150 is only an envelope | Owner/operator / AZ-001, AZ-004 |
| R-15 | API drift or scope growth / High | Generated contracts, prior-client checks, PRD/task traceability, evidence gates; changes revise decisions first | Maintainer/owner / SET-003, QA-003 |

P0/P1 security, factuality and evidence invariants cannot be waived. A P2 exception records impact, workaround, owner and follow-up task. Public release needs separate capacity, distribution, licensing and operational decisions.
