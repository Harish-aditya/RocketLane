"""Explicit live adapters. No adapter silently falls back to simulation."""
import base64
import json
import os
import time
import re
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from .models import Deal


class IntegrationError(Exception):
    pass


class UncertainWrite(IntegrationError):
    """A write may have succeeded. Reconcile before retrying."""


def required(name):
    value = os.getenv(name)
    if not value:
        raise IntegrationError(f'Missing environment variable: {name}')
    return value


def request(method, url, headers, payload=None):
    data = None if payload is None else json.dumps(payload).encode()
    req = Request(url, data=data, method=method, headers={**headers, 'Content-Type': 'application/json'})
    attempts = 3 if method == 'GET' else 1
    for attempt in range(attempts):
        try:
            with urlopen(req, timeout=30) as response:
                return json.load(response)
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            transient = not isinstance(exc, HTTPError) or exc.code == 429 or exc.code >= 500
            if method == 'GET' and transient and attempt < attempts - 1:
                time.sleep(2 ** attempt)
                continue
            # Never include response bodies, authorization headers or customer data in logs.
            error = UncertainWrite if method in {'POST','PUT','PATCH','DELETE'} else IntegrationError
            raise error(f'{method} integration request failed; reconciliation may be required') from exc


class LiveServices:
    def call(self, deal):
        # AE routing is operational configuration, not a mandatory customer email field.
        phone = deal.get('ae_phone') or os.getenv('AE_DEFAULT_PHONE')
        if not phone:
            raise IntegrationError('AE phone routing unavailable; configure AE_DEFAULT_PHONE for the designated AE or supply optional AE Phone')
        try:
            Deal.phone(phone)
        except ValueError as exc:
            raise IntegrationError('Configured AE phone must use E.164 format') from exc
        ae_name = deal.get('ae_name') or os.getenv('AE_DEFAULT_NAME') or 'Account Executive'
        return request('POST', 'https://api.vapi.ai/call',
            {'Authorization': 'Bearer ' + required('VAPI_API_KEY')}, {
                'assistantId': required('VAPI_ASSISTANT_ID'),
                'phoneNumberId': required('VAPI_PHONE_NUMBER_ID'),
                'customer': {'number': phone},
                'assistantOverrides': {'firstMessage': f'Hello {ae_name}. Please confirm the onboarding plan for {deal["customer_name"]}. Say only Enterprise or Growth.'}
            })['id']

    def outcome(self, call_id):
        call = request('GET', f'https://api.vapi.ai/call/{call_id}',
                       {'Authorization': 'Bearer ' + required('VAPI_API_KEY')})
        if call.get('status') != 'ended':
            return None
        messages = call.get('messages') or call.get('artifact', {}).get('messages', [])
        answers = [m.get('message', '') for m in messages if m.get('role') == 'user']
        # Fail closed on multi-turn or contradictory responses. Human review can inspect provider evidence.
        return answers[0] if len(answers) == 1 else 'unresolved'

    def project(self, run):
        plan = run['plan'].upper()
        payload = {
            'projectName': f'{run["deal"]["customer_name"]} onboarding [{run["id"]}]',
            'customer': {'companyName': run['deal']['customer_name']},
            'autoCreateCompany': True,
            'owner': {'emailId': run.get('owner_email') or required('ROCKETLANE_OWNER_EMAIL')},
            'teamMembers': {'members': [{'emailId': run.get('csm_email') or required(plan + '_CSM_EMAIL')}]},
            'startDate': run['start_date'],
            'sources': json.loads(required(plan + '_TEMPLATE_SOURCES')),
            'externalReferenceId': run['id'],
        }
        # Template duration and role mappings must be verified during tenant setup.
        result = request('POST', 'https://api.rocketlane.com/api/1.0/projects',
                         {'api-key': required('ROCKETLANE_API_KEY')}, payload)
        return str(result['projectId'])

    def slack(self, method, payload, accepted_errors=()):
        result = request('POST', 'https://slack.com/api/' + method,
                         {'Authorization': 'Bearer ' + required('SLACK_BOT_TOKEN')}, payload)
        if not result.get('ok'):
            if result.get('error') in accepted_errors:
                return result
            if result.get('error') in {'internal_error', 'fatal_error'}:
                raise UncertainWrite('Slack result uncertain; inspect provider before retry')
            raise IntegrationError('Slack returned ' + result.get('error', 'unknown_error'))
        return result

    def channel(self, name):
        return self.slack('conversations.create', {'name': name, 'is_private': True})['channel']['id']

    def team(self, plan):
        from .models import Plan
        tier = Plan(plan).value.upper()
        specific = required(tier + '_SLACK_TEAM_USER_IDS')
        if not any(value.strip() for value in specific.split(',')):
            raise IntegrationError('Confirmed-plan Slack team mapping must contain at least one member ID')
        users = list(dict.fromkeys(value.strip() for value in
                     (os.getenv('SLACK_SHARED_TEAM_USER_IDS', '') + ',' + specific).split(',') if value.strip()))
        if not users or any(not re.fullmatch(r'[UW][A-Z0-9]+', user) for user in users):
            raise IntegrationError('Configure valid Slack member IDs for the confirmed plan; emails and display names are not user IDs')
        return users

    def invite_member(self, channel, user_id):
        # One user per request allows precise durable progress and safe recovery.
        self.slack('conversations.invite', {'channel': channel, 'users': user_id},
                   accepted_errors=('already_in_channel',))

    def invite_customer(self, channel, email):
        from urllib.parse import urlencode
        from pydantic import TypeAdapter, EmailStr
        email=str(TypeAdapter(EmailStr).validate_python(email))
        mode=os.getenv('SLACK_CUSTOMER_INVITE_MODE','manual')
        if mode not in {'manual','connect'}:
            raise IntegrationError('SLACK_CUSTOMER_INVITE_MODE must be manual or connect')
        result=request('GET','https://slack.com/api/users.lookupByEmail?'+urlencode({'email':email}),
                       {'Authorization':'Bearer '+required('SLACK_BOT_TOKEN')})
        if result.get('ok'):
            user=result['user']
            if user.get('deleted') or user.get('is_bot') or user.get('is_invited_user'):
                return {'status':'manual_required','reason':'Customer account must finish joining or be activated','email':email}
            self.invite_member(channel,user['id'])
            return {'status':'member_added','user_id':user['id'],'email':email}
        error=result.get('error','unknown_error')
        if error not in {'users_not_found','missing_scope'}:
            raise IntegrationError('Slack customer lookup returned '+error)
        if mode=='manual':
            return {'status':'manual_required','email':email,
                    'reason':'Customer email lookup requires users:read.email or a workspace administrator must invite the customer'}
        try:
            invitation=self.slack('conversations.inviteShared',{'channel':channel,'emails':[email],'external_limited':True})
        except UncertainWrite:
            raise
        except IntegrationError as exc:
            if str(exc) in {'Slack returned '+e for e in ('missing_scope','not_paid','restricted_action','not_allowed_for_grid_workspace','user_not_found','not_supported')}:
                return {'status':'manual_required','email':email,'reason':str(exc)}
            raise
        if not invitation.get('invite_id'):
            raise UncertainWrite('Customer invitation receipt missing; inspect Slack before retry')
        return {'status':'invitation_sent','invite_id':invitation['invite_id'],'email':email}

    def topic(self, channel, text):
        self.slack('conversations.setTopic', {'channel': channel, 'topic': text[:250]})

    def welcome(self, channel, text, run_id):
        self.slack('chat.postMessage', {'channel': channel, 'text': text, 'client_msg_id': run_id})


