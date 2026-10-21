"""Business-facing solution documentation with numbered workflow references."""
from scripts.document_layout import *
import textwrap

doc.core_properties.subject = 'Customer onboarding solution approach using custom LangGraph orchestration'
doc.styles['Normal'].paragraph_format.line_spacing = 1.08

titles = [
    '1. Executive Summary', '2. Current-State Workflow Analysis', '3. Business Requirements',
    '4. Plan-Tier Requirements', '5. Proposed Agentic Workflow', '6. Guardrails and Exception Handling',
    '7. Integration Requirements', '8. Acceptance Criteria and Testing Strategy',
    '9. Assumptions, Open Questions and Dependencies', '10. Scope, Deliverables and Success Criteria',
    'Appendix A. Workflow Diagram', 'Appendix B. Requirements Traceability Matrix']


def heading(title):
    doc.add_heading(title, 2)


def continuation(title):
    doc.add_page_break()
    heading(title)


def section(index):
    doc.add_page_break()
    h = doc.add_heading(titles[index], 1)
    start = OxmlElement('w:bookmarkStart')
    start.set(qn('w:id'), str(index))
    start.set(qn('w:name'), f'section_{index}')
    end = OxmlElement('w:bookmarkEnd'); end.set(qn('w:id'), str(index))
    h._p.insert(0, start); h._p.append(end)


def diagram(key, title, steps, branches=(), note=None):
    """Code-drawn process figure with explicit numbered business steps."""
    width = 1680
    step_h, gap, margin = 110, 48, 24
    height = margin * 2 + len(steps) * (step_h + gap) - gap + (95 if note else 0)
    im = Image.new('RGB', (width, height), 'white')
    draw = ImageDraw.Draw(im)
    font = ImageFont.truetype('C:/Windows/Fonts/calibri.ttf', 32)
    small = ImageFont.truetype('C:/Windows/Fonts/calibri.ttf', 30)
    main_x, main_w = 22, 1010
    branch_x, branch_w = 1110, 548

    def rect(x, y, w, h, label, fill, chosen):
        draw.rounded_rectangle((x, y, x+w, y+h), radius=12, outline='#6B7280', width=2, fill=fill)
        limit = 110 if w > 1500 else (64 if w > 800 else 31)
        lines = []
        for part in label.split('\n'):
            lines.extend(textwrap.wrap(part, limit) or [''])
        line_height = 35
        top = y + (h-len(lines)*line_height)/2
        for line in lines:
            draw.text((x+w/2, top), line, fill='black', font=chosen, anchor='mt')
            top += line_height

    def arrow(x1, y1, x2, y2):
        draw.line((x1, y1, x2, y2), fill='#374151', width=4)
        if y2 > y1:
            draw.polygon([(x2,y2),(x2-9,y2-16),(x2+9,y2-16)],fill='#374151')
        else:
            draw.polygon([(x2,y2),(x2-16,y2-9),(x2-16,y2+9)],fill='#374151')

    for index, (number, label) in enumerate(steps):
        y = margin + index*(step_h+gap)
        rect(main_x,y,main_w,step_h,number+'  '+label,'#EDF2F7',font)
        if index < len(steps)-1:
            x=main_x+main_w/2
            arrow(x,y+step_h,x,y+step_h+gap)
    for index, label in branches:
        y=margin+index*(step_h+gap)
        rect(branch_x,y,branch_w,step_h,label,'#FFF5E5',small)
        arrow(main_x+main_w,y+step_h/2,branch_x,y+step_h/2)
    if note:
        rect(22,height-78,width-44,64,note,'#E7EDF5',small)
    image_path=QA/(key+'.png')
    im.save(image_path)
    para=p('')
    para.paragraph_format.keep_with_next=True
    picture=para.add_run().add_picture(str(image_path),width=Inches(6.65))
    picture._inline.docPr.set('descr', title+'. '+'; '.join(number+' '+label for number,label in steps))
    cap=p(title)
    cap.paragraph_format.space_after=Pt(9)
    cap.runs[0].italic=True
    cap.runs[0].font.size=Pt(10)


p('NovaCRM Customer Onboarding Automation','Title')
p('Solution Approach and Project Documentation','Subtitle')
p('Prepared by Harish\nForward Deployed Engineer Assessment\n21 October 2026  |  Version 1.3')
p('A business guide to confirming a new customer’s plan, preparing the right Rocketlane project and establishing onboarding communication. The proposed solution uses custom LangGraph orchestration, with people involved whenever information or an outcome cannot be trusted.')
doc.add_heading('Table of Contents',1)
for index,title in enumerate(titles):
    para=p(''); para.paragraph_format.space_after=Pt(7)
    link=OxmlElement('w:hyperlink'); link.set(qn('w:anchor'),f'section_{index}')
    rr=OxmlElement('w:r'); tt=OxmlElement('w:t'); tt.text=title
    rr.append(tt); link.append(rr); para._p.append(link)

section(0)
p('NovaCRM needs a consistent way to begin customer onboarding without selecting the wrong plan, repeating setup work or overlooking missing information. The solution gives two agents clear responsibilities: Agent 1 checks the deal, confirms the plan with the Account Executive and prepares the Rocketlane project; Agent 2 establishes personalized customer communication.')
sub('1.1 Business outcome','Every eligible deal should reach a clear outcome: onboarding setup is ready, more information is needed, or a person must resolve an exception. Enterprise customers receive a 30-day project with dedicated CSM support. Growth customers receive a 14-day project with pooled CSM support. Both follow the same four phases and 15 proposed tasks, with more time allocated to Enterprise complexity.')
sub('1.2 Workflow and guardrail summary','Agent 1 must not guess missing customer information or the plan. A real call to the correct AE must produce a clear Enterprise or Growth confirmation before project creation. Agent 2 must not announce success before the project and communication steps are confirmed. Both agents retain completed work during a failure and request human help when a result is uncertain.')
sub('1.3 Roles and ongoing control','The AE confirms the customer’s plan. The CSM coordinates onboarding delivery. Rocketlane stores tasks, progress, due dates and ownership. Native rules notify the Project Manager when a task is one day overdue and the Project Owner when it is four days overdue. Customer data verification remains a required delivery checkpoint before readiness approval.')
sub('1.4 Reading this document','Section 4 explains the phase requirements. Section 5 begins each agent summary with a diagram, then shows the combined workflow and completion states. Diagram steps use section-based numbering such as 5.1.1, and the text refers to those same identifiers. Section 6 expands the safeguards by agent, and Section 8 defines scenario-based acceptance across six test types.')
sub('1.5 Delivery boundary','The repository has custom LangGraph orchestration, capacity-based CSM allocation, a project-load dashboard, recovery controls and optional model-backed agents. Local tests cover these controls. Clarification replies, delivered human alerts, customer Slack access and some provider checks remain acceptance work. Live service behavior, native automations and walkthrough videos must be verified separately. Proposed behavior below is not a claim that every integration has already passed.')

