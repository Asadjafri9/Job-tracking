# AI Job Application Copilot

## Comprehensive Product, Architecture, and Implementation Roadmap

This roadmap is designed to take the project from an initial idea to a secure, tested, deployable MVP, with a clear path toward a production-grade open-source product.

The objective is not to generate a large amount of code quickly. It is to build the product incrementally, with explicit requirements, small implementation tasks, measurable acceptance criteria, and tests at every stage.

The roadmap is intentionally broader and more detailed than a normal project checklist. It covers product discovery, technical architecture, repository setup, database design, authentication, profile management, resume processing, browser automation, AI integration, application tracking, Gmail, synchronization, security, testing, deployment, documentation, and future enhancements.

# 1. Product vision and scope

## 1.1 Product objective

Build an AI-powered Job Application Copilot that helps computer science students, recent graduates, and technology professionals manage repetitive job application work.

The product should allow a user to maintain a verified professional profile, use that information to prepare application answers, fill supported job application forms, generate tailored cover letters, track application progress, and manage relevant email drafts.

The system must remain a copilot rather than an autonomous application-submission bot. The user retains control over generated content, form filling, email creation, and final submission.

## 1.2 Core user journey

Step 1 — Build a professional profile

The user adds personal details, education, experience, skills, projects, resumes, and reusable answers.

Step 2 — Open a job application

The Chrome extension identifies supported form fields and relevant questions.

Step 3 — Prepare suggested answers

The AI retrieves relevant profile facts, drafts answers, and flags missing information.

Step 4 — Review and approve

The user reviews, edits, approves, or rejects each proposed answer.

Step 5 — Fill and track

Approved values are inserted into supported fields, and the user can save the application in the dashboard.

## 1.3 Product principles

1. Accuracy over automation: never invent education, employment history, skills, salary information, or work authorization details.
2. Human approval: never submit job applications or send emails without explicit user action.
3. Privacy by design: collect and retain only the data needed for the product.
4. Provider independence: support a common interface for multiple AI providers.
5. User-controlled storage: support local-only operation for suitable features and optional cloud synchronization.
6. Progressive compatibility: support a limited set of form patterns first, then expand based on testing.
7. Open-source core: keep core functionality, documentation, and contribution workflows accessible.
8. Testable implementation: every meaningful feature must have acceptance criteria and appropriate automated tests.
9. Resilience: AI, network, browser, or synchronization failures should not corrupt saved user data.
10. Transparency: show users which information was used to generate an answer and where uncertainty remains.

## 1.4 Selected technology stack

The project owner selected React, FastAPI, PostgreSQL, and Azure on October 12, 2026. These replace the earlier Next.js and Supabase defaults. Supporting tools and individual Azure services below are recommendations to confirm in architecture decision records.

| Area                   | Selected technology or supporting recommendation              |
| ---------------------- | ------------------------------------------------------------- |
| Web dashboard          | React; TypeScript and Vite recommended                        |
| Backend API            | FastAPI and Python                                            |
| Browser extension      | Chrome Manifest V3, React and TypeScript                      |
| Database               | PostgreSQL                                                    |
| Deployment platform    | Azure                                                         |
| Frontend dependencies  | pnpm workspaces recommended                                   |
| Backend dependencies   | Python virtual environment and a committed dependency lock; uv recommended |
| Database access        | SQLAlchemy and Alembic recommended                            |
| Authentication         | Identity provider and session/token contract to select in Phase 01 |
| File storage           | Private Azure Blob Storage recommended                        |
| Validation             | Pydantic in FastAPI; Zod or comparable validation in browser code |
| Frontend unit tests    | Vitest                                                        |
| Backend tests          | pytest with FastAPI API tests recommended                      |
| Browser/UI testing     | Playwright, plus extension-specific tests where needed        |
| Formatting and linting | Prettier and ESLint for TypeScript; Ruff for Python recommended |
| CI                     | GitHub Actions with separate frontend and backend checks      |
| AI                     | Python provider adapters behind authenticated FastAPI operations; BYOK credential flow to select |
| Email                  | Gmail API integration, subject to scope and verification decisions |

Use one FastAPI application organized into modules for the first release. Deploy the React dashboard separately as browser assets. The dashboard and extension use the API for authorized cloud operations; the backend owns database access, private file authorization, provider calls, and integration credentials.

A proposed Azure topology is React on Azure Static Web Apps, FastAPI on Azure App Service for Linux, PostgreSQL on Azure Database for PostgreSQL, private files in Azure Blob Storage, secrets in Azure Key Vault, and monitoring through Azure Monitor/Application Insights. Confirm service plans, region, networking, identity permissions, and budget before provisioning. Decide between a linked API route and a separate API hostname; this affects routing, CORS, and the authentication flow.

