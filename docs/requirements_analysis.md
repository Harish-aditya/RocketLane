# NovaCRM Onboarding Requirements and Workflow Analysis

Prepared by Harish • Forward Deployed Engineer Assessment • 21 October 2026

## 1 Executive summary

NovaCRM needs a reliable handoff from a closed deal to a correctly configured onboarding project and customer communication channel. The proposed solution uses custom LangGraph orchestration for two setup agents, Rocketlane for project delivery, and Slack for communication. An explicit voice confirmation from the Account Executive determines the plan before project creation.

The required outcomes are correct plan selection, clear ownership, visible task progress, verified migration, and timely escalation. Setup completion means the project and channel are ready; it does not mean the customer's onboarding work is complete.

The original assignment requires overdue automation **inside Rocketlane**, rather than a separate escalation agent. The later Slack-monitoring extension supplements that requirement. Application-generated Slack alerts are not evidence that native Rocketlane automation has been configured.

## 2 Current workflow and problems

NovaCRM serves approximately 200 customers. The Account Executive emails the CS inbox after a deal closes. CS manually selects an Asana onboarding template, creates approximately 15 tasks across Kickoff, Data Migration, Configuration and Go-Live, establishes a customer Slack channel, and schedules kickoff. Staff maintain phase checklists, escalate long-blocked work, and prepare the final support handover.

| Current step | Observed problem | Required improvement |
|---|---|---|
| AE email handoff | Missing details require manual follow-up | Validate inputs and identify the exact missing information |
| Template selection | Enterprise and Growth templates are mixed up | Obtain explicit voice confirmation and use verified plan mappings |
| Project setup | Repeated manual entry and inconsistent assignment | Create one traceable Rocketlane project with phases, tasks and dates |
| Communication | Channel creation and introductions depend on CS availability | Personalize the channel, topic and welcome |
| Migration | A task can be marked done without verified customer data | Require customer verification and evidence before sign-off |
| Escalation | Blocked work is overlooked | Configure the required native overdue rules and verify recipients |
| Handover | Support may receive incomplete context | Retain accountable owners and an accepted handover checkpoint |

The existing blocked-for-more-than-three-days practice is different from the assignment's overdue thresholds. This analysis follows **one day overdue to the Project Manager and four days overdue to the Project Owner**. Inactivity before a due date is not an additional trigger unless separately agreed.

## 3 Confirmed requirements and clarifications

Karthik clarified that AE means Account Executive; basic task assumptions are permitted; Enterprise takes longer because of complexity; and no additional mandatory deal fields are required.

| ID | Requirement | Acceptance evidence |
|---|---|---|
| R01 | Monitor an approved Gmail source and initiate onboarding | A new qualifying email is detected by the running worker |
| R02 | Require customer name, contact email and opportunity link | Valid input accepted; missing/malformed input rejected without downstream writes |
| R03 | Confirm Enterprise or Growth through a real Voice AI call | Connected call, authenticated provider reference and clear AE response |
| R04 | Do not guess an unclear plan | Retry or human review with no project/channel creation |
| R05 | Create the correct Rocketlane project via API | Actual project ID, template, phases, tasks, dates and ownership |
| R06 | Enterprise uses 30 days and dedicated CSM support | Native project schedule and named CSM |
| R07 | Growth uses 14 days and pooled CSM support | Native project schedule and assigned pool representative |
| R08 | Personalize customer Slack communication | Channel name, topic, welcome and customer-access evidence or disclosed permitted simulation |
| R09 | Configure overdue escalation within Rocketlane | Native rule configuration and actual PM/Owner notification evidence |
| R10 | Protect migration verification | Customer evidence and approval/dependency checks before readiness |
| R11 | Log timestamps, inputs, outputs and decisions | Linked run, call, project, channel, audit and checkpoint records |
| R12 | Handle duplicate events and partial failure | One intended resource; uncertain writes require evidence before retry |

AE name and phone may be supplied as optional metadata. The correct calling destination must still be resolved through trusted routing configuration. A phone number is an operational prerequisite, not a fourth mandatory customer-email field. The plan must not be supplied as a shortcut in the email.

## 4 Plan and phase requirements

