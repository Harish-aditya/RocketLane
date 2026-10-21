"""Explicit Slack-only commands; never enable live voice or project creation."""
import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from .services import LiveServices, IntegrationError, UncertainWrite
from .store import Store


def publish(store, run_id, service=None):
    service = service or LiveServices()
    with store.transaction():
        run = store.get(run_id)
        channel = run.get('channel_id') or ''
        if not re.fullmatch(r'[CG][A-Z0-9]+', channel):
            raise ValueError('A real Slack channel linked to this run is required')
        rows = store.db.execute('SELECT phase_name,task_name,status,owner_name,source FROM onboarding_tasks WHERE run_id=? ORDER BY task_id', (run_id,)).fetchall()
        snapshot = {'state': run['state'], 'plan': run.get('plan'), 'tasks': [dict(r) for r in rows]}
        digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True).encode()).hexdigest()
        store.db.execute('''CREATE TABLE IF NOT EXISTS slack_status_delivery(
            run_id TEXT PRIMARY KEY, digest TEXT, status TEXT NOT NULL,
            message_ts TEXT, updated_at TEXT NOT NULL)''')
        previous = store.db.execute('SELECT * FROM slack_status_delivery WHERE run_id=?', (run_id,)).fetchone()
        if previous and previous['status'] == 'uncertain':
            raise UncertainWrite('Inspect the Slack channel and delivery ledger before another status post')
        if previous and previous['digest'] == digest:
            return {'status': 'unchanged', 'channel_id': channel}
        # Persist before the network call. A crash cannot cause a blind duplicate post.
        store.db.execute('INSERT OR REPLACE INTO slack_status_delivery VALUES(?,?,?,?,?)',
                         (run_id, digest, 'uncertain', None, datetime.now(timezone.utc).isoformat()))
    completed = sum(r['status'].lower() in {'completed', 'complete', 'done'} for r in rows)
    def safe(value):
        return str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    text = (f"Onboarding status — {safe((run.get('deal') or {}).get('customer_name', run_id))}\n"
            f"Plan: {safe(run.get('plan') or 'Awaiting confirmation')}\n"
            f"Automation state: {safe(run['state'])} (setup completion does not mean onboarding completion)\n"
            f"Recorded tasks: {completed}/{len(rows)} completed\n")
    if not rows or any(r['source'] != 'rocketlane' for r in rows):
        text += 'Task data is a local planning snapshot; Rocketlane progress has not been synchronized.\n'
    if run.get('simulation'):
        text += 'Voice/project workflow is simulated.\n'
    text += '\n'.join(f"• {safe(r['phase_name'])}: {safe(r['task_name'])} — {safe(r['status'])}; owner: {safe(r['owner_name'] or 'Unassigned')}" for r in rows)
    try:
        result = service.slack('chat.postMessage', {'channel': channel, 'text': text[:39000],
                               'mrkdwn': False, 'unfurl_links': False, 'unfurl_media': False})
        if not result.get('ts'):
            raise UncertainWrite('Slack status receipt missing; inspect channel before retry')
    except UncertainWrite:
        raise
    except IntegrationError:
        with store.transaction():
            store.db.execute('DELETE FROM slack_status_delivery WHERE run_id=?', (run_id,))
        raise
    with store.transaction():
        store.db.execute("UPDATE slack_status_delivery SET status='sent',message_ts=? WHERE run_id=?", (result['ts'], run_id))
        store.event(run, 'slack_status_sent', 'Recorded task status published to linked Slack channel')
    return {'status': 'sent', 'channel_id': channel, 'message_ts': result['ts']}


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', default='demo-local-worker.db', help='Exact database path; no automatic prefix')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('check', help='Validate Slack bot credentials and team mappings without channel writes')
    status = commands.add_parser('publish', help='Post changed recorded progress to the linked real channel')
    status.add_argument('run_id')
    args = parser.parse_args()
    service = LiveServices()
    try:
        if args.command == 'check':
            auth = service.slack('auth.test', {})
            result = {'authenticated': True, 'workspace': auth.get('team'),
                      'enterprise_team': service.team('Enterprise'), 'growth_team': service.team('Growth')}
        else:
            if not Path(args.db).is_file():
                raise ValueError('Database does not exist')
            store = Store(args.db)
            try:
                result = publish(store, args.run_id, service)
            finally:
                store.db.close()
        print(json.dumps(result))
    except (IntegrationError, ValueError, KeyError) as exc:
        parser.exit(1, str(exc) + '\n')


if __name__ == '__main__':
    main()