section(1)
p('NovaCRM serves approximately 200 customers. Its Customer Success team currently relies on email, Asana and Slack to move a customer from a closed deal to ongoing support.')
table(['Stage','Current activity','Business risk'],[
('Deal handoff','AE emails customer and opportunity information to the CS inbox.','Incomplete handoff and repeated clarification.'),
('Project setup','CS manually selects an Asana onboarding template.','Enterprise and Growth templates can be mixed up.'),
('Kickoff','CS creates a customer Slack channel and schedules the kickoff.','Manual coordination delays the start.'),
('Delivery','Team tracks about 15 tasks across four phase checklists.','Inconsistent updates and missed dependencies.'),
('Verification','Migration tasks can be marked complete without checking customer data.','Incorrect data reaches later stages.'),
('Escalation','Tasks blocked for more than three days should be escalated.','Escalations are often missed.'),
('Handoff','CS writes a summary and moves the customer to support.','Support may receive incomplete context.')],[1.0,3.0,2.7])
sub('2.1 Improvement required','The new approach replaces manual Asana project setup with the right Rocketlane template, introduces real voice confirmation of the plan and gives each incomplete or failed request an explicit next action. It preserves the four onboarding phases and the people responsible for delivery.')
sub('2.2 Escalation distinction','The current blocked-for-three-days practice differs from the assignment’s explicit overdue rules. This project implements the required one-day Project Manager and four-day Project Owner notifications inside Rocketlane. An additional blocked-task rule requires a separate business decision.')

section(2)
p('The business requirements describe what the customer and CS team should experience, regardless of the underlying software components.')
table(['ID','Requirement','Expected outcome'],[
('BR01','Recognize approved AE deal emails.','New qualifying emails start one traceable onboarding request.'),
('BR02','Validate customer name, contact email and opportunity link.','Missing or invalid details cause a specific clarification request.'),
('BR03','Confirm the plan through a real AE phone call.','Only clear Enterprise or Growth confirmation unlocks project setup.'),
('BR04','Prepare the right project and ownership.','Rocketlane contains the correct phases, tasks, dates and CSM assignment.'),
('BR05','Prepare customer communication.','Channel name, topic and welcome match the customer and confirmed plan.'),
('BR06','Escalate overdue delivery tasks.','Native Rocketlane rules notify the correct people at days one and four.'),
('BR07','Recover without duplicating completed work.','Repeated requests and partial failures retain existing resources.'),
('BR08','Explain what happened and why.','A timestamped history links decisions, actions and their results.')],[.55,2.75,3.4])
sub('3.1 Required information','Only customer name, contact email and Salesforce opportunity link are mandatory deal fields. The correct AE must still be identified from an approved source, and a phone number must be available through routing configuration. AE identity and phone are not additional mandatory customer fields. The plan is deliberately obtained from the call.')
sub('3.2 Responsibility and storage','Rocketlane is the source of task progress and ownership. The application retains the request status, call evidence, confirmed plan, created resource references and action history. An authorized operator owns exceptions that cannot be safely resolved automatically.')

section(3)
p('The plans share scope, phases and completion checkpoints. Enterprise receives more delivery time because its onboarding is more complex. Additional Enterprise-only approvals or tasks are not assumed.')
table(['Requirement','Enterprise','Growth'],[
('Project duration','30 days','14 days'),('Support model','Dedicated CSM','Pooled CSM'),
('Kickoff','Days 1–3  |  3 days','Days 1–2  |  2 days'),
('Data Migration','Days 4–15  |  12 days','Days 3–7  |  5 days'),
('Configuration','Days 16–25  |  10 days','Days 8–11  |  4 days'),
('Go-Live','Days 26–30  |  5 days','Days 12–14  |  3 days'),
('Scope and approvals','Same 15 proposed tasks and gates','Same 15 proposed tasks and gates')],[1.7,2.5,2.5])
sub('4.1 Phase planning principles','The total durations and CSM models come from the assignment. The exact phase allocations and task definitions are proposed assumptions permitted by Karthik. Calendar-day versus working-day interpretation, holidays, task dependencies and the native template’s date calculation must be checked before acceptance.')
sub('4.2 Phase entry and exit rules','A phase begins when its inputs and responsible people are available. It ends when its deliverables are accepted and any required evidence is recorded. A due date alone does not establish completion. A phase that cannot meet its exit conditions remains visible as incomplete or blocked, with a named next action.')
sub('4.3 Ownership and plan verification','The CSM coordinates phase delivery. Individual task assignees carry out the work, the customer champion provides customer decisions and the Project Manager monitors delivery risk. The Project Owner has overall accountability. Agent 1 verifies the selected project template and role mappings; the agents do not perform the customer’s migration or configuration work themselves.')
p('Staffing extension: a shared roster of ten CSMs supports both plans, with two Project Managers and one Project Owner. The assigned CSM also performs migration and configuration. Enterprise dedication means a named CSM for the onboarding, not exclusive use of that person. Growth receives a named representative selected from the pool. The mixed-plan capacity interpretation is documented as an assumption in Section 9.4.')

