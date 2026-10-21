from pathlib import Path
import time

import pytest
from langgraph.graph.state import CompiledStateGraph

from app.services import DemoServices, UncertainWrite
from app.store import Store
from app.workflow import Workflow
from app.worker import cycle
from app.worker import single_worker

BODY = Path('examples/minimal_deal.txt').read_text()


def test_compiled_graph_and_agent_subgraphs():
    flow = Workflow(Store(':memory:'), DemoServices())
    assert isinstance(flow.graph, CompiledStateGraph)
    names = flow.graph.get_graph().nodes
    assert {'intake_routing_agent', 'communication_agent', 'provision_project', 'human_reconciliation'} <= names.keys()
    run = flow.ingest('one', BODY)
    assert flow.run(run['id'])['state'] == 'complete'
    assert flow.graph.get_state(flow.config(run['id'])).values['run']['state'] == 'complete'


def test_checkpoint_restart_waiting_for_call(tmp_path):
    path = tmp_path / 'state.db'
    services = DemoServices()
    flow = Workflow(Store(path), services)
    run = flow.ingest('one', BODY)
    assert flow.step(run['id'])['state'] == 'awaiting_voice'
    flow.close()
    flow.store.db.close()
    restarted = Workflow(Store(path), services)
    snapshot = restarted.graph.get_state(restarted.config(run['id']))
    assert snapshot.values['run']['call_id'] == 'demo-call-1'
    assert restarted.run(run['id'])['state'] == 'complete'
    assert services.calls == services.projects == 1


def test_interrupt_survives_restart_and_validates_target(tmp_path):
    services = DemoServices()
    def uncertain(run):
        services.projects += 1
        raise UncertainWrite('timeout')
    services.project = uncertain
    path = tmp_path / 'state.db'
    flow = Workflow(Store(path), services)
    run = flow.run(flow.ingest('one', BODY)['id'])
    snapshot = flow.graph.get_state(flow.config(run['id']))
    assert snapshot.tasks[0].interrupts
    flow.close()
    flow.store.db.close()
    restarted = Workflow(Store(path), services)
    assert restarted.step(run['id'])['state'] == 'reconcile'
    assert services.projects == 1
    with pytest.raises(ValueError, match='match the interrupted action'):
        restarted.reconcile(run['id'], 'awaiting_voice', 'Wrong target', 'call-2')
    with pytest.raises(ValueError):
        restarted.reconcile(run['id'], 'project_created', '', 'p-123')
    fixed = restarted.reconcile(run['id'], 'project_created', 'Verified external reference in provider', 'p-123')
    assert fixed['project_id'] == 'p-123'
    assert restarted.run(run['id'])['state'] == 'complete'
    assert services.projects == 1


def test_crash_after_provider_success_before_checkpoint_does_not_duplicate():
    services = DemoServices()
    flow = Workflow(Store(':memory:'), services)
    run = flow.ingest('one', BODY)
    flow.step(run['id'])
    flow.step(run['id'])
    original = flow.store.save
    def crash(run):
        if run['state'] == 'project_created':
            raise RuntimeError('Simulated process death after remote create')
        original(run)
    flow.store.save = crash
    with pytest.raises(RuntimeError):
        flow.step(run['id'])
    flow.store.save = original
    assert flow.step(run['id'])['state'] == 'reconcile'
    assert services.projects == 1


def test_scheduled_retry_does_not_redial_before_due():
    services = DemoServices('ambiguous')
    flow = Workflow(Store(':memory:'), services, retry_delay=60)
    run = flow.run(flow.ingest('one', BODY)['id'])
    assert run['state'] == 'retry_voice'
    for _ in range(3):
        flow.run(run['id'])
    assert services.calls == 1
    with flow.store.transaction():
        run['next_attempt_at'] = time.time() - 1
        flow.store.save(run)
    assert flow.step(run['id'])['state'] == 'awaiting_voice'
    assert services.calls == 2


def test_worker_automatically_ingests_and_runs_without_duplicate_creation():
    class Gmail:
        def messages(self):
            yield 'one', BODY
    services = DemoServices('Growth')
    flow = Workflow(Store(':memory:'), services)
    result = cycle(flow, Gmail())
    assert result['runs'][0]['state'] == 'complete'
    cycle(flow, Gmail())
    assert services.calls == services.projects == services.channels == 1


def test_worker_yields_for_active_voice_call():
    services = DemoServices()
    services.outcome = lambda _: None
    flow = Workflow(Store(':memory:'), services)
    run = flow.ingest('one', BODY)
    assert cycle(flow)['runs'][0]['state'] == 'awaiting_voice'
    cycle(flow)
    assert services.calls == 1


def test_two_threads_are_isolated():
    services = DemoServices()
    flow = Workflow(Store(':memory:'), services)
    one = flow.ingest('one', BODY)
    two = flow.ingest('two', BODY.replace('acme-001', 'acme-002'))
    flow.run(one['id'])
    flow.step(two['id'])
    assert flow.graph.get_state(flow.config(one['id'])).values['run']['state'] == 'complete'
    assert flow.graph.get_state(flow.config(two['id'])).values['run']['state'] == 'awaiting_voice'
    assert services.projects == 1


def test_intake_outage_does_not_starve_active_work():
    class BrokenGmail:
        def messages(self):
            raise RuntimeError('Provider unavailable')
    flow = Workflow(Store(':memory:'), DemoServices())
    flow.ingest('one', BODY)
    result = cycle(flow, BrokenGmail())
    assert result['errors']
    assert result['runs'][0]['state'] == 'complete'


def test_worker_lock_is_exclusive_and_released(tmp_path):
    database = str(tmp_path / 'state.db')
    with single_worker(database):
        with pytest.raises(RuntimeError, match='Another worker'):
            with single_worker(database):
                pytest.fail('Second worker should not acquire the lock')
    with single_worker(database):
        pass


def test_reconciliation_commit_survives_checkpoint_failure():
    services = DemoServices()
    services.project = lambda _: (_ for _ in ()).throw(UncertainWrite('timeout'))
    flow = Workflow(Store(':memory:'), services)
    run = flow.run(flow.ingest('one', BODY)['id'])
    original = flow._apply_reconciliation
    def crash(*args):
        original(*args)
        raise RuntimeError('Crash after operator update committed')
    flow._apply_reconciliation = crash
    with pytest.raises(RuntimeError):
        flow.reconcile(run['id'], 'project_created', 'Verified provider project', 'p123')
    flow._apply_reconciliation = original
    assert flow.run(run['id'])['state'] == 'complete'
    events = flow.store.events(run['id'])
    assert len([event for event in events if event['action'] == 'operator_reconciliation']) == 1


def test_migrates_legacy_uncertain_write_record():
    flow = Workflow(Store(':memory:'), DemoServices())
    run = flow.ingest('one', BODY)
    with flow.store.transaction():
        run.update(state='reconcile', error='call: uncertain write; inspect provider and reconcile')
        flow.store.save(run)
    assert flow.reconcile(run['id'], 'awaiting_voice', 'Located real provider call', 'call-123')['call_id'] == 'call-123'
