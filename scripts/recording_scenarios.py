"""Prepare isolated recording rehearsals. All integrations are always simulated."""
import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from dotenv import dotenv_values
from app.services import DemoServices, UncertainWrite
from app.store import Store
from app.workflow import Workflow


def preflight():
    values=dotenv_values('.env')
    keys=['GMAIL_REFRESH_TOKEN','GMAIL_CLIENT_ID','GMAIL_CLIENT_SECRET','ROCKETLANE_API_KEY',
          'ENTERPRISE_TEMPLATE_SOURCES','GROWTH_TEMPLATE_SOURCES',
          'ROCKETLANE_TASK_STATUS_VALUES','ROCKETLANE_TASK_URL_TEMPLATE','SLACK_BOT_TOKEN']
    return {'checked_at':datetime.now(ZoneInfo('Asia/Kolkata')).isoformat(),
            'configuration_present':{key:bool(values.get(key)) for key in keys},
            'configuration_is_not_live_verification':True,
            'manual_evidence_required':['Authorized outbound call actually connects and confirms the plan',
                'Real directory members, emails, Slack IDs and spare CSM capacity',
                'Both native Rocketlane templates instantiate the correct tasks, phases and dates',
                'Native Rocketlane +1 PM / +4 Owner rules and delivery evidence',
                'Customer Slack access or clearly disclosed secondary-integration simulation',
                'Gmail automatic approved labeling; subject-only polling is a controlled test',
                'Slack groups:history permission installed for optional delivery monitoring']}


class UncertainProject(DemoServices):
    def project(self,run):
        super().project(run)
        raise UncertainWrite('Simulated timeout after project create request')


def prepare(session,output_root='recordings'):
    if not re.fullmatch(r'[A-Za-z0-9_-]+',session):
        raise ValueError('Session must contain only letters, numbers, hyphens and underscores')
    root=Path(output_root)/session
    root.mkdir(parents=True,exist_ok=False)
    report={'session':session,'all_integrations_simulated':True,'cases':[]}
    scenarios=[('positive-enterprise','Enterprise','complete'),('positive-growth','Growth','complete'),
               ('negative-missing-field','Enterprise','rejected'),
               ('negative-ambiguous','the expensive one','escalated'),
               ('negative-no-usable-answer','unresolved','escalated'),
               ('negative-uncertain-project','Enterprise','reconcile')]
    for label,answer,expected in scenarios:
        body=(f'Customer Name: Recording {label}\nContact Email: recording@customer.example\n'
              f'Salesforce Opportunity Link: https://crm.example/opportunities/{session}-{label}\n')
        if label=='negative-missing-field':
            body=body.replace('Contact Email: recording@customer.example\n','')
        email=root/(label+'.txt');email.write_text(body,encoding='utf-8')
        db=root/('demo-'+label+'.db')
        store=Store(db)
        services=UncertainProject(answer) if label=='negative-uncertain-project' else DemoServices(answer)
        flow=Workflow(store,services,retry_delay=0)
        try:
            run=flow.ingest('rehearsal-'+session+'-'+label,body)
            for _ in range(3):
                run=flow.run(run['id'])
            assert run['state']==expected,(label,run['state'])
            if expected in {'rejected','escalated'}:
                assert services.projects==services.channels==0
            if expected=='complete':
                assert services.projects==services.channels==services.welcomes==1
                assert len(run['added_team_user_ids'])==3
            actions={'calls':services.calls,'projects':services.projects,'channels':services.channels,
                     'invitations':len(services.invitation_calls),'welcomes':services.welcomes}
            detail={'case':label,'run_id':run['id'],'state':run['state'],'plan':run.get('plan'),
                    'duration_days':run.get('duration'),'actions':actions,
                    'database':str(db.resolve()),'email_fixture':str(email.resolve()),
                    'checkpoints':store.db.execute('SELECT COUNT(*) FROM checkpoint_events').fetchone()[0],
                    'audit_events':len(store.events(run['id'])),'simulation':True,
                    'retry_delay_seconds':0}
            if label=='negative-no-usable-answer':
                detail['simulation_detail']='Simulated ended call with no usable response; no actual unanswered phone call is placed.'
            report['cases'].append(detail)
            print(f"SIMULATION | {label}: {run['state']} | calls={services.calls}, projects={services.projects}, channels={services.channels}")
        finally:
            flow.close();store.db.close()
    report_path=root/'scenario_report.json'
    report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Report: '+str(report_path.resolve()))
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--preflight',action='store_true',help='Print configuration booleans only; no network or secret output')
    parser.add_argument('--session',default='rehearsal-'+datetime.now(ZoneInfo('Asia/Kolkata')).strftime('%Y%m%d-%H%M%S'))
    parser.add_argument('--output-root',default='recordings')
    args=parser.parse_args()
    if args.preflight:
        print(json.dumps(preflight(),indent=2))
    else:
        prepare(args.session,args.output_root)
