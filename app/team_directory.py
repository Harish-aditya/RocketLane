"""Local mock directory for allocation and escalation planning; no Slack accounts are created."""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def initialize(db):
    db.executescript('''
        CREATE TABLE IF NOT EXISTS team_members (
            member_id TEXT PRIMARY KEY, display_name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL, role TEXT NOT NULL,
            plan_tier TEXT NOT NULL CHECK(plan_tier IN ('Shared','Enterprise','Growth')),
            escalation_after_days INTEGER,
            slack_user_id TEXT UNIQUE,
            is_mock INTEGER NOT NULL DEFAULT 1 CHECK(is_mock IN (0,1)),
            active INTEGER NOT NULL DEFAULT 1 CHECK(active IN (0,1)),
            created_at TEXT NOT NULL,
            CHECK(escalation_after_days IS NULL OR escalation_after_days > 0),
            CHECK(is_mock=0 OR slack_user_id IS NULL)
        );
        CREATE INDEX IF NOT EXISTS team_routing ON team_members(active,plan_tier,role);
        CREATE TABLE IF NOT EXISTS onboarding_assignments (
            run_id TEXT PRIMARY KEY REFERENCES runs(id),
            csm_id TEXT NOT NULL REFERENCES team_members(member_id),
            pm_id TEXT NOT NULL REFERENCES team_members(member_id),
            owner_id TEXT NOT NULL REFERENCES team_members(member_id),
            plan TEXT NOT NULL CHECK(plan IN ('Enterprise','Growth')),
            capacity_units INTEGER NOT NULL CHECK(capacity_units IN (1,2)),
            status TEXT NOT NULL CHECK(status IN ('active','completed','cancelled')),
            assigned_at TEXT NOT NULL, released_at TEXT, release_reason TEXT
        );
    ''')


MOCK_MEMBERS = [
    ('mock-pm', 'Maya Project Manager', 'Project Manager', 'Shared', 1),
    ('mock-pm-2', 'Priya Project Manager', 'Project Manager', 'Shared', 1),
    ('mock-owner', 'Owen Project Owner', 'Project Owner', 'Shared', 4),
] + [(f'mock-csm-{i:02}', name + ' CSM', 'CSM', 'Shared', None)
     for i, name in enumerate(['Elena', 'Grace', 'Dev', 'Casey', 'Arun', 'Nisha',
                               'Vikram', 'Meera', 'Ravi', 'Anita'], 1)]


def seed(store):
    with store.transaction():
        # Retire the previous seed identities; preserve their history and real users.
        store.db.execute("""UPDATE team_members SET active=0 WHERE is_mock=1 AND member_id IN
            ('mock-enterprise-csm','mock-growth-csm','mock-migration','mock-configuration')""")
        for member_id, name, role, tier, days in MOCK_MEMBERS:
            store.db.execute('''INSERT OR IGNORE INTO team_members
                (member_id,display_name,email,role,plan_tier,escalation_after_days,created_at)
                VALUES(?,?,?,?,?,?,?)''', (member_id, name, member_id + '@example.invalid', role,
                tier, days, datetime.now(timezone.utc).isoformat()))
    return members(store)


def members(store):
    return [dict(r) for r in store.db.execute('SELECT * FROM team_members ORDER BY member_id')]


def workloads(store):
    return [dict(r) for r in store.db.execute('''SELECT m.member_id,m.display_name,m.is_mock,
        COALESCE(SUM(a.capacity_units),0) AS used_units,4-COALESCE(SUM(a.capacity_units),0) AS free_units,
        SUM(CASE WHEN a.plan='Enterprise' THEN 1 ELSE 0 END) AS enterprise_count,
        SUM(CASE WHEN a.plan='Growth' THEN 1 ELSE 0 END) AS growth_count
        FROM team_members m LEFT JOIN onboarding_assignments a
        ON a.csm_id=m.member_id AND a.status='active'
        WHERE m.active=1 AND m.role='CSM' GROUP BY m.member_id ORDER BY m.member_id''')]


def allocate(store, run_id, live=False):
    """Reserve weighted capacity atomically. Replays return the original assignment."""
    with store.transaction():
        run = store.get(run_id)
        if run.get('plan') not in {'Enterprise', 'Growth'} or not run.get('voice_evidence', {}).get('confirmed_plan') == run['plan']:
            raise ValueError('Explicit voice plan confirmation required before allocation')
        existing = store.db.execute('SELECT * FROM onboarding_assignments WHERE run_id=?', (run_id,)).fetchone()
        if existing:
            if existing['status'] != 'active':
                raise ValueError('Released onboarding cannot be automatically reallocated')
            return dict(existing)
        if run['state'] not in {'confirmed', 'awaiting_capacity'}:
            raise ValueError('Allocation requires confirmed or waiting onboarding')
        units = 2 if run['plan'] == 'Enterprise' else 1
        def candidates(role, column):
            # Column comes only from the fixed literals below, never user input.
            return store.db.execute(f'''SELECT m.*,
                COALESCE(SUM(a.capacity_units),0) AS load FROM team_members m
                LEFT JOIN onboarding_assignments a ON a.{column}=m.member_id AND a.status='active'
                WHERE m.active=1 AND m.role=? AND m.plan_tier IN ('Shared',?)
                AND m.is_mock=? AND (?=0 OR m.slack_user_id IS NOT NULL)
                GROUP BY m.member_id ORDER BY load,m.member_id''',
                (role, run['plan'], 0 if live else 1, int(live))).fetchall()
        csms = [r for r in candidates('CSM', 'csm_id') if r['load'] + units <= 4]
        pms = candidates('Project Manager', 'pm_id')
        owners = candidates('Project Owner', 'owner_id')
        if not csms or not pms or not owners:
            return None
        csm, pm, owner = csms[0], pms[0], owners[0]
        if live and any(not r['slack_user_id'] for r in (csm, pm, owner)):
            return None
        store.db.execute('INSERT INTO onboarding_assignments VALUES(?,?,?,?,?,?,?,?,NULL,NULL)',
                         (run_id,csm['member_id'],pm['member_id'],owner['member_id'],run['plan'],units,
                          'active',datetime.now(timezone.utc).isoformat()))
        # CSM owns migration and configuration as part of the same onboarding.
        run.update(csm_id=csm['member_id'],csm_name=csm['display_name'],csm_email=csm['email'],pm_id=pm['member_id'],
                   pm_email=pm['email'],owner_email=owner['email'],
                   owner_id=owner['member_id'],migration_specialist_id=csm['member_id'],
                   configuration_specialist_id=csm['member_id'])
        store.save(run)
        store.event(run, 'team_allocated', f'CSM {csm["member_id"]}; {units} of 4 capacity units reserved; PM {pm["member_id"]}')
        return dict(store.db.execute('SELECT * FROM onboarding_assignments WHERE run_id=?', (run_id,)).fetchone())


