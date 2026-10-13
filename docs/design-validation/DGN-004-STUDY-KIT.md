# DGN-004 moderator kit

This kit is for five individual, moderated sessions with representative job seekers. It is a preparation artifact only: no participants have been recruited or contacted, and no sessions or findings are claimed. Use aliases P1–P5 and do not add names, contact details, résumés, employer information, or recordings to this repository.

## Participant profile and session setup

Recruit five adults who are actively applying or expect to apply for work in the next three months and have completed at least one job application in the last year. Aim for a mix of job-search experience and comfort with browser tools. Do not require a particular profession or use employees who authored the prototype as participants. Ask for consent before starting; participation is voluntary, questions can be skipped, and the participant may stop at any time. Do not record audio/video. Take only anonymized, minimal notes; paraphrase quotes and remove identifying details.

Use the static prototype at `design-prototype/README.md`, with a 1280px desktop browser and a 390px narrow dashboard. Show the 360–420px extension panel as a separate browser-width preview. Do not connect an account, upload documents, open Gmail, call a provider, visit a job site, scan a source, fill a real form, or send/submit anything. Tell participants that the prototype is not functional and all content is fictional.

## 50-minute session script

### Opening · 5 minutes

Read: “Thanks for helping review a design prototype. We are evaluating the screens, not you. Some controls only preview an example and no information will be saved or sent. Please say what you expect to happen and what you are looking for. You may skip any task or stop whenever you like. I will take anonymized notes and will not record this session. Is it okay to begin?”

If consent is not given, stop and record only “session not started; consent declined.” Do not ask why. Start from the empty Home screen. Avoid explaining controls before the participant has had a chance to explore.

### Tasks · about 39 minutes total

Give the task prompt verbatim, then observe silently. Use only the neutral probes listed below. Stop each task after its timebox; do not teach the interface before recording what happened.

| ID / time | Participant prompt | Journey / screens | Observe the intended outcome |
| --- | --- | --- | --- |
| T1 · 8 min | “You are setting up this workspace for a job search. Add the information you would want to use, review a detail extracted from a résumé, and decide what you would do next.” | Onboarding and profile; Home, Basics, Experience, Documents, AI setup, Profile documents | Finds the next useful step; understands documents are optional/private; recognizes extracted facts need individual confirmation; understands AI keys are optional. |
| T2 · 10 min | “You are on a job application and want help with answers, while staying in control of what goes onto the employer’s form. Show me what you would review and what you would leave for yourself.” | Extension detected, analyzing, suggestions, manual, filled, review | Understands what job/profile data may be sent; finds provenance; leaves authorization/manual questions unanswered; understands filled values are visible to the hiring page before submit; does not expect the extension to submit. |
| T3 · 5 min | “You remember clicking Submit for one application. Find out what the workspace currently knows about whether it was accepted.” | Applications list/detail/evidence; returning Home | Distinguishes “Submission attempted” from “Applied”; finds evidence and uncertainty; knows user confirmation or verified site evidence is needed. |
| T4 · 8 min | “Prepare an email application and decide what happens when you choose the Gmail handoff. Tell me when you think it would count as sent.” | Email draft/review/handoff/confirmation | Reviews exact recipient/message; understands résumé attachment and Send remain in Gmail; does not mistake opening Gmail/compose for sent; identifies explicit confirmation step. Do not open a real Gmail tab. |
| T5 · 8 min | “Follow a public company careers page for roles that fit you each morning. Set up what you would need, then check what the workspace tells you after one source could not be checked.” | Alerts setup/digest/partial/failure/paused; notification inbox | Finds URL/role/location/timezone and separate consent; recognizes sample preview is not a live check; understands partial/failure is not “no jobs”; distinguishes matches from applications and sees local next-check time. |

### Neutral probes

Use only when needed: “What are you looking for now?”, “What do you expect this control to do?”, “What does this status mean to you?”, “What would you do next?”, and “What, if anything, feels unclear?” Do not praise, correct, suggest a control, or ask whether the participant likes the colors during a task.

### Debrief · 6 minutes

Ask: “Which step was hardest to understand?”, “Was any screen asking for more than you expected?”, “What would you change first?”, and “What did you expect the product to do that it did not?” Close by reminding them the screens were fictional and no data was saved or sent.

## Anonymized observation form

Copy one block per task and use aliases P1–P5. Record observable behavior, paraphrased and de-identified. Do not store personal answers or job-search history.

```text
Session alias: P__      Date (optional): YYYY-MM-DD      Viewport: desktop / 390 / extension
Consent to participate: yes / no       Session started: yes / no
Prior application-form familiarity: low / medium / high / prefer not to say

Task ID: T__      Started / stopped: __:__ / __:__
Unaided outcome: completed / partial / not completed / skipped
Path taken (screen labels only):
Hesitation or misinterpretation (observable, paraphrased):
Neutral probe / moderator help level: none / repeated prompt / pointed to section / task stopped
Control/status expected by participant (paraphrase):
Privacy, consent, submission, or sent-state misunderstanding: none / describe without personal data
Impact: low / moderate / high      Frequency so far: __ / __ sessions
Potential design response (hypothesis, not yet a finding):

Debrief themes (paraphrase):
Participant-requested deletion of notes: yes / no / not applicable
```

Do not mark an outcome “successful” only because a participant reached the last screen; record whether they interpreted the status and next action correctly. Do not infer a finding from one participant without labeling its frequency.

## Design change log template

Create one row per evidence-backed change; leave the table empty until sessions happen.

| Change ID | Observation IDs / sessions (e.g. T2, P1/P3) | Issue and observed evidence | Count / denominator | Impact and contract risk | Design decision | Screen/copy/component changed | Follow-up or unresolved question |
| --- | --- | --- | --- | --- | --- | --- | --- |
| — | — | No sessions completed yet | — | — | — | — | — |

After each change, retain the before/after screen references and explain whether it resolves the observed problem without weakening user consent, factual provenance, manual review, or user-controlled submission/sending. User study results do not approve the Rolevo name or logo; DGN-006 remains separate.