continuation('4.4 Kickoff phase requirements')
p('Purpose: agree what successful onboarding means and who will contribute. Enterprise has three proposed days for coordination; Growth has two. The expected outputs and approval gate are the same.')
table(['Task','Expected result'],[
('4.4.1 Confirm goals and success criteria','Named business outcomes, measures of success and known constraints.'),
('4.4.2 Introduce stakeholders and CSM','AE, CSM, customer champion and delivery owners have agreed contact paths.'),
('4.4.3 Agree the delivery plan and responsibilities','Phase dates, task ownership, customer inputs and decision points are understood.')],[2.6,4.1])
p('Entry: the customer and confirmed plan are known and the onboarding project is available. Exit: the CSM and customer champion agree the goals, ownership and working plan. If the champion is unavailable or the scope is disputed, the CSM resolves that gap before dependent work proceeds. Scheduling and conducting the kickoff remain delivery activities unless separately automated.')
heading('4.5 Data Migration phase requirements')
p('Purpose: move the required customer data and prove that it is usable. Enterprise has 12 proposed days; Growth has five. More time allows complexity and correction without weakening the verification standard for either tier.')
table(['Task','Expected result'],[
('4.5.1 Inventory source data and access','Agreed data sources, access permissions, record counts and migration boundaries.'),
('4.5.2 Map fields and prepare import','Reviewed field mappings, required transformations and an import approach.'),
('4.5.3 Run migration and resolve errors','Import results, rejected records and correction actions are recorded.'),
('4.5.4 Verify counts and sampled data with the customer','Reconciled counts, sample checks and customer approval support sign-off.')],[2.6,4.1])
p('Entry: scope and required access are agreed. Exit: discrepancies are resolved or explicitly accepted, and the customer champion approves verification evidence. An upload finishing or a task being marked done is insufficient. Failed checks return the migration to correction; readiness approval must not bypass this gate.')

continuation('4.6 Configuration phase requirements')
p('Purpose: configure the customer’s workspace so it supports the agreed use cases. Enterprise has ten proposed days; Growth has four. The wider Enterprise window accommodates complexity, while the acceptance standard remains consistent.')
table(['Task','Expected result'],[
('4.6.1 Configure workspace settings','Required business settings and agreed workflows are in place.'),
('4.6.2 Configure roles and permissions','Users can perform authorized work without unnecessary access.'),
('4.6.3 Configure integrations','Agreed integrations connect successfully and failures are visible.'),
('4.6.4 Run customer acceptance checks','Representative customer use cases pass with issues recorded and resolved.')],[2.6,4.1])
p('Entry: configuration inputs and required data are ready for the work being performed. Exit: acceptance checks pass and outstanding issues have an agreed resolution. Access failures, incorrect permissions or broken integrations stop affected tasks; the team must not report the workspace as ready while critical checks fail.')
heading('4.7 Go Live phase requirements')
p('Purpose: enable customer use and arrange a clear transition to ongoing support. Enterprise has five proposed days; Growth has three. Both tiers need the same readiness evidence and ownership of remaining issues.')
table(['Task','Expected result'],[
('4.7.1 Train customer administrators','Administrators understand routine operation and support routes.'),
('4.7.2 Approve readiness','Migration verification, configuration acceptance and critical issue status are reviewed.'),
('4.7.3 Launch the production workflow','The agreed launch proceeds with responsible people available.'),
('4.7.4 Complete handover and success review','Support receives the agreed context, open issues, owners and next actions.')],[2.6,4.1])
p('Entry: data and configuration checks support launch readiness. Exit: the customer and CSM accept the handover and ongoing support ownership is clear. An unresolved critical issue pauses launch. These are project delivery requirements; the setup automation does not itself train users, launch customer operations or automatically transfer the support case.')

section(4)
heading('5.1 Agent 1 Intake and Routing')
diagram('agent1_workflow','Figure 5.1 Agent 1 workflow',[
('5.1.1','Receive the AE email and identify the request'),
('5.1.2','Check customer details and the correct AE'),
('5.1.3','Call the AE to confirm Enterprise or Growth'),
('5.1.4','Allocate an available CSM and prepare the project')],[(1,'Missing or conflicting details\nAsk for correction and pause'),(2,'No clear answer\nRetry or involve a person'),(3,'No capacity or uncertain project\nQueue or request review')])
p('Agent 1 prepares a trustworthy handoff to the CS team. It checks that the request is complete, asks the correct AE to confirm the plan on a real call and creates the right onboarding project. It does not guess, bypass the call or create another project when the first result is uncertain.')
sub('5.1.1 Receive and identify','Read the approved deal email, record its reference and check whether the request was already handled. The customer’s name, contact email and opportunity link connect the request to the right customer. A repeated email should point to the existing work.')
sub('5.1.2 Check the information','Confirm that the three required details are present and valid, and that the correct AE can be contacted. Missing information leads to a specific clarification request; a correction should resume the original request. Agent 1 does not substitute a different phone number or invent missing details.')
sub('5.1.3 Confirm the plan','Ask the AE whether the customer is on Enterprise or Growth. A clear answer allows the request to proceed. Silence, voicemail, conflicting answers or phrases such as “probably the larger package” cause a bounded retry or human review. An email statement alone does not replace the required call.')
sub('5.1.4 Prepare the project','After the plan is confirmed, check each eligible CSM’s active onboarding workload. Select the least-loaded available CSM and reserve capacity before creating the project; assign a Project Manager and the Project Owner. The CSM also owns migration and configuration. If everyone is occupied, retain the request in a visible waiting queue and retry later without creating a project or channel. Use the confirmed plan to select the Rocketlane template and dates. A timeout after project creation requires review before another attempt. See Section 9.4 for capacity assumptions.')

continuation('5.2 Agent 2 Communication')
diagram('agent2_workflow','Figure 5.2 Agent 2 workflow',[
('5.2.1','Receive the verified customer and project details'),
('5.2.2','Prepare the personalized channel and welcome'),
('5.2.3','Establish the customer communication channel'),
('5.2.4','Verify access and delivery then report the outcome')],[(0,'Project not verified\nReturn to Agent 1 or reviewer'),(1,'Wrong customer or plan\nCorrect before publishing'),(2,'Sharing or delivery fails\nKeep project and retry safely')])
p('Agent 2 makes the start of onboarding clear to the customer. It uses the project already prepared by Agent 1 to create the right communication space and welcome message. It checks the customer and plan before publishing and does not claim success if customer access or message delivery is unconfirmed.')
sub('5.2.1 Receive the verified handoff','Use the customer name, contact email, confirmed plan, CSM arrangement and project reference from Agent 1. Do not guess a missing project or independently change the plan. An incomplete handoff goes back for correction without another project being created.')
sub('5.2.2 Prepare the communication','Include the customer and tier in the channel name, topic and welcome. Explain the agreed duration, CSM support and next step. Review the content so that it does not promise completed migration, confirmed kickoff dates or additional services that were never agreed.')
sub('5.2.3 Establish the channel','Create or locate the appropriate Slack channel and arrange customer participation through the supported workspace or sharing process. A channel that only the bot can see is not customer-shared. If the assessment uses a mock, label both the integration and customer participation as simulated.')
sub('5.2.4 Verify and report','Confirm channel access, topic and welcome delivery. Save their references so a retry continues the failed communication step rather than recreating the project. A real access failure remains incomplete; a permitted mock is reported as mock completion, not as a live shared channel.')

