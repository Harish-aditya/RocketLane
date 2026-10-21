# Team directory and capacity allocation

The active mock roster in demo-local-worker.db contains 10 CSMs, two project managers and one project owner. Each CSM also performs migration and configuration; there are no separate specialists. Four previous mock CSM/specialist identities are inactive and retained for history. These are local records, not Slack accounts.

## Capacity policy

A CSM has four workload units. Enterprise onboarding uses two units and Growth uses one. Each CSM can carry two Enterprise, four Growth, or one Enterprise plus two Growth onboardings. This shared mixed-plan limit is an assumption based on the requested 2:4 ratio.

After explicit plan confirmation, the agent selects the least-loaded eligible CSM and least-loaded project manager; ties resolve by member ID. The single owner is assigned to every request. Reservations commit in one SQLite write transaction, preventing concurrent overbooking. Replays reuse existing assignments. Task ownership defaults to the selected CSM, including migration/configuration. Customer verification still needs the customer champion.

Without capacity, the run waits in awaiting_capacity and creates no project/channel. The worker retries on later cycles; this is not a strict FIFO queue. The dashboard shows workload and available slots. Completed setup does not release capacity.

## Persistence and release

team_members stores identities and roles. onboarding_assignments records run, CSM, PM, owner, plan, reserved units, status, timestamps and release reason. Decisions are audited.

```powershell
.\.venv\Scripts\python.exe -m app.team_directory seed
.\.venv\Scripts\python.exe -m app.team_directory workloads
.\.venv\Scripts\python.exe -m app.team_directory release RUN_ID --status completed --reason "Customer handover accepted"
```

Use --status cancelled with a reason to cancel and release capacity. Pending provider writes must be reconciled first. Failed runs retain capacity until resolved or explicitly cancelled. Native task completion does not yet automatically release capacity.

## Slack and escalation

New channels use the assigned PM, owner and CSM. Demo invitations use synthetic IDs. Live allocation requires non-mock directory records with actual Slack IDs. Project CSM and owner emails come from the selected records. Existing runs/channels are not reassigned.

Project managers are escalation candidates at +1 day and owner at +4 days. Directory escalation preview lists candidates; future notification delivery should use the run's assigned pm_id/owner_id. Automated overdue notifications remain separate work. External onboarding work must be imported before relying on live occupancy.

Slack provisioning requires paid SCIM access: https://docs.slack.dev/admins/scim-api/.
