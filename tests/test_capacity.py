from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from app.store import Store
from app.workflow import Workflow
from app.services import DemoServices
from app.team_directory import seed, allocate, workloads, release

BODY = Path('examples/minimal_deal.txt').read_text()


def confirmed(flow, n, plan='Enterprise'):
    flow.services.answer = plan
    run = flow.ingest(str(n), BODY.replace('acme-001', f'acme-{n:04d}'))
    flow.step(run['id'])
    return flow.step(run['id'])


def test_weighted_mixed_capacity_and_release():
    store = Store(':memory:')
    flow = Workflow(store, DemoServices())
    seed(store)
    with store.transaction():
        store.db.execute("UPDATE team_members SET active=0 WHERE role='CSM' AND member_id!='mock-csm-01'")
    try:
        one = flow.run(confirmed(flow, 1)['id'])
        two = flow.run(confirmed(flow, 2, 'Growth')['id'])
        three = flow.run(confirmed(flow, 3, 'Growth')['id'])
        assert all(r['state'] == 'complete' for r in (one,two,three))
        assert workloads(store)[0]['used_units'] == 4
        assert one['migration_specialist_id'] == one['configuration_specialist_id'] == one['csm_id']
        waiting = flow.run(confirmed(flow, 4, 'Growth')['id'])
        assert waiting['state'] == 'awaiting_capacity'
        assert waiting['project_id'] is None
        assert flow.services.projects == 3
        release(store, one['id'], 'completed', 'Customer handover accepted')
        resumed = flow.run(waiting['id'])
        assert resumed['state'] == 'complete'
        assert workloads(store)[0]['used_units'] == 3
        before = store.db.execute('SELECT COUNT(*) FROM onboarding_assignments').fetchone()[0]
        flow.run(resumed['id'])
        assert store.db.execute('SELECT COUNT(*) FROM onboarding_assignments').fetchone()[0] == before
    finally:
        flow.close()


@pytest.mark.parametrize('plan,limit', [('Enterprise',2),('Growth',4)])
def test_limits_and_least_loaded_allocation(plan,limit):
    store = Store(':memory:')
    flow = Workflow(store, DemoServices())
    seed(store)
    try:
        assignments = [allocate(store, confirmed(flow,i,plan)['id']) for i in range(10*limit)]
        assert len({a['csm_id'] for a in assignments[:10]}) == 10
        assert len({a['pm_id'] for a in assignments[:2]}) == 2
        assert all(r['used_units'] == 4 for r in workloads(store))
        assert allocate(store, confirmed(flow,100,plan)['id']) is None
    finally:
        flow.close()


def test_concurrent_reservation_cannot_overbook(tmp_path):
    path = tmp_path/'allocation.db'
    store = Store(path)
    seed(store)
    flow = Workflow(store, DemoServices())
    runs = [confirmed(flow,i)['id'] for i in range(4)]
    with store.transaction():
        store.db.execute("UPDATE team_members SET active=0 WHERE role='CSM' AND member_id!='mock-csm-01'")
    # Separate connections simulate competing processes, with one remaining CSM.
    stores = [Store(path) for _ in runs]
    try:
        with ThreadPoolExecutor(max_workers=4) as executor:
            results = list(executor.map(lambda pair: allocate(*pair), zip(stores,runs)))
        assert sum(r is not None for r in results) == 2
        assert workloads(store)[0]['used_units'] == 4
        assert allocate(store, next(r['run_id'] for r in results if r)) is not None
        assert workloads(store)[0]['used_units'] == 4
    finally:
        for other in stores:
            other.db.close()
        flow.close()