continuation('5.3 Combined workflow after Agent 2')
diagram('combined_workflow','Figure 5.3 Combined onboarding setup workflow',[
('5.3.1','AE sends an approved new deal email'),
('5.3.2','Agent 1 checks information and existing work'),
('5.3.3','AE clearly confirms the plan on a real call'),
('5.3.4','Agent 1 verifies the right Rocketlane project'),
('5.3.5','Agent 2 prepares and verifies communication'),
('5.3.6','Record the outcome and hand over to the CSM')],[(1,'Missing input\nClarification loop'),(2,'Unresolved plan\nRetry or human review'),(4,'Communication problem\nResume without a new project')],note='Rocketlane delivery control   One day overdue to PM   Four days overdue to Owner')
p('The two agents share one customer request. Steps 5.3.1–5.3.4 establish that the correct project exists. Step 5.3.5 establishes communication using that same project. Step 5.3.6 records whether setup is ready, still waiting or needs a person. A problem in Agent 2 does not undo Agent 1’s successful project setup.')
sub('5.3.7 Ongoing delivery control','After setup, the CSM and task owners carry out Kickoff, Data Migration, Configuration and Go-Live in Rocketlane. Native overdue rules continue to operate during delivery. Migration verification and readiness approval remain phase requirements; setup completion does not certify that they have already occurred.')

continuation('5.4 State and completion workflow')
diagram('completion_workflow','Figure 5.4 Outcome and completion workflow',[
('5.4.1','Record the request and its current position'),
('5.4.2','If something is missing wait for the right input'),
('5.4.3','If an outcome is uncertain request human review'),
('5.4.4','Confirm both project and communication outcomes'),
('5.4.5','Mark setup ready and hand over to the CSM')],[(1,'Await correction or call result\nKeep the request open'),(2,'Verify evidence\nResume only the affected step'),(3,'Disclosed Slack mock\nRecord mock completion')])
p('The status should tell the team what happens next. “Waiting” means the request has not failed permanently, but the next required input is not available. “Human review” means a person must check evidence or resolve a decision. “Setup ready” means the onboarding resources are prepared; it does not mean the customer has finished onboarding.')
table(['Step reference','Business status','Condition and next action'],[
('5.4.1','Received or processing','The request is recorded and its next step is known.'),
('5.4.2','Awaiting clarification or call result','Keep current work; resume when valid input arrives or a scheduled retry is due.'),
('5.4.3','Human review required','A named reviewer checks uncertain outcomes and records the decision.'),
('5.4.4','Project ready but communication incomplete','Keep the project; finish access or message delivery before declaring live readiness.'),
('5.4.5','Setup ready or mock completion','Record evidence and clearly disclose any simulated secondary integration.')],[.9,2.1,3.7])
sub('5.4.6 Completion checks','For live completion, the correct Rocketlane project, timeline and ownership must be verified, and customer communication must be accessible and delivered. Required native rules must also be configured and evidenced for overall solution acceptance. Full customer onboarding completion is a later delivery decision made through the phase exit criteria in Section 4.')

section(5)
heading('6.1 Agent 1 intake and plan confirmation guardrails')
p('These scenarios protect the customer handoff and determine whether Agent 1 may proceed. Each exception should identify the affected request, the reason it stopped, the person responsible and the action needed to resume.')
table(['Scenario and reference','Required behavior','Human role and release condition'],[
('6.1.1 Missing contact email\nStep 5.1.2','List the missing field, pause before any call or project and request correction.','AE supplies the detail; Agent 1 revalidates the same request.'),
('6.1.2 Malformed or conflicting details\nStep 5.1.2','Do not choose between contradictory contacts, names or links without confirmation.','AE confirms authoritative information; reviewer resolves identity conflicts.'),
('6.1.3 Unknown AE or phone\nStep 5.1.2','Do not call another employee or an untrusted number from unrelated content.','Operator verifies the correct AE route before any call.'),
('6.1.4 No answer or voicemail\nStep 5.1.3','Retain call reference; schedule bounded retries; stop at the configured limit.','AE answers a later real call or reviewer arranges another authorized attempt.'),
('6.1.5 Ambiguous or contradictory plan\nStep 5.1.3','Do not infer the tier from sales value, email wording or an AI summary.','Obtain clear AE voice confirmation; reviewer cannot replace it with an assumption.'),
('6.1.6 Call still active or outcome unavailable\nStep 5.1.3','Wait within the configured timeout; do not start overlapping calls.','Operator inspects provider evidence if the timeout expires.')],[1.8,2.55,2.35],font=9.5)
sub('6.1.7 Retry and evidence rules','The current default is at most three ended unresolved-call attempts, with a minimum 60-second delay in live mode. A call unresolved after ten minutes requires inspection before redialing. Record the call reference, decision and next action. A retry is not permission to bypass the clear-confirmation requirement.')