def assigned_slack_team(store, run, simulated=False):
    result = []
    for key in ('pm_id', 'owner_id', 'csm_id'):
        member = store.db.execute('SELECT * FROM team_members WHERE member_id=?', (run[key],)).fetchone()
        if not member or not member['active']:
            raise ValueError('Assigned team member is inactive or missing')
        if simulated:
            # Clearly synthetic; never used by the live adapter.
            result.append('UDEMO' + member['member_id'].replace('-', '').upper())
        else:
            if member['is_mock'] or not member['slack_user_id']:
                raise ValueError('Real Slack member mapping required for allocated team')
            result.append(member['slack_user_id'])
    return result


def release(store, run_id, status, reason):
    if status not in {'completed', 'cancelled'} or not reason.strip():
        raise ValueError('Completion/cancellation and reason required')
    with store.transaction():
        run = store.get(run_id)
        if run.get('onboarding_status') in {'completed','cancelled'}:
            raise ValueError('Onboarding already released')
        if run['state'] == 'reconcile' or run['state'].endswith('_pending'):
            raise ValueError('Reconcile pending provider writes before releasing capacity')
        if status == 'completed' and run['state'] != 'complete':
            raise ValueError('Only fully set up onboarding can be completed')
        row = store.db.execute('SELECT * FROM onboarding_assignments WHERE run_id=? AND status=\'active\'', (run_id,)).fetchone()
        if not row:
            raise ValueError('Active assignment required')
        store.db.execute('UPDATE onboarding_assignments SET status=?,released_at=?,release_reason=? WHERE run_id=?',
                         (status,datetime.now(timezone.utc).isoformat(),reason,run_id))
        run['onboarding_status'] = status
        if status == 'cancelled' and run['state'] != 'complete':
            run.update(state='escalated',error='Onboarding cancelled by operator')
        store.save(run)
        store.event(run, 'capacity_released', reason)


def team(store, plan, live=False):
    if plan not in {'Enterprise', 'Growth'}:
        raise ValueError('Explicit Enterprise or Growth plan required')
    rows = [dict(r) for r in store.db.execute('''SELECT * FROM team_members
        WHERE active=1 AND plan_tier IN ('Shared',?) ORDER BY member_id''', (plan,))]
    if live and (not rows or any(r['is_mock'] or not r['slack_user_id'] for r in rows)):
        raise ValueError('Mock or unlinked directory members cannot be used for real Slack invitations')
    return rows


def escalation(store, plan, overdue_days, completed=False):
    if overdue_days < 0:
        raise ValueError('Overdue days cannot be negative')
    candidates = team(store, plan)
    if completed:
        return []
    # Return the highest reached escalation level, so day four routes to Owner.
    eligible = [r for r in candidates if r['escalation_after_days'] is not None
                and overdue_days >= r['escalation_after_days']]
    threshold = max((r['escalation_after_days'] for r in eligible), default=None)
    return [r for r in eligible if r['escalation_after_days'] == threshold]


def main():
    from .store import Store
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='demo-local-worker.db')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('seed')
    sub.add_parser('list')
    sub.add_parser('workloads')
    finish = sub.add_parser('release')
    finish.add_argument('run_id')
    finish.add_argument('--status', choices=['completed', 'cancelled'], required=True)
    finish.add_argument('--reason', required=True)
    allocation = sub.add_parser('team')
    allocation.add_argument('plan', choices=['Enterprise', 'Growth'])
    route = sub.add_parser('escalation')
    route.add_argument('plan', choices=['Enterprise', 'Growth'])
    route.add_argument('--overdue-days', type=int, required=True)
    args = parser.parse_args()
    if not Path(args.db).is_file():
        parser.error('Use an existing workflow database')
    store = Store(args.db)
    try:
        if args.command == 'seed':
            result = seed(store)
        elif args.command == 'list':
            result = members(store)
        elif args.command == 'team':
            result = team(store, args.plan)
        elif args.command == 'workloads':
            result = workloads(store)
        elif args.command == 'release':
            release(store,args.run_id,args.status,args.reason)
            result = {'released': args.run_id, 'status': args.status}
        else:
            result = escalation(store, args.plan, args.overdue_days)
        print(json.dumps(result, indent=2))
    finally:
        store.db.close()


if __name__ == '__main__':
    main()
