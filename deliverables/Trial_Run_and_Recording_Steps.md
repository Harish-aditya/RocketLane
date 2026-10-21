# Customer Invitation Trial and Recording Steps

## Project task simulation — completed

The existing positive run now has all **15 tasks completed at 100%**: Kickoff (3), Data Migration (4), Configuration (4), and Go-Live (4). Each task passed through in-progress and completed states in the delivery graph. Simulated migration verification was recorded, the demo CSM assignment was released, and this completed project's delivery monitor was disabled. Evidence: `recordings/positive_project_task_simulation.json`.

These are synthetic local updates, not messages written by real Slack users or native Rocketlane updates. The task source is `local_demo_simulation`; audit records identify synthetic inputs and simulated approval. The existing completed run is safe to invoke again but will not replay progress.

To record task progression on a **fresh, fully set up positive run**, pause the delivery worker using the verified process instructions in this guide, then substitute its run ID below. The script acquires the delivery worker lock; it refuses live projects and requires earlier phases to be complete. Refresh the dashboard after each command and show the task table and checkpoint log:

```powershell
.\.venv\Scripts\python.exe -m scripts.simulate_project_tasks NEW_RUN_ID --phase Kickoff
.\.venv\Scripts\python.exe -m scripts.simulate_project_tasks NEW_RUN_ID --phase "Data Migration"
.\.venv\Scripts\python.exe -m scripts.simulate_project_tasks NEW_RUN_ID --phase Configuration
.\.venv\Scripts\python.exe -m scripts.simulate_project_tasks NEW_RUN_ID --phase Go-Live
```

Use `--phase all` to finish all four phases in one invocation. Each phase command runs both in-progress and completed transitions; intermediate states remain visible in logs/checkpoints rather than waiting on screen. After the final phase, show 15/15 complete and released CSM capacity. Restore the delivery worker afterward with `.\.venv\Scripts\python.exe -u -m app.delivery worker --interval 60`.

21 October 2026 • Run from `C:\RocketLane`

## Latest recheck — positive setup completed

The positive run `361fbe81dfbb980976aca763a0256432` completed on 21 October 2026 at 09:38 UTC. Slack customer email lookup now works. The customer account `harishaditya866@gmail.com` resolved to Star Boy (`U0CA22QMVMG`), and channel membership was verified together with the three internal team accounts. The topic was set and Slack accepted the welcome message. The same project and channel were reused.

The customer is an existing workspace member who also represents the PM in this demo; no new external invitation email was sent. Voice and Rocketlane remain simulated. “Complete” means onboarding setup is complete, not that all customer onboarding tasks are finished.

For recording a fresh journey, use the new-take instructions below. Do not retry this completed run. Sections 1–3 retain the initial permission-blocked trial history; the permission fix and resume steps are already complete for this run. Evidence: `recordings/customer_invite_trial_result.json`.

## 1 Initial trial result (before successful recheck)

| Stage | Observed result |
|---|---|
| Test email | Sent and received by harishaditya1308@gmail.com |
| Input validation | Three required fields accepted |
| Voice | Growth answer simulated; no real phone call placed |
| Rocketlane project | Simulated project `demo-project-361fbe81` |
| CSM allocation | Mock capacity reserved for Vikram CSM; Elsa represents the CSM in Slack |
| Slack channel | Real channel `C0CARGF56UT` created |
| Internal team | Elsa, Star Boy and Harish Aditya verified as members |
| Customer email | harishaditya866@gmail.com |
| Customer step | Paused as `customer_invite_manual`: users:read.email is missing |
| Welcome | Not posted while customer invitation remains unresolved |
| Overall result | Correct pause at a configuration guardrail; positive journey is not yet complete |

Positive trial run: `361fbe81dfbb980976aca763a0256432`.

Slack channel: https://app.slack.com/client/T0C9LSJASF9/C0CARGF56UT.

Negative trial: a second real email omitted Contact Email. Run `16b808ce9736be230983fde8127a9c31` was rejected with `contact_email`; there was no call action, project or Slack channel for that request.

Detailed local evidence: `recordings/customer_invite_trial_result.json`. The current Gmail test uses exact-subject selection, not automated label application. Both trials leave production/native Rocketlane acceptance unproven.

## 2 Fix the customer lookup before a positive recording

In Slack App Settings → OAuth & Permissions → Bot Token Scopes, add **users:read.email** and reinstall the app into the RocketLane workspace. The existing users:read scope alone does not reveal email addresses. Keep the same bot token unless Slack rotates it; if rotated, update the local `.env` without displaying it on camera.

For this free-workspace demonstration the customer email is an existing workspace account. The expected result is **member_added**, not a new Slack Connect invitation email. That account also represents the PM in the small three-account demo. Disclose the dual role; it is not evidence of inviting a new external customer.

An external-customer email invitation requires the supported Slack Connect path and its permissions/eligibility, or a verified administrator invitation. Do not enable a paid service just for this recording.

## 3 Finish the existing trial on camera

1. Open the dashboard and search for **Recording Trial NovaGrowth**. Show the customer invitation action-needed state and its exact permission error.
2. After the scope is installed, open a PowerShell terminal in `C:\RocketLane` and run:

```powershell
.\.venv\Scripts\python.exe -m app.main --gmail-slack-demo --db local-worker.db retry-customer-invite 361fbe81dfbb980976aca763a0256432
```

3. Show that the existing channel is reused. Expected outcome after lookup succeeds: customer `member_added`, topic set, welcome posted and overall setup `complete`.
4. Open the existing Slack channel. Show the member list, topic and welcome. The invitation retry must not create another project or channel.
5. In the dashboard, open the run and checkpoint/audit history. Show the customer invite intent/result and the existing channel ID.

