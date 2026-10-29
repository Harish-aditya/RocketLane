"""Dedicated Rocketlane integration agent. No language model chooses API writes."""
import argparse
import json
import os
from pathlib import Path
from urllib.parse import urlencode

from .services import IntegrationError, UncertainWrite, required


class RocketlaneAgent:
    """Typed, bounded tools shared by setup and guarded delivery workflows."""

    @staticmethod
    def configuration(name):
        try:
            return json.loads(required(name))
        except (ValueError, TypeError):
            raise IntegrationError('Invalid Rocketlane JSON configuration: ' + name) from None

    def create_project(self, run):
        if run.get('plan') not in {'Enterprise', 'Growth'}:
            raise IntegrationError('Confirmed Enterprise or Growth plan required')
        plan = run['plan'].upper()
        sources = self.configuration(plan + '_TEMPLATE_SOURCES')
        if not isinstance(sources, list) or not sources:
            raise IntegrationError('Verified nonempty Rocketlane template sources required')
        payload = {
            'projectName': f'{run["deal"]["customer_name"]} onboarding [{run["id"]}]',
            'customer': {'companyName': run['deal']['customer_name']},
            'autoCreateCompany': True,
            'owner': {'emailId': run.get('owner_email') or required('ROCKETLANE_OWNER_EMAIL')},
            'teamMembers': {'members': [{'emailId': run.get('csm_email') or required(plan + '_CSM_EMAIL')}]},
            'startDate': run['start_date'],
            'sources': sources,
            'externalReferenceId': run['id'],
        }
        result = self.rocket('POST', 'projects', payload)
        project_id = result.get('projectId') if isinstance(result, dict) else None
        if isinstance(project_id, bool) or not str(project_id or '').isdigit():
            raise UncertainWrite('Rocketlane project receipt missing; inspect provider before retry')
        return str(project_id)

    def project(self, project_id):
        if isinstance(project_id, bool) or not str(project_id).isdigit():
            raise IntegrationError('Real Rocketlane project ID required')
        return self.rocket('GET', 'projects/' + str(project_id) + '?includeAllFields=true')

    def rocket(self,method,path,payload=None):
        from .services import request
        return request(method,'https://api.rocketlane.com/api/1.0/'+path,
                       {'api-key':required('ROCKETLANE_API_KEY')},payload)

    def tasks(self,project):
        if not str(project).isdigit():
            raise IntegrationError('Real Rocketlane project ID required')
        params={'projectId.eq':project,'includeAllFields':'true','limit':100}
        tasks,cursors=[],set()
        for _ in range(100):
            result=self.rocket('GET','tasks?'+urlencode(params))
            if not isinstance(result,dict) or not isinstance(result.get('data'),list):
                raise IntegrationError('Unexpected Rocketlane task response')
            tasks.extend(result['data'])
            pagination=result.get('pagination') or {}
            cursor=pagination.get('nextPageToken')
            if not cursor:
                if pagination.get('hasMore'):
                    raise IntegrationError('Rocketlane pagination token missing; snapshot incomplete')
                return tasks
            if cursor in cursors:
                raise IntegrationError('Rocketlane pagination loop')
            cursors.add(cursor);params['pageToken']=cursor
        raise IntegrationError('Rocketlane page limit reached')

    def task(self,task_id):
        if not str(task_id).isdigit():
            raise IntegrationError('Native task ID must be numeric')
        return self.rocket('GET','tasks/'+str(task_id)+'?includeAllFields=true')

    def update(self,task_id,status,progress):
        if (status not in {'not_started','in_progress','blocked','completed'} or isinstance(progress,bool)
                or not isinstance(progress,int) or not 0<=progress<=100
                or (status=='completed') != (progress==100) or (status=='not_started' and progress!=0)):
            raise IntegrationError('Invalid Rocketlane task status or progress')
        mappings=self.configuration('ROCKETLANE_TASK_STATUS_VALUES')
        if not isinstance(mappings,dict) or status not in mappings or mappings[status] is None or isinstance(mappings[status],bool):
            raise IntegrationError('Verified tenant task status values required')
        if not str(task_id).isdigit():
            raise IntegrationError('Native task ID must be numeric')
        self.rocket('PUT','tasks/'+str(task_id),{'status':{'value':mappings[status]},
                                               'progress':progress,'atRisk':status=='blocked'})


def main():
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[1] / '.env')
    parser = argparse.ArgumentParser(description='Rocketlane agent diagnostics; remote operations here are read-only')
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('config', help='Show configuration presence without revealing credentials')
    inspect = sub.add_parser('inspect-project', help='Read a real project and its task count; never creates or updates it')
    inspect.add_argument('project_id')
    args = parser.parse_args()
    if args.command == 'config':
        keys = ['ROCKETLANE_API_KEY', 'ROCKETLANE_OWNER_EMAIL', 'ENTERPRISE_TEMPLATE_SOURCES',
                'GROWTH_TEMPLATE_SOURCES', 'ROCKETLANE_TASK_STATUS_VALUES']
        print(json.dumps({'agent': 'Rocketlane', 'configuration_present': {k: bool(os.getenv(k)) for k in keys},
                          'note': 'Presence does not verify credentials, templates or tenant mappings.'}, indent=2))
    else:
        agent = RocketlaneAgent()
        project = agent.project(args.project_id)
        tasks = agent.tasks(args.project_id)
        print(json.dumps({'agent': 'Rocketlane', 'project_id': args.project_id,
                          'project_name': project.get('projectName'), 'task_count': len(tasks), 'read_only': True}, indent=2))


if __name__ == '__main__':
    main()
