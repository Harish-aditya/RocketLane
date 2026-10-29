"""Advance local demo tasks through the delivery graph; never call external APIs."""
import argparse
import json
import time
from decimal import Decimal
from pathlib import Path

from app.delivery import DeliveryMonitor, now
from app.store import Store
from app.team_directory import release
from app.worker import single_worker


class SimulatedUpdates:
    def __init__(self):
        self.messages = []

    def history(self, channel, oldest):
        return self.messages

    def post(self, *args):
        raise RuntimeError('Task simulation must not send Slack messages')


class TaskSimulationMonitor(DeliveryMonitor):
    def escalate(self, rid, today=None):
        # Fast-forwarding a happy path must not generate overdue alert receipts.
        pass


def simulate(store, rid, phase='all'):
    run = store.get(rid)
    cfg = store.db.execute('SELECT * FROM delivery_monitors WHERE run_id=?', (rid,)).fetchone()
    if (not run.get('simulation') or not str(run.get('project_id', '')).startswith('demo-project-')
            or run['state'] != 'complete' or not cfg or cfg['mode'] != 'local_demo'):
        raise ValueError('Only a fully set up simulated project with a local_demo monitor is allowed')
    if run.get('onboarding_status') in {'completed', 'cancelled'}:
        return {'run_id': rid, 'delivery_status': run['onboarding_status'], 'changed': False}
    phases = [p['name'] for p in run['phases']]
    selected = phases if phase == 'all' else [phase]
    if any(p not in phases for p in selected):
        raise ValueError('Unknown phase')
    api = SimulatedUpdates()
    monitor = TaskSimulationMonitor(store, api)
    report = []
    try:
        for name in selected:
            tasks = store.db.execute('SELECT * FROM onboarding_tasks WHERE run_id=? AND phase_name=? ORDER BY task_id',
                                     (rid, name)).fetchall()
            if not tasks:
                raise ValueError('Phase tasks missing')
            for prior in phases[:phases.index(name)]:
                if store.db.execute("SELECT 1 FROM onboarding_tasks WHERE run_id=? AND phase_name=? AND status!='completed'",
                                    (rid, prior)).fetchone():
                    raise ValueError('Complete previous phase first: ' + prior)
            if all(t['status'] == 'completed' for t in tasks):
                continue
            if name == 'Data Migration':
                with store.transaction():
                    run = store.get(rid)
                    run.update(migration_verified=True,
                               migration_verification_source='SIMULATION: sample counts and customer approval fixture')
                    store.save(run)
                    store.event(run, 'migration_verification',
                                'SIMULATION ONLY: fixture customer accepts sample data; no real customer approval')
            for status, progress in [('in_progress', 40), ('completed', 100)]:
                active = [t for t in store.db.execute('SELECT * FROM onboarding_tasks WHERE run_id=? AND phase_name=?',
                                                    (rid, name)) if t['status'] != 'completed']
                if not active:
                    continue
                cursor = store.db.execute('SELECT oldest_ts FROM delivery_monitors WHERE run_id=?', (rid,)).fetchone()[0]
                prior_stamps = [Decimal(row[0]) for row in store.db.execute(
                    'SELECT message_ts FROM delivery_updates WHERE channel_id=?', (cfg['channel_id'],))]
                stamp = max([Decimal(str(time.time())), Decimal(cursor)] + prior_stamps) + Decimal('0.000001')
                api.messages = [{'ts': str(stamp + Decimal(n) / 1000000), 'user': cfg['csm_user'],
                                 'text': f'TASK {t["task_id"]} STATUS {status} PROGRESS {progress} NOTE SIMULATION ONLY'}
                                for n, t in enumerate(active)]
                with store.transaction():
                    store.event(run, 'task_simulation_batch', f'SIMULATION ONLY: {name}, {status}, {len(active)} tasks; synthetic input, not Slack messages')
                try:
                    monitor.graph.invoke({'run_id': rid}, {'configurable': {'thread_id': rid}})
                finally:
                    with store.transaction():
                        # Synthetic input must not consume real Slack history.
                        store.db.execute('UPDATE delivery_monitors SET oldest_ts=? WHERE run_id=?', (cursor, rid))
                        for m in api.messages:
                            store.db.execute("UPDATE delivery_updates SET detail='SIMULATION ONLY: synthetic task update; no Slack message' WHERE channel_id=? AND message_ts=?",
                                             (cfg['channel_id'], m['ts']))
                for t in active:
                    actual = store.db.execute('SELECT status,progress FROM onboarding_tasks WHERE task_id=?', (t['task_id'],)).fetchone()
                    if tuple(actual) != (status, progress):
                        raise ValueError('Simulated update did not apply: ' + t['task_id'])
                with store.transaction():
                    store.db.execute("UPDATE onboarding_tasks SET source='local_demo_simulation' WHERE run_id=? AND phase_name=?", (rid, name))
                    store.db.execute('UPDATE delivery_monitors SET last_checked=?,error=NULL WHERE run_id=?', (now(), rid))
            report.append({'phase': name, 'completed_tasks': len(tasks)})
        remaining = store.db.execute("SELECT COUNT(*) FROM onboarding_tasks WHERE run_id=? AND status!='completed'", (rid,)).fetchone()[0]
        if remaining == 0:
            release(store, rid, 'completed', 'SIMULATION ONLY: all demo project tasks completed; release demo CSM capacity')
            with store.transaction():
                store.db.execute('UPDATE delivery_monitors SET enabled=0,error=NULL WHERE run_id=?', (rid,))
                store.event(run, 'task_simulation_complete', 'SIMULATION ONLY: four phases completed, monitor stopped, demo capacity released')
        return {'run_id': rid, 'simulation': True, 'phases': report, 'remaining_tasks': remaining,
                'delivery_status': store.get(rid).get('onboarding_status', 'active')}
    finally:
        monitor.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run_id')
    parser.add_argument('--db', default='demo-local-worker.db')
    parser.add_argument('--phase', default='all', choices=['all', 'Kickoff', 'Data Migration', 'Configuration', 'Go-Live'])
    args = parser.parse_args()
    if not Path(args.db).is_file():
        parser.error('Existing database required')
    with single_worker(args.db + '.delivery'):
        store = Store(args.db)
        try:
            print(json.dumps(simulate(store, args.run_id, args.phase), indent=2))
        finally:
            store.db.close()


if __name__ == '__main__':
    main()
