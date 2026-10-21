from pathlib import Path
import pytest

from app.services import DemoServices, LiveServices, IntegrationError, UncertainWrite
from app.store import Store
from app.workflow import Workflow
from app import services as services_module
from scripts.confirmation_scenarios import scenario

BODY = Path('examples/minimal_deal.txt').read_text()


@pytest.mark.parametrize('plan,days,csm', [('Enterprise', 30, 'Dedicated CSM'), ('Growth', 14, 'Pooled CSM representative')])
def test_confirmed_plan_selects_and_adds_team_before_welcome(plan, days, csm):
    result = scenario(plan)
    assert result['state'] == 'complete'
    assert result['duration_days'] == days
    assert result['team_added'] == ['Project Manager', 'Project Owner', csm]
    assert result['actions']['member_invitations'] == 3
    assert result['actions']['welcome_messages'] == 1
    assert result['audit_actions'].index('add_member_result') < result['audit_actions'].index('welcome_intent')


def test_expensive_one_requests_explicit_plan_without_side_effects():
    result = scenario('the expensive one')
    assert result['state'] == 'retry_voice'
    assert result['confirmed_plan'] is None
    assert 'Enterprise or Growth' in result['confirmation_required']
    assert result['team_added'] == []
    assert result['actions'] == {'calls': 1, 'projects': 0, 'channels': 0, 'member_invitations': 0, 'welcome_messages': 0}


def test_expensive_response_resumes_only_after_new_explicit_confirmation():
    services = DemoServices(['the expensive one', 'Growth'])
    flow = Workflow(Store(':memory:'), services)
    run = flow.run(flow.ingest('one', BODY)['id'])
    assert run['state'] == 'retry_voice'
    run = flow.run(run['id'])
    assert run['state'] == 'complete'
    assert run['plan'] == 'Growth'
    assert 'UDEMOMOCKCSM01' in run['added_team_user_ids']
    assert run['csm_id'] == 'mock-csm-01'
    assert services.calls == 2


def test_ambiguous_retry_limit_never_invites_team():
    services = DemoServices('the expensive one')
    flow = Workflow(Store(':memory:'), services)
    run = flow.ingest('one', BODY)
    for _ in range(3):
        run = flow.run(run['id'])
    assert run['state'] == 'escalated'
    assert services.projects == services.channels == 0
    assert services.invitation_calls == []


def test_team_configuration_deduplicates_shared_and_plan_members(monkeypatch):
    monkeypatch.setenv('SLACK_SHARED_TEAM_USER_IDS', 'U111,U222')
    monkeypatch.setenv('ENTERPRISE_SLACK_TEAM_USER_IDS', 'U222,U333')
    monkeypatch.setenv('GROWTH_SLACK_TEAM_USER_IDS', 'U444')
    assert LiveServices().team('Enterprise') == ['U111', 'U222', 'U333']
    assert LiveServices().team('Growth') == ['U111', 'U222', 'U444']


def test_live_team_rejects_missing_or_invalid_plan_mapping(monkeypatch):
    monkeypatch.delenv('ENTERPRISE_SLACK_TEAM_USER_IDS', raising=False)
    with pytest.raises(IntegrationError):
        LiveServices().team('Enterprise')
    monkeypatch.setenv('ENTERPRISE_SLACK_TEAM_USER_IDS', 'person@example.com')
    with pytest.raises(IntegrationError):
        LiveServices().team('Enterprise')


def test_slack_invitation_already_in_channel_is_safe(monkeypatch):
    monkeypatch.setenv('SLACK_BOT_TOKEN', 'test-only')
    sent = []
    def post(method, url, headers, payload):
        sent.append(payload)
        return {'ok': False, 'error': 'already_in_channel'}
    monkeypatch.setattr(services_module, 'request', post)
    LiveServices().invite_member('C123', 'U123')
    assert sent == [{'channel': 'C123', 'users': 'U123'}]


def test_partial_invitation_timeout_preserves_completed_members_and_project(tmp_path):
    services = DemoServices()
    original = services.invite_member
    def fail_second(channel, user):
        if user == 'UDEMOMOCKOWNER':
            raise UncertainWrite('timeout')
        return original(channel, user)
    services.invite_member = fail_second
    path = tmp_path / 'state.db'
    flow = Workflow(Store(path), services)
    run = flow.run(flow.ingest('one', BODY)['id'])
    assert run['state'] == 'reconcile'
    assert run['added_team_user_ids'] == ['UDEMOMOCKPM']
    assert services.welcomes == 0
    flow.close()
    flow.store.db.close()
    flow = Workflow(Store(path), services)
    with pytest.raises(ValueError, match='Member ID must match'):
        flow.reconcile(run['id'], 'member_added', 'Wrong member', 'UWRONG')
    flow.reconcile(run['id'], 'member_added', 'Verified Owner is already in Slack channel', 'UDEMOMOCKOWNER')
    services.invite_member = original
    run = flow.run(run['id'])
    assert run['state'] == 'complete'
    assert run['added_team_user_ids'] == ['UDEMOMOCKPM', 'UDEMOMOCKOWNER', 'UDEMOMOCKCSM01']
    assert services.projects == services.channels == services.welcomes == 1
    assert [user for _, user in services.invitation_calls].count('UDEMOMOCKPM') == 1


def test_replayed_completed_workflow_does_not_reinvite():
    services = DemoServices()
    flow = Workflow(Store(':memory:'), services)
    run = flow.run(flow.ingest('one', BODY)['id'])
    flow.run(run['id'])
    assert len(services.invitation_calls) == 3
