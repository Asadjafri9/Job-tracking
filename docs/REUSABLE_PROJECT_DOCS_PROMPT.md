# Reusable prompt: create a project documentation set

Copy the prompt below into an AI coding assistant while working in the root of a new project repository. Replace the bracketed project brief if you have one; otherwise ask the assistant to inspect the repository and draft a brief from the available evidence.

---

## Prompt

Act as a product-minded technical writer and software architect. Help me create a practical, consistent documentation set for this project. The documents must describe this project, not a generic template or another project's domain.

### Project brief

`[Describe the product, intended users, main problem, desired outcome, known constraints, and any decisions already made. If some details are unknown, say so.]`

### First inspect the repository

Read the existing README, source tree, configuration, tests, and any existing planning documents before writing. Treat repository evidence and my explicit decisions as authoritative. Distinguish implemented behavior from intended behavior. Do not claim a command, feature, integration, deployment, or test has succeeded unless the repository or observed run provides evidence.

If the project already has documentation, map it and identify contradictions, gaps, and the active source of truth before changing files. Preserve useful history, but label archived or reference material clearly. Do not replace or delete existing content without a clear reason.

### Build a tailored document set

Choose only documents that help this project's users and maintainers. For a small project, a README, requirements/plan, architecture notes, and verification guide may be enough. Add separate contracts for data, APIs, security/privacy, deployment, integrations, compatibility, operations, or substantial features only when the project needs them.

For a product or multi-component application, consider these roles:

- **README.md** — what it is, who it serves, setup, usage, and links to maintained docs.
- **PRD.md** — users, problem, scope, functional requirements, non-goals, and observable acceptance criteria.
- **DECISIONS.md** — accepted choices, rationale, assumptions/defaults, date, and how decisions can change.
- **ARCHITECTURE.md** — components, boundaries, key flows, dependencies, and important failure behavior.
- **Domain contracts** — only needed for major features or integrations; state inputs, outputs, states, edge cases, and user-visible behavior.
- **Data/API/security/deployment docs** — add when the system has material contracts or operational/security concerns; be specific and internally consistent.
- **TASKS.md** — a sequenced backlog with dependencies and completion criteria tied to requirements.
- **TESTING.md** — verification strategy and actual available commands. Label proposed future checks as planned, not as runnable or passed.
- **RISKS.md** — meaningful open risks, triggers, mitigations, owners, and how to verify controls.
- **PROGRESS.md** — concise current state, updated with evidence.
- **RELEASE_CHECKLIST.md** — release gates with space for observed evidence; do not mark unchecked work complete.
- **DOCS_GUIDE.md** — optional index explaining how the documents relate and which ones are active.

Do not create every suggested file automatically. Explain the chosen set briefly and omit documents that add no value. Avoid duplicate requirements spread across files: link to the authoritative document and summarize only where needed.

### Writing and accuracy rules

1. Separate **confirmed decisions**, **assumptions**, **open questions**, **proposals**, and **verified facts**. Never silently turn an assumption into a decision.
2. If a choice blocks useful planning, ask a concise question. Otherwise record a reasonable, reversible default as a proposal and make it visible.
3. Keep scope realistic. State non-goals and unsupported cases where they prevent mistaken expectations.
4. Write requirements so a person can tell whether they are satisfied. Link requirements to relevant tasks and verification where practical.
5. Keep cross-document names, versions, terminology, statuses, and technical choices consistent. Prefer links and stable IDs over copied text.
6. Include privacy, security, accessibility, reliability, and failure handling when relevant to the product; scale detail to actual risk.
7. Do not invent APIs, schema, provider behavior, legal/compliance claims, costs, infrastructure, test results, or release readiness. Label unknowns and future work explicitly.
8. Keep planning distinct from implementation. A plan is not evidence that code exists or works. Never mark a task, test, risk mitigation, or release gate complete without evidence.
9. Use the repository's existing conventions and avoid introducing a documentation framework or tooling dependency unless needed.
10. Make documents concise enough to maintain. Put detailed contracts in separate files only when that improves clarity or review.

### Working method

1. Inspect the repo and report the project facts you found, the proposed document list, and any contradictions or critical unknowns.
2. Draft the selected files in the project's existing docs location (or suggest one if absent), with links between them.
3. Cross-check the finished set for contradictions, unsupported claims, stale duplicated content, broken relative links, and tasks without acceptance criteria.
4. Summarize files created or changed, assumptions that remain, and any facts I need to confirm. Do not claim tests or checks ran unless they did.

Start by inspecting the repository. Then proceed with the documentation work using the rules above.

---

## Reuse notes

- Use this prompt from each new repository and provide its specific brief; do not copy this project's product requirements or technology choices.
- For an existing project, tell the assistant to update and reconcile current docs instead of generating a duplicate set.
- For a small script or prototype, request the short version and omit heavyweight planning artifacts.
- Keep the resulting documents in the repository so they can evolve with the code.
