"""Populate the local demo dashboard using simulated integrations only."""
import argparse
import json
from pathlib import Path
from app.services import DemoServices
from app.store import Store
from app.workflow import Workflow
from app.worker import single_worker
from app.team_directory import release


def seed_dashboard(database):
    if not Path(database).name.startswith('demo-'):
        raise ValueError('Dashboard fixtures require a demo- database')
    with single_worker(str(database)):
        store = Store(database)
        services = DemoServices()
        flow = Workflow(store, services)
        try:
            marker = store.db.execute("SELECT id FROM runs WHERE message_id='dashboard-fixture-v1-complete'").fetchone()
            if marker:
                return {'status': 'already_seeded', 'fixture_version': 1}
            # Do not alter capacity, assignments or task progress on an occupied database.
            if store.db.execute('SELECT COUNT(*) FROM onboarding_assignments').fetchone()[0]:
                raise ValueError('Seed requires no existing allocations; use a fresh demo database')
            companies = ['Atlas Retail','Beacon Health','Cedar Finance','Delta Logistics','Evergreen Labs',
                         'Falcon Manufacturing','Granite Software','Harbor Travel','Indigo Education','Juniper Energy',
                         'Kite Analytics','Lumen Design','Maple Commerce','Northstar Media','Orion Foods',
                         'Pioneer Robotics','Quartz Systems','Riverstone Apps','Summit Services','Terra Networks',
                         'Union Digital','Vertex Studio','Willow Works','Xenon Research','Yellowfin Cloud',
                         'Zenith Partners','Aspen Ventures']
            created = []
            def create(index, plan):
                services.answer = plan
                body = (f'Customer Name: [Mock] {companies[index]}\n'
                        f'Contact Email: champion@fixture{index}.example\n'
                        f'Salesforce Opportunity Link: https://crm.example/opportunities/dashboard-fixture-{index:02d}')
                return flow.run(flow.ingest(f'dashboard-fixture-v1-{index:02d}', body)['id'])
            # Ten CSMs each receive one Enterprise, then one Growth; five receive
            # a second Growth. Remaining individual slots cannot fit Enterprise.
            for i in range(25):
                run = create(i, 'Enterprise' if i < 10 else 'Growth')
                assert run['state'] == 'complete', run['state']
                with store.transaction():
                    tasks = store.db.execute('SELECT task_id FROM onboarding_tasks WHERE run_id=? ORDER BY task_id', (run['id'],)).fetchall()
                    done = 2 + (i * 3) % 11
                    for j, task in enumerate(tasks):
                        state = 'completed' if j < done else ('blocked' if j == done and i % 4 == 0 else 'in_progress' if j == done else 'not_started')
                        store.db.execute('UPDATE onboarding_tasks SET status=? WHERE task_id=?', (state, task['task_id']))
                    store.event(run, 'mock_delivery_progress', 'Synthetic task progress for dashboard demonstration; not Rocketlane data')
                created.append(run['id'])
            historical = create(25, 'Growth')
            with store.transaction():
                store.db.execute("UPDATE onboarding_tasks SET status='completed' WHERE run_id=?", (historical['id'],))
            release(store, historical['id'], 'completed', 'Mock customer handover accepted for dashboard demonstration')
            waiting = create(26, 'Enterprise')
            assert waiting['state'] == 'awaiting_capacity'
            # A completion marker makes subsequent invocations a no-op.
            with store.transaction():
                store.db.execute("UPDATE runs SET message_id='dashboard-fixture-v1-complete' WHERE id=?", (waiting['id'],))
                waiting['message_id'] = 'dashboard-fixture-v1-complete'
                store.save(waiting)
            return {'status': 'seeded', 'active_projects': 25, 'completed_projects': 1,
                    'queued_enterprise': 1, 'simulated': True}
        finally:
            flow.close()
            store.db.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='demo-local-worker.db')
    args = parser.parse_args()
    print(json.dumps(seed_dashboard(args.db)))
