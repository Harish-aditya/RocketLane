import json
import sqlite3
import threading
from pathlib import Path
from contextlib import contextmanager
from datetime import datetime, timezone


class Store:
    def __init__(self, path='onboarding.db'):
        self.path = str(path)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(path, timeout=30, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        PRAGMA journal_mode=WAL;
        CREATE TABLE IF NOT EXISTS runs (
          id TEXT PRIMARY KEY, message_id TEXT UNIQUE NOT NULL,
          opportunity TEXT UNIQUE, state TEXT NOT NULL, data TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS audit (
          sequence INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT,
          timestamp TEXT NOT NULL, action TEXT NOT NULL, detail TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS onboarding_status (
          run_id TEXT PRIMARY KEY, customer_name TEXT, plan TEXT, status TEXT NOT NULL,
          project_id TEXT, channel_id TEXT, simulation INTEGER NOT NULL DEFAULT 1,
          created_at TEXT NOT NULL, updated_at TEXT NOT NULL, error TEXT);
        CREATE TABLE IF NOT EXISTS agent_runs (
          execution_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
          agent_name TEXT NOT NULL, action TEXT NOT NULL, status TEXT NOT NULL,
          started_at TEXT NOT NULL, finished_at TEXT, rationale TEXT);
        CREATE INDEX IF NOT EXISTS agent_runs_lookup ON agent_runs(run_id, action, status);
        CREATE TABLE IF NOT EXISTS onboarding_tasks (
          task_id TEXT PRIMARY KEY, run_id TEXT NOT NULL, phase_name TEXT NOT NULL,
          task_name TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'not_started',
          owner_role TEXT NOT NULL, owner_name TEXT, source TEXT NOT NULL,
          updated_at TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS tasks_lookup ON onboarding_tasks(run_id);
        CREATE TABLE IF NOT EXISTS checkpoint_events (
          event_id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL,
          namespace TEXT NOT NULL, checkpoint_id TEXT NOT NULL, step INTEGER,
          source TEXT, timestamp TEXT NOT NULL, state TEXT, snapshot TEXT NOT NULL,
          UNIQUE(run_id, namespace, checkpoint_id));
        CREATE TABLE IF NOT EXISTS worker_status (
          worker_id TEXT PRIMARY KEY, mode TEXT NOT NULL, last_seen TEXT NOT NULL,
          errors TEXT NOT NULL);
        ''')
        from .team_directory import initialize
        initialize(self.db)
        from .delivery import initialize as initialize_delivery
        initialize_delivery(self.db)
        # Populate status/task projections for pre-dashboard runs without inventing
        # historical agent execution times or provider task progress.
        with self.transaction():
            for row in self.db.execute('SELECT data FROM runs').fetchall():
                self.project_status(json.loads(row['data']))
            # Historical intake events have reliable timestamps and outcomes;
            # do not fabricate unrecorded historical action/checkpoint executions.
            self.db.execute('''INSERT INTO agent_runs(run_id,agent_name,action,status,started_at,finished_at,rationale)
                SELECT a.run_id,'Intake and routing','intake',
                CASE WHEN a.detail LIKE 'Missing/invalid fields:%' THEN 'rejected' ELSE 'completed' END,
                a.timestamp,a.timestamp,a.detail FROM audit a WHERE a.action='intake'
                AND NOT EXISTS (SELECT 1 FROM agent_runs g WHERE g.run_id=a.run_id AND g.action='intake')''')

    @contextmanager
    def transaction(self):
        with self.lock:
            self.db.execute('BEGIN IMMEDIATE')
            try:
                yield
                self.db.commit()
            except Exception:
                self.db.rollback()
                raise

    def save(self, run):
        self.db.execute('UPDATE runs SET state=?,data=? WHERE id=?',
                        (run['state'], json.dumps(run), run['id']))
        self.project_status(run)

    def project_status(self, run):
        now = datetime.now(timezone.utc).isoformat()
        # Older demo records carry explicit demo resource IDs. Unknown records
        # are labeled unknown rather than asserted to be live in the dashboard.
        simulation = run.get('simulation', Path(self.path).name.startswith('demo-') or str(run.get('project_id') or '').startswith('demo-'))
        self.db.execute('''INSERT INTO onboarding_status VALUES(?,?,?,?,?,?,?,?,?,?)
            ON CONFLICT(run_id) DO UPDATE SET customer_name=excluded.customer_name,
            plan=excluded.plan,status=excluded.status,project_id=excluded.project_id,
            channel_id=excluded.channel_id,simulation=excluded.simulation,
            updated_at=excluded.updated_at,error=excluded.error''',
            (run['id'], (run.get('deal') or {}).get('customer_name'), run.get('plan'), run['state'],
             run.get('project_id'), run.get('channel_id'), int(simulation),
             run.get('created_at', now), now, run.get('error')))
        if run.get('project_id') and not self.db.execute("SELECT 1 FROM delivery_monitors WHERE run_id=? AND mode='live'",(run['id'],)).fetchone():
            for pi, phase in enumerate(run.get('phases', []), 1):
                for ti, name in enumerate(phase['tasks'], 1):
                    self.db.execute('''INSERT OR IGNORE INTO onboarding_tasks
                        (task_id,run_id,phase_name,task_name,status,owner_role,owner_name,source,updated_at)
                        VALUES(?,?,?,?,?,?,?,?,?)''',
                        (f'{run["id"]}:{pi}:{ti}', run['id'], phase['name'], name, 'not_started',
                         'Customer champion and CSM' if 'verif' in name.lower() else 'CSM', run.get('csm_name'),
                         'simulated_template' if simulation else 'template_not_synced', now))
            if run.get('csm_name'):
                self.db.execute('UPDATE onboarding_tasks SET owner_name=? WHERE run_id=? AND owner_name IS NULL AND source IN (\'simulated_template\',\'template_not_synced\')',
                                (run['csm_name'],run['id']))

    def event(self, run, action, detail, *, inputs=None, outputs=None):
        if inputs is not None or outputs is not None:
            detail = json.dumps({'rationale': detail, 'inputs': inputs or {}, 'outputs': outputs or {}})
        self.db.execute('INSERT INTO audit(run_id,timestamp,action,detail) VALUES(?,?,?,?)',
                        (run['id'], datetime.now(timezone.utc).isoformat(), action, detail))
        now = datetime.now(timezone.utc).isoformat()
        agent = 'Communication' if action.startswith(('channel_', 'add_member_','customer_invite_', 'topic_', 'welcome_')) else 'Intake and routing'
        if action.startswith('project_'):
            agent = 'Project provisioning'
        if action == 'intake':
            status = 'rejected' if run['state'] == 'rejected' else 'completed'
            self.db.execute('INSERT INTO agent_runs(run_id,agent_name,action,status,started_at,finished_at,rationale) VALUES(?,?,?,?,?,?,?)',
                            (run['id'], agent, action, status, now, now, detail))
        elif action.endswith('_intent'):
            self.db.execute('INSERT INTO agent_runs(run_id,agent_name,action,status,started_at,rationale) VALUES(?,?,?,?,?,?)',
                            (run['id'], agent, action.removesuffix('_intent'), 'running', now, detail))
        elif action.endswith('_result') or action in {'voice_timeout', 'worker_error'}:
            name = action.removesuffix('_result') if action.endswith('_result') else ('outcome' if action == 'voice_timeout' else None)
            status = {'reconcile': 'needs_review','customer_invite_manual':'needs_review', 'escalated': 'failed', 'retry_voice': 'waiting',
                      'awaiting_voice': 'waiting'}.get(run.get('state'), 'completed')
            if action == 'worker_error':
                status = 'failed'
            self.db.execute('''UPDATE agent_runs SET status=?,finished_at=?,rationale=? WHERE execution_id=(
                SELECT execution_id FROM agent_runs WHERE run_id=? AND status='running'
                AND (? IS NULL OR action=?) ORDER BY execution_id DESC LIMIT 1)''',
                (status, now, detail, run['id'], name, name))

    def record_checkpoint(self, config, checkpoint, metadata):
        values = checkpoint.get('channel_values', {})
        run = values.get('run') or {}
        # Log only an allowlist, never raw email bodies, auth headers or model messages.
        summary = {key: run.get(key) for key in ['state', 'plan', 'project_id', 'channel_id', 'call_attempts']}
        summary['team_members_added'] = len(run.get('added_team_user_ids', []))
        with self.transaction():
            self.db.execute('''INSERT OR IGNORE INTO checkpoint_events
                (run_id,namespace,checkpoint_id,step,source,timestamp,state,snapshot) VALUES(?,?,?,?,?,?,?,?)''',
                (config['configurable']['thread_id'], config['configurable'].get('checkpoint_ns', ''),
                 checkpoint['id'], metadata.get('step'), metadata.get('source'),
                 datetime.now(timezone.utc).isoformat(), run.get('state'), json.dumps(summary)))

    def heartbeat(self, mode, errors):
        with self.transaction():
            self.db.execute('''INSERT INTO worker_status VALUES('local',?,?,?) ON CONFLICT(worker_id)
                DO UPDATE SET mode=excluded.mode,last_seen=excluded.last_seen,errors=excluded.errors''',
                (mode, datetime.now(timezone.utc).isoformat(), json.dumps(errors)))

    def get(self, run_id):
        with self.lock:
            row = self.db.execute('SELECT data FROM runs WHERE id=?', (run_id,)).fetchone()
            if not row:
                raise KeyError(run_id)
            return json.loads(row['data'])

    def events(self, run_id):
        with self.lock:
            return [dict(r) for r in self.db.execute('SELECT * FROM audit WHERE run_id=? ORDER BY sequence', (run_id,))]
