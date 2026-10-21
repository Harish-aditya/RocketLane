from pathlib import Path
import pytest
from app.services import DemoServices, IntegrationError, UncertainWrite
from app.store import Store
from app.workflow import Workflow

BODY = Path('examples/deal.txt').read_text()


def setup(answer='Enterprise'):
    services = DemoServices(answer)
    store = Store(':memory:')
    return Workflow(store, services), services


def finish(flow, run):
    for _ in range(12):
        run = flow.step(run['id'])
    return run


@pytest.mark.parametrize('plan,days,mode', [('Enterprise', 30, 'dedicated'), ('Growth', 14, 'pooled')])
def test_happy_paths(plan, days, mode):
    flow, services = setup(plan)
    run = finish(flow, flow.ingest('one', BODY))
    assert (run['state'], run['duration'], run['csm_mode']) == ('complete', days, mode)
    assert (services.calls, services.projects, services.channels, services.welcomes) == (1, 1, 1, 1)
    assert run['migration_verified'] is False
    assert all(e['timestamp'] and e['detail'] for e in flow.store.events(run['id']))


@pytest.mark.parametrize('field', ['Customer Name', 'Contact Email', 'Opportunity URL'])
def test_missing_fields(field):
    flow, services = setup()
    run = finish(flow, flow.ingest('bad', '\n'.join(l for l in BODY.splitlines() if not l.startswith(field + ':'))))
    assert run['state'] == 'rejected'
    assert services.calls == services.projects == 0


@pytest.mark.parametrize('plan', ['Enterprise', 'Growth'])
def test_only_three_deal_fields_required(plan):
    flow, services = setup(plan)
    body = Path('examples/minimal_deal.txt').read_text()
    run = finish(flow, flow.ingest('minimal', body))
    assert run['state'] == 'complete'
    assert run['deal']['ae_phone'] is None
    assert len(run['phases']) == 4
    assert sum(p['duration_days'] for p in run['phases']) == run['duration']
    assert sum(len(p['tasks']) for p in run['phases']) == 15


def test_both_plans_share_tasks_and_differ_in_phase_duration():
    from app.plans import plan_config
    enterprise, growth = plan_config('Enterprise'), plan_config('Growth')
    assert [p['tasks'] for p in enterprise['phases']] == [p['tasks'] for p in growth['phases']]
    assert enterprise['phase_days'] != growth['phase_days']


@pytest.mark.parametrize('answer', ['unresolved', 'probably Enterprise', 'Enterprise or Growth', 'not Growth', ''])
def test_bounded_voice_retries(answer):
    flow, services = setup(answer)
    run = finish(flow, flow.ingest('one', BODY))
    assert run['state'] == 'escalated'
    assert services.calls == 3
    assert services.projects == 0


def test_duplicates_and_restart(tmp_path):
    services = DemoServices()
    store = Store(tmp_path / 'state.db')
    flow = Workflow(store, services)
    first = finish(flow, flow.ingest('one', BODY))
    store.db.close()
    restarted = Workflow(Store(tmp_path / 'state.db'), services)
    second = restarted.ingest('two', BODY)
    assert first['id'] == second['id']
    finish(restarted, second)
    assert services.projects == 1


def test_uncertain_project_write_never_retried():
    flow, services = setup()
    def fail(run):
        services.projects += 1
        raise UncertainWrite('timeout')
    services.project = fail
    run = finish(flow, flow.ingest('one', BODY))
    assert run['state'] == 'reconcile'
    assert services.projects == 1
    assert services.channels == 0
    flow.reconcile(run['id'], 'project_created', 'Found project in Rocketlane by external reference', 'real-project')
    assert finish(flow, run)['state'] == 'complete'
    assert services.projects == 1


def test_slack_recovery_keeps_project():
    flow, services = setup()
    original = services.channel
    def fail(name):
        raise UncertainWrite('timeout')
    services.channel = fail
    run = finish(flow, flow.ingest('one', BODY))
    assert run['state'] == 'reconcile'
    assert run['project_id']
    services.channel = original
    flow.reconcile(run['id'], 'channel_created', 'Located existing Slack channel', 'C123')
    assert finish(flow, run)['state'] == 'complete'
    assert services.projects == 1


def test_pending_write_after_crash():
    flow, services = setup()
    run = flow.ingest('one', BODY)
    with flow.store.transaction():
        run['state'] = 'call_pending'
        flow.store.save(run)
    assert flow.step(run['id'])['state'] == 'reconcile'
    assert services.calls == 0


def test_pending_call_does_not_start_another_call():
    flow, services = setup()
    services.outcome = lambda _: None
    run = finish(flow, flow.ingest('one', BODY))
    assert run['state'] == 'awaiting_voice'
    assert services.calls == 1


def test_verification_requires_evidence():
    flow, _ = setup()
    run = finish(flow, flow.ingest('one', BODY))
    with pytest.raises(ValueError):
        flow.verify_migration(run['id'], '', '')
    assert flow.verify_migration(run['id'], 'Customer champion', 'Checksums and sample records approved')['migration_verified']
