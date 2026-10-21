# Slack configuration

1. Open https://api.slack.com/apps and choose **Create New App → From a manifest**. Select your development workspace and paste `config/slack-app-manifest.json`.
2. Install the app to the workspace. The bot scopes are `groups:write` (private channel creation, invitations and topics) and `chat:write` (status messages). Reinstall if you change permissions. No incoming webhook, public server, Events API or paid voice service is required.
3. Copy the **Bot User OAuth Token** into the local `.env` as `SLACK_BOT_TOKEN`. Do not commit it or paste it into chat.
4. In Slack, open each team member's profile → More → Copy member ID. Configure comma-separated IDs:

```dotenv
SLACK_BOT_TOKEN=xoxb-your-bot-token
SLACK_SHARED_TEAM_USER_IDS=U_PROJECT_MANAGER,U_OWNER
ENTERPRISE_SLACK_TEAM_USER_IDS=U_DEDICATED_CSM
GROWTH_SLACK_TEAM_USER_IDS=U_POOLED_CSM
```

Replace the example IDs with actual Slack IDs (normally U followed by letters/numbers; no underscores). These must be existing workspace members. Shared members are added for either plan; plan-specific members only after explicit Enterprise/Growth confirmation.

5. Validate credentials and mapping syntax without creating a channel:

```powershell
.\.venv\Scripts\python.exe -m app.slack_status check
```

This authenticates the bot but does not prove that every mapped member is active; invitations are checked by Slack when the channel is created.

## Channel and status workflow

The existing live graph creates a private customer channel after plan confirmation and project creation, invites the mapped team one person at a time, sets the topic, then posts the welcome. Uncertain writes require human reconciliation before retry. Do not switch the Gmail demo worker to `--live` solely to test Slack: that also enables real voice and Rocketlane writes.

For a run already linked to a real Slack channel, post a recorded status snapshot independently:

```powershell
.\.venv\Scripts\python.exe -m app.slack_status --db onboarding.db publish RUN_ID
```

The command uses the exact database path, posts only when the snapshot changes, and records the delivery in `slack_status_delivery` and the audit log. A crash or uncertain response blocks another post until the operator checks the channel and reconciles the delivery ledger. The command rejects simulated channel IDs. It reports phase/task status and owners from the local database and explicitly labels unsynchronized or simulated data. It does not read Slack replies or treat messages as task updates. Scheduled status publishing and native Rocketlane progress synchronization are separate follow-up work.

Missing configuration currently prevents real Slack channel creation. Supply the token and member IDs locally, then rerun `check` before a live channel test.

References: https://docs.slack.dev/reference/methods/conversations.create/ and https://docs.slack.dev/reference/methods/chat.postMessage/

## Real Gmail and Slack integration test

Use `--gmail-slack-demo` instead of `--gmail-demo` for an explicit test that simulates voice/project operations and creates real Slack channels. This mode requires the verified three-account role mappings in `slack_demo_members`; those accounts represent the allocated mock team. It does not create live Rocketlane projects or demonstrate real AE confirmation.

```powershell
$env:GMAIL_QUERY = 'subject:"YOUR UNIQUE TEST SUBJECT"'
.\.venv\Scripts\python.exe -m app.main --gmail-slack-demo --db local-worker.db worker --once --answer Growth
Remove-Item Env:GMAIL_QUERY
```

Pause the normal worker before a one-time test against the same database, then restore it afterward. Do not use `--live` for this test. Subject filtering is useful with read-only Gmail access; it does not prove automatic label application. The normal worker query remains `label:onboarding-new-deal`.

Verified test: Integration Test NovaGrowth Labs, Growth, run `3c6b57a330a1af7ad62ec509f12c802e`, Slack channel `C0CAYM8EAL9`. Gmail receipt, real channel creation, three member invitations, welcome and 60 graph checkpoints were verified. Voice and Rocketlane were simulated.