continuation('6.2 Agent 1 project setup guardrails')
table(['Scenario and reference','Required behavior','Human role and release condition'],[
('6.2.1 Repeated email or opportunity\nStep 5.1.1','Locate the existing request and keep its history rather than starting another project.','Reviewer resolves a genuinely separate deal or corrected identity.'),
('6.2.2 Existing customer onboarding\nStep 5.1.4','Check the provider and local records; flag an active project instead of automatically duplicating it.','CSM or Project Manager decides reuse versus a separately authorized onboarding.'),
('6.2.3 Wrong dates or ownership\nStep 5.1.4','Do not hand over an incorrectly configured project as ready.','Project Manager corrects native template or role mappings; verify again.'),
('6.2.4 API unavailable before a safe read\nStep 5.1.4','Retry reads within a bound, retain the request and show the failure.','Operator restores credentials/service or schedules a later attempt.'),
('6.2.5 Timeout after project creation request\nStep 5.1.4','Treat the result as unknown. Do not send another create request blindly.','Reviewer searches Rocketlane, records project evidence and resumes safely.')],[1.8,2.55,2.35],font=9.5)
heading('6.3 Agent 2 communication guardrails')
table(['Scenario and reference','Required behavior','Human role and release condition'],[
('6.3.1 Incomplete project handoff\nStep 5.2.1','Pause communication; do not invent the project or change the plan.','Agent 1 or reviewer supplies a verified handoff.'),
('6.3.2 Wrong or misleading draft\nStep 5.2.2','Reject content with the wrong customer/tier or unsupported promises.','Use corrected approved facts or the safe message template.'),
('6.3.3 Customer cannot access channel\nStep 5.2.3','Do not label bot-only access as successful sharing.','Workspace administrator or CSM establishes the correct customer access.'),
('6.3.4 Channel/message timeout\nStep 5.2.4','Keep the project and existing channel; inspect delivery before repeating the action.','Reviewer verifies existing channel/message references and resumes only the gap.')],[1.8,2.55,2.35],font=9.5)

continuation('6.4 Human in the loop')
p('Human in the loop means that a person receives a specific decision to make, reviews the available evidence and records an authorized response before the affected workflow continues. It is part of the normal exception process, not a general permission to override the business rules.')
table(['Situation','Reviewer','Decision and evidence'],[
('Missing or disputed deal information','AE; operator for identity conflicts','Confirm the correct fields and connect the response to the original request.'),
('Exhausted or unclear calls','AE and responsible CS operator','Arrange another authorized call or retain the unresolved status; never assume the plan.'),
('Uncertain project or Slack write','Operator with provider access','Locate the resource or establish that it was not created; record reference and rationale.'),
('Template, role or scope conflict','Project Manager or CSM','Correct configuration or approve an explicit business change before proceeding.'),
('Data verification or readiness failure','Customer champion and CSM','Review counts/sample checks, acceptance results and remaining risks before sign-off.')],[2.05,1.7,2.95])
sub('6.4.1 Review and resume process','Pause the affected request and name the reviewer. Show what is known, what is uncertain and what action is proposed. The reviewer checks provider or customer evidence, records a reason and supplies the corrected information or matching resource reference. Resume only the affected step. If evidence remains insufficient, keep the request open and escalated.')
sub('6.4.2 Boundaries that people must preserve','A reviewer cannot substitute an assumed plan for the required AE voice confirmation, hide a simulated integration, or approve migration merely because an import finished. Customer or contract changes follow an agreed business approval process. The current implementation exposes local operator reconciliation; an authenticated review service and delivered alerts are target capabilities, not already verified features.')
sub('6.5 Shared audit and delivery safeguards','Both agents record who acted, when, which customer request was affected, the relevant input/output references and why the decision was made. Keep secrets and unrestricted recordings out of logs. Treat email instructions as untrusted content. Native migration approval/dependency controls and native overdue notifications protect delivery after setup; local evidence records alone cannot enforce Rocketlane task transitions.')
sub('6.6 Staffing and capacity safeguards','Agent 1 checks and reserves capacity in one durable decision before project creation. A replay retains the same assignment, concurrent requests cannot exceed four units per CSM, and full occupancy leaves the request queued. Failed or uncertain setup retains its reservation until a person resolves or cancels it. Agent 2 uses only the allocated PM, Owner and CSM for new channels and blocks mock identities from real invitations. Completed setup must never be interpreted as completed onboarding or available CSM capacity.')

section(6)
p('The solution uses a custom Python LangGraph application. This section keeps the technical integration responsibilities separate from the business workflow in Section 5. Each integration must preserve the customer identity, existing progress and evidence needed for safe recovery.')
table(['Integration','Responsibility','Acceptance evidence'],[
('Gmail','Approved inbox access; message/sender/thread references; clarification and correction flow.','A new email starts processing and a corrected reply resumes the intended request.'),
('LangGraph and agents','Coordinate the two agents, validation, branches, durable progress and review/resume.','Restart, branch and authorized resume tests pass without repeated side effects.'),
('Voice provider','Place actual outbound calls and retrieve linked speech/outcome evidence.','Authorized AE call clearly confirms the tier; no-answer/voicemail are handled safely.'),
('Rocketlane','Create from native templates and retain project, task, phase, date and role information.','Both tiers have correct native structure, duration and ownership.'),
('Slack','Channel, topic, welcome and supported customer participation.','Correct customer access and delivery, or a clearly disclosed permitted mock.'),
('State and review records','Store request status, action history, retry schedule, resource references and review outcomes.','Worker restart preserves progress and reviews cannot skip unmet conditions.')],[1.15,3.0,2.55])
sub('7.1 Configuration and operating requirements','Secrets belong in environment configuration or a secret manager. The application uses persistent SQLite business records and separate LangGraph checkpoints for the assessment; production requires appropriate database, access and worker coordination controls. Run one worker per database and retain both state and checkpoint files. An optional model provider requires its own package, credentials and compatibility verification.')
sub('7.2 Native overdue escalation','Configure the required rules inside Rocketlane: one day overdue to Project Manager, four days overdue to Project Owner. Verify completed-task exclusions, role recipients, timezone, evaluation timing and repeat behavior. Application failure alerts are separate from these native task notifications.')
sub('7.3 Project load tracking','SQLite records team identities, active onboarding assignments, reserved capacity, assignment timestamps and release reasons. The local dashboard shows CSM Enterprise/Growth counts, used and available capacity, project assignments, Project Manager and Owner load, and requests waiting for capacity. Setup readiness remains separate from onboarding completion. Mock records and unsynchronized task data are disclosed. Work outside this application must be imported before this directory can represent full live occupancy.')