Both plans have the same proposed scope and verification standards. The exact tasks and phase allocations are assumptions permitted by Karthik; only the total 30-day/14-day durations and support models are supplied requirements.

| Phase | Enterprise | Growth | Proposed tasks |
|---|---|---|---|
| Kickoff | Days 1–3 | Days 1–2 | Confirm goals and success criteria; introduce stakeholders and CSM; agree the delivery plan and responsibilities |
| Data Migration | Days 4–15 | Days 3–7 | Inventory data/access; map fields and prepare import; run migration and resolve errors; verify record counts and sampled data with the customer |
| Configuration | Days 16–25 | Days 8–11 | Configure workspace settings; roles/permissions; integrations; customer acceptance checks |
| Go-Live | Days 26–30 | Days 12–14 | Train administrators; approve readiness including migration verification; launch production workflow; complete handover and success review |

A phase ends when its deliverables and verification criteria are accepted, not merely because its scheduled end date arrives. Failed data checks return the task to correction. Customer launch must not bypass unresolved critical issues.

## 5 Proposed agentic workflow

### 5.1 Agent 1 intake and routing

1. Read the approved email and identify the request using its message and opportunity references.
2. Validate the three required fields. Identify missing details rather than inventing them.
3. Contact the correct AE using the configured Voice AI integration.
4. Accept only a clear Enterprise or Growth response from the completed call.
5. Check CSM availability, reserve capacity and select the responsible project manager and owner.
6. Create the project through the Rocketlane API using the confirmed template and timeline.
7. Retain the result and hand the verified references to Agent 2. An uncertain remote write pauses for reconciliation.

### 5.2 Agent 2 communication

1. Receive the confirmed customer, plan, assigned team and project reference.
2. Create the personalized private onboarding channel.
3. Add the assigned CSM, project manager and owner. Resolve the Contact Email and add an existing Slack member, or send an eligible Slack Connect email invitation. If permissions/plan prevent sending, pause for an administrator invitation and evidence before continuing. Track invitation-sent separately from joined membership.
4. Set the topic, post the welcome and verify the completed communication steps.
5. Register delivery monitoring for a real Slack channel. Preserve the project if communication setup fails.

### 5.3 Delivery monitoring extension

The delivery worker reads explicit top-level task updates from assigned Slack users. It matches an exact task ID, checks status/progress consistency and updates Rocketlane only in live mode. Ambiguous messages, unauthorized senders, regressions and missing verification evidence enter human review. Local-demo mode updates SQLite only and labels its notifications accordingly.

The dashboard displays CSM workload, project assignments, task ownership and due dates, agent attempts, checkpoints, monitoring errors, reviews and escalation receipts. Rocketlane remains the native delivery system of record in live mode; SQLite is the orchestration ledger and local projection.

### 5.4 Native overdue automation

Configure Rocketlane rules for incomplete tasks at +1 day to the assigned PM and +4 days to the assigned Owner. Verify timezone, schedule, completed-task exclusion and repeat behavior. Record actual native notification evidence. The optional application delivery monitor can also post Slack alerts; agree whether it supplements or duplicates native notifications before enabling both.

## 6 Guardrails and exceptions

| Scenario | Required response | Current implementation boundary |
|---|---|---|
| Missing or malformed field | Ask for specific clarification; do not proceed | Rejected state and field details are implemented; delivered clarification email remains outstanding |
| AE does not answer or gives an unclear response | Bounded retry or human escalation | Retry/escalation states implemented; actual voice/provider outcomes require live evidence |
| Active call remains unresolved | Avoid repeated dialing while outcome is unknown | Provider polling and a ten-minute unresolved-call guard |
| Duplicate email/opportunity | Reuse the existing run | Local uniqueness and repeat-action guards; provider-side existing-project discovery remains a live gap |
| Timeout after a project/channel write | Inspect provider evidence before retry | Durable action intent and human reconciliation |
| All CSMs occupied | Queue the confirmed request | No project/channel creation before capacity is available |
| Slack setup fails after project creation | Preserve the project and resume safely | Per-step state and membership progress retained |
| Slack task message is ambiguous or unauthorized | Require human review | Explicit command parser and per-channel role checks |
| Migration/readiness is declared complete without evidence | Hold sign-off | Local verification guard; native enforcement must be verified in Rocketlane |
| Remote task changes or update result is uncertain | Re-read and reconcile | Fresh read, verified write, pending receipt and review tools |
| Monitoring source unavailable | Report the error and avoid stale escalation | Dashboard error and failed-cycle escalation suppression |

