import pytest

from app.rocketlane_agent import RocketlaneAgent
from app.services import IntegrationError, UncertainWrite


def test_project_without_receipt_requires_reconciliation(monkeypatch):
    agent = RocketlaneAgent()
    monkeypatch.setenv('GROWTH_TEMPLATE_SOURCES', '[{"templateId": 123}]')
    monkeypatch.setattr(agent, 'rocket', lambda *args: {})
    run = {'plan': 'Growth', 'id': 'confirmed-run', 'start_date': '2026-10-29',
           'deal': {'customer_name': 'Acme'}, 'owner_email': 'owner@example.com', 'csm_email': 'csm@example.com'}
    with pytest.raises(UncertainWrite, match='receipt missing'):
        agent.create_project(run)


def test_invalid_template_configuration_never_writes(monkeypatch):
    agent = RocketlaneAgent()
    monkeypatch.setattr(agent, 'rocket', lambda *args: pytest.fail('No provider write allowed'))
    for value in ('not-json', '[]', '{}'):
        monkeypatch.setenv('GROWTH_TEMPLATE_SOURCES', value)
        with pytest.raises(IntegrationError):
            agent.create_project({'plan': 'Growth'})


def test_task_write_validates_progress_and_tenant_mapping(monkeypatch):
    agent = RocketlaneAgent()
    monkeypatch.setenv('ROCKETLANE_TASK_STATUS_VALUES', '{"completed": 7}')
    writes = []
    monkeypatch.setattr(agent, 'rocket', lambda *args: writes.append(args))
    for status, progress in [('completed', 90), ('blocked', 100), ('completed', True), ('not_started', 40)]:
        with pytest.raises(IntegrationError):
            agent.update('123', status, progress)
    assert writes == []
    agent.update('123', 'completed', 100)
    assert writes == [('PUT', 'tasks/123', {'status': {'value': 7}, 'progress': 100, 'atRisk': False})]


def test_read_only_project_tool_rejects_demo_resource(monkeypatch):
    agent = RocketlaneAgent()
    monkeypatch.setattr(agent, 'rocket', lambda *args: pytest.fail('No provider read allowed'))
    with pytest.raises(IntegrationError):
        agent.project('demo-project-123')