section(7)
p('Testing must establish both useful customer outcomes and safe behavior when information, people or services are unavailable. The strategy covers unit, integration, system, smoke, load and stress testing. Each test records the starting conditions, actions, expected result and evidence of the actual result.')
table(['Test level','Business question','Test setting'],[
('8.1 Unit','Does each rule make the correct decision?','Small isolated tests with controlled inputs and mocked dependencies.'),
('8.2 Integration','Do connected components exchange the right information?','Provider-shaped fixtures and sandbox contract checks.'),
('8.3 System','Does the complete onboarding setup work and recover?','End-to-end requests across both agents and persistent state.'),
('8.4 Smoke','Is the deployed application basically ready to operate?','Short checks after setup, deployment or configuration change.'),
('8.5 Load','Can expected demand be handled reliably?','Agreed normal and peak arrival rates with measured resource use.'),
('8.6 Stress','What happens beyond capacity or during severe disruption?','Controlled overload, process failure and recovery exercises.')],[1.0,2.7,3.0])
sub('8.0 Acceptance principles','Enterprise and Growth must both be represented. Positive outcomes must verify actual template, ownership and communication details, not only that an API returned success. Negative outcomes must show that no unintended call, project or duplicate message was created. Native rules require tenant evidence. An authorized real phone call and Rocketlane API run are mandatory live checks; allowed secondary mocks must be labeled.')
sub('8.0.1 Evidence and test ownership','Engineering owns repeatable automated tests and recovery evidence. The CSM/Project Manager validates business outcomes and template roles. The customer champion validates migration acceptance where relevant. Report failures, blocked tests and untested assumptions openly. The existing 40 local tests are baseline evidence; broader tests described here remain a planned acceptance suite unless results are attached.')

continuation('8.1 Unit testing scenarios')
table(['Scenario','Expected result'],[
('8.1.1 Three valid deal fields with no extra AE fields','Accept the deal; resolve calling details separately.'),
('8.1.2 Missing name/email/link or malformed values','Identify the exact field; no call or project is authorized.'),
('8.1.3 Enterprise, Growth, ambiguity and contradiction','Accept only an explicit supported tier; no default plan.'),
('8.1.4 Phase totals and CSM mapping','Enterprise totals 30, Growth 14; four phases and 15 shared tasks remain consistent.'),
('8.1.5 Incorrect generated communication','Reject missing customer/tier facts and use the approved safe content.'),
('8.1.6 Retry, duplicate and resume decisions','Apply bounds and delays; reject mismatched review targets; retain existing resources.')],[2.9,3.8])
p('Unit exit condition: each rule has positive, negative and relevant boundary cases. Tests run without external calls and demonstrate that invalid input cannot unlock a later action.')
heading('8.2 Integration testing scenarios')
table(['Scenario','Expected result'],[
('8.2.1 Gmail content and identity handoff','Body and sender/thread identifiers reach the right request without cross-customer mixing.'),
('8.2.2 Voice provider outcomes','Active, ended, no-answer, voicemail and multi-turn fixtures map to the intended wait/confirm/retry outcome.'),
('8.2.3 Rocketlane sources, dates and roles','Both tier requests use valid template sources; created native phases/tasks and assignments are verified.'),
('8.2.4 Slack permissions and delivery','Correct name/topic/welcome; access failures remain visible; repeats do not duplicate prior work.'),
('8.2.5 Checkpoint and business record recovery','Restart and resume preserve references; a provider success followed by local failure does not cause blind recreation.')],[2.9,3.8])
p('Integration exit condition: request/response contracts pass against controlled fixtures and applicable sandbox checks. Credentials, limits and permissions are verified without exposing secrets.')

continuation('8.3 System testing scenarios')
table(['Scenario','Expected result'],[
('8.3.1 Enterprise and Growth complete journeys','Email triggers a real call, correct native project and verified communication; outcomes match Sections 4 and 5.'),
('8.3.2 Missing field corrected later','Specific clarification is issued; correction resumes the same request; no premature call/project.'),
('8.3.3 AE unavailable or ambiguous','Bounded retry then human review; no project exists without clear confirmation.'),
('8.3.4 Existing project and replayed events','Existing onboarding is located or flagged; repeat email/outcome does not create another resource.'),
('8.3.5 Partial failure and recovery','Project survives Slack failure; uncertain writes require evidence; restart resumes the correct step.'),
('8.3.6 Native escalation and migration gate','Day-one/day-four notifications reach correct roles; completed-task control is excluded; verification is required before readiness.')],[2.8,3.9])
p('System exit condition: mandatory customer journeys pass with traceable evidence, no unexplained duplicates and correct human handoffs. Record both the positive and negative walkthroughs. A local mock-only journey is not proof of live voice or Rocketlane acceptance.')
heading('8.4 Smoke testing scenarios')
bullets([
    '8.4.1 Start the worker and verify its configuration, database and durable checkpoint access.',
    '8.4.2 Confirm inbox access and basic provider authentication in the sandbox; report a missing or expired credential clearly.',
    '8.4.3 Process one controlled synthetic request and inspect the recorded status and action history.',
    '8.4.4 Confirm stop/restart behavior and that a second worker cannot take the same local database lock.',
    '8.4.5 After a change, run a short approved service check before enabling normal intake. Do not place real test calls without an authorized destination.'
])
p('Smoke exit condition: core dependencies are reachable, records are readable and the minimal approved path operates. Stop deployment acceptance if these basic checks fail.')