## 7 Staffing and capacity assumptions

The user-requested staffing extension contains ten CSMs, two project managers and one project owner. The CSM also performs migration and configuration. One CSM can manage two Enterprise or four Growth onboardings concurrently.

The mixed-plan interpretation is an implementation assumption: Enterprise consumes two workload units, Growth one, and each CSM has four units. One Enterprise plus two Growth is allowed. The least-loaded eligible CSM is chosen; ties resolve by member ID. Project managers are balanced by reserved load. No PM/Owner ceiling has been specified.

Reservations commit atomically in SQLite, survive restart and remain active after setup completion. Explicit onboarding completion or cancellation with evidence releases capacity. Queue retries are not guaranteed strict FIFO. External onboarding workload must be imported before relying on live occupancy.

The initial 13 profiles are mock records, not Slack accounts. Three existing Slack accounts currently represent the demo roles: Elsa as CSM, Star Boy as PM and Harish Aditya as Owner. A production directory requires actual staff identities, emails and member IDs.

## 8 Integrations and ownership of data

| System | Responsibility | Prerequisites |
|---|---|---|
| Gmail | Receive qualifying deal notifications | OAuth, trusted source/label routing and monitored mailbox |
| Voice AI | Verbally confirm the AE's plan | Authorized outbound-capable number, correct AE route and verified call outcome |
| Rocketlane | Native projects, templates, tasks, phases, dates, owners and overdue rules | API key, verified sources, tenant status mappings and automation access |
| Slack | Customer/team communication, explicit task updates and notifications | Bot membership and appropriate channel/history/write permissions |
| LangGraph and SQLite | Orchestration, reservations, reviews, audit, checkpoints and delivery receipts | Durable files, one worker per operating role and defined access/retention |

The inbox label is a sandbox trust assumption; it does not itself cryptographically authenticate an AE. Production requires approved sender routing and appropriate operator access. Secrets and unrelated personal data must not appear in recordings or logs.

## 9 Acceptance and testing

Unit tests cover input validation, explicit plan recognition, phase totals, capacity and task-update rules. Integration tests cover provider contracts, saved references, pagination, Slack membership and status synchronization. System tests cover complete plan journeys, failures and recovery. Smoke checks validate worker startup and dependency access. Load/stress scenarios verify queue visibility, capacity saturation, concurrent reservations, provider outages and controlled recovery.

The latest completed repository test run recorded **89 passing tests** before the recording rehearsal was prepared. Controlled tests and mock journeys do not prove live voice, native project instantiation, customer sharing or native automation.

Positive acceptance requires one real email-triggered journey with an actual successful voice confirmation, API-created native project, personalized communication and demonstrated Rocketlane automation. Negative acceptance requires visible invalid-input or unresolved-call handling, bounded retries, traceable decisions and proof that unauthorized downstream resources were not created.

## 10 Current evidence and remaining dependencies

As of 21 October 2026, a real Gmail-to-Slack test created channel `C0CAYM8EAL9`, added the three existing users, posted a welcome and saved 60 checkpoints. Its voice and Rocketlane project were simulated. The test used a subject filter because the monitored Gmail connection is read-only; it did not prove automatic label application.

The current readiness check found no Rocketlane API key, Enterprise/Growth template sources, task-status mapping or verified task URL template. The configured voice credentials have not produced acceptance evidence of a permitted outbound call. The latest Slack history check reported missing_scope; private-channel delivery monitoring needs groups:history and app reinstallation. Native Rocketlane automation configuration and actual delivery evidence remain outstanding.

Customer Slack guest/Connect access, native migration controls, provider-side existing-project discovery, delivered clarification messages, voice-failure human notification and final support handoff remain acceptance items or extensions. Optional Slack simulation must be disclosed; the assignment does not permit replacing its real voice requirement with a text simulation.

Kickoff scheduling, executing migration/configuration, automated final handoff and production throughput commitments are not implied by setup completion. Calendar days, holiday handling, retention and reviewer response expectations require business confirmation.

