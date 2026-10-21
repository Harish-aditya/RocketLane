import argparse
import json
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from .services import DemoServices, LiveServices, GmailService, GmailSlackDemoServices
from .store import Store
from .workflow import Workflow
from .worker import serve
from .model_config import agents_for_model


def main():
    env_path = Path(__file__).resolve().parents[1] / '.env'
    load_dotenv(env_path, override=False)
    parser = argparse.ArgumentParser(description='Rocketlane onboarding automation')
    parser.add_argument('--db', default='onboarding.db')
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--live', action='store_true', help='Enable real external side effects')
    modes.add_argument('--gmail-demo', action='store_true', help='Read real Gmail; simulate all voice, project and Slack actions')
    modes.add_argument('--gmail-slack-demo', action='store_true', help='Real Gmail and Slack; simulate voice and Rocketlane projects')
    parser.add_argument('--model', help='Optional provider:model for model-backed extraction/welcome; requires optional packages')
    sub = parser.add_subparsers(dest='command', required=True)
    ingest = sub.add_parser('ingest')
    ingest.add_argument('file')
    ingest.add_argument('--message-id', required=True)
    sub.add_parser('poll-gmail')
    sub.add_parser('advance', help='Advance each active workflow by one step; run with a single worker')
    worker = sub.add_parser('worker', help='Continuously poll Gmail (live mode) and advance due graph runs')
    worker.add_argument('--interval', type=int, default=15, choices=range(1, 61), metavar='1-60')
    worker.add_argument('--once', action='store_true')
    worker.add_argument('--answer', default='Enterprise', help='Simulated AE response for demo/gmail-demo mode')
    run = sub.add_parser('run', help='Advance a run until it needs a provider result or operator input')
    run.add_argument('run_id')
    sub.add_parser('graph', help='Print the implemented graph as Mermaid')
    checkpoint = sub.add_parser('checkpoint', help='Inspect persisted graph status without executing nodes')
    checkpoint.add_argument('run_id')
    step = sub.add_parser('step')
    step.add_argument('run_id')
    step.add_argument('--answer', default='Enterprise', help='Demo only')
    show = sub.add_parser('show')
    show.add_argument('run_id')
    audit = sub.add_parser('audit')
    audit.add_argument('run_id')
    reconcile = sub.add_parser('reconcile')
    reconcile.add_argument('run_id')
    reconcile.add_argument('target')
    reconcile.add_argument('--resource-id')
    reconcile.add_argument('--evidence', required=True)
    verify = sub.add_parser('verify-migration')
    verify.add_argument('run_id')
    verify.add_argument('--verifier', required=True)
    verify.add_argument('--evidence', required=True)
    customer=sub.add_parser('record-customer-invite',help='Record verified administrator invitation for a waiting customer')
    customer.add_argument('run_id');customer.add_argument('--email',required=True)
    customer.add_argument('--status',choices=['invitation_sent','member_added'],required=True)
    customer.add_argument('--resource-id',required=True);customer.add_argument('--evidence',required=True)
    retry_customer=sub.add_parser('retry-customer-invite',help='Retry a definitive customer invitation handoff after permissions are fixed')
    retry_customer.add_argument('run_id')
    args = parser.parse_args()
    # Prevent a simulated result from entering a live workflow database.
    path = Path(args.db)
    db_path = args.db if args.live or args.db == ':memory:' else str(path.with_name('demo-' + path.name))
    store = Store(db_path)
    intake, communication = agents_for_model(args.model)
    services = (LiveServices() if args.live else GmailSlackDemoServices(store,getattr(args,'answer','Enterprise'))
                if args.gmail_slack_demo else DemoServices(getattr(args,'answer','Enterprise')))
    flow = Workflow(store, services,
                    retry_delay=60 if args.live else 0, intake_agent=intake, communication_agent=communication)
    if args.command == 'ingest':
        result = flow.ingest(args.message_id, Path(args.file).read_text(encoding='utf-8'))
    elif args.command == 'poll-gmail':
        if not (args.live or args.gmail_demo or args.gmail_slack_demo):
            parser.error('poll-gmail requires --live or --gmail-demo')
        result = [flow.ingest(mid, body) for mid, body in GmailService(env_path=env_path).messages()]
    elif args.command == 'step':
        result = flow.step(args.run_id)
    elif args.command == 'run':
        result = flow.run(args.run_id)
    elif args.command == 'worker':
        mode = 'LIVE' if args.live else ('REAL_GMAIL_AND_SLACK_SIMULATED_VOICE_PROJECT' if args.gmail_slack_demo else 'REAL_GMAIL_SIMULATED_DOWNSTREAM' if args.gmail_demo else 'DEMO')
        def report(value):
            # Ongoing logs contain run references/status, not complete customer emails.
            print(json.dumps({'timestamp': datetime.now(timezone.utc).isoformat(), 'mode': mode,
                              'ingested': value['ingested'],
                              'email_results': value['email_results'],
                              'runs': [{'id': r['id'], 'state': r['state'], 'plan': r.get('plan'),
                                        'team_members_added': len(r.get('added_team_user_ids', [])),
                                        'invalid_fields': r.get('error') if r['state'] == 'rejected' else None}
                                       for r in value['runs']], 'errors': value['errors']}), flush=True)
        try:
            import os
            print(json.dumps({'event': 'worker_start', 'mode': mode, 'interval_seconds': args.interval,
                              'gmail_query': os.getenv('GMAIL_QUERY','label:onboarding-new-deal') if args.live or args.gmail_demo or args.gmail_slack_demo else None,
                              'simulated_answer': None if args.live else args.answer}), flush=True)
            serve(flow, GmailService(env_path=env_path) if args.live or args.gmail_demo or args.gmail_slack_demo else None,
                  args.interval, args.once, emit=report)
        except KeyboardInterrupt:
            pass
        finally:
            flow.close()
            store.db.close()
        return
    elif args.command == 'graph':
        print(flow.graph.get_graph(xray=True).draw_mermaid())
        flow.close()
        store.db.close()
        return
    elif args.command == 'checkpoint':
        snapshot = flow.graph.get_state(flow.config(args.run_id))
        result = {'thread_id': args.run_id, 'next': snapshot.next, 'values': snapshot.values,
                  'interrupts': [item.value for task in snapshot.tasks for item in task.interrupts]}
    elif args.command == 'advance':
        ids = [r['id'] for r in store.db.execute("SELECT id FROM runs WHERE state NOT IN ('complete','rejected','escalated','reconcile','customer_invite_manual')")]
        result = [flow.step(run_id) for run_id in ids]
    elif args.command=='retry-customer-invite':
        flow.retry_customer_invite(args.run_id)
        result=flow.run(args.run_id)
    elif args.command=='record-customer-invite':
        result=flow.record_customer_invite(args.run_id,args.email,args.status,args.resource_id,args.evidence)
    elif args.command == 'show':
        result = store.get(args.run_id)
    elif args.command == 'audit':
        result = store.events(args.run_id)
    elif args.command == 'reconcile':
        result = flow.reconcile(args.run_id, args.target, args.evidence, args.resource_id)
    else:
        result = flow.verify_migration(args.run_id, args.verifier, args.evidence)
    print(json.dumps(result, indent=2))
    flow.close()
    store.db.close()


if __name__ == '__main__':
    main()