continuation('8.5 Load testing scenarios')
p('Define expected normal and peak deal arrival rates with the business before measuring capacity. Approximately 200 existing customers does not establish a deal-arrival target. Use simulated voice and project endpoints for volume tests; reserve real-provider tests for limited approved checks.')
table(['Scenario','Measures and expected behavior'],[
('8.5.1 Sustained normal arrivals','Measure intake lag, completion latency, error rate, database size and worker CPU/memory; all accepted requests remain traceable.'),
('8.5.2 Peak burst with active calls','Measure queue depth and oldest waiting request; pending calls do not block unrelated ready work indefinitely.'),
('8.5.3 Duplicate-heavy input','Repeated messages/opportunities do not multiply project/channel creation or corrupt the accepted run.'),
('8.5.4 Mixed customer plans and retry states','Enterprise/Growth routing stays correct and customer context remains isolated while retries are due.')],[2.6,4.1])
p('Load acceptance: agree numeric throughput, queue-delay, latency and error-rate limits before execution. Pass only when those limits are met without duplicate side effects, missing audit events or exhausted resources. The current worker is sequential; tests must measure that limit rather than imply unsupported parallel capacity.')
heading('8.6 Stress testing scenarios')
table(['Scenario','Expected protection and recovery'],[
('8.6.1 Input beyond sustainable capacity','Queue/backlog is visible; accepted work is not silently dropped; operators can stop intake and recover.'),
('8.6.2 Extended 429/5xx and voice outage','Retries stay bounded, delays are respected and no call/project creation storm occurs.'),
('8.6.3 Process killed after external success','On restart, uncertain work is reviewed against provider evidence before another write.'),
('8.6.4 Database unavailable or storage exhausted','Stop unsafe progression, surface the failure and preserve/recover committed state; no success is reported without evidence.')],[2.6,4.1])
p('Stress acceptance: demonstrate controlled failure, no cross-customer leakage or bypass of confirmation, and recovery once capacity/service is restored. Record recovery time, unresolved work and duplicate counts. Stress thresholds and recovery objectives are proposed test commitments, not already measured results.')

section(8)
sub('9.1 Confirmed business clarifications','AE means Account Executive. Basic task assumptions are allowed. Enterprise onboarding takes longer because of complexity. The main tier difference is project and phase duration, together with the stated CSM arrangement. No mandatory deal fields are added beyond customer name, contact email and Salesforce opportunity link.')
sub('9.2 Delivery assumptions','The proposed phases share 15 tasks and equal verification standards. Calendar-day allocations are illustrative. One designated AE and a trusted configured phone route can support the assessment; multiple AEs require an approved directory. A structured email is the baseline input; broader prose/HTML support needs explicit tests. Staffing and capacity extensions are recorded separately in Section 9.4.')
table(['Open question','Resolution needed'],[
('Calendar and phase dependencies','Confirm working/calendar days, holidays, inclusive dates and which tasks can overlap.'),
('Real role mapping and existing workload','Replace mock identities with approved real member mappings; import onboarding work outside the application.'),
('Existing onboarding','Agree reuse versus separate onboarding when the same customer has another active project.'),
('Customer participation','Agree Slack membership/guest/Connect approach and customer access approval owner.'),
('Human review operations','Name reviewers, notification channel, response expectation and authorized resume path.'),
('Test capacity and retention','Agree load/stress targets, recovery objectives, evidence retention and recording approvals.')],[2.2,4.5])
sub('9.3 Dependencies','Live acceptance needs the running Python/LangGraph worker, durable state storage, Gmail OAuth, an outbound-enabled voice account, an authorized AE number, Rocketlane API and native automation permissions, valid templates and a supported communication destination. Optional model-backed agents require a compatible provider. Access to these systems and completion of the scenario-based tests are separate from writing the solution design.')

continuation('9.4 Staffing and capacity assumptions')
p('The roster and per-plan limits below are user-requested extensions to the assignment. The mixed-plan conversion, assignment policy and release policy are implementation assumptions; they are not requirements supplied by Karthik.')
table(['Item','Assumption or agreed extension'],[
('9.4.1 Team structure','Ten CSMs, two Project Managers and one Project Owner. Each CSM also covers migration and configuration; no separate specialists are allocated.'),
('9.4.2 Concurrent plan limits','One CSM supports at most two Enterprise onboardings or four Growth onboardings concurrently.'),
('9.4.3 Mixed-plan interpretation','One Enterprise consumes two workload units and Growth consumes one; each CSM has four units. One Enterprise plus two Growth is allowed; two Enterprise plus any Growth is not.'),
('9.4.4 Assignment decision','Select the active eligible CSM with the lowest reserved workload; break ties by member ID. Balance project management by reserved load. No PM or Owner capacity ceiling has been specified.'),
('9.4.5 Full occupancy','Queue the confirmed request when no complete eligible team is available. Retry during later worker cycles; strict first-in-first-out ordering is not guaranteed.'),
('9.4.6 Reservation lifetime','Reserve capacity before project creation. Keep it through setup, delivery and unresolved failures. Release only after explicit completion or cancellation with a recorded reason; resolve uncertain provider writes first.'),
('9.4.7 Data and identity boundary','Initial identities are local mock records, not Slack accounts. Real invitations require verified non-mock member mappings. Only application-recorded assignments count; external work requires import.')],[1.7,5.0],font=10)
p('Examples: two Enterprise requests occupy all four units; four Growth requests do the same. One Enterprise and one Growth leave one unit, so only another Growth fits. Completing channel setup does not free a CSM. These rules apply equally to migration and configuration because the same CSM performs those responsibilities.')

continuation('9.5 Capacity acceptance scenarios')
table(['Test level','Scenario and expected outcome'],[
('Unit','Validate Enterprise cost two, Growth cost one and maximum four. Reject an ambiguous plan; exclude inactive members. Verify the same CSM covers migration and configuration.'),
('Integration','Reserve assignments in SQLite and retain them across worker restart. Link the selected CSM, PM and Owner to the run and channel team. Reject mock mappings for live invitations.'),
('System','Fill all ten CSMs with twenty Enterprise or forty Growth requests; queue the next request without project/channel creation. Release a completed assignment and process a waiting request.'),
('Smoke','Load the roster and dashboard; check active project totals, CSM counts, leadership load and waiting-request totals against SQLite.'),
('Load and stress','Submit competing reservations for the final available slots. No CSM may exceed four units. Replays retain the original assignment; provider failure does not silently release capacity.')],[1.3,5.4],font=10)
p('Automated local tests cover per-tier saturation, mixed workloads, least-loaded selection, concurrent reservations, queued workflow resumption and explicit release. These checks do not prove live Rocketlane ownership, real Slack access or production-scale throughput. External workload import, native completion-driven release and scheduled overdue delivery remain separate acceptance work.')

