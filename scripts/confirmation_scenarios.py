"""Three free, fully simulated voice/project/Slack cases. No live APIs are used."""
import argparse
import json
from pathlib import Path

from app.services import DemoServices
from app.store import Store
from app.workflow import Workflow


def scenario(response):
    services = DemoServices(response)
    store = Store(':memory:')
    flow = Workflow(store, services)
    try:
        body = Path(__file__).resolve().parents[1].joinpath('examples/minimal_deal.txt').read_text()
        run = flow.run(flow.ingest('simulated-' + response, body)['id'])
        names = {'UDEMOMOCKPM': 'Project Manager', 'UDEMOMOCKOWNER': 'Project Owner',
                 'UDEMOMOCKCSM01': 'Dedicated CSM' if run.get('plan') == 'Enterprise' else 'Pooled CSM representative'}
        return {
            'simulation': True, 'response': response, 'state': run['state'],
            'confirmed_plan': run.get('plan'), 'duration_days': run.get('duration'),
            'csm_mode': run.get('csm_mode'), 'project_id': run.get('project_id'),
            'slack_channel': services.channel_names.get(run.get('channel_id')),
            'team_added': [names.get(user, user) for user in run.get('added_team_user_ids', [])],
            'confirmation_required': run.get('confirmation_request'),
            'actions': {'calls': services.calls, 'projects': services.projects, 'channels': services.channels,
                        'member_invitations': len(services.invitation_calls), 'welcome_messages': services.welcomes},
            'audit_actions': [event['action'] for event in store.events(run['id'])],
        }
    finally:
        flow.close()
        store.db.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path('deliverables/simulated_confirmation_cases.json'))
    args = parser.parse_args()
    report = [scenario(answer) for answer in ['Enterprise', 'Growth', 'the expensive one']]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    for result in report:
        print(f'{result["response"]!r} -> {result["state"]}; plan={result["confirmed_plan"]}; '
              f'team={", ".join(result["team_added"]) or "none"}')
        if result['confirmation_required']:
            print('  Clarification: ' + result['confirmation_required'])
    print('All services simulated. Report: ' + str(args.output))


if __name__ == '__main__':
    main()
