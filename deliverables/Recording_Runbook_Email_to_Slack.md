# Recording runbook: Gmail to Slack onboarding

Use this order for a positive Growth case and a negative missing-field case. Real Gmail and Slack are used; voice and Rocketlane projects are simulated. Workers are currently stopped; the dashboard was left running.

Before recording, open the sender Gmail account, the recipient Gmail account, Slack, PowerShell and http://127.0.0.1:8080/. Keep credentials off screen. The configured Gmail OAuth account must be the recipient account. Use Growth: the checked demo directory has four CSMs with one spare unit each, but no CSM has the two spare units needed for Enterprise. Capacity can change after other requests.

The common `.env` query is `from:harishaditya866@gmail.com to:harishaditya1308@gmail.com subject:"NovaCRM Onboarding"`. It matches the subject phrase anywhere; the square brackets are a visual convention, not a strict regex boundary. No Gmail label is required. Do not pass an old `-GmailQuery` override when using this shared trigger.

## 1 Send both onboarding emails

From: harishaditya866@gmail.com. To: harishaditya1308@gmail.com.

Positive subject: `[NovaCRM Onboarding] take05 positive`

```text
Customer Name: Recording Take05 Growth
Contact Email: harishaditya866@gmail.com
Salesforce Opportunity Link: https://crm.example/deal/recording-take05-positive
```

Negative subject: `[NovaCRM Onboarding] take05 negative`

```text
Customer Name: Recording Take05 Missing Email
Salesforce Opportunity Link: https://crm.example/deal/recording-take05-negative
```

Say: “Both emails enter the same intake workflow. The negative email deliberately omits the customer contact email.” Show both received messages in the recipient inbox. The CRM links are test identifiers, not real Salesforce records.

For another take, replace take05 in the subjects, names, opportunity links below; the configured common Gmail query stays unchanged. Reusing an opportunity or Gmail message will deduplicate rather than create a fresh run.

## 2–3 Show the answer setting and start the worker

The answer is configured before starting the worker. Show `-Answer Growth` on screen and say: “For this free development demonstration, I supply the AE's answer as Growth. Enterprise is also supported, subject to available capacity.” This input is not inferred from the email.

```powershell
Set-Location C:\RocketLane
.\scripts\run_agent.ps1 -Component onboarding -Answer Growth
```

Wait for a complete JSON polling result. Show `worker_start`, the real Gmail/Slack simulation mode, `ingested` containing the captured run IDs, and `runs`. The positive result should reach `complete` with `plan: Growth` and `team_members_added: 3`. The negative result should reach `rejected` with `invalid_fields: contact_email`.

Logs are emitted after each polling cycle, not as an interactive pause at every action. Capture the positive and negative IDs; do not mistake the worker's mode string for an all-live implementation. If a permission error or manual customer step appears, show that result and resolve it before calling the positive scenario complete.

## 4 Show that Slack channel creation was triggered

In a second terminal, substitute the positive ID from the log:

```powershell
Set-Location C:\RocketLane
$positiveRun = 'PASTE_POSITIVE_RUN_ID'
.\.venv\Scripts\python.exe -m app.main --gmail-slack-demo --db local-worker.db audit $positiveRun
```

Show `channel_result`, team member results, `customer_invite_result`, `topic_result` and `welcome_result`. These are durable action results. To display the resulting channel and customer receipt:

```powershell
.\.venv\Scripts\python.exe -m app.main --gmail-slack-demo --db local-worker.db show $positiveRun
```

Say: “The validated request and confirmed plan caused a real Slack channel to be created. The customer membership step and welcome message completed.” For the negative run, show `rejected`, its missing contact field, and absent project/channel IDs. It must not create a channel or proceed to voice/project actions.

## 5 Show the created Slack channel

Open the returned channel ID using `https://app.slack.com/client/T0C9LSJASF9/CHANNEL_ID`. Show the welcome, Growth plan, topic and membership. The welcome marks this as an integration test. The mock allocated CSM is represented in Slack by Elsa; PM is Star Boy and Owner is Harish Aditya.

The contact email resolves to Star Boy, an existing workspace member who also represents the PM. Say: “For this demo, the customer's existing Slack account is included in the channel.” Do not claim that a new external invitation email was sent.

## 6 Show dashboard allocation and monitoring

Open http://127.0.0.1:8080/ and search for `Recording Take05 Growth`. Show the assigned CSM, Growth's 14-day schedule, tasks, capacity/workload, customer membership and checkpoint/audit records. The workload model permits 4 units per CSM: Enterprise uses 2 and Growth uses 1. CSM owns migration and configuration too. Allocation uses available capacity; do not promise a specific CSM name.

Onboarding setup being complete does not mean all project tasks are complete. Show the missing-field case as rejected.

If demonstrating ongoing channel monitoring, start this in another terminal:

```powershell
.\scripts\run_agent.ps1 -Component delivery
```

The delivery agent reads authorized Slack task commands, updates local demo task progress and checks deadlines. History permissions must be installed. An enabled monitor alone does not prove successful polling or escalation: show its last-check/error state. Actual overdue escalation is a separate scenario from this setup demonstration.

If the dashboard is unavailable, start it once in a separate terminal:

```powershell
.\scripts\run_agent.ps1 -Component dashboard
```

## 7 Closing narration

“This demonstrates real Gmail intake, validation, capacity-based assignment and Slack channel setup. To keep development free and avoid outbound calling costs, I simulated the voice confirmation using the worker's plan answer. Rocketlane project creation is also simulated in this environment. The negative request is rejected before downstream resources are created.”

After recording, Ctrl+C each worker terminal. Leave the dashboard running if desired. This recording does not establish live voice or native Rocketlane acceptance.
