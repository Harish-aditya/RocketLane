# Slack delivery monitoring and Rocketlane progress

The delivery agent continues after onboarding setup. Its LangGraph loop synchronizes Rocketlane tasks, reads Slack updates, and checks overdue work. SQLite stores update decisions, escalation receipts and checkpoint references. The existing setup worker and delivery worker run independently.

## Operating modes

`live` reads/writes a real Rocketlane project and posts real Slack notifications. It requires `ROCKETLANE_API_KEY`, verified tenant-specific `ROCKETLANE_TASK_STATUS_VALUES`, real project/task IDs and assigned Slack identities. Never substitute guessed status codes. Set `ROCKETLANE_TASK_URL_TEMPLATE` to your verified HTTPS task URL with `{project_id}` and `{task_id}` placeholders.

`local_demo` reads a real Slack channel but updates only the local simulated task records. Alerts are marked LOCAL DEMO. It does not create or update Rocketlane resources. Initial task deadlines use the end of the configured phase and calendar-day spans. Existing native task schedules are used in live mode instead.

New channels created by the live or Gmail/Slack demo workflow automatically register a delivery monitor after successful welcome. Purely simulated channels are excluded. Start the separate delivery worker to poll registered channels.

## Configuration

The bot must be a member of the monitored channel. Private channels require `groups:history` to read updates and `chat:write` to notify the team. Public channel reading requires `channels:history`. The manifest includes these scopes, but editing the manifest file does not grant permissions: update OAuth permissions in Slack and reinstall the app.

Current development channel configuration:

```powershell
.\.venv\Scripts\python.exe -m app.delivery configure 3c6b57a330a1af7ad62ec509f12c802e --mode local_demo --csm U0CAQDLMDC3 --pm U0CA22QMVMG --owner U0CA09DLC6S
.\.venv\Scripts\python.exe -u -m app.delivery worker --interval 60
.\.venv\Scripts\python.exe -m app.delivery status
```

Elsa is the Slack CSM representative, Star Boy the PM and Harish Aditya the Owner. Local simulated capacity allocation remains separately identified; these demo accounts represent those roles.

## Reporting progress

Send a top-level message in the customer's channel:

```text
TASK <exact task ID> STATUS in_progress PROGRESS 40
TASK <exact task ID> STATUS blocked PROGRESS 40 NOTE Waiting for customer access
TASK <exact task ID> STATUS completed PROGRESS 100
```

Copy the task ID from the dashboard delivery task list. Live mode accepts either the local `rocketlane:<id>` reference or the native numeric task ID, scoped to that project. Supported states are `not_started`, `in_progress`, `blocked` and `completed`. Status/progress must agree. Only the assigned CSM, PM or Owner can update tasks. Bot messages and Slack system events are ignored. Free-form progress messages are recorded for human review rather than guessed. Thread-only messages and edits of already-processed messages are not task commands; post a new top-level update instead. Monitoring starts at configuration time and does not replay historical conversation.

Updates are processed oldest first across complete history pages. The same Slack message cannot apply twice. Reopening a completed task, reducing progress, cross-project IDs or missing verification evidence requires review. Migration sign-off/readiness cannot be completed without recorded verification. Live writes are preceded by a fresh task read and followed by verification. The API does not supply an atomic compare-and-swap guarantee, so a remote edit racing the final write remains a live acceptance risk.

## Escalation policy

An unfinished task one calendar day overdue triggers a mention of its assigned PM in the onboarding channel. Four days overdue triggers its assigned Owner. First monitoring a task beyond four days sends any unsent thresholds, including a missed PM threshold. Each threshold is sent once per task and due date. A changed due date establishes a new schedule. Completed tasks, completed/cancelled onboardings and tasks with uncertain pending updates are excluded. Setup readiness does not imply delivery completion or release CSM capacity.

Alerts include task, owner, due date, overdue age, status, progress and blocker note; live task links use the verified URL template. An unavailable link is explicitly disclosed. Lack of activity before the due date is not an additional trigger. Rocketlane API or Slack history failures stop escalation for that cycle and appear in the dashboard. Last valid task data is retained after partial/failed synchronization.

This implements application-driven Slack escalation. Native Rocketlane automation configuration remains a separate tenant acceptance item; do not enable duplicate native and application notifications without agreeing the desired behavior.

## Human review and recovery

The dashboard's Delivery monitoring and escalation panel shows permission errors, update reviews and notification receipts. Review commands use the trusted local operator; stop the delivery worker before manual review so it cannot race the decision.

```powershell
.\.venv\Scripts\python.exe -m app.delivery review RUN_ID MESSAGE_TS --decision apply --reviewer "Project Owner" --evidence "Verified customer confirmation" --task-id TASK_ID --status completed --progress 100
.\.venv\Scripts\python.exe -m app.delivery review RUN_ID MESSAGE_TS --decision reject --reviewer "Project Owner" --evidence "Wrong task reference"
```

For an uncertain native write, review first reads Rocketlane. If the intended state already exists, it finalizes the local receipt without repeating the write. Migration evidence remains mandatory. For an uncertain alert, inspect Slack first:

```powershell
.\.venv\Scripts\python.exe -m app.delivery resolve-alert RUN_ID TASK_ID YYYY-MM-DD --threshold 1 --decision sent --reviewer "Project Manager" --evidence "Confirmed alert in Slack"
```

Use `--decision retry` only when provider evidence proves the alert was not delivered. An uncertain receipt never retries automatically. Preserve the business database and `.delivery.checkpoints.db` together. The delivery worker holds its own OS lock, so a second delivery worker cannot poll the same database.

## Verification boundary

Automated fixtures exercise explicit/ambiguous updates, role checks, task scope, migration gates, complete pagination, native synchronization, failed snapshots, uncertain writes, human reconciliation, deadlines, completed-task exclusion and duplicate alert protection. These tests do not replace live Rocketlane tenant acceptance. The present environment has no Rocketlane API key, and Slack currently reports missing_scope for private-channel history until `groups:history` is granted.

API references: https://developer.rocketlane.com/reference/update-task, https://developer.rocketlane.com/reference/get-all-tasks, https://developer.rocketlane.com/docs/pagination and https://docs.slack.dev/reference/methods/conversations.history/.
