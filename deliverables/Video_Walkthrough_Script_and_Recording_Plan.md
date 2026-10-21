# NovaCRM Assessment Recording Script and Plan

Prepared for Harish • 21 October 2026

Submit the Part 1 requirements document and two videos: one positive journey and one negative journey. The scripts below are speaking notes and an evidence checklist. They do not claim that unverified integrations have already passed.

## 1 Recording objective and truthfulness

The assessor should see an actual email arrive, hear a real AE voice interaction, inspect the correct API-created Rocketlane project, see personalized Slack setup and verify native Rocketlane overdue automation. In the negative video, the assessor should see the system stop unsafe progression, retain its decisions and retry/escalate appropriately.

Keep a visible mode label throughout: **LIVE ACCEPTANCE** for actual providers, **INTEGRATION DEMO** when only Gmail/Slack are real, or **OFFLINE REHEARSAL** when everything is simulated. A simulated voice answer, demo project ID or application-generated alert must not be presented as real voice, a native Rocketlane project or native automation.

Current evidence supports a real Gmail/Slack integration demo and offline rehearsals. The final positive acceptance recording still needs a working outbound voice interaction, actual Rocketlane configuration and native automation evidence. Secondary Slack simulation is permitted by the assignment when disclosed; real voice is explicitly required.

## 2 Prepare before recording

### 2.1 Assets and windows

Prepare these windows in order, with readable zoom:

1. Part 1 requirements analysis: `deliverables/Part_1_Requirements_Analysis.md`.
2. The monitored Gmail inbox and the test email compose window.
3. The worker terminal and dashboard.
4. Voice provider call view, with the authorized AE ready to answer.
5. The Rocketlane project list, templates and native automation settings.
6. The Slack workspace/channel.

Use synthetic customer details and unique opportunity references for each case. Keep environment secrets, unrelated inbox messages, personal phone numbers and tokens off-screen. Check microphone/system audio and obtain the AE's agreement to include their test call in the recording. Use Loom or another recorder already available to you; no purchase is required by this plan.

### 2.2 Readiness checks

From `C:\RocketLane`:

```powershell
.\.venv\Scripts\python.exe -m scripts.recording_scenarios --preflight
.\.venv\Scripts\python.exe -m pytest -q
```

The preflight prints only configuration-presence booleans, never credentials. A populated setting is not proof that the provider works.

Before a LIVE ACCEPTANCE take, verify:

- The approved Gmail trigger actually selects the newly arriving test email. Use the UI or a trusted filter to apply `onboarding-new-deal`; the current worker OAuth connection is read-only. If a temporary subject filter is used, state that explicitly and do not claim automated label application.
- The real outbound-capable voice account can reach the authorized AE. Credentials alone do not prove calling capability. The AE should say only **Enterprise** or **Growth** when asked, matching the current conservative transcript guard.
- Rocketlane API key and both template `sources` arrays are configured. Templates instantiate the correct four phases, 15 tasks, duration, ownership and migration approval controls.
- The live database has actual `team_members` entries: active CSM, PM and Owner, with `is_mock=0`, correct emails and Slack user IDs. Mock records and the three-account Slack demonstration mapping do not create a production staff directory. Ensure an Enterprise allocation has at least two free CSM units.
- Slack channel creation/invitations work. Demonstrate approved customer participation or disclose its simulation. For the optional progress-monitoring extension, grant `groups:history` and reinstall the app.
- Native Rocketlane rules are enabled: +1 day PM and +4 days Owner, incomplete tasks only. Verify actual recipient identities and notification delivery. Do not run application-generated notifications while proving that a notification came from Rocketlane itself.

Current blockers: no configured Rocketlane API key/template sources/status mapping/task URL template, no accepted live voice evidence, and the last private Slack history read returned `missing_scope`. Native automation and customer-sharing evidence are pending.

## 3 Video one positive journey

Suggested edited length: 6–8 minutes. Record the actual sequence continuously where practical. Long provider waits may be shortened with an on-screen explanation and visible original timestamps.

