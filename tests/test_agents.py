from pathlib import Path
import pytest
from pydantic import ValidationError

from app.agents import IntakeAgent, CommunicationAgent
from app.services import DemoServices
from app.store import Store
from app.workflow import Workflow


class StructuredModel:
    def __init__(self):
        self.requests = []
    def with_structured_output(self, schema):
        self.schema = schema
        return self
    def invoke(self, messages):
        self.requests.append(messages)
        if self.schema.__name__ == 'ExtractedDeal':
            return {'customer_name': 'Acme Labs', 'contact_email': 'champion@acme.example',
                    'opportunity_url': 'https://crm.example/opportunities/acme-001'}
        return {'welcome': 'Welcome Acme Labs! Enterprise onboarding takes 30 days with a dedicated CSM. '
                           'Project ID demo-project-ce1a9aa2. Migration requires customer verification.'}


def test_structured_model_agents_work_inside_graph():
    model = StructuredModel()
    flow = Workflow(Store(':memory:'), DemoServices(), intake_agent=IntakeAgent(model),
                    communication_agent=CommunicationAgent(model))
    run = flow.ingest('one', Path('examples/minimal_deal.txt').read_text())
    run = flow.run(run['id'])
    assert run['state'] == 'complete'
    assert len(model.requests) == 2  # Intake and one persisted communication draft.
    assert 'verification' in run['welcome_text']
    assert run['voice_evidence']['confirmed_plan'] == 'Enterprise'


def test_model_cannot_invent_missing_contact():
    with pytest.raises(ValidationError):
        IntakeAgent(StructuredModel()).parse('Customer Name: Acme Labs\nOpportunity URL: https://crm.example/opportunities/acme-001')


def test_unpersonalized_model_draft_falls_back_to_verified_template():
    class BadModel(StructuredModel):
        def invoke(self, messages):
            return {'welcome': 'Welcome! Your onboarding is complete.'}
    flow = Workflow(Store(':memory:'), DemoServices('Growth'), communication_agent=CommunicationAgent(BadModel()))
    run = flow.run(flow.ingest('one', Path('examples/minimal_deal.txt').read_text())['id'])
    assert 'Growth' in run['welcome_text']
    assert '14 days' in run['welcome_text']
    assert 'complete.' not in run['welcome_text']
def test_intake_accepts_transport_wrapped_opportunity_link():
    from app.agents import IntakeAgent
    body = ('Customer Name: Integration Test\r\nContact Email: test@acme.example\r\n'
            'Salesforce Opportunity Link:\r\nhttps://crm.example/opportunities/test-01\r\n')
    deal = IntakeAgent().parse(body)
    assert str(deal.opportunity_url) == 'https://crm.example/opportunities/test-01'