class GmailService:
    def __init__(self, env_path=None):
        self.env_path = env_path
        self.headers = {'Authorization': 'Bearer ' + required('GMAIL_ACCESS_TOKEN')}

    def _refresh(self):
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request as GoogleRequest
        from dotenv import set_key
        try:
            credentials = Credentials(token=os.getenv('GMAIL_ACCESS_TOKEN'),
                refresh_token=required('GMAIL_REFRESH_TOKEN'),
                client_id=required('GMAIL_CLIENT_ID'), client_secret=required('GMAIL_CLIENT_SECRET'),
                token_uri='https://oauth2.googleapis.com/token')
            credentials.refresh(GoogleRequest())
            if not credentials.token:
                raise IntegrationError('Gmail refresh did not return a token')
            os.environ['GMAIL_ACCESS_TOKEN'] = credentials.token
            self.headers = {'Authorization': 'Bearer ' + credentials.token}
            if self.env_path is not None:
                set_key(str(self.env_path), 'GMAIL_ACCESS_TOKEN', credentials.token)
                if credentials.expiry:
                    set_key(str(self.env_path), 'GMAIL_TOKEN_EXPIRY', credentials.expiry.isoformat())
        except Exception:
            raise IntegrationError('Gmail token refresh failed; repeat Gmail authorization') from None

    def _get(self, url):
        try:
            return request('GET', url, self.headers)
        except IntegrationError as exc:
            if not isinstance(exc.__cause__, HTTPError) or exc.__cause__.code != 401:
                raise
            self._refresh()
            return request('GET', url, self.headers)

    def messages(self):
        from urllib.parse import urlencode
        base = 'https://gmail.googleapis.com/gmail/v1/users/me/messages'
        query = {'q': os.getenv('GMAIL_QUERY', 'label:onboarding-new-deal'), 'maxResults': 100}
        while True:
            page = self._get(base + '?' + urlencode(query))
            for item in page.get('messages', []):
                message = self._get(base + '/' + item['id'] + '?format=full')
                def plain(part):
                    if part.get('mimeType') == 'text/plain':
                        data = part.get('body', {}).get('data', '')
                        return base64.urlsafe_b64decode(data + '=' * (-len(data) % 4)).decode('utf-8')
                    return '\n'.join(plain(p) for p in part.get('parts', []))
                yield item['id'], plain(message['payload'])
            if not page.get('nextPageToken'):
                break
            query['pageToken'] = page['nextPageToken']