| Time | Screen and action | Narration | Evidence to capture |
|---|---|---|---|
| 0:00–0:25 | Show the Part 1 summary and mode label | “NovaCRM currently coordinates onboarding manually. This solution validates the handoff, confirms the plan with the AE, creates the correct project and establishes communication. This recording shows [state the actual mode].” | The document and honest integration mode |
| 0:25–1:00 | Show the running worker, then send the synthetic email | “The email supplies customer name, contact email and opportunity link. It deliberately does not include the plan. The worker is monitoring the approved inbox.” | Recipient, received message, timestamp and actual trigger selection |
| 1:00–1:35 | Show the new dashboard run and validation result | “The intake agent accepted the required fields and created one traceable request. The plan is still unconfirmed, so no project has been created.” | Run ID, validated/awaiting-voice state, no premature project |
| 1:35–2:20 | Show/hear the real voice call | Agent: “Please confirm Enterprise or Growth.” AE: “Enterprise.” Presenter: “The plan comes from the completed call, not a default or the email.” | Actual provider call ID, completed call and clear answer |
| 2:20–3:25 | Show the API-created Rocketlane project | “Enterprise selects the 30-day onboarding template and a named dedicated CSM. These are the four phases and the 15 shared tasks. The longer duration addresses complexity, not extra assumed scope.” | Actual project ID, creation time, correct sources/template, date span, phase/task list and assigned CSM |
| 3:25–4:10 | Show CSM and project management assignment | “The allocator checks active workload. Enterprise consumes two of four CSM units. The same CSM owns migration and configuration, with a project manager and owner assigned.” | Reservation, actual role mappings and available capacity |
| 4:10–5:00 | Open the created Slack channel | “The communication agent creates a customer-specific channel, sets the topic, invites the assigned team and posts the welcome. Customer access is [show actual access or disclose the simulation].” | Name, topic, welcome, membership and project reference |
| 5:00–6:20 | Show native Rocketlane automation and notification evidence | “This overdue automation is configured inside Rocketlane: one day overdue goes to the Project Manager, four days overdue goes to the Project Owner. Completed tasks are excluded.” | Rule source, conditions, recipients, enabled state and native delivery evidence |
| 6:20–7:00 | Show checkpoint/audit and a controlled duplicate check | “The audit links the email, call, project and channel. Reprocessing this opportunity retains one intended project and channel. Setup readiness does not mean the customer has completed onboarding.” | Same run/resource references, no second create |
| 7:00–7:30 | Close with acceptance boundary | “The positive scenario demonstrates [list only observed live steps]. Remaining production extensions are documented separately.” | Clear result and any disclosed limitations |

During Slack setup, show the validated **Contact Email** and the customer invitation action after internal team membership. Capture either the customer's actual membership or the Slack invitation receipt. “Invitation sent” means acceptance is pending. If the free workspace cannot send an automatic invitation, show the `customer_invite_manual` pause, the administrator's Slack invitation and its recorded receipt before the welcome. Do not substitute the internal team invitation for customer access.

For a Growth variant, use a separate opportunity and have the AE say **Growth**. Show 14 days, the pooled representative and Growth phase dates. Do not change a run's plan manually to manufacture a second result.

### 3.1 Positive email to copy

Subject: `Assessment positive Enterprise 20261021-01`

```text
Customer Name: Assessment Enterprise Customer
Contact Email: harishaditya866@gmail.com
Salesforce Opportunity Link: https://crm.example/opportunities/assessment-positive-20261021-01
```

The opportunity URL above is an illustrative test reference. Replace it with an approved sandbox opportunity if available. The application parses the link; it does not validate the deal against Salesforce.

### 3.2 Live operating commands

Use a dedicated assessment database with real staff entries already prepared. Do not use the populated mock demonstration database for the final live take. Do not start two setup workers on the same database.

```powershell
$env:GMAIL_QUERY = 'label:onboarding-new-deal subject:"Assessment positive Enterprise 20261021-01"'
.\.venv\Scripts\python.exe -u -m app.main --live --db recordings/assessment-live.db worker --interval 15
```

This is a real-side-effect command: it can place the actual authorized call and create native Rocketlane/Slack resources. Run it only after the prerequisites pass and while the authorized AE is ready. Stop with Ctrl+C after the scenario, then remove the session-only query:

```powershell
Remove-Item Env:GMAIL_QUERY
```

