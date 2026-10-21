# Native Rocketlane escalation setup

The application delivery monitor now implements Slack-driven task updates and Slack overdue alerts. See `docs/delivery_monitoring.md`. The steps below concern native Rocketlane rules, which still require tenant configuration and live verification.

Tenant configuration is required. This application does not claim to create native automations through an undocumented API.

1. In your Rocketlane tenant, inspect available native task automations and overdue triggers. Confirm your plan supports scheduled/day-relative conditions and role notifications. UI labels vary; use your tenant's current documentation.
2. For both onboarding templates, configure a task-overdue rule for **one day overdue** with task status not complete. Notify the **Project Manager** role with project, task, due date and task link.
3. Configure a second rule for **four days overdue**, excluding completed tasks. Notify the **Project Owner** role. Confirm these are distinct role mappings where required.
4. Configure one-time thresholds or record that recurring notifications are intentional. Confirm timezone, working-day/calendar-day interpretation, rescheduling behavior and whether overdue dates are evaluated once per day.
5. Create sandbox tasks at one and four days overdue and a completed control task. Verify the correct recipients receive notifications, the control does not, and rules apply to projects instantiated from each template.
6. Save screenshots, rule IDs, recipient evidence, tenant timezone and test date with the submission. Do not claim completion until these checks pass.

In both templates, make migration sign-off depend on customer data verification. Require reconciliation counts, sampled record checks and named customer approval. The local `verify-migration` command records evidence but cannot enforce native task status transitions.

Status at delivery: configuration and tenant verification pending.