class DemoServices:
    simulated = True
    def __init__(self, answer='Enterprise'):
        self.answer = answer
        self.calls = self.projects = self.channels = self.welcomes = 0
        self.invited_members = {}
        self.invitation_calls = []
        self.channel_names = {}
        self.customer_invitations = []
    def call(self, deal):
        self.calls += 1
        return f'demo-call-{self.calls}'
    def outcome(self, call_id):
        if isinstance(self.answer, (list, tuple)):
            index = int(call_id.rsplit('-', 1)[1]) - 1
            return self.answer[min(index, len(self.answer) - 1)]
        return self.answer
    def project(self, run):
        self.projects += 1
        return f'demo-project-{run["id"][:8]}'
    def channel(self, name):
        self.channels += 1
        channel = 'demo-' + name
        self.channel_names[channel] = name
        return channel
    def team(self, plan):
        from .models import Plan
        tier = Plan(plan)
        csm = 'UDEMOCSMDEDICATED' if tier.value == 'Enterprise' else 'UDEMOCSMPOOL'
        return ['UDEMOPM', 'UDEMOOWNER', csm]
    def invite_member(self, channel, user_id):
        self.invitation_calls.append((channel, user_id))
        self.invited_members.setdefault(channel, set()).add(user_id)
    def topic(self, channel, text):
        pass
    def invite_customer(self, channel, email):
        self.customer_invitations.append((channel,email))
        return {'status':'simulated','email':email,'invite_id':'demo-customer-invite-'+str(len(self.customer_invitations))}
    def welcome(self, channel, text, run_id):
        self.welcomes += 1


class GmailSlackDemoServices(DemoServices):
    """Real Slack, simulated voice/projects. Requires explicit selection by the operator."""
    real_slack = True

    def __init__(self, store, answer='Growth'):
        super().__init__(answer)
        self.live = LiveServices()
        self.store = store

    def team(self, plan):
        from .models import Plan
        Plan(plan)
        rows = self.store.db.execute('''SELECT role,slack_user_id FROM slack_demo_members
            WHERE channel_id='C0CAQQTDYR3' AND invite_status='added' ''').fetchall()
        roles = {r['role']: r['slack_user_id'] for r in rows}
        if set(roles) != {'CSM','Project Manager','Project Owner'}:
            raise IntegrationError('Verified existing Slack demo role mappings required')
        return [roles[r] for r in ('Project Manager','Project Owner','CSM')]

    def channel(self, name):
        return self.live.channel(name)

    def invite_member(self, channel, user_id):
        self.live.invite_member(channel, user_id)

    def invite_customer(self, channel, email):
        return self.live.invite_customer(channel,email)

    def topic(self, channel, text):
        self.live.topic(channel, 'INTEGRATION TEST | ' + text)

    def welcome(self, channel, text, run_id):
        self.live.welcome(channel,
            'INTEGRATION TEST — real Gmail intake and Slack channel; voice confirmation and Rocketlane project are simulated.\n'
            + text + '\nSlack demo roles: Elsa is CSM (migration and configuration); Star Boy is Project Manager; '
            'Harish Aditya is Project Owner. These accounts represent the mock allocation for this test.', run_id)