Inspect the live run in another terminal with the exact same database:

```powershell
.\.venv\Scripts\python.exe -m app.dashboard --db recordings/assessment-live.db --port 8081
.\.venv\Scripts\python.exe -m app.main --live --db recordings/assessment-live.db audit RUN_ID
.\.venv\Scripts\python.exe -m app.main --live --db recordings/assessment-live.db checkpoint RUN_ID
```

The placeholders `RUN_ID` and later `TASK_ID`/`MESSAGE_TS` must be copied from actual records. Never substitute a fabricated ID as acceptance evidence.

### 3.3 Demonstrating native overdue rules without waiting four days on camera

Before the take, prepare authorized sandbox control tasks: an incomplete task one day overdue assigned to the PM's project, an incomplete task four days overdue assigned to the Owner's project, and a completed overdue control task. If task dates are backdated, keep start dates on/before due dates and clearly identify these as prepared test fixtures.

Show the native rule conditions and the genuine notification/audit results from Rocketlane's scheduled evaluation. Explain the test dates and evaluation time. Do not alter the computer clock or claim an immediate notification if the native engine has not evaluated yet. If notification evidence is not available, show configuration as configuration and leave live escalation acceptance pending.

## 4 Video two negative journey

Suggested length: 4–6 minutes. Use two short subcases: malformed input and ambiguous voice confirmation. The optional unanswered-call and uncertain-write cases can be additional clips, not replacements for visible evidence.

| Time | Screen and action | Narration | Expected evidence |
|---|---|---|---|
| 0:00–0:20 | Show the negative scenario title and mode | “This recording tests whether the system prevents unsafe onboarding when information is missing or the plan is unclear.” | LIVE ACCEPTANCE or explicit simulation label |
| 0:20–1:20 | Send an email missing contact email; show the rejected run | “The contact email is mandatory. The system identifies that field and stops before calling or creating resources. It does not invent a contact.” | Rejected status, exact missing field, zero call/project/channel activity |
| 1:20–1:40 | Explain the clarification boundary | “The current prototype records the clarification requirement for operator action. An automatic clarification email is not implemented, so I am not claiming one was sent.” | Actual audit/operator view; no fabricated reply |
| 1:40–2:30 | Send a separate valid email; AE says “the expensive one” | “This response may sound like Enterprise, but the guardrail accepts only an explicit supported plan. The project remains blocked.” | Actual call evidence and retry_voice state |
| 2:30–3:50 | Show subsequent retries and final escalation | “Retries are bounded. Live attempts are spaced by the configured delay. After three unusable completed-call outcomes, the request escalates for a human decision.” | Attempts 1–3, timestamps, next-attempt timing, final escalated status |
| 3:50–4:40 | Show absence of downstream resources and review evidence | “There is no project or channel for this unresolved opportunity. The trace explains why. A person must obtain a valid confirmation; they cannot simply default the tier.” | Empty references, project/channel search or call counters appropriate to the actual mode |
| 4:40–5:10 | Close with guardrails | “The negative journey shows validation, bounded retries and an explicit human handoff. Database escalation is a recorded state; a delivered voice-failure human notification remains separate work.” | Honest result and remaining boundary |

### 4.1 Missing-field email

Subject: `Assessment negative missing contact 20261021-01`

```text
Customer Name: Assessment Missing Contact
Salesforce Opportunity Link: https://crm.example/opportunities/assessment-missing-contact-20261021-01
```

Use the matching unique subject in the temporary worker query. Expect rejection with `contact_email`; the plan remains unset and there must be no call, project or channel.

### 4.2 Ambiguous-plan email and AE dialogue

Subject: `Assessment negative ambiguous plan 20261021-01`

```text
Customer Name: Assessment Ambiguous Plan
Contact Email: harishaditya866@gmail.com
Salesforce Opportunity Link: https://crm.example/opportunities/assessment-ambiguous-20261021-01
```

AE reply on each authorized test attempt: **“The expensive one.”** Do not include “Enterprise” in the same response. The current transcript guard also rejects multi-turn or conflicting responses. Show the recorded evidence rather than inferring what a model probably intended.