References: [React hosting on Azure Static Web Apps](https://learn.microsoft.com/en-us/azure/static-web-apps/overview), [FastAPI on Azure App Service](https://learn.microsoft.com/en-us/azure/app-service/quickstart-python), and [Azure Database for PostgreSQL](https://learn.microsoft.com/en-us/azure/postgresql/overview).

# 2. Roadmap structure and completion rules

The project is divided into 16 implementation phases, preceded by a formal planning phase.

Each task should be small enough to implement, review, and verify independently. A task that becomes too large should be divided again before implementation.

## Definition of done

A task is complete only when all applicable requirements below are satisfied:

- The stated requirement is implemented.
- Relevant tests pass.
- Existing functionality has not regressed.
- Types, validation, and error handling are in place.
- Security implications have been considered.
- Documentation is updated where necessary.
- The changes have been reviewed.
- The implementation evidence is recorded.
- Git changes are committed when the task is ready.

Do not mark a task complete merely because a coding agent reports success.

# 3. Phase 00 — Product requirements and MVP definition

Objective: Establish exactly what the first release must do, what it must not do, and how success will be measured.

Deliverables: `PRD.md`, user journeys, feature inventory, acceptance criteria, and an MVP scope document.

## Task 00.1 — Define target users

Document the initial user groups:

- Computer science students seeking internships.
- Recent graduates applying for entry-level roles.
- Software engineers and other technology professionals.
- Users who repeatedly complete applications across different hiring websites.

For each group, document the most common application tasks and difficulties.

Acceptance criteria: The PRD identifies the primary user, their main problem, and the first use case the product will optimize.

## Task 00.2 — Define user journeys

Write step-by-step journeys for:

1. Account creation and initial setup.
2. Profile creation and resume upload.
3. Opening a supported job application.
4. Detecting application fields.
5. Generating and reviewing suggested answers.
6. Filling approved values into a form.
7. Saving and updating an application.
8. Creating an email draft.
9. Exporting or deleting user data.

Acceptance criteria: Every primary journey has a defined starting point, expected result, failure cases, and user-visible feedback.

## Task 00.3 — Create the feature inventory

Classify features into three groups:

- MVP: essential for the first useful release.
- Post-MVP: valuable improvements that can wait.
- Out of scope: features that should not be attempted during initial development.

For example, basic profile management belongs in the MVP. A fully autonomous agent that discovers jobs, applies to them, and sends messages independently does not.

Acceptance criteria: Every proposed feature has a priority and a clear rationale.

## Task 00.4 — Define functional requirements

Write requirements using stable identifiers such as `FR-001`, `FR-002`, and `FR-003`.

Examples:

- `FR-001`: Users can create and edit a professional profile.
- `FR-002`: Users can upload and manage resumes.
- `FR-003`: The extension can detect supported form fields.
- `FR-004`: Users can review and edit AI-generated answers.
- `FR-005`: Users can fill supported fields after approval.
- `FR-006`: Users can save and update application records.
- `FR-007`: Users can configure an AI provider.
- `FR-008`: Users can create email drafts through an authorized integration.
- `FR-009`: Users can export and delete their data.

Acceptance criteria: Each requirement has a testable outcome rather than vague language such as “works well.”

## Task 00.5 — Define non-functional requirements

Specify expectations for:

- Security and privacy.
- Accessibility and usability.
- Performance and responsiveness.
- Browser compatibility.
- Data integrity.
- Reliability and recovery.
- Observability and debugging.
- Maintainability.
- Open-source contribution.
- Deployment and cost.

Avoid setting arbitrary performance guarantees before establishing a baseline. Record measurable targets during the architecture and testing phases.

## Task 00.6 — Define product success metrics

Track useful product outcomes, for example:

- Percentage of supported forms detected correctly.
- Percentage of generated answers accepted without major edits.
- Form-fill success rate.
- Rate of unsupported-field detection.
- Application records successfully saved.
- AI request failure rate.
- User-reported factual errors.
- Time required to complete a supported application workflow.

Acceptance criteria: Metrics have definitions and collection methods. Sensitive application content should not be collected merely for analytics.

## Task 00.7 — Define product boundaries

Document explicit exclusions for the first release:

- No unattended submission of applications.
- No automatic email sending.
- No scraping large numbers of job sites.
- No guaranteed compatibility with every applicant tracking system.
- No unnecessary collection of credentials from job sites.
- No vector database unless real retrieval requirements justify one.
- No microservices without a demonstrated operational reason.

## Task 00.8 — Review and freeze the initial scope

Review the requirements for duplication, ambiguity, missing failure cases, and unnecessary features.

Phase exit gate: The PRD is sufficiently complete to guide architecture without requiring the coding agent to invent major product decisions.

# 4. Phase 01 — Architecture, system boundaries, and design decisions

Objective: Design the major components and define how they interact before building them.

Deliverables: `ARCHITECTURE.md`, architecture diagrams, ADRs, interface contracts, and a threat-model draft.

## Task 01.1 — Define component responsibilities

Document the responsibilities of:

- Chrome extension.
- React dashboard.
- FastAPI backend modules and API routes.
- Selected identity provider and FastAPI session/token validation.
- PostgreSQL database.
- Private Azure Blob Storage and backend file authorization.
- Python AI provider adapters behind FastAPI.
- Gmail integration.
- Local browser storage.
- Synchronization engine.

Acceptance criteria: Every responsibility has one clear owner, and no component accesses another component's internal implementation unnecessarily.

## Task 01.2 — Define the repository structure

Use a maintainable structure such as:

```
ai-job-copilot/
├── apps/
│   ├── extension/
│   ├── web/
│   └── api/
│       ├── app/
│       │   ├── main.py
│       │   ├── modules/
│       │   └── providers/
│       ├── migrations/
│       ├── tests/
│       ├── alembic.ini
│       ├── pyproject.toml
│       └── uv.lock
├── packages/
│   ├── browser-shared/
│   └── api-client/
├── infra/
│   └── azure/
├── docs/
│   ├── PRD.md
│   ├── ARCHITECTURE.md
│   ├── DATABASE.md
│   ├── SECURITY.md
│   ├── PRIVACY.md
│   ├── API.md
│   ├── TESTING.md
│   └── DEPLOYMENT.md
├── tests/
│   ├── integration/
│   ├── e2e/
│   ├── security/
│   └── fixtures/
├── .github/
│   └── workflows/
├── package.json
├── pnpm-workspace.yaml
├── .env.example
├── .gitignore
├── LICENSE
└── README.md
```

Add folders only when they contain a real responsibility. The Python dependency and migration files shown assume the proposed uv and Alembic tooling is selected. Frontend workspaces do not manage Python dependencies. Keep Azure infrastructure configuration reproducible using the infrastructure-as-code tool selected in Phase 01.

## Task 01.3 — Define package boundaries

Specify which code can be shared:

- Browser-only shared types, validation, and utilities used by the React dashboard and extension.
- A TypeScript API client generated from FastAPI's OpenAPI schema, with a reproducible generation command.
- API error and data contracts defined by backend Pydantic models and reflected in OpenAPI.
- Python AI provider contracts shared within the backend modules.

Keep database clients, integration tokens, and provider credentials in the backend. TypeScript and Python cannot share implementation modules directly; use the API schema to align their contracts. Backend validation remains authoritative even when browser code validates the same inputs.

Acceptance criteria: The dependency direction is documented, circular dependencies are prohibited, and CI detects drift between OpenAPI and the generated browser client.

## Task 01.4 — Define the request flow

Document a normal AI-assisted application flow:

1. The extension identifies a form.
2. The extension extracts only the required field metadata.
3. The user selects a generation action.
4. FastAPI validates the session and request, then obtains the permitted profile facts for the selected storage mode.
5. A backend Python AI adapter generates structured suggestions using only the approved context.
6. The output is validated.
7. The user reviews the result.
8. The approved values are inserted into the form.
9. The user decides whether to save the application.

Acceptance criteria: The diagram shows where authentication, authorization, validation, and user approval occur. It defines trusted dashboard and extension origins, the session/token contract, and credential handling. A local-only mode must separately specify how generation reaches the backend or provider and obtain consent for any remote processing.

## Task 01.5 — Define data ownership

For every type of data, identify its authoritative location.

Examples:

- Account identity: authentication provider.
- Structured professional profile: database or local profile store, depending on storage mode.
- Original resume: private file storage or approved local storage.
- AI-generated drafts: temporary local state unless explicitly saved.
- Application history: application database or local store.
- API keys: a secure provider-specific credential mechanism, not an ordinary profile field.

Acceptance criteria: No data type has an ambiguous source of truth.

## Task 01.6 — Create architecture decision records

Create one short document per significant decision:

- `ADR-001-technology-stack.md`
- `ADR-002-modular-monolith.md`
- `ADR-003-storage-and-sync.md`
- `ADR-004-ai-provider-interface.md`
- `ADR-005-extension-permissions.md`
- `ADR-006-gmail-oauth.md`
- `ADR-007-authentication-and-api-security.md`
- `ADR-008-azure-deployment-and-budget.md`
- `ADR-009-python-tooling-and-openapi-contracts.md`

Each record should contain the context, options considered, selected decision, trade-offs, and conditions that would justify revisiting it.

Phase exit gate: A developer unfamiliar with the project can understand the major components, their responsibilities, and the reasons behind the design.

# 5. Phase 02 — Repository and developer environment

Objective: Create a reproducible development environment before implementing product features.

Deliverables: A working monorepo, automated checks, environment documentation, and a baseline test suite.

## Task 02.1 — Verify the development tools

Confirm compatible versions of:

- Node.js and the selected frontend package manager.
- Python and the selected Python dependency manager.
- Git.
- TypeScript.
- The required browser.
- PostgreSQL and Alembic or the selected migration tooling.
- Azure CLI when deployment work begins.

Document the supported versions.

## Task 02.2 — Initialize Git

- Initialize the repository.
- Add a `.gitignore`.
- Exclude build outputs, local environment files, temporary uploads, and secrets.
- Add a clear initial commit.

Acceptance criteria: No API keys, private resumes, credentials, or generated secrets are committed.

## Task 02.3 — Initialize the package workspace

- Create the root `package.json`.
- Configure pnpm workspaces.
- Add workspace scripts.
- Establish consistent package naming.
- Pin dependency versions through the lockfile.
- Create the backend Python project configuration and a separate dependency lock.
- Document frontend and backend installation, development, and build commands.

Acceptance criteria: A fresh checkout can install dependencies using the documented command.

## Task 02.4 — Create the web application shell

- Initialize the React dashboard, using Vite if the supporting recommendation is selected.
- Configure TypeScript.
- Add a minimal landing page.
- Configure client-side routing, API URL configuration, and hosting fallback for direct route visits.
- Confirm the application runs locally.

### Task 02.4a — Create the FastAPI application shell

- Initialize the Python backend with typed configuration and Pydantic request/response models.
- Add liveness and readiness endpoints with no sensitive details.
- Define a versioned API route prefix and a consistent error response.
- Configure the development server and document the Azure production startup command.
- Select explicit allowed dashboard and extension origins; document whether the production dashboard uses a linked API route or a separate API origin.
- Add a reproducible OpenAPI export and browser-client generation command.

Acceptance criteria: The dashboard can call a documented non-sensitive API endpoint locally. Invalid input receives the documented error response, and the production startup configuration launches the API successfully.

## Task 02.5 — Create the extension shell

- Add the Manifest V3 manifest.
- Add a minimal popup or side panel.
- Add a background service worker.
- Add a basic content script.
- Verify that the extension loads in a development browser.

Acceptance criteria: The extension loads without manifest errors and does not request broad permissions unnecessarily.

## Task 02.6 — Configure formatting and linting

- Add ESLint.
- Add Prettier.
- Configure TypeScript strictness.
- Define consistent import and naming conventions.
- Add scripts for linting and formatting checks.
- Configure Python formatting/linting and the selected type checker separately from the TypeScript checks.

## Task 02.7 — Configure automated tests

- Add Vitest.
- Create one example unit test.
- Configure test discovery.
- Add a command that runs the suite in CI.
- Configure pytest for backend business rules, request validation, and API authorization tests.

## Task 02.8 — Create continuous integration

Create a GitHub Actions workflow that:

1. Installs locked frontend and Python dependencies.
2. Checks formatting.
3. Runs linting.
4. Runs type checking.
5. Runs frontend and backend tests, including API contract checks.
6. Builds the web app.
7. Builds or validates the extension.
8. Verifies backend packaging/startup configuration and checks migration consistency.

Phase exit gate: A clean checkout can be installed, tested, and built using documented commands.

# 6. Phase 03 — Database design and security foundation

Objective: Establish the data model and enforce access control before sensitive user information is introduced.

Deliverables: Database schema, migrations, indexes, constraints, row-level security policies, and database tests.

## Task 03.1 — Design the entity relationship diagram

Start with these core entities:

- `profiles`
- `resumes`
- `education`
- `experience`
- `skills`
- `user_skills`
- `projects`
- `answer_bank`
- `applications`
- `application_answers`
- `integrations`
- `ai_settings`
- `sync_metadata`
- `audit_events`

The final schema may differ after the data model is reviewed.

## Task 03.2 — Define table ownership and relationships

For each table, specify:

- Primary key.
- User ownership.
- Foreign keys.
- Nullability.
- Unique constraints.
- Creation and update timestamps.
- Deletion behavior.
- Required indexes.

Acceptance criteria: Invalid relationships and unintended duplicate records are prevented by database constraints wherever practical.

## Task 03.3 — Design the profile schema

Define structured fields for:

- Contact information.
- Location and work preferences.
- Education.
- Employment and internships.
- Skills.
- Projects.
- Portfolio and professional links.
- Work authorization information, if the user chooses to provide it.

Keep optional sensitive information separate from basic profile data when possible.

## Task 03.4 — Design resume records

A resume record should track relevant metadata, such as:

- Resume ID.
- Owner ID.
- Display name.
- Storage location or local reference.
- File type.
- File size.
- Upload or creation timestamp.
- Parsing status.
- Version information.
- User-selected default status.

Do not expose private file locations or permanent public URLs to unauthorized clients.

## Task 03.5 — Design application records

Define fields for:

- Employer.
- Job title.
- Job posting URL.
- Application status.
- Relevant resume version.
- Application date.
- Follow-up date.
- User notes.
- Created and updated timestamps.

Add a history model if users need to inspect status transitions over time.

## Task 03.6 — Create versioned database migrations

- Add an initial migration.
- Create the core tables.
- Add constraints and indexes.
- Create a reproducible local setup.
- Document migration ordering.
- Keep migrations with the FastAPI backend; use Alembic if the supporting recommendation is selected.
- Use distinct runtime and migration database roles, and specify PostgreSQL connection pooling and transaction boundaries.

Acceptance criteria: A fresh database can be created entirely from committed migrations.

## Task 03.7 — Implement row-level security

For every user-owned table:

- Enable row-level security.
- Define read policies.
- Define insert policies.
- Define update policies.
- Define delete policies.
- Test access using two separate test users.

FastAPI must derive ownership from the authenticated identity and enforce it for each cloud operation. If PostgreSQL row-level security is used as an additional boundary, specify how the verified user context is set within each transaction and cleared safely with pooled connections. The runtime database role must not unintentionally bypass the policies through ownership, elevated privileges, or `BYPASSRLS`. Test the actual runtime role, including consecutive requests from different users on reused connections. See [PostgreSQL row security policies](https://www.postgresql.org/docs/current/ddl-rowsecurity.html).

Do not assume that a frontend filter or a hidden UI control provides data security.

## Task 03.8 — Secure private file storage

- Create a private resume storage area.
- Use a private Azure Blob container and a defined backend authorization flow.
- Define owner-specific file paths.
- Restrict uploads to accepted types and sizes.
- Use short-lived authorized download links where appropriate.
- Define deletion behavior for associated files.

## Task 03.9 — Add database security tests

Verify that one user cannot read, modify, or delete another user's profile, resume metadata, application records, or saved answers.

Phase exit gate: The schema is reproducible, relationships are enforced, and ownership rules pass automated tests.

# 7. Phase 04 — Authentication and account lifecycle

Objective: Establish secure identity management and account lifecycle behavior.

Deliverables: Registration, login, logout, session handling, protected routes, and account deletion planning.

## Task 04.1 — Configure authentication

Select the authentication provider and session/token contract in Phase 01, then configure them here. Azure hosting does not itself select the application's identity provider. Define registration, recovery, verification, and extension sign-in capabilities supported by the selected provider.

Document how FastAPI validates the authenticated identity on each protected operation. For JWT-based authentication, specify issuer, audience, expiry, and signing-key validation. For browser cookie sessions, specify cookie attributes and CSRF protection. Define extension-specific redirects and token handling, explicit allowed origins, and how sign-out/revocation propagates to both clients. CORS configuration does not replace authentication or authorization. See [FastAPI CORS guidance](https://fastapi.tiangolo.com/tutorial/cors/).

## Task 04.2 — Implement registration

- Add the registration UI.
- Validate email and password inputs.
- Handle duplicate accounts.
- Handle provider errors.
- Show clear success and failure states.

## Task 04.3 — Implement login and logout

- Build login and logout flows.
- Handle invalid credentials.
- Handle expired sessions.
- Prevent protected pages from being treated as public pages.

## Task 04.4 — Implement session management

- Establish how sessions are refreshed.
- Avoid exposing access tokens unnecessarily.
- Verify server-side authorization.
- Handle revoked or expired sessions.

## Task 04.5 — Protect dashboard routes

- Require an authenticated session where appropriate.
- Redirect unauthenticated users.
- Verify ownership on server-side data access.
- Avoid trusting user IDs supplied by the client.

## Task 04.6 — Define account recovery and deletion

Document and implement the appropriate password recovery or identity-provider recovery flow.

Define what happens to profiles, resumes, applications, integrations, and associated files when an account is deleted.

Phase exit gate: A user can create an account, access only their own protected data, recover access through the supported flow, and initiate the documented deletion process.

# 8. Phase 05 — Profile, resume, and professional data management

Objective: Create the verified information source that powers answer generation and autofill.

Deliverables: Profile CRUD operations, resume management, structured professional data, reusable answers, and validation.

## Task 05.1 — Build the profile model

Create typed models and validation schemas for:

- Basic information.
- Contact information.
- Location.
- Job preferences.
- Links.
- Optional eligibility information.

## Task 05.2 — Implement profile persistence

- Create profile records.
- Read the current user's profile.
- Update profile fields.
- Handle empty profiles.
- Handle validation errors.
- Test persistence after reload.

## Task 05.3 — Build the profile editor

Create a UI that allows users to:

- View profile information.
- Edit fields.
- Save changes.
- Cancel unsaved edits.
- See validation messages.
- Understand which fields are optional.

## Task 05.4 — Implement education management

- Add an education record.
- Edit a record.
- Delete a record.
- Validate dates and required fields.
- Support multiple education entries.

## Task 05.5 — Implement experience management

Support employment, internships, and relevant experience.

Each record should have structured fields for role, organization, dates, description, and optional links.

## Task 05.6 — Implement skills management

- Add and remove skills.
- Avoid accidental duplicates.
- Support user-provided proficiency levels if needed.
- Keep skill claims grounded in user input.

## Task 05.7 — Implement projects management

Store project names, descriptions, technologies, links, and relevant achievements.

Avoid turning unverified AI-generated summaries into authoritative facts automatically.

## Task 05.8 — Implement resume upload and management

- Validate file type and size.
- Upload to approved storage.
- Save metadata.
- Show upload progress.
- Handle failures.
- Allow users to download or delete their resumes.

## Task 05.9 — Implement resume parsing

Begin with a limited set of common text-based PDF and DOCX files.

- Extract text in an appropriate processing environment.
- Normalize whitespace and encoding.
- Detect likely sections.
- Extract candidate education, experience, skills, and projects.
- Show a parsing preview.
- Ask the user to confirm extracted information before saving it as verified profile data.

Scanned PDFs may require OCR and should be treated as a later enhancement if the initial parser cannot handle them reliably.

Phase exit gate: Users can maintain structured professional data and manage resumes. Extracted information is distinguishable from user-confirmed information.

# 9. Phase 06 — Local storage, cloud storage, and synchronization

Objective: Support the agreed storage modes without data loss, accidental disclosure, or unpredictable conflicts.

Deliverables: Storage interfaces, local persistence, cloud persistence, synchronization rules, conflict handling, and recovery tests.

## Task 06.1 — Define storage modes

Document two primary modes:

- Local-only: appropriate profile information and application data remain in local storage where supported.
- Cloud-enabled: the user explicitly enables account-based storage and synchronization.

Specify which features require cloud access. For example, a cloud-hosted dashboard cannot display data that exists only in a browser extension unless the user exports it or enables synchronization.

## Task 06.2 — Define data classification

Classify every data type:

- Public application metadata.
- Private profile data.
- Resume files.
- AI-generated drafts.
- Credentials and access tokens.
- Diagnostic information.

Define where each category can be stored, processed, logged, and transmitted.

## Task 06.3 — Create storage interfaces

Define interfaces for operations such as:

- Read.
- Create.
- Update.
- Delete.
- List.
- Export.

Implement local and cloud adapters behind these interfaces where practical.

Acceptance criteria: Feature logic does not depend directly on a particular storage implementation.

## Task 06.4 — Implement local persistence

Use browser extension storage for small settings and IndexedDB for structured local records where appropriate.

Test:

- Save and reload.
- Browser restart.
- Invalid stored records.
- Storage quota errors.
- Schema upgrades.
- Data deletion.

## Task 06.5 — Implement cloud persistence

Create authenticated FastAPI operations for cloud records. Apply API ownership checks and the selected database authorization policies to every user-owned resource. The React dashboard and extension must not hold database credentials or connect directly to PostgreSQL.

Do not trust an extension-supplied user ID as proof of ownership.

## Task 06.6 — Define synchronization metadata

Specify stable record IDs, revision information, timestamps, and deletion markers where needed.

Define how to recognize records that have not yet synchronized.

## Task 06.7 — Implement synchronization

Start with one record type, such as a profile, rather than synchronizing every entity at once.

- Upload local changes.
- Download remote changes.
- Detect conflicts.
- Retry temporary failures.
- Avoid duplicate creation.
- Preserve changes after a failed request.

Expand to other record types only after the first type passes tests.

## Task 06.8 — Test conflict and recovery scenarios

Test cases should include:

- The same profile is edited on two devices.
- A network request fails.
- The browser closes during synchronization.
- A record is deleted while offline.
- A user signs out while unsynchronized changes exist.
- The cloud record is newer than the local record.

Phase exit gate: Supported storage modes behave predictably, and synchronization does not silently overwrite valid user data.

# 10. Phase 07 — Web dashboard

Objective: Build the main user interface for profile management, resume management, AI settings, and application tracking.

Deliverables: Responsive dashboard, reusable UI components, accessible navigation, loading and error states, and integrated data flows.

## Task 07.1 — Define dashboard navigation

Create a navigation structure for:

- Overview.
- Profile.
- Resumes.
- Applications.
- Answer bank.
- AI settings.
- Integrations.
- Privacy and account settings.

Hide or disable unfinished capabilities without suggesting they already work.

## Task 07.2 — Build the design system

Define:

- Typography.
- Spacing.
- Buttons.
- Inputs.
- Cards.
- Dialogs.
- Notifications.
- Loading indicators.
- Empty states.
- Error states.

Reuse components rather than implementing slightly different controls on every page.

## Task 07.3 — Implement the overview page

Show useful information such as:

- Application counts.
- Recently updated applications.
- Follow-up reminders.
- Profile completion prompts.
- Recent activity.

Do not introduce complex analytics until the underlying application data is reliable.

## Task 07.4 — Integrate profile management

Connect the profile editor to the persistence layer and verify loading, editing, saving, and error recovery.

## Task 07.5 — Integrate resume management

Build the resume list, upload interface, default resume selection, download action, and deletion confirmation.

## Task 07.6 — Implement the answer bank

Allow users to create, edit, categorize, and remove reusable answers.

Potential categories include:

- Career motivation.
- Project descriptions.
- Strengths and achievements.
- Preferred work arrangements.
- Salary expectations.
- Other recurring application questions.

Sensitive answers should remain private, and users must be able to review them before reuse.

## Task 07.7 — Implement AI settings

Show:

- Selected provider.
- Connection status.
- Model configuration where supported.
- BYOK configuration status.
- Managed-service usage information, if offered.
- Clear explanations of how credentials are stored and used.

Never display a stored API key in full after it has been saved.

## Task 07.8 — Add accessibility and responsive behavior

Verify keyboard navigation, focus management, readable error messages, screen-reader labels, and small-screen layouts.

Phase exit gate: The dashboard supports the implemented backend features end to end, including loading, validation, errors, and empty states.

# 11. Phase 08 — Chrome extension foundation

Objective: Establish a secure, maintainable extension architecture before attempting to support complex job forms.

Deliverables: Installable extension, popup or side panel, content-script infrastructure, messaging contracts, permission design, and extension tests.

## Task 08.1 — Define the extension manifest

Configure the minimum required Manifest V3 properties:

- Manifest version.
- Name and version.
- Popup or side panel entry point.
- Background service worker.
- Content scripts.
- Required permissions.
- Optional host permissions where feasible.

Avoid requesting access to every website by default if user-initiated or narrower permissions can satisfy the workflow.

## Task 08.2 — Build the extension UI shell

Implement a basic interface that displays:

- Extension status.
- Current page compatibility.
- Sign-in or connection status.
- A button to inspect a supported form.
- Clear errors and loading states.

## Task 08.3 — Implement the service worker

Keep background responsibilities focused:

- Coordinate extension events.
- Handle permitted messaging.
- Manage supported background operations.
- Recover gracefully when the service worker is suspended and restarted.

Do not rely on long-running in-memory state that the browser does not guarantee will persist.

## Task 08.4 — Implement content-script isolation

Define which code runs in the page context and which code runs in the isolated extension context.

Treat all page content as untrusted. A job description or form field must never be allowed to issue privileged extension commands merely because its text resembles an instruction.

## Task 08.5 — Define message contracts

Create validated message types for operations such as:

- Inspect current form.
- Return detected fields.
- Request suggested answers.
- Apply approved values.
- Report fill results.
- Save application metadata.

Reject malformed or unexpected messages.

## Task 08.6 — Implement extension authentication

Define how the extension obtains and uses an authorized session.

Test expired sessions, sign-out, unauthorized requests, and revoked access.

## Task 08.7 — Implement local settings

Store appropriate preferences such as:

- Selected resume.
- Preferred form behavior.
- Review preferences.
- Enabled features.

Do not store secrets in ordinary settings or expose credentials to page scripts.

## Task 08.8 — Create extension test fixtures

Create local HTML fixtures for:

- A simple form.
- A form with required fields.
- A form with select and checkbox controls.
- A form with dynamic fields.
- A form with misleading labels.
- An unsupported form.

Phase exit gate: The extension installs, communicates using validated messages, respects permissions, and can inspect a controlled test page without filling or submitting it yet.

# 12. Phase 09 — Job form detection and field mapping

Objective: Reliably identify common form fields and determine which profile data can safely populate them.

Deliverables: Field-detection engine, normalized field schema, mapping rules, confidence scoring, and test coverage.

## Task 09.1 — Define the normalized field schema

Represent detected fields using a common model that may include:

- Field identifier.
- Label.
- Accessible name.
- Field type.
- Required status.
- Available options.
- Current value, where needed.
- Group or section.
- Detection confidence.
- Supported or unsupported status.

Keep the normalized model independent of the website's particular HTML structure.

## Task 09.2 — Detect standard HTML controls

Support initial detection of:

- Text inputs.
- Email inputs.
- Telephone inputs.
- Number inputs.
- Textareas.
- Select controls.
- Checkboxes.
- Radio groups.
- File inputs.

Treat custom controls and rich JavaScript widgets as potentially unsupported until explicitly tested.

## Task 09.3 — Extract accessible labels

Use relevant HTML semantics:

- Associated `label` elements.
- Accessible names.
- Placeholder text as a fallback.
- Fieldset legends.
- Required attributes.
- Nearby descriptive text when necessary.

Avoid relying only on placeholder text, which may be missing or ambiguous.

## Task 09.4 — Normalize field names

Convert website-specific variations into canonical field types.

Examples:

- “First name” → `first_name`
- “Email address” → `email`
- “LinkedIn profile” → `linkedin_url`
- “Why do you want to work here?” → `motivation_question`

Canonical mapping must not imply that every question has a known answer.

## Task 09.5 — Create mapping rules

Map common fields to verified profile data.

For example:

- `email` → verified contact email.
- `education` → selected education record.
- `portfolio_url` → verified portfolio link.
- `project_description` → relevant project information.

If a mapping is ambiguous, ask the user rather than silently selecting an unrelated value.

## Task 09.6 — Add mapping confidence

Define explicit behavior for confidence levels:

- High confidence: eligible for a clear suggestion.
- Medium confidence: show a suggestion requiring review.
- Low confidence: ask the user or leave unsupported.

Confidence should be based on understandable evidence, not a fabricated numerical probability.

## Task 09.7 — Handle repeated and grouped fields

Test multiple education entries, multiple work experiences, repeated checkbox groups, and address fields.

Do not map every repeated field to the same profile value without a clear rule.

## Task 09.8 — Detect dynamic form changes

Support reinspection when relevant fields appear after:

- A section expands.
- A user changes a selection.
- A form loads additional fields.
- A page updates its DOM.

Use observers carefully to avoid excessive CPU use or repeated processing.

## Task 09.9 — Build the compatibility test suite

Use HTML fixtures and, where permitted, real test environments to verify:

- Detection accuracy.
- Required-field identification.
- Accessible label extraction.
- Dynamic updates.
- Unsupported-field behavior.
- False-positive and false-negative cases.

Phase exit gate: The detector produces normalized, explainable field descriptions and does not fill fields simply because their labels appear vaguely similar.

# 13. Phase 10 — Review interface and approved autofill

Objective: Turn detected fields into a safe, user-controlled autofill workflow.

Deliverables: Review panel, answer-to-field mapping, field filling, verification, recovery, and audit-friendly result reporting.

## Task 10.1 — Define the review workflow

The user should be able to see:

- Detected field.
- Proposed value.
- Source of the proposed value.
- Confidence or uncertainty.
- Whether the answer requires confirmation.
- Whether the field is supported.

## Task 10.2 — Build answer editing

Allow the user to:

- Edit a proposed value.
- Approve a value.
- Reject a value.
- Request a new suggestion where AI is available.
- Mark a field as unknown.
- Skip unsupported fields.

## Task 10.3 — Add source attribution

For profile-derived answers, show the originating profile field or resume section when practical.

For AI-generated answers, identify the relevant source information and any assumptions that require confirmation.

## Task 10.4 — Implement basic autofill

Begin with standard inputs and textareas.

- Validate the target field.
- Validate the proposed value.
- Apply the value.
- Trigger the relevant input events.
- Verify the resulting field state.
- Record success or failure.

Do not use brittle page-context code that assumes every website behaves identically.

## Task 10.5 — Implement select and checkbox filling

- Match select options using explicit normalization rules.
- Confirm the selected option exists.
- Map checkbox values only when their meaning is clear.
- Ask for confirmation where multiple options could be correct.

## Task 10.6 — Handle controlled frontend components

Some forms use React or other frameworks with controlled state.

Test whether the supported filling mechanism produces a real state update. If the UI framework rejects the change or the value does not persist, report the failure instead of claiming success.

## Task 10.7 — Protect sensitive and consequential fields

Require explicit confirmation for fields involving potentially consequential declarations, such as:

- Work authorization.
- Legal attestations.
- Disability or demographic questions.
- Criminal-history declarations.
- Salary or compensation expectations.
- Consent and certification checkboxes.

The product should not guess answers to these questions.

## Task 10.8 — Implement partial success and recovery

If eight fields are filled and two fail, report the actual result.

Allow the user to retry failed supported fields without blindly overwriting their manual edits.

## Task 10.9 — Enforce the submission boundary

Do not automatically click submit, accept legal declarations, or trigger a final application submission.

Provide a clear handoff so the user can inspect the completed form and submit it themselves.

Phase exit gate: The user can review and edit suggestions, fill supported fields, identify failures, and retain control over the final application submission.

# 14. Phase 11 — AI provider architecture and answer generation

Objective: Add reliable AI assistance without tying the entire product to one model provider or allowing generated content to become unverified user facts.

Deliverables: Provider interface, secure credential handling, answer-generation pipeline, structured output validation, error handling, and AI evaluation tests.

## Task 11.1 — Define the AI provider interface

Create a shared contract for operations such as:

- Generate a structured answer.
- Generate a cover letter.
- Rewrite user-provided text.
- Summarize relevant resume content.

Implement provider contracts in Python within the FastAPI backend. Expose supported user operations through validated API schemas; generate browser client types from OpenAPI. Provider-specific credentials remain behind the chosen backend credential mechanism.

Keep provider-specific request formats inside their adapters.

Acceptance criteria: The core application can request a generation task without depending directly on one provider's SDK.

## Task 11.2 — Define the supported provider model

Document the difference between:

- BYOK: users provide their own provider credentials.
- Managed AI: the service provides access under its own account and applicable usage limits.

Decide which model is supported by the first release during Phase 01. Implement only the credential and billing flows that are actually required. Use backend-mediated generation as the initial architecture; a local direct-to-provider mode requires a separate explicit architecture decision.

## Task 11.3 — Design credential handling

Document where credentials are stored, how they are used, and who can access them.

- Never commit API keys.
- Never put server-only credentials in the extension bundle.
- Never return full stored secrets to the UI.
- Never write credentials to ordinary application logs.
- Use a secure credential-storage mechanism appropriate to the architecture.
- Define separate handling for deployment secrets and per-user BYOK/OAuth credentials. Azure Key Vault is the proposed home for service secrets and encryption-key material; choose an encrypted, owner-scoped credential store and rotation/deletion contract for per-user secrets.
- Explain provider data-processing practices to users.

For BYOK, direct calls from the user's device can reduce the need for the application's backend to handle the provider key, but expose the key to the user's local environment. Backend-mediated calls require an appropriately protected credential-storage and authorization design. Document this trade-off before choosing the implementation.

## Task 11.4 — Implement one provider adapter

Start with one provider and one generation operation.

- Configure the provider.
- Validate the request.
- Handle authentication failures.
- Handle rate limits.
- Handle timeouts.
- Normalize provider errors.
- Validate the returned content.

Do not implement five providers before the first adapter works reliably.

## Task 11.5 — Define a structured generation request

A generation request should include only the necessary information:

- Application question.
- Relevant verified profile facts.
- Relevant resume or project excerpts.
- Desired output format.
- Length constraints.
- User-selected tone, if applicable.

Avoid sending the entire user profile and all resumes for every question.

## Task 11.6 — Implement answer generation

Build the first workflow for questions such as:

- “Why are you interested in this role?”
- “Describe a relevant project.”
- “What experience do you have with this technology?”

The AI should prioritize relevant user-provided facts rather than generic claims.

## Task 11.7 — Validate structured output

Define a response schema, for example:

- Draft answer.
- Referenced profile facts.
- Missing information.
- Uncertainty indicators.
- Validation errors.

Reject malformed responses and handle incomplete outputs gracefully.

## Task 11.8 — Add factuality safeguards

Implement checks to prevent unsupported claims from being presented as verified facts.

Examples:

- Do not invent years of experience.
- Do not invent employment dates.
- Do not claim a degree that is absent from the profile.
- Do not fabricate project outcomes or numerical achievements.
- Do not assume legal eligibility or work authorization.

Where reliable validation is impossible, request user confirmation.

## Task 11.9 — Implement retries, quotas, and cost controls

Define behavior for:

- Rate limits.
- Network failures.
- Invalid provider credentials.
- Provider outages.
- Excessive response length.
- Repeated generation requests.
- Managed-service usage limits.

Retries should be bounded and should not duplicate expensive requests unnecessarily.

## Task 11.10 — Evaluate answer quality

Build a small set of test questions with known profile facts and expected constraints.

Evaluate:

- Factual consistency.
- Relevance.
- Completeness.
- Unsupported claims.
- Output-schema validity.
- User-editability.
- Provider failure handling.

Phase exit gate: The application can generate, validate, display, and safely handle AI drafts through a defined provider interface.

# 15. Phase 12 — Application tracking and workflow management

Objective: Give users a reliable place to organize applications, preserve relevant context, and monitor their progress.

Deliverables: Application CRUD, status workflow, filters, reminders, saved answers, and export support.

## Task 12.1 — Define the application lifecycle

Establish a controlled set of statuses, such as:

- Interested.
- Preparing.
- Applied.
- Assessment.
- Interview.
- Offer.
- Rejected.
- Withdrawn.

Allow the status model to be adjusted later based on user feedback.

## Task 12.2 — Implement application creation

Users should be able to create an application record manually or save one from the extension.

Capture only the information required for tracking.

## Task 12.3 — Link application context

Where appropriate, associate an application with:

- Employer and role.
- Job posting URL.
- Selected resume version.
- Saved answers.
- Application date.
- Notes.
- Relevant email drafts.

Keep a snapshot of application-specific content where necessary so later profile edits do not silently rewrite historical application information.

## Task 12.4 — Implement status updates

Allow users to update the status manually.

Record status history when useful, including timestamps and the origin of the change.

## Task 12.5 — Implement search and filtering

Support useful filters:

- Status.
- Employer.
- Date range.
- Job title.
- Follow-up date.

Start with straightforward database queries and indexes.

## Task 12.6 — Implement application details

Create a detail page that shows the saved information, status history, related answers, and relevant actions.

## Task 12.7 — Implement follow-up reminders

Let users add follow-up dates and see overdue or upcoming reminders.

Begin with in-app reminders. Scheduled emails or notifications can be a separate enhancement.

## Task 12.8 — Implement export and deletion

Allow users to export application records in a documented format and delete records they no longer want.

Ensure that deletion rules are consistent with associated files and saved answer records.

Phase exit gate: A user can create, review, update, filter, export, and delete application records without losing historical context unexpectedly.

# 16. Phase 13 — Gmail integration

Objective: Add email functionality using narrow permissions and explicit user approval.

Deliverables: OAuth flow, authorized Gmail client, draft creation, error handling, and optional email-based tracking.

## Task 13.1 — Define Gmail use cases

Start with a limited scope:

- Create a draft follow-up email.
- Create a draft interview thank-you email.
- Create a draft application-related message.
- Optionally, associate a draft with an application.

Reading mailbox messages for status tracking should be treated as a separate feature requiring a distinct permission and privacy review.

## Task 13.2 — Configure OAuth

- Configure the application identity and redirect URLs.
- Request the narrowest permissions that support the approved features.
- Document why each permission is needed.
- Handle authorization denial.
- Handle expired or revoked access.

## Task 13.3 — Implement integration state

Track whether Gmail is:

- Not connected.
- Awaiting authorization.
- Connected.
- Expired or requiring reauthorization.
- Disconnected.

Do not store Gmail credentials in ordinary profile fields.

## Task 13.4 — Implement the Gmail client abstraction

Keep Gmail-specific operations separate from application workflow logic.

Start with a small interface for creating a draft and reporting its result.

## Task 13.5 — Generate email drafts

Allow users to select an application and create an email draft using relevant verified information.

The generated message should be editable before it is handed off to Gmail.

## Task 13.6 — Create the draft

- Validate recipient and subject.
- Validate the message body.
- Call the authorized Gmail API.
- Handle API errors.
- Record the draft association where appropriate.
- Show a clear result to the user.

Do not send the email automatically.

## Task 13.7 — Test permission boundaries

Verify that the implementation cannot perform actions outside the authorized scope.

Test denied consent, expired access, revoked tokens, and unauthorized requests.

## Task 13.8 — Decide whether email-based status tracking belongs in the MVP

If included, separately specify:

- Which messages may be processed.
- Whether processing is manual or periodic.
- Which message metadata is stored.
- How false status matches are handled.
- How users review proposed status changes.
- How users disconnect the integration and delete associated data.

Do not silently scan the mailbox merely because Gmail is connected.

Phase exit gate: Users can authorize Gmail, create editable drafts, and disconnect the integration without granting unnecessary mailbox access.

# 17. Phase 14 — Security, quality, privacy, and reliability

Objective: Evaluate the complete product as a system rather than treating each feature as independently safe.

Deliverables: Threat model, privacy review, automated regression suite, security tests, operational checks, and remediation records.

## Task 14.1 — Complete the threat model

Document threats involving:

- Account takeover.
- Cross-user data access.
- API key exposure.
- Malicious or misleading web pages.
- Prompt injection.
- Resume and document processing.
- Unauthorized extension messaging.
- OAuth token misuse.
- Malicious file uploads.
- Synchronization conflicts.
- Accidental data disclosure through logs.

Assign each risk a severity, mitigation, and verification method.

## Task 14.2 — Review authorization

Test that:

- Users access only their own records.
- Server-side routes enforce authorization.
- Extension requests are validated.
- Administrative credentials never reach client code.
- Integration actions require valid authorization.

## Task 14.3 — Review input validation

Validate all untrusted inputs, including:

- Form metadata.
- User-entered profile values.
- Uploaded file metadata.
- AI outputs.
- API requests.
- OAuth callback parameters.
- Imported records.

## Task 14.4 — Review prompt injection and untrusted content

Treat job descriptions, websites, resumes, emails, and form text as data rather than privileged instructions.

A webpage must not be able to convince the AI to disclose unrelated profile data, change security rules, or invoke an unauthorized tool.

Keep tool permissions narrowly scoped and require explicit approval for consequential operations.

## Task 14.5 — Review file handling

Test:

- Unsupported file types.
- Oversized uploads.
- Malformed documents.
- Parsing failures.
- Unauthorized downloads.
- Deletion of files and metadata.
- Safe rendering of extracted content.

## Task 14.6 — Implement observability

Add structured logs and operational metrics for relevant failures.

Avoid logging full resumes, personal profile data, API keys, OAuth tokens, or complete application answers unless a carefully justified, consent-based diagnostic feature requires them.

## Task 14.7 — Run integration tests

Test real interactions between:

- Authentication and database access.
- Profile persistence and resume management.
- Extension and backend.
- Field detection and autofill.
- AI adapters and output validation.
- Application tracking and Gmail drafts.
- Storage and synchronization.

## Task 14.8 — Run end-to-end tests

Create a small set of deterministic workflows using test accounts and local HTML fixtures.

At minimum, verify:

1. Register and log in.
2. Create a profile.
3. Add a resume.
4. Open a supported form.
5. Detect fields.
6. Generate and review an answer.
7. Fill approved values.
8. Save an application.
9. Update the application status.
10. Disconnect an integration.

## Task 14.9 — Test failure and recovery scenarios

Simulate:

- Network interruption.
- AI provider outage.
- Expired authentication.
- Database failure.
- Browser extension restart.
- Invalid AI output.
- Partial autofill failure.
- Sync conflicts.
- OAuth revocation.

## Task 14.10 — Perform privacy and deletion tests

Verify that users can export and delete their data and understand what deletion means for:

- Database records.
- Resume files.
- Local caches.
- Pending synchronization operations.
- Connected integrations.
- Relevant backups, subject to the documented retention policy.

## Task 14.11 — Establish release-blocking defects

Define severity levels and explicitly identify which failures block release.

Cross-user data exposure, secret leakage, unauthorized submissions, and silent data loss should be treated as release blockers.

Phase exit gate: Critical security issues are resolved, important workflows pass regression tests, and remaining risks are documented rather than ignored.

# 18. Phase 15 — Deployment, release, and beta launch

Objective: Prepare a reproducible release that can be installed, operated, monitored, and maintained.

Deliverables: Deployment configuration, production environment, release checklist, user documentation, and a small beta release.

Azure is the selected deployment platform. Confirm the service topology in Phase 01, before implementation relies on hosting assumptions. The proposed deployment separates the React static build, FastAPI runtime, PostgreSQL, private resume files, and secret management.

## Task 15.1 — Select deployment environments

Define separate environments for:

- Local development.
- Testing or staging.
- Production.

Keep credentials, databases, OAuth configuration, and AI usage policies appropriately separated.

For each Azure environment, document resource ownership, region, naming, expected monthly cost, service limits, database connectivity, secret access, and allowed dashboard/extension origins. Keep a reproducible infrastructure configuration. Use narrowly scoped deployment identities and define how GitHub Actions authenticates to Azure. Budget alerts report spend; separately define quotas and operational controls intended to limit costs.

## Task 15.2 — Prepare the production database

- Apply migrations in a controlled process.
- Verify database policies.
- Configure backups and recovery procedures.
- Check indexes for common queries.
- Confirm production credentials are not used in local development.
- Provision the selected Azure Database for PostgreSQL service and verify the API's TLS connection and permitted network path.
- Configure runtime/migration roles, connection limits, and recovery targets; exercise a restore before beta.

## Task 15.3 — Deploy the dashboard

- Deploy the React static build to the selected Azure frontend service.
- Configure SPA route fallback, the public API route/URL, and authentication callback URLs.
- Keep service secrets out of the browser build; frontend configuration is public.
- Verify protected routes.
- Test error reporting.
- Verify that private information is not exposed through public pages.

### Task 15.3a — Deploy the FastAPI backend

- Deploy the API to the selected Azure runtime; Azure App Service for Linux is the proposed starting point.
- Configure the ASGI startup command, supported Python runtime, health endpoints, and request limits.
- Configure authorized access to PostgreSQL, private blobs, and the chosen secret store.
- Set production authentication validation, allowed origins, and cookie/CSRF settings where applicable.
- Run migrations through a controlled release step using the migration role.
- Add redacted logs, failure monitoring, rollback instructions, and a documented API-version compatibility policy.
- Decide whether resume parsing fits bounded API requests or needs durable background processing; implement the selected execution and retry model before exposing the feature.

Acceptance criteria: The deployed dashboard and extension can perform an authorized operation through FastAPI. Unauthorized requests are rejected, private resources remain inaccessible without ownership checks, and the release/rollback process is documented and exercised.

## Task 15.4 — Configure the extension release build

- Create a reproducible production build.
- Remove development-only settings.
- Verify the manifest and permissions.
- Check that no secrets are bundled.
- Test the production build independently of the development environment.

## Task 15.5 — Document installation

Write clear instructions for:

- Installing the extension in development mode.
- Connecting an account.
- Configuring an AI provider.
- Setting up a profile.
- Using supported application forms.
- Troubleshooting common errors.

## Task 15.6 — Prepare open-source documentation

Create and review:

- `README.md`
- `CONTRIBUTING.md`
- `LICENSE`
- `SECURITY.md` or a security reporting policy.
- `PRIVACY.md`
- `.env.example`
- Development setup instructions.
- Architecture documentation.

Do not publish a license until the project owner has selected one deliberately.

## Task 15.7 — Create the release checklist

Verify:

- All release-blocking tests pass.
- Database migrations are reproducible.
- No known critical vulnerabilities remain.
- Account deletion works.
- Error states are understandable.
- User data is protected.
- Backup and recovery expectations are documented.
- AI provider failures are handled gracefully.

## Task 15.8 — Conduct a limited beta

Begin with a small group of testers and a controlled set of supported form patterns.

Ask testers to report:

- Detection errors.
- Incorrect suggestions.
- Autofill failures.
- Confusing UI.
- Performance problems.
- Privacy concerns.
- Missing functionality.

Collect only the feedback and diagnostic information that is necessary and appropriately disclosed.

## Task 15.9 — Review beta findings

Classify issues by severity and frequency.

Prioritize data safety, factual errors, failed core workflows, and confusing user approvals before adding more features.

## Task 15.10 — Publish the first stable MVP

Tag the release, publish setup instructions, document supported functionality and limitations, and provide a process for reporting issues.

Phase exit gate: A new user can install, configure, and use the documented MVP without relying on undocumented manual intervention by the developer.

# 19. Cross-cutting engineering work

The preceding phases define the implementation order. These responsibilities apply throughout development rather than being postponed until the end.

## 19.1 Testing strategy

Use different testing levels for different risks.

| Test level              | What it verifies                         |
| ----------------------- | ---------------------------------------- |
| Unit tests              | Individual functions and business rules  |
| Schema tests            | Valid and invalid data structures        |
| Component tests         | UI states and user interactions          |
| Integration tests       | Multiple modules working together        |
| Database security tests | Access controls and ownership            |
| Extension tests         | Manifest, messages, and browser behavior |
| End-to-end tests        | Complete user journeys                   |
| Security tests          | Unauthorized access and attack scenarios |
| Regression tests        | Previously fixed defects stay fixed      |

Every bug fix should include a regression test when practical.

## 19.2 Documentation strategy

Maintain documentation alongside the code:

- Product requirements.
- Architecture and decisions.
- Database schema.
- API contracts.
- Security and privacy.
- Testing and troubleshooting.
- Deployment and recovery.
- Feature limitations.
- Contribution guidelines.

Documentation should explain current behavior, not merely the intended future design.

## 19.3 AI coding-agent workflow

Use the following workflow for each small task:

1

Read

Read the relevant PRD, architecture decision, and existing code.

2

Plan

Ask for a narrow implementation plan and list of files to change.

3

Implement

Implement only the agreed task; avoid unrelated refactoring.

4

Verify

Run relevant tests, linting, type checks, and builds.

5

Review

Inspect the diff, security implications, and acceptance criteria.

6

Record

Update documentation and task status; commit when ready.

A coding agent should not be allowed to silently change the database architecture, add unnecessary dependencies, weaken authorization, or mark unverified work as complete.

# 20. Post-MVP roadmap

These features should be considered after the core workflows are stable and users have provided feedback.

## Phase 16 — Compatibility and product expansion

- Add more supported form patterns.
- Introduce site-specific adapters where justified.
- Improve detection of dynamic and custom controls.
- Expand regression fixtures.
- Add better handling of repeated sections.
- Support Firefox after validating the extension architecture.
- Improve resume parsing and optional OCR.
- Add import and export improvements.

## Phase 17 — Advanced AI assistance

- Improve answer personalization.
- Add configurable writing styles.
- Support cover-letter generation.
- Add job-description and resume relevance analysis.
- Improve source attribution.
- Evaluate retrieval techniques for large profiles.
- Consider embeddings and vector search only if keyword and structured retrieval are insufficient.
- Add provider comparisons and cost reporting where useful.

## Phase 18 — Workflow automation

- Add user-approved follow-up reminders.
- Consider additional email providers.
- Add optional email-based status suggestions.
- Introduce a review queue for suggested status updates.
- Add calendar integration if there is a demonstrated need.
- Explore more advanced task orchestration without removing user control.

## Phase 19 — Hosted service and sustainability

- Evaluate managed AI plans.
- Consider hosted synchronization and collaboration features.
- Introduce transparent usage quotas.
- Measure infrastructure costs.
- Establish abuse prevention and rate limits.
- Define a support and incident-response process.
- Evaluate paid features only after validating real demand.

These are potential future directions, not commitments for the first release.

# 21. Project management: make every task trackable

A detailed roadmap is useful only if you can track what is implemented, what is blocked, and what still needs verification. Create a simple task-management system inside the repository.

## Task 21.1 — Create the project tracking documents

Create these files:

```
docs/
├── ROADMAP.md
├── TASKS.md
├── PROGRESS.md
├── DECISIONS.md
├── RISKS.md
└── RELEASE_CHECKLIST.md
```

Their responsibilities should be different:

| File                   | Purpose                                                    |
| ---------------------- | ---------------------------------------------------------- |
| `ROADMAP.md`           | Overall phases and their dependencies                      |
| `TASKS.md`             | Individual tasks, IDs, priorities, and acceptance criteria |
| `PROGRESS.md`          | Current phase, completed work, next task, and blockers     |
| `DECISIONS.md`         | Links to important technical decisions                     |
| `RISKS.md`             | Known risks, severity, mitigation, and status              |
| `RELEASE_CHECKLIST.md` | Conditions that must be met before a release               |

## Task 21.2 — Give each task a consistent status

Use a small status vocabulary:

- `NOT_STARTED`
- `IN_PROGRESS`
- `BLOCKED`
- `IN_REVIEW`
- `DONE`

A task should not be marked `DONE` simply because code was generated. Its acceptance criteria must have been verified.

## Task 21.3 — Break oversized tasks down further

For example, “Implement authentication” is too broad to execute as a single task. It should be divided into tasks such as:

- `AUTH-001`: Configure the authentication provider.
- `AUTH-002`: Implement registration.
- `AUTH-003`: Validate registration inputs.
- `AUTH-004`: Handle duplicate-account errors.
- `AUTH-005`: Implement login.
- `AUTH-006`: Implement logout.
- `AUTH-007`: Protect a dashboard route.
- `AUTH-008`: Verify authorization for a user-owned resource.
- `AUTH-009`: Add tests for expired sessions.
- `AUTH-010`: Document the authentication flow.

Each task should have its own acceptance criteria, relevant files, dependencies, and verification commands.

## Task 21.4 — Establish a rule for task size

As a practical starting point, aim for one small, independently reviewable change per task. If a task affects many unrelated modules or introduces several new concepts at once, split it.

Some tasks will take only a few minutes; others, especially database security or browser integration tests, may take longer. Small tasks are a way to control complexity, not a promise that every task will be quick.

# 22. Recommended implementation order

Do not implement all 16 phases simultaneously. Follow the dependency order below.

A

Foundation

Product requirements → Architecture → Repository → Database and security → Authentication

B

Core user experience

Profile and resumes → Storage and sync → Dashboard

C

Browser functionality

Extension foundation → Field detection → Review and approved autofill

D

Intelligence and workflow

AI provider layer → Application tracking → Gmail integration

E

Release

Security review → Integration and end-to-end testing → Deployment → Beta feedback

The sequence can be adjusted when a dependency requires it, but changes should be documented rather than made implicitly.

# 23. The very first implementation task

Do not start by generating the whole repository or asking a coding agent to build the entire application.

Start with Task 00.1 — Define the target user and core problem.

Your first deliverable should be a short, reviewable `docs/PRD.md` that answers:

1. Who is the primary user?
2. What problem are they trying to solve?
3. What does the product do?
4. What is included in the first release?
5. What is explicitly excluded?
6. What does successful completion of the main user journey look like?

Once that document is reviewed, proceed to Task 00.2. Do not jump directly to authentication, database creation, or AI integration.

The overall development principle: finish one small task, verify it, record the result, and then move to the next task. That is how this roadmap becomes a working product rather than a large collection of partially implemented features.
