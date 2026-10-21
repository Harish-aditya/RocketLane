# Confirmed assignment clarifications

Source: Karthik's answers supplied by Harish in this chat on 20 October 2026.

| Question | Confirmed answer | Implementation consequence |
|---|---|---|
| AE meaning | Account Executive | Use this expansion in documentation |
| Task definitions | Basic assumptions are acceptable | Define 15 illustrative tasks shared by both plans |
| Enterprise duration | Longer because of complexity | Allocate more time without inventing additional Enterprise-only scope |
| Plan differences | Primarily project and phase duration | Same phases, tasks, approvals and deliverables; different phase schedules |
| Mandatory input | No fields beyond customer name, contact email and Salesforce opportunity link | Optional AE identity/phone; configured phone routing is a separate live integration prerequisite |

The original dedicated Enterprise CSM and pooled Growth CSM rule remains in effect. The answer does not remove this existing assignment distinction.

## Proposed shared template

The task names below and exact day allocations are our assumptions, not additional requirements from Karthik. Both plans use the same 15 tasks and the same verification/approval checkpoints. Calendar-day spans are an implementation assumption to verify against native template scheduling.

| Phase | Enterprise | Growth | Shared tasks |
|---|---|---|---|
| Kickoff | Days 1–3 (3 days) | Days 1–2 (2 days) | Confirm goals and success criteria; introduce stakeholders and CSM; agree delivery plan and responsibilities |
| Data Migration | Days 4–15 (12 days) | Days 3–7 (5 days) | Inventory source data/access; map fields and prepare import; run migration and resolve errors; verify counts and sample data with customer |
| Configuration | Days 16–25 (10 days) | Days 8–11 (4 days) | Configure workspace settings; roles/permissions; integrations; customer acceptance checks |
| Go-Live | Days 26–30 (5 days) | Days 12–14 (3 days) | Train administrators; approve readiness including migration verification; launch production workflow; handover and success review |

The executable source is `app/plan_templates.json`. Workflow confirmation stores the selected schedule in the run. Configure corresponding Rocketlane native templates with these tasks and durations; the local JSON does not automatically create or update native templates.

## Minimal email contract

```text
Customer Name: Acme Labs
Contact Email: champion@acme.example
Salesforce Opportunity Link: https://crm.example/opportunities/acme-001
```

`Opportunity URL` and `Salesforce Opportunity URL` are accepted aliases for the opportunity field. A valid HTTP(S) link is required; a strict Salesforce hostname restriction is not assumed because tenant domains can vary.

AE Name, AE Email and AE Phone are optional metadata. In a single-AE assessment sandbox, set `AE_DEFAULT_PHONE` and optionally `AE_DEFAULT_NAME` independently of the email. With multiple AEs, implement trusted sender-to-phone directory routing; a shared default must not silently route unrelated AEs. An absent live phone route escalates before any provider call or project creation; it does not invalidate the three-field email. No plan value in the email bypasses explicit voice confirmation.
