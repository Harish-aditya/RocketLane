# Rocketlane agent

`app/rocketlane_agent.py` owns communication with Rocketlane. Its bounded tools create a project, read a project, paginate project tasks, read an individual task and update task status/progress. This is a deterministic integration agent: a language model cannot invent resource IDs, templates, status values or API operations.

## Workflow integration

Gmail intake → plan confirmation → CSM allocation → **Rocketlane agent** → Slack setup → delivery monitoring.

The setup graph includes a `rocketlane_agent` node inside the existing `provision_project` subgraph. The outer name is preserved for checkpoint compatibility. The original operations layer still persists intent before creation, stores the returned project ID, and pauses uncertain writes for human reconciliation. New project execution rows appear as **Rocketlane** in the dashboard. Historical agent labels are retained.

`LiveServices.project` delegates creation to the agent. `DeliveryAPI` inherits its Rocketlane tools, while retaining Slack history and notifications. The delivery graph still validates a complete project-scoped task snapshot before replacing local data, checks author permissions and migration evidence, reads fresh task state before a write, verifies the result afterward, and handles overdue escalation. Keep the setup and delivery workers as separate processes.

Demo and Gmail/Slack demo modes continue to simulate Rocketlane projects. Local task simulation does not call this agent's remote tools. No external call is made merely by importing or inspecting configuration.

## Configuration

Set these locally in `.env` without committing credentials:

```dotenv
ROCKETLANE_API_KEY=your_tenant_api_key
ROCKETLANE_OWNER_EMAIL=real_owner_email
ENTERPRISE_CSM_EMAIL=real_enterprise_representative_email
GROWTH_CSM_EMAIL=real_growth_representative_email
ENTERPRISE_TEMPLATE_SOURCES=verified_sources_array_from_your_tenant
GROWTH_TEMPLATE_SOURCES=verified_sources_array_from_your_tenant
ROCKETLANE_TASK_STATUS_VALUES=verified_status_mapping_from_your_tenant
```

The `*_SOURCES` values must be valid nonempty JSON arrays. Task status values must be a JSON object mapping supported states (`not_started`, `in_progress`, `blocked`, `completed`) to verified tenant values. Do not paste the descriptive placeholders above unchanged. Assigned real directory emails take precedence over fallback owner/CSM environment settings; the mock staff directory is not valid native tenant staffing.

API access requires a tenant API key. Template selection, task statuses and role/date mapping require tenant verification. Reference: [Rocketlane API quick start](https://developer.rocketlane.com/docs/quick-start), [create project](https://developer.rocketlane.com/reference/create-project), [get tasks](https://developer.rocketlane.com/reference/get-all-tasks).

## Check the agent

For a standalone read-only connection check with full project details, set `ROCKETLANE_API_KEY` and `ROCKETLANE_PROJECT_ID` in the repository `.env`, then run:

```powershell
.\.venv\Scripts\python.exe -m app.check_rocketlane
```

The app loads `.env` relative to the repository, validates a positive numeric project ID, and fetches `GET /projects/{projectId}?includeAllFields=true`. Shell environment variables take precedence over `.env`. A successful response prints `connected: true` and the project JSON. Failures return exit code 1 with configuration, authentication, access or network guidance, without printing the API key or provider error body. An alternate file can be supplied with `--env-file PATH`.

From `C:\RocketLane`:

```powershell
# Local configuration presence only; no network or secret output.
.\.venv\Scripts\python.exe -m app.rocketlane_agent config

# Read a real project and its task count after configuring the tenant API key.
# Replace 12345 with a real numeric project ID. No writes are made.
.\.venv\Scripts\python.exe -m app.rocketlane_agent inspect-project 12345
```

Presence checks do not validate credentials. The diagnostic command fails when configuration is missing; it never falls back to a simulated result. It rejects demo project IDs.

Existing free-development commands remain unchanged:

```powershell
.\scripts\run_agent.ps1 -Component onboarding -Answer Growth
.\scripts\run_agent.ps1 -Component delivery
```

These use real Gmail/Slack and simulated Rocketlane. Existing `local_demo` projects are not automatically converted to live projects. Native delivery requires a fully set up real project and a monitor configured in `live` mode. The existing setup `--live` option also enables real voice and Slack side effects; it is not a Rocketlane-only connection test.

## Guardrails and validation

- Project creation requires a confirmed supported plan and template sources. A successful create response without a usable project ID is uncertain and requires reconciliation rather than another POST.
- Task/project reads require numeric native IDs. Task enumeration is bounded and detects missing/repeated pagination cursors.
- Updates require consistent status and integer progress from 0–100 and a tenant status mapping. Completed means 100%; not-started means 0%.
- Existing delivery role, project-scope, migration verification, durable-intent and read-after-write checks remain in effect. Remote concurrent edits can still race a write; no atomic provider compare-and-swap is claimed.
- No live tenant acceptance was performed: configuration is currently absent. Automated tests exercise payloads, uncertainty, invalid configuration, task validation and existing integration flows using fixtures.
