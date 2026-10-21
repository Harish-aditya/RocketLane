import json
from pathlib import Path
from app.dashboard import read_data
from app.services import DemoServices
from app.store import Store
from app.workflow import Workflow

BODY = Path('examples/minimal_deal.txt').read_text()


def test_dashboard_captures_agent_attempts_tasks_and_real_checkpoints(tmp_path):
    database = tmp_path / 'worker.db'
    store = Store(database)
    flow = Workflow(store, DemoServices())
    run = flow.run(flow.ingest('one', BODY)['id'])
    summary = read_data(database)
    assert summary['metrics']['total_onboardings'] == 1
    assert summary['metrics']['setup_ready'] == 1
    assert summary['metrics']['total_agent_runs'] > 0
    assert summary['metrics']['checkpoints'] > 0
    detail = read_data(database, run['id'])
    assert len(detail['tasks']) == 15
    assert all(t['status'] == 'not_started' and t['owner_name'] == run['csm_name'] for t in detail['tasks'])
    assert detail['run']['simulation'] == 1
    assert detail['assignment'][0]['csm_id'] == run['csm_id']
    assert summary['capacity'] == {'active_projects': 1, 'waiting_requests': 0,
                                   'fully_occupied_csms': 0, 'available_units': 38}
    assert summary['project_load'][0]['csm_name'] == run['csm_name']
    assert sum(r['active_projects'] for r in summary['leadership_load'] if r['role']=='Project Manager') == 1
    assert len(summary['leadership_load']) == 3
    assert detail['checkpoints']
    assert not any(a['status'] == 'running' for a in detail['agents'])
    before = summary['metrics']['total_agent_runs']
    flow.run(run['id'])
    assert read_data(database)['metrics']['total_agent_runs'] == before
    assert read_data(database)['metrics']['tasks'] == 15


def test_invalid_run_shows_attention_and_no_tasks(tmp_path):
    database = tmp_path / 'worker.db'
    flow = Workflow(Store(database), DemoServices())
    run = flow.ingest('bad', 'Customer Name: Acme')
    summary = read_data(database)
    assert summary['metrics']['needs_attention'] == 1
    assert summary['metrics']['setup_ready'] == 0
    assert summary['metrics']['total_agent_runs'] == 1
    assert read_data(database, run['id'])['tasks'] == []
    assert read_data(database, 'missing') is None


def test_checkpoint_mirror_excludes_secrets_and_email_content(tmp_path):
    database = tmp_path / 'worker.db'
    store = Store(database)
    config = {'configurable': {'thread_id': 'test', 'checkpoint_ns': 'test-node'}}
    checkpoint = {'id': 'checkpoint-1', 'channel_values': {'secret': 'hidden',
                  'run': {'state': 'confirmed', 'access_token': 'private-token', 'deal': {'contact_email': 'private@example.com'}}}}
    store.record_checkpoint(config, checkpoint, {'step': 1, 'source': 'loop'})
    store.record_checkpoint(config, checkpoint, {'step': 1, 'source': 'loop'})
    rows = store.db.execute('SELECT snapshot FROM checkpoint_events').fetchall()
    assert len(rows) == 1
    assert 'private' not in rows[0][0] and 'hidden' not in rows[0][0]


def test_schema_migration_does_not_duplicate_or_reset_task_progress(tmp_path):
    database = tmp_path / 'worker.db'
    store = Store(database)
    flow = Workflow(store, DemoServices())
    flow.run(flow.ingest('one', BODY)['id'])
    with store.transaction():
        store.db.execute("UPDATE onboarding_tasks SET status='in_progress',owner_name='Assigned reviewer' WHERE task_id=(SELECT task_id FROM onboarding_tasks LIMIT 1)")
    count = read_data(database)['metrics']['total_agent_runs']
    flow.close()
    store.db.close()
    migrated = Store(database)
    assert read_data(database)['metrics']['total_agent_runs'] == count
    assert migrated.db.execute("SELECT COUNT(*) FROM onboarding_tasks WHERE status='in_progress' AND owner_name='Assigned reviewer'").fetchone()[0] == 1


def test_worker_heartbeat_visible_without_reading_log_files(tmp_path):
    database = tmp_path / 'worker.db'
    store = Store(database)
    store.heartbeat('real_gmail_simulated_downstream', [])
    assert read_data(database)['worker'][0]['mode'] == 'real_gmail_simulated_downstream'
