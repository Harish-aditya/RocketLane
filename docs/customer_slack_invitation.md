# Customer invitation after channel creation

The communication workflow now follows: create channel → add assigned team → invite customer by contact email → set topic → welcome. The contact email comes from the validated onboarding request, not from a generated message or inferred identity.

## Supported routes

1. **Existing workspace member:** resolve the email using `users.lookupByEmail` (`users:read.email`), then add the returned member ID with `conversations.invite`. Already-in-channel is safe to reconcile. Successful addition is recorded as `member_added`.
2. **External Slack Connect invitation:** set `SLACK_CUSTOMER_INVITE_MODE=connect` only for an eligible, approved Slack Connect setup. The bot needs `conversations.connect:write`. The workflow calls `conversations.inviteShared` with one email and `external_limited=true`, retaining the invitation ID. Success means `invitation_sent`, not that the customer has accepted or joined.
3. **Free/manual fallback:** the default `SLACK_CUSTOMER_INVITE_MODE=manual` adds existing members when possible. When email lookup is unavailable or the customer is not a joined member, the workflow pauses as `customer_invite_manual`. An administrator invites the customer through Slack, accepts any workspace approval requirements, and records the provider evidence. No unsupported free-workspace invitation API is used.

The app manifest adds email lookup permission only. External Connect permission is opt-in and must be configured/reinstalled separately; the code never expands app permissions automatically. Slack Connect may be limited by plan, workspace policy and whether the recipient is known to the app. An absent scope or unsupported plan cannot be reported as successful delivery.

## Manual invitation receipt and resume

After correcting a definitive permission/manual handoff, use `app.main ... retry-customer-invite RUN_ID` in the original operating mode to retry only customer access and continue the existing run. It reuses the channel/team; uncertain writes still require reconciliation. A purely simulated worker cannot complete a run marked as real-Slack demo.

Open the correct customer channel in Slack, invite the **exact Contact Email**, and confirm that Slack actually sent an invitation or that the joined member is present. Then use the same mode and database as the waiting workflow:

```powershell
.\.venv\Scripts\python.exe -m app.main --gmail-slack-demo --db local-worker.db record-customer-invite RUN_ID --email customer@example.com --status invitation_sent --resource-id VERIFIED_INVITATION_REFERENCE --evidence "Administrator verified the invitation was sent to the customer for this channel"
.\.venv\Scripts\python.exe -m app.main --gmail-slack-demo --db local-worker.db run RUN_ID
```

Use `--live --db YOUR_LIVE_DATABASE` for a genuinely live workflow. `--db` in demo modes adds the usual `demo-` prefix; keep the exact established database/mode combination. For a customer already joined, choose `--status member_added` and pass their actual Slack member ID as `--resource-id`.

The receipt must match the waiting run and its customer email. It is an explicit human assertion backed by evidence, not an automated membership verification. It cannot resolve an unrelated customer or bypass a pending uncertain API write.

## Uncertain writes and lifecycle

The customer-invite action persists intent before making a request. A timeout or missing receipt enters `reconcile`; it never blindly resends the invite. After inspecting Slack evidence, reconcile to `customer_invited` with the matching resource reference, then resume the run. Customer acceptance is a separate human event; the current workflow does not automatically poll Slack Connect acceptance.

Invitations and status are stored in the run's `customer_invitation` object and the action audit; the dashboard shows the outcome. `simulated` is reserved for fully simulated integrations. The real-Gmail/Slack demo adapter executes the real customer step and can therefore pause for missing permission/manual action.

New onboarding requests require this step. Existing completed runs are not retroactively invited, and old runs without the new requirement marker preserve their earlier route. No customer invitations were sent simply by installing this code change.

References: https://docs.slack.dev/reference/methods/users.lookupByEmail/, https://docs.slack.dev/reference/methods/conversations.invite/ and https://docs.slack.dev/reference/methods/conversations.inviteShared/.