section(9)
sub('10.1 Included solution scope','Approved email intake, clarification/correction, AE routing, real voice confirmation, correct Rocketlane provisioning, personalized communication, native overdue rules, persistent state, audit, bounded recovery, human review and acceptance evidence are the intended solution scope. Implemented features and outstanding work must be distinguished during handover.')
sub('10.2 Delivery activities outside setup automation','The assigned CSM executes migration and configuration as well as coordinating onboarding. Automated kickoff scheduling, execution of the actual delivery work, automatic final handoff summaries and support-system transfer remain extensions unless separately added. Capacity-based CSM allocation and the local project-load dashboard are now implemented extensions under the assumptions in Section 9.4. They do not execute the customer’s migration or configuration work.')
table(['Deliverable','Required contents'],[
('Solution documentation','Current/proposed flows, expanded phase requirements, scenario guardrails and traceability.'),
('Source and configuration','Custom LangGraph application, agent configuration, adapters, safe secret examples and operating instructions.'),
('Rocketlane configuration','Both templates with task/role mappings and native overdue rules; live verification evidence.'),
('Testing package','Unit, integration, system, smoke, load and stress plans/results with unexecuted cases identified.'),
('Walkthrough videos','A complete positive example and a negative example; actual voice and Rocketlane evidence with mock disclosure.')],[2.0,4.7])
sub('10.3 Success criteria','Each accepted request produces at most one intended onboarding project and uses the AE-confirmed tier. The correct timeline and owners are verified. Customer communication is personalized and accessible, or its permitted simulation is clearly disclosed. Missing or uncertain outcomes cannot silently advance. Native overdue rules are evidenced, human decisions are traceable and mandatory acceptance scenarios pass.')
sub('10.4 Implementation and acceptance status','The latest repository verification recorded 67 passing local tests, including graph recovery, capacity reservations, mixed-plan limits and concurrent allocation. Project-load dashboard checks are maintained with the implementation. This does not prove live provider configuration, every scenario in Section 8 or full delivery automation. Remaining integration behavior, delivered clarification/alerts, customer sharing, native rules and final recordings require completion or acceptance evidence.')

section(10)
p('The workflow figures appear at the point where each business process is introduced. This index identifies the diagrams and the numbered steps used in the narrative, so reviewers can trace an exception or outcome without reading implementation code.')
table(['Figure','Location','Numbered workflow'],[
('5.1 Agent 1','Start of Section 5.1','5.1.1 receive; 5.1.2 validate; 5.1.3 confirm; 5.1.4 prepare project.'),
('5.2 Agent 2','Start of Section 5.2','5.2.1 verified handoff; 5.2.2 prepare; 5.2.3 establish; 5.2.4 verify.'),
('5.3 Combined flow','After Agent 2 in Section 5.3','5.3.1–5.3.6 follow the shared request; 5.3.7 describes ongoing delivery control.'),
('5.4 Completion flow','After combined flow in Section 5.4','5.4.1–5.4.5 track outcomes; 5.4.6 specifies completion checks.')],[1.5,1.7,3.5])
heading('A.1 How to read the diagrams')
p('Read the main boxes from top to bottom. Each box starts with its numbered text reference. Side branches identify a condition that prevents normal progression; they are not alternate ways to skip confirmation or declare success. Yellow branches require correction, retry or review. The combined diagram’s delivery control band identifies the native Rocketlane notifications.')
heading('A.2 Exception and recovery interpretation')
p('Missing information at 5.1.2 returns to clarification. Unclear speech at 5.1.3 returns to retry or human review. An uncertain project at 5.1.4 requires provider evidence. A communication failure at 5.2.3 or 5.2.4 keeps the existing project and resumes the unfinished step. Completion step 5.4.4 verifies both outcomes before 5.4.5 can report live readiness.')
heading('A.3 Business and implementation boundary')
p('The diagrams express the proposed customer and operator experience. LangGraph coordinates the application steps, while Rocketlane stores and tracks delivery work. The state diagram’s business labels may be presented more simply than internal status names. An unimplemented clarification or review notification must be disclosed rather than implied by the diagram alone.')

section(11)
p('The matrix links required behavior to the revised workflow and scenario-based test plan. It identifies acceptance targets rather than asserting that every listed test has already passed.')
table(['ID','Requirement','Design reference','Acceptance reference'],[
('R01','Automatic approved Gmail intake','5.1.1 and 7','8.2.1; 8.3.1; 8.4.2'),
('R02','Three required fields and correction','3.1; 5.1.2; 6.1.1–6.1.2','8.1.1–8.1.2; 8.3.2'),
('R03','Correct AE routing','5.1.2; 6.1.3','8.2.1; 8.4.2'),
('R04','Real voice confirmation','5.1.3; 6.1.4–6.1.6','8.1.3; 8.2.2; 8.3.3'),
('R05','No project on uncertain plan','5.1.3; 6.1.5','8.1.3; 8.3.3'),
('R06','Enterprise duration and CSM','4.1–4.7; 5.1.4','8.1.4; 8.2.3; 8.3.1'),
('R07','Growth duration and CSM','4.1–4.7; 5.1.4','8.1.4; 8.2.3; 8.3.1'),
('R08','Native tasks phases and ownership','4.4–4.7; 7','8.2.3; 8.3.1'),
('R09','Two agents and shared handoff','5.1–5.3','8.3.1; 8.3.5'),
('R10','Personalized customer communication','5.2.1–5.2.4; 6.3','8.1.5; 8.2.4; 8.3.1'),
('R11','Native day one and day four alerts','5.3.7; 7.2','8.3.6'),
('R12','Audit and human in the loop','6.4–6.5; 5.4','8.1.6; 8.2.5; 8.3.5'),
('R13','Duplicate and failure recovery','6.2; 6.3.4','8.3.4–8.3.5; 8.6.3'),
('R14','Migration verification gate','4.5.4; 4.7.2; 6.5','8.3.6'),
('R15','Broad testing and safe operation','8.0–8.6','All six test levels; 8.5–8.6 targets agreed'),
('R16','Documentation and videos','10.3–10.4','8.3 exit criteria and delivery evidence'),
('E01','CSM capacity and team assignment extension','5.1.4; 9.4','9.5 capacity acceptance scenarios'),
('E02','Project load dashboard extension','7.3; 9.4','9.5 smoke and integration checks')],[.43,2.0,2.05,2.22],font=9)

path=OUT/'NovaCRM_Onboarding_Solution_Approach_LangGraph.docx'
doc.save(path)
print(path.resolve())
