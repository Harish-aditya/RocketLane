# Local onboarding operations dashboard

Start against the same business database as the local Gmail worker:

```powershell
.\.venv\Scripts\python.exe -m app.dashboard --db demo-local-worker.db --port 8080
```

Open `http://127.0.0.1:8080`. The server listens only on loopback and exposes read-only routes. It does not place calls, modify Gmail, create projects or send Slack messages. The UI refreshes every five seconds and reports the worker heartbeat separately from the browser's own successful refresh.

## Dashboard views

- Unique onboarding requests, measured agent executions, setup-ready requests, and requests needing attention.
- Searchable customer/run table with plan, current state, task counts, simulation marker and last update.
- Per-run delivery task table with phase, status and owner.
- Committed LangGraph checkpoint timeline, agent attempts, and expandable action audit.
- Recent activity and intake/communication/provisioning execution breakdown.

"Agent executions" means recorded intake or communication action attempts, not unique customers or phone calls. Project provisioning is shown separately. Historical intake audit can be backfilled; missing historical node runs/checkpoints are not fabricated. Detailed endpoints show the latest 200 records per type; summary totals cover the entire selected database.

## Database tables

| Table | Responsibility |
|---|---|
| `runs` | Original authoritative workflow business state and resource references |
| `audit` | Existing timestamped input/output/rationale events |
| `onboarding_status` | Queryable customer, plan, state, environment, resource IDs and timestamps |
| `agent_runs` | Per-action execution start, outcome, finish time and rationale |
| `onboarding_tasks` | One row per planned task with phase, status, expected owner role, actual owner and data source |
| `checkpoint_events` | Every committed LangGraph checkpoint ID, namespace, step and allowlisted state summary |
| `worker_status` | Last worker heartbeat, mode and operational errors |

`LoggedSqliteSaver` mirrors actual committed graph checkpoints; business snapshots alone are not labeled LangGraph checkpoints. The graph/checkpoint database and business ledger are separate files and do not form a distributed transaction. Keep both files when backing up. Unexpected action failures remain visible through audit/worker errors and guarded recovery.

## Task status meaning

Project creation adds the selected template's 15 task rows. These start as `not_started`, with no invented actual assignee. Expected roles are planning labels, not verified provider ownership. `simulated_template` rows come from demo runs; `template_not_synced` rows are native-template planning snapshots whose provider status is unknown. The dashboard does not synchronize Rocketlane task updates or mark delivery complete when setup finishes. Actual provider task progress/assignee synchronization remains a separate integration requirement.

## Running instances

The local dashboard PID is in `recordings/dashboard.pid`; server logs are in `recordings/dashboard.log` and `recordings/dashboard_error.log`. The restarted Gmail demo worker PID remains in `recordings/local_worker.pid`; its logs are in `recordings/local_worker_dashboard.log` and `recordings/local_worker_dashboard_error.log`. These files are ignored by Git. Stop only the processes associated with these recorded instances. The dashboard is intended for trusted local use, not public deployment.
