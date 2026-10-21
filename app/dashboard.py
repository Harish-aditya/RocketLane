"""Local read-only dashboard. Does not trigger agents or provider actions."""
import argparse
import json
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

from .store import Store
from .team_directory import workloads

STATIC = Path(__file__).with_name('dashboard_static')


def read_checkpoints(database, run_id=None, before=None):
    if before is not None and (not isinstance(before, int) or before < 1):
        raise ValueError('Checkpoint cursor must be a positive integer')
    connection = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('BEGIN')
        clauses, params = [], []
        if run_id:
            clauses.append('c.run_id=?')
            params.append(run_id)
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        total = connection.execute('SELECT COUNT(*) FROM checkpoint_events c' + where, params).fetchone()[0]
        if before is not None:
            clauses.append('c.event_id<?')
            params.append(before)
        where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
        records = [dict(r) for r in connection.execute('''SELECT c.*,s.customer_name,s.simulation
            FROM checkpoint_events c LEFT JOIN onboarding_status s ON s.run_id=c.run_id'''
            + where + ' ORDER BY c.event_id DESC LIMIT 51', params)]
        return {'items': records[:50], 'total': total,
                'next_cursor': records[49]['event_id'] if len(records) > 50 else None}
    finally:
        connection.close()


def read_data(database, run_id=None):
    connection = sqlite3.connect(Path(database).resolve().as_uri() + '?mode=ro', uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute('BEGIN')
        def rows(query, params=()):
            return [dict(row) for row in connection.execute(query, params)]
        if run_id is not None:
            records = rows('''SELECT s.*,json_extract(r.data,'$.slack_mode') AS slack_mode,
                json_extract(r.data,'$.customer_invitation.status') AS customer_invitation_status
                FROM onboarding_status s JOIN runs r ON r.id=s.run_id WHERE s.run_id=?''', (run_id,))
            if not records:
                return None
            return {'run': records[0],
                    'assignment': rows('''SELECT a.*,c.display_name AS csm_name,p.display_name AS pm_name,
                        o.display_name AS owner_name FROM onboarding_assignments a
                        JOIN team_members c ON c.member_id=a.csm_id JOIN team_members p ON p.member_id=a.pm_id
                        JOIN team_members o ON o.member_id=a.owner_id WHERE a.run_id=?''', (run_id,)),
                    'tasks': rows('SELECT * FROM onboarding_tasks WHERE run_id=? ORDER BY task_id', (run_id,)),
                    'agents': rows('SELECT * FROM agent_runs WHERE run_id=? ORDER BY execution_id DESC LIMIT 200', (run_id,)),
                    'checkpoints': rows('SELECT * FROM checkpoint_events WHERE run_id=? ORDER BY event_id DESC LIMIT 200', (run_id,)),
                    'delivery_monitors': rows('SELECT * FROM delivery_monitors WHERE run_id=?',(run_id,)),
                    'delivery_updates': rows('SELECT * FROM delivery_updates WHERE run_id=? ORDER BY created_at DESC LIMIT 100',(run_id,)),
                    'delivery_alerts': rows('SELECT * FROM delivery_alerts WHERE run_id=? ORDER BY created_at DESC LIMIT 100',(run_id,)),
                    'audit': rows('SELECT sequence,timestamp,action,detail FROM audit WHERE run_id=? ORDER BY sequence DESC LIMIT 200', (run_id,))}
        metrics = {
            'total_onboardings': connection.execute('SELECT COUNT(*) FROM onboarding_status').fetchone()[0],
            'total_agent_runs': connection.execute("SELECT COUNT(*) FROM agent_runs WHERE agent_name!='Project provisioning'").fetchone()[0],
            'setup_ready': connection.execute("SELECT COUNT(*) FROM onboarding_status WHERE status='complete'").fetchone()[0],
            'needs_attention': connection.execute("SELECT COUNT(*) FROM onboarding_status WHERE status IN ('rejected','escalated','reconcile','retry_voice','awaiting_capacity','customer_invite_manual')").fetchone()[0],
            'checkpoints': connection.execute('SELECT COUNT(*) FROM checkpoint_events').fetchone()[0],
            'tasks': connection.execute('SELECT COUNT(*) FROM onboarding_tasks').fetchone()[0],
        }
        runs = rows('''SELECT s.*,json_extract((SELECT data FROM runs r WHERE r.id=s.run_id),'$.slack_mode') AS slack_mode,
            json_extract((SELECT data FROM runs r WHERE r.id=s.run_id),'$.customer_invitation.status') AS customer_invitation_status,
            COUNT(t.task_id) AS task_count,
            SUM(CASE WHEN t.status='completed' THEN 1 ELSE 0 END) AS tasks_completed
            FROM onboarding_status s LEFT JOIN onboarding_tasks t ON t.run_id=s.run_id
            GROUP BY s.run_id ORDER BY s.created_at DESC LIMIT 200''')
        class DirectoryView:
            db = connection
        csm_load = workloads(DirectoryView())
        project_load = rows('''SELECT a.run_id,a.plan,a.status AS assignment_status,a.capacity_units,a.assigned_at,
            s.customer_name,s.project_id,s.status AS workflow_status,c.display_name AS csm_name,
            p.display_name AS pm_name,o.display_name AS owner_name,c.is_mock
            FROM onboarding_assignments a JOIN onboarding_status s ON s.run_id=a.run_id
            JOIN team_members c ON c.member_id=a.csm_id JOIN team_members p ON p.member_id=a.pm_id
            JOIN team_members o ON o.member_id=a.owner_id ORDER BY a.assigned_at DESC LIMIT 200''')
        leadership_load = rows('''SELECT m.member_id,m.display_name,m.role,m.is_mock,
            COUNT(a.run_id) AS active_projects FROM team_members m LEFT JOIN onboarding_assignments a
            ON (a.pm_id=m.member_id OR a.owner_id=m.member_id) AND a.status='active'
            WHERE m.active=1 AND m.role IN ('Project Manager','Project Owner') GROUP BY m.member_id
            ORDER BY m.role,m.member_id''')
        capacity = {'active_projects': connection.execute("SELECT COUNT(*) FROM onboarding_assignments WHERE status='active'").fetchone()[0],
                    'waiting_requests': connection.execute("SELECT COUNT(*) FROM runs WHERE state='awaiting_capacity'").fetchone()[0],
                    'fully_occupied_csms': sum(r['used_units'] >= 4 for r in csm_load),
                    'available_units': sum(r['free_units'] for r in csm_load)}
        return {'metrics': metrics, 'runs': runs, 'csm_workloads': csm_load,
                'project_load': project_load, 'leadership_load': leadership_load, 'capacity': capacity,
                'delivery': {'monitors': rows('''SELECT m.*,s.customer_name FROM delivery_monitors m
                                                JOIN onboarding_status s ON s.run_id=m.run_id'''),
                             'updates': rows('SELECT * FROM delivery_updates ORDER BY created_at DESC LIMIT 100'),
                             'alerts': rows('SELECT * FROM delivery_alerts ORDER BY created_at DESC LIMIT 100')},
                'agent_breakdown': rows('SELECT agent_name,COUNT(*) AS count FROM agent_runs GROUP BY agent_name'),
                'recent_events': rows('SELECT run_id,timestamp,action,detail FROM audit ORDER BY sequence DESC LIMIT 20'),
                'worker': rows('SELECT * FROM worker_status'),
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'database': Path(database).name,
                'notice': 'Agent executions count intake and communication action attempts, not unique customers. '
                          'Task records disclose local/demo or Rocketlane source; live synchronization requires a configured delivery monitor.'}
    finally:
        connection.close()


def handler_for(database):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_GET(self):
            parsed = urlparse(self.path)
            path = parsed.path
            try:
                if path == '/api/checkpoints':
                    query = parse_qs(parsed.query)
                    cursor = query.get('before', [None])[0]
                    return self.respond(200, read_checkpoints(database, query.get('run_id', [None])[0],
                                                             int(cursor) if cursor is not None else None))
                if path == '/api/summary':
                    return self.respond(200, read_data(database))
                if path.startswith('/api/runs/'):
                    run_id = path.removeprefix('/api/runs/')
                    value = read_data(database, run_id)
                    return self.respond(200 if value else 404, value or {'error': 'Run not found'})
                files = {'/': ('index.html', 'text/html'), '/app.js': ('app.js', 'text/javascript'),
                         '/styles.css': ('styles.css', 'text/css')}
                if path not in files:
                    return self.respond(404, {'error': 'Not found'})
                name, kind = files[path]
                data = (STATIC / name).read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', kind + '; charset=utf-8')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('Cache-Control', 'no-store')
                self.end_headers()
                self.wfile.write(data)
            except ValueError:
                self.respond(400, {'error': 'Invalid checkpoint cursor'})
            except (sqlite3.Error, OSError):
                self.respond(503, {'error': 'Dashboard data temporarily unavailable'})

        def respond(self, code, value):
            data = json.dumps(value).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)
    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='demo-local-worker.db')
    parser.add_argument('--port', type=int, default=8080)
    args = parser.parse_args()
    if not Path(args.db).exists():
        parser.error('Database does not exist; use the same database as your worker')
    store = Store(args.db)  # Idempotent schema migration/projection backfill.
    store.db.close()
    server = ThreadingHTTPServer(('127.0.0.1', args.port), handler_for(args.db))
    print(f'Dashboard: http://127.0.0.1:{args.port} | database: {Path(args.db).name}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