Narration: “The first attempt paused because the bot could not resolve the customer's email. After correcting the permission, I retry only the invitation step. The existing channel and project reference are retained. This is real Gmail and Slack, with voice and Rocketlane simulated.”

If the permission remains missing, the command pauses again. Do not record a success claim or manufacture an operator receipt. If an administrator actually invites/verifies the customer manually, follow `docs/customer_slack_invitation.md` to record that evidence instead.

## 4 Recreate a fresh positive take from email arrival

### 4.1 Open recording windows

Open Gmail at harishaditya1308@gmail.com, the local dashboard at http://127.0.0.1:8080/, the Slack workspace, and the terminal. Hide unrelated email, phone numbers and credentials. Keep the mode label **REAL GMAIL AND SLACK — SIMULATED VOICE AND ROCKETLANE** visible in your narration or title card.

### 4.2 Pause the normal worker

If it is running in your terminal, use Ctrl+C. If the managed background worker is running, stop only the recorded RocketLane process tree:

```powershell
$setupWorkerId = [int](Get-Content -LiteralPath .\recordings\local_worker.pid)
$setupWorkerInfo = Get-CimInstance Win32_Process -Filter "ProcessId=$setupWorkerId"
if ($setupWorkerInfo.CommandLine -notmatch 'app\.main.*--gmail-demo.*local-worker\.db') {
    throw 'The PID does not identify the expected RocketLane demo worker. Inspect it before stopping.'
}
taskkill /PID $setupWorkerId /T /F
```

The independent delivery monitor/dashboard can remain open. Do not stop arbitrary Python processes or delete the database to repeat a recording.

### 4.3 Start the test worker before sending

Use a new subject and opportunity reference for every take. This example uses take 04:

```powershell
$env:GMAIL_QUERY = 'subject:"NovaCRM recording take 20261021-04"'
.\.venv\Scripts\python.exe -u -m app.main --gmail-slack-demo --db local-worker.db worker --interval 15 --answer Growth
```

This worker reads real Gmail and creates real Slack resources. The Growth voice answer and Rocketlane project are simulated. Keep the terminal running while sending the mail. Only one setup worker should own this database.

### 4.4 Send this email

To: `harishaditya1308@gmail.com`

Subject: `NovaCRM recording take 20261021-04`

```text
Customer Name: Recording Take 04 NovaGrowth
Contact Email: harishaditya866@gmail.com
Salesforce Opportunity Link: https://crm.example/deal/take04
```

Record the received email and then the worker output. The body intentionally has no plan tier. On this test, `--answer Growth` supplies the disclosed simulated response.

### 4.5 Show the outcome in order

1. Dashboard request validated and simulated voice confirmation recorded.
2. Growth schedule: 14 days, four phases, 15 tasks and allocated CSM capacity.
3. Real customer-specific Slack channel created.
4. Assigned team added.
5. Customer email lookup/addition recorded. Show member_added or the true manual/awaiting-invitation status.
6. Topic and welcome, only after the customer step is resolved.
7. Timestamped action audit and checkpoints. Emphasize that setup readiness is not completion of the 15 delivery tasks.

Expected narration: “The email is detected automatically within this configured subject query. The plan and native project are simulated in this development mode. Slack channel creation, team membership and customer lookup are real. I am showing the actual invitation result rather than assuming that the customer joined.”

When a run reaches `customer_invite_manual`, stop and show the reason. Resolve the specific permission or perform a verified administrator invitation; resume that same run rather than sending a new email to hide the failure.

## 5 Recreate the negative take

Stop the positive worker with Ctrl+C. Set a new subject and restart the same mode:

```powershell
$env:GMAIL_QUERY = 'subject:"NovaCRM recording negative take 20261021-04"'
.\.venv\Scripts\python.exe -u -m app.main --gmail-slack-demo --db local-worker.db worker --interval 15 --answer Growth
```

Send to harishaditya1308@gmail.com:

Subject: `NovaCRM recording negative take 20261021-04`

```text
Customer Name: Recording Negative Take 04
Salesforce Opportunity Link: https://crm.example/deal/negative04
```

Show `rejected`, missing `contact_email`, no call intent and empty project/channel references. Explain: “The required customer email is missing. The system stops before voice or provisioning; it does not guess a customer or silently continue.” Delivered clarification email is not implemented, so demonstrate the recorded operator action requirement instead.

For the additional ambiguous/no-usable-answer rehearsal, use `scripts/recording_scenarios.py` and label all its integrations as simulated. A full live negative voice recording still needs an actual authorized call.

## 6 Stop the recording test cleanly

Use Ctrl+C in the test worker terminal, then:

```powershell
Remove-Item Env:GMAIL_QUERY
.\.venv\Scripts\python.exe -u -m app.main --gmail-demo --db local-worker.db worker --interval 15 --answer Enterprise
```

The last command restores the normal label-based worker in the foreground. Keep it running or stop it intentionally. It simulates downstream actions; it is not a persistent real-Slack deployment.

Existing recorded opportunities are deduplicated. Use a new take number instead of trying to recreate the same opportunity. If CSM capacity is full, the correct result is awaiting_capacity; complete/cancel only genuinely finished test assignments with a recorded reason, or use a fresh approved rehearsal environment. Do not falsify capacity for the camera.

## 7 Final submission boundary

These exact steps recreate the current integration demonstration and its guardrails. The assignment's full positive acceptance video additionally needs real Voice AI confirmation, real Rocketlane API provisioning and native Rocketlane automation proof. See `Video_Walkthrough_Script_and_Recording_Plan.md` for that final acceptance script.
