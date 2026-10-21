from pathlib import Path

import pytest

from app.delivery import configure
from app.services import DemoServices
from app.store import Store
from app.workflow import Workflow
from scripts.simulate_project_tasks import simulate


def test_task_simulation_completes_delivery_and_releases_capacity(tmp_path):
    store = Store(tmp_path / 'simulation.db')
    flow = Workflow(store, DemoServices())
    try:
        run = flow.run(flow.ingest('simulation', Path('examples/minimal_deal.txt').read_text())['id'])
        run['channel_id'] = 'C111'
        with store.transaction():
            store.save(run)
        configure(store, run['id'], 'local_demo', 'U111', 'U222', 'U333')
        with pytest.raises(ValueError, match='previous phase'):
            simulate(store, run['id'], 'Go-Live')
        result = simulate(store, run['id'])
        assert result['remaining_tasks'] == 0
        assert result['delivery_status'] == 'completed'
        assert store.db.execute("SELECT COUNT(*) FROM onboarding_tasks WHERE run_id=? AND status='completed' AND progress=100", (run['id'],)).fetchone()[0] == 15
        assert store.db.execute('SELECT status FROM onboarding_assignments WHERE run_id=?', (run['id'],)).fetchone()[0] == 'completed'
        assert store.db.execute('SELECT COUNT(*) FROM checkpoint_events WHERE run_id=?', (run['id'],)).fetchone()[0] > 0
        assert store.db.execute('SELECT COUNT(*) FROM delivery_alerts WHERE run_id=?', (run['id'],)).fetchone()[0] == 0
        assert simulate(store, run['id'])['changed'] is False
        with store.transaction():
            run = store.get(run['id'])
            run['simulation'] = False
            store.save(run)
        with pytest.raises(ValueError, match='simulated project'):
            simulate(store, run['id'])
    finally:
        flow.close()
        store.db.close()
