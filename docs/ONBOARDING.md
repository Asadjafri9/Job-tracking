# Rich onboarding and profile contract

## Steps and models

1. Identity/cloud disclosure/timezone.
2. Basic professional profile: full/display name, explicit first/last names where needed, contact email separate from login email, international phone, city/country/address if provided, LinkedIn/GitHub/portfolio links, education, employment/projects/skills.
3. Optional useful preferences: desired roles, locations/remote/relocation, availability, salary preference if explicitly supplied, confirmed work-authorization facts with jurisdiction, personal writing tips, reusable responses and current application preferences. DOB/age are optional separate-purpose facts; age is derived from an explicitly confirmed DOB and current local date or entered with an as-of date. Never infer them from education/resume chronology.
4. Upload documents: RESUME, LINKEDIN_PDF, COVER_LETTER, SUPPORTING_DOCUMENT. Text PDF/DOCX except LinkedIn PDF; ten files, each ≤5 MiB, total active quota ≤50 MiB/account. Originals immutable; replacement creates a new version. User chooses a default resume/current cover letter.
5. Preview parsing results, resolve conflicts, confirm useful facts and writing preferences. Do not block dashboard entry for missing optional data.
6. Configure providers, order/fallback, saved/session-only keys and background-monitoring consent.

Profile facts carry UUID, type/group/canonical key, version, origin MANUAL or DOCUMENT_CANDIDATE, source document/page/paragraph anchor, confirmation time and optional sensitivity/purpose tags. Only confirmed versions are eligible for factual answering; retrieved input is limited to relevant facts. User-owned tips are preferences, never permission to bypass approvals or fabricate claims.

## Parsing pipeline

Reserve quota/metadata → validate media/signature/size → private upload → queue PARSE_DOCUMENT. Use pypdf and python-docx for bounded text extraction in a subprocess with 256 MiB memory, 15-second CPU/wall deadline, ≤50 pages, ≤100,000 extracted chars and bounded ZIP expansion (≤25 MiB/1,000 entries). No macros, JavaScript, external fetch, document execution or embedded-file rendering. Malformed/password-protected/oversized/scanned files return explicit status; manual entry stays available.

Normalize text and anchors locally; use an enabled consented provider for structured candidate extraction if the user chooses it. Exclude irrelevant personal sections from requests. Select deterministic anchored sections within the provider input cap; show omitted sections and offer explicit additional extraction operations instead of silently truncating or dispatching unlimited chunks. No binary upload to model vendors is required. Parsing before keys exist can produce local text/section preview; AI extraction runs after provider setup and consent. Store candidate data privately until confirmed/rejected. Page text and uploaded documents are untrusted data, not system instructions.

Show old/new contradictory dates, employers, degree names and numerical achievements; require a user choice, never silently merge. A cover-letter claim is not confirmed by repetition in that letter. Style/tone may be reused after review; factual claims need a confirmed source. Replacing or deleting a source marks affected facts for review and invalidates pending autofill generations; preserved application snapshots remain unchanged.

## Use and UI

Onboarding progress and missing-information panel explain which fields help autofill, email drafting or monitoring. Empty dashboard is real—no fake application cards. Provide Skip for optional fields/documents/provider setup. Document status: UPLOADING, READY, PARSE_QUEUED, PARSING, REVIEW_REQUIRED, CONFIRMED, UNSUPPORTED, FAILED, DELETING. Distinguish original-file readiness from parsed-fact readiness.

Sensitive facts are excluded from default provider context and monitoring. Enable purpose-specific use only after explicit consent; demographics/final certifications remain manual. A confirmed generic authorization fact cannot answer a different country's legal question without exact matching scope. Default application knowledge is most-recent-first confirmed records, with explicit user selection when repeated sections are ambiguous.

Acceptance: exact-source candidate preview and conflict resolution; no unconfirmed claims; 10-file/50 MiB quota races handled; parser restart/limits fail safely; optional data isn't required; keys/docs/facts remain isolated between two users.
