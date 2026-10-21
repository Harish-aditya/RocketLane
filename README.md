# Rocketlane onboarding automation

## Local operations dashboard

```powershell
.\.venv\Scripts\python.exe -m app.dashboard --db demo-local-worker.db --port 8080
```

Open [the local dashboard](http://127.0.0.1:8080) for total agent attempts, customer run statuses, planned delivery tasks, worker heartbeat, and per-run checkpoint/audit timelines. Search and filter runs, then select **View** to inspect their details. The page refreshes every five seconds. Database tables capture status projections, per-agent attempts, task records and committed LangGraph checkpoint events. See [dashboard documentation](docs/dashboard.md) for schema and measurement definitions. Task progress is a local planning snapshot, not synchronized Rocketlane progress; setup readiness never automatically completes delivery tasks.

Scope follows [Karthik's confirmed clarifications](docs/clarifications.md): only customer name, contact email and Salesforce opportunity link are mandatory. Both plans share 15 tasks; Enterprise complexity is reflected in longer project and phase durations.

A runnable Python assessment project with custom LangGraph orchestration, Intake & Routing and Communication subgraphs, durable SQLite checkpoints, Gmail polling, Vapi outbound calls, Rocketlane project creation and private Slack channels.

## Run locally (PowerShell)

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m scripts.demo_scenarios
```

This workspace already has an installed `.venv`. Demo scenarios use isolated in-memory databases and simulated services. They make no external requests.

## Three simulated confirmations and Slack team membership

```powershell
.\.venv\Scripts\python.exe -m scripts.confirmation_scenarios
```

This free demo uses no credentials or external requests and saves `deliverables/simulated_confirmation_cases.json`:

| Simulated AE response | Result | Simulated Slack team |
|---|---|---|
| Enterprise | 30-day dedicated-CSM onboarding completes | Project Manager, Project Owner, dedicated CSM |
| Growth | 14-day pooled-CSM onboarding completes | Project Manager, Project Owner, pooled CSM representative |
| the expensive one | Explicit Enterprise/Growth clarification required; no project/channel/invitations | None |

The example roles are assumptions; replace them with the real agreed team mapping before live use. The ambiguous case remains `retry_voice` after one attempt, then escalates if the bounded retry limit is exhausted. An explicit response on a subsequent simulated call can resume the flow; the test suite covers that recovery.

For live membership, configure comma-separated existing Slack **user IDs** in `SLACK_SHARED_TEAM_USER_IDS` (optional common members), `ENTERPRISE_SLACK_TEAM_USER_IDS` and `GROWTH_SLACK_TEAM_USER_IDS` (required per-tier members). For example, common members can be PM/Owner and tier members the relevant CSM. IDs must belong to the channel workspace; display names and emails are not user IDs. No real user IDs are supplied by the demo. Channel creation selects and snapshots the team only after explicit plan confirmation. Each invitation is a durable LangGraph action, followed by topic and welcome. A failed invitation prevents welcome/completion and retains the project and previously added members. Already-present membership is safe.

Unknown invitation outcomes require inspection of actual channel membership, then:

```powershell
.\.venv\Scripts\python.exe -m app.main --live reconcile RUN_ID member_added --resource-id SLACK_USER_ID --evidence 'Verified this member is in the existing channel'
```

The user ID must match the interrupted invitation. Team additions use `conversations.invite` with the appropriate private-channel invite permissions (such as `groups:write` or applicable granular invite scopes). Customer guest provisioning or Slack Connect invitations remain separate from adding existing internal workspace members. This demo creates only simulated channels and memberships; it does not send real Slack invitations.

To inspect a persistent demo:

```powershell
.\.venv\Scripts\python.exe -m app.main ingest examples/deal.txt --message-id sample-001
.\.venv\Scripts\python.exe -m app.main advance
```

Repeat `advance` to move through call initiation, confirmation, project creation, channel creation, topic and welcome. Use `show RUN_ID` and `audit RUN_ID` to inspect results. `step RUN_ID --answer Growth` provides a simulated voice response for a specific run. Demo databases use a `demo-` filename prefix; never point live commands at a demo database.

## LangGraph execution

```powershell
# Advance through ready nodes until waiting on voice, a retry, or an operator.
.\.venv\Scripts\python.exe -m app.main run RUN_ID
# Process all existing demo runs in one worker cycle; no Gmail or external calls.
.\.venv\Scripts\python.exe -m app.main worker --once
# Inspect graph topology and a run's durable checkpoint.
.\.venv\Scripts\python.exe -m app.main graph
.\.venv\Scripts\python.exe -m app.main checkpoint RUN_ID
```

`app/graph_workflow.py` compiles an actual `StateGraph` with typed state, conditional edges, intake/communication subgraphs, provisioning and human reconciliation. `app/operations.py` owns guarded business operations. The existing `Workflow` import and CLI remain compatible. Each customer uses its run ID as LangGraph `thread_id`. Checkpoints persist beside the business database as `DATABASE.checkpoints.db`; protect and retain both files. In-memory demos use an in-memory SQLite checkpointer.

The built-in agents are deterministic by default, allowing credential-free tests and demos. For model-backed extraction and welcome drafting, install `requirements-models.txt` plus your selected LangChain provider package, configure that provider's credentials, and pass `--model provider:model-name` before the command. Provider/model compatibility must be verified with your chosen service. The base installation does not make LLM requests. Programmatic callers can inject `IntakeAgent(model)` and `CommunicationAgent(model)` into `Workflow`. Model extraction must be grounded in the supplied email; plan confirmation stays deterministic and voice-only. Model drafts that omit required personalization fall back to the verified message template. Model calls can incur costs and send customer context to the configured provider.

## Live setup

Set variables in the local `.env` or process environment, for example `$env:VAPI_API_KEY='...'`. The CLI loads the repository .env without overriding existing process environment variables. Never paste real secrets into source files or commit customer records.

1. Gmail: enable the API and acquire a Gmail readonly OAuth access token. Create the `onboarding-new-deal` label and filter only approved AE senders into it. The label is the trust boundary; do not label arbitrary external email. The Gmail adapter refreshes expired access tokens after a 401 when OAuth client and refresh-token settings are available; repeat authorization if refresh is revoked or expires. Intake accepts the three structured plain-text fields in `examples/minimal_deal.txt`; AE fields in `examples/deal.txt` are optional; arbitrary prose, HTML-only messages and attachments are not supported.
2. Vapi: configure `AE_DEFAULT_PHONE` for the single designated assessment AE, or supply optional `AE Phone` metadata. For multiple AEs, implement trusted sender-to-phone directory routing before live use. Missing phone routing escalates without invalidating the email. Create an assistant and an outbound-capable phone number. Configure the assistant to ask for exactly one response, Enterprise or Growth, then end the call. Confirm identity before the plan question in your production assistant. The adapter uses actual user transcript messages, never an AI summary. Multiple user turns fail closed for manual review. Only call authorized AE numbers. Calls incur provider charges.
3. Rocketlane: create or select Enterprise and Growth templates with 30 and 14 day schedules. Set the project owner and dedicated/pooled CSM member email addresses. For pooled assignment, this implementation maps to a configured pool representative; automatic capacity-based selection is not implemented. Copy the exact `sources` array from your tenant's Create Project API request into each `*_TEMPLATE_SOURCES` environment value. The adapter forwards it rather than guessing nested template field names. Use the shared tasks and phase schedules in `app/plan_templates.json` and verify native template role mapping, durations and task assignments in your sandbox. Local configuration does not modify native templates. Review existing customer projects before enabling intake: local opportunity deduplication does not discover projects created manually outside this application.
4. Slack: install a bot with the required private-channel create/invite/topic permissions and `chat:write`. Configure the shared and tier-specific team user IDs described above. Private channel creation, per-member invitations, topic and welcome are separate durable steps. Customer guest invitations/Slack Connect are manual; the app does not assume that an email address belongs to a Slack workspace member.
5. Configure and verify native overdue rules using `docs/native_automation.md`. No external escalation scheduler is used.

```powershell
.\.venv\Scripts\python.exe -m app.main --live poll-gmail
.\.venv\Scripts\python.exe -m app.main --live advance
# Automatic intake and execution until stopped with Ctrl+C:
.\.venv\Scripts\python.exe -m app.main --live worker --interval 15
```

The worker polls and advances accepted runs automatically, yielding between active calls and retry times. Use **one worker** per database; an OS file lock prevents two `worker` processes owning the same database. Stop the worker before using mutating operator commands; manual commands and multiple hosts are not protected by a distributed lease. Gmail intake failures are logged and do not block previously accepted runs. Voice outcomes are polled with authenticated requests to Vapi; no public webhook server is required. Unresolved ended calls retry at most three times, at least 60 seconds apart. A call still active after ten minutes escalates for inspection instead of redialing blindly.

## Recovery and evidence

Every external write has a committed intent. A timeout, uncertain POST result or interrupted pending step becomes `reconcile`. Inspect the provider by call ID, project external reference/run ID, or deterministic channel name. Never blindly repeat a create request. After finding the resource:

```powershell
.\.venv\Scripts\python.exe -m app.main --live reconcile RUN_ID project_created --resource-id PROJECT_ID --evidence 'Operator verified matching externalReferenceId in Rocketlane'
.\.venv\Scripts\python.exe -m app.main --live advance
```

Other reconciliation targets are `awaiting_voice`, `channel_created`, `topic_set`, and `complete` (only after independently confirming the welcome was delivered). The target must match the interrupted action. LangGraph `interrupt()` persists the review request; `reconcile` validates evidence before resuming through `Command(resume=...)` on the same thread. Invalid targets cannot skip voice or provisioning. Operator receipts make replay safe if the ledger commits before the graph checkpoint. The CLI assumes a trusted local operator; no public authenticated HTTP service is implemented. Escalated records require operator investigation; there is no generic reset button that bypasses voice validation. For confirmed no-side-effect failures, remediation currently requires a reviewed state repair or a fresh database in a sandbox.

Safe GET requests retry transient errors with bounded backoff. POST requests never automatically retry because these APIs' idempotency guarantees have not been established. Provider errors remain visible in state and audit records.

```powershell
.\.venv\Scripts\python.exe -m app.main --live verify-migration RUN_ID --verifier 'Customer champion' --evidence 'Reconciled counts and sample records; approval ticket CUSTOMER-123'
```

Migration verification is a local evidence gate. It does not intercept task completion inside Rocketlane; configure the corresponding task dependency/approval in the template. Workflow `complete` means onboarding setup completed, not that customer onboarding or migration finished.

## Submission status

Implemented and locally tested: validation, both plan routes, voice gating, adapters, persistence, deduplication, audit, uncertain-write recovery, migration evidence and demo scenarios. Live API compatibility, actual voice calls, tenant templates and native automation require credentials and tenant verification. No live calls or customer projects have been created, native rules have not been configured, and walkthrough videos have not been recorded. See `docs/demo_walkthrough.md` for the recording script.

LangGraph migration verification: **40 local tests pass**, including durable restart, interrupt/resume across restart, invalid reconciliation, crash after provider write, crash after operator commit, worker locking, automatic intake, retry scheduling, thread isolation and injected structured-model agents. Real model-provider requests have not been executed. Missing-field email replies, delivered human escalation alerts, sender-directory routing, provider-side existing-project discovery and customer Slack invitations remain assessment gaps.

The original assignment text has now been supplied and cross-checked alongside Karthik's clarifications. See [requirements cross-check](docs/requirements_crosscheck.md) for the full coverage matrix and submission gaps. The project is a partially implemented prototype; passing local tests does not establish completion of the live acceptance requirements.

## References

- [Rocketlane Create Project](https://developer.rocketlane.com/reference/create-project)
- [Rocketlane request/authentication example](https://developer.rocketlane.com/docs/examples)
- [Vapi Create Call](https://docs.vapi.ai/api-reference/calls/create)
- [Gmail messages.list](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list)
- [Slack conversations.create](https://docs.slack.dev/reference/methods/conversations.create/)
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph interrupts and resume](https://docs.langchain.com/oss/python/langgraph/interrupts)

## Local real Gmail with simulated downstream actions

```powershell
.\.venv\Scripts\python.exe -m app.main --gmail-demo --db local-worker.db worker --interval 15 --answer Enterprise
```

This mode reads real Gmail with the configured label, but uses only simulated phone confirmation, projects, channels and membership. It keeps a separate `demo-local-worker.db` and checkpoint file. `--answer Growth` or `--answer "the expensive one"` changes the simulated response; it is never represented as real voice evidence. `--gmail-demo` and `--live` cannot be combined. The default without either flag does not read Gmail. Gmail OAuth tokens and credentials are loaded from `.env`, and the Gmail adapter can refresh a saved access token on a 401. Logs should be kept in the ignored `recordings/` directory.

The local background worker launched for this session records its PID in `recordings/local_worker.pid`, output in `recordings/local_worker.log`, and errors in `recordings/local_worker_error.log`. A rejected email remains in audit/state and does not trigger simulated provisioning. Send a corrected new email with the required label to retry; correction of an already recorded message in place is not implemented.