In live mode the current retry delay is 60 seconds. If you shorten the edit, add “60-second retry interval condensed; original timestamps shown.” Never set rehearsal timing to zero and call the result a live retry demonstration.

### 4.3 Optional failure clips

- **No answer:** show the actual provider's ended/no-answer outcome and the linked retry or escalation. An active call with no outcome can remain awaiting_voice until the ten-minute unresolved-call guard; do not imply every no-answer condition follows an identical path.
- **Uncertain project write:** use an explicitly labeled injected simulation to show reconcile and the saved pending action. No blind second create is permitted. Show the existing resource/provider evidence before an authorized resume.
- **Slack/Rocketlane delivery update:** optionally show an ambiguous task message entering review and a migration sign-off being held without customer evidence. Do not substitute these application guardrails for the required native automation demonstration.

## 5 Safe offline rehearsal

This script always uses simulated adapters. It loads no live credentials, sends no emails, places no calls and creates no external projects or channels. Each case gets an isolated SQLite database and real LangGraph checkpoint history. It cannot fulfill the assignment's live acceptance requirement.

```powershell
.\.venv\Scripts\python.exe -m scripts.recording_scenarios --session my-assessment-rehearsal
```

The script refuses to overwrite an existing session directory. Use a new session name for another take. Rehearsal retries use zero delay and must be disclosed as compressed simulation.

| Rehearsal case | Expected final state | Calls | Projects | Channels |
|---|---|---:|---:|---:|
| Enterprise happy path | complete | 1 | 1 | 1 |
| Growth happy path | complete | 1 | 1 | 1 |
| Missing contact email | rejected | 0 | 0 | 0 |
| Ambiguous plan, three attempts | escalated | 3 | 0 | 0 |
| Ended call with no usable response | escalated | 3 | 0 | 0 |
| Project write result uncertain | reconcile | 1 | 1 attempted | 0 |

The no-usable-answer fixture is not an actual unanswered phone call. The uncertain-write project count represents an attempted simulated create, not a verified native project.

For the prepared session already generated in this repository:

```powershell
.\.venv\Scripts\python.exe -m app.dashboard --db recordings/assessment-rehearsal-20261021/demo-positive-enterprise.db --port 8081
```

Open `http://127.0.0.1:8081/`, select the case's run and inspect its tasks/checkpoints/audit. For a negative take, stop that dashboard and relaunch it against `demo-negative-ambiguous.db` or `demo-negative-missing-field.db` in the same session folder. Do not run the setup worker against these completed rehearsal fixtures. The JSON report contains the exact run IDs and database paths.

Opening narration for rehearsal: **“This is an offline rehearsal. All provider actions are simulated, and retry waits are compressed. The recording demonstrates orchestration and guardrails, not live provider acceptance.”**

For the existing partial integration demo, show customer **Integration Test NovaGrowth Labs**, run `3c6b57a330a1af7ad62ec509f12c802e` and Slack channel `C0CAYM8EAL9`. Say: **“Gmail receipt and Slack setup are real; the voice confirmation and Rocketlane project are simulated. The test was selected by subject.”**

## 6 Evidence and submission checklist

| Deliverable | File or evidence | Completion rule |
|---|---|---|
| Part 1 | `Part_1_Requirements_Analysis.md` | Current/proposed process, clarifications, requirements, assumptions, guardrails and acceptance limits are included |
| Positive video | `01-positive-onboarding.mp4` or Loom link | Actual email, successful voice, correct native project, Slack and native automation evidence are visible; any permitted simulation disclosed |
| Negative video | `02-negative-guardrails.mp4` or Loom link | Invalid input and/or unresolved voice, retries, safe stop and evidence are visible |
| Evidence index | Run/message/call/project/channel IDs and native rule/notification references | All references belong to the recorded case and match timestamps |
| Test result | Latest actual pytest output | Record the result at recording time; do not reuse an outdated count as a new test run |
| Rehearsal report | `scenario_report.json` | Clearly labeled simulation, useful for practice and automated outcome checks |

Watch both exports once before submission. Check that call audio is audible, screen text is readable, resource references match and tokens/unrelated messages are not visible. The two video files or viewable links must actually exist before marking the recording deliverable complete. This package supplies the plan and script; it does not claim to have recorded or published videos.
