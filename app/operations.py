import hashlib
import json
import time
from datetime import datetime
from zoneinfo import ZoneInfo
from pydantic import ValidationError
from .agents import IntakeAgent, CommunicationAgent
from .models import explicit_plan
from .plans import plan_config
from .services import IntegrationError, UncertainWrite


class Operations:
    def __init__(self, store, services, max_calls=3, retry_delay=0, intake_agent=None, communication_agent=None):
        if max_calls < 1 or retry_delay < 0:
            raise ValueError('max_calls must be positive and retry_delay nonnegative')
        self.store, self.services, self.max_calls = store, services, max_calls
        self.retry_delay = retry_delay
        self.intake_agent = intake_agent or IntakeAgent()
        self.communication_agent = communication_agent or CommunicationAgent()

    def ingest(self, message_id, body):
        if not message_id.strip():
            raise ValueError('message_id required')
        try:
            deal = self.intake_agent.parse(body).model_dump(mode='json')
            opportunity = deal['opportunity_url'].rstrip('/')
            error = None
        except ValidationError as exc:
            deal, opportunity = None, None
            error = ', '.join('.'.join(map(str, e['loc'])) for e in exc.errors())
        run_id = hashlib.sha256((opportunity or message_id).encode()).hexdigest()[:32]
        with self.store.transaction():
            existing = self.store.db.execute('SELECT id FROM runs WHERE message_id=? OR opportunity=?', (message_id, opportunity)).fetchone()
            if existing:
                return self.store.get(existing['id'])
            run = {'id': run_id, 'message_id': message_id, 'deal': deal,
                   'created_at': datetime.now(ZoneInfo('UTC')).isoformat(),
                   'simulation': bool(getattr(self.services, 'simulated', False)),
                   'state': 'rejected' if error else 'validated', 'call_attempts': 0,
                   'project_id': None, 'channel_id': None, 'migration_verified': False,
                   'error': error}
            run['customer_invite_required'] = True
            run['voice_mode'] = 'real' if getattr(self.services, 'real_voice', False) else 'simulated'
            self.store.db.execute('INSERT INTO runs VALUES(?,?,?,?,?)', (run_id, message_id, opportunity, run['state'], json.dumps(run)))
            self.store.project_status(run)
            self.store.event(run, 'intake', 'Missing/invalid fields: ' + error if error else 'Mandatory fields validated; opportunity deduplicated')
        return run

    def _perform(self, run_id, action):
        if action == 'project':
            from .team_directory import allocate, seed
            if getattr(self.services, 'simulated', False):
                seed(self.store)
            assignment = allocate(self.store, run_id, live=not getattr(self.services, 'simulated', False))
            if assignment is None:
                with self.store.transaction():
                    run = self.store.get(run_id)
                    if run['state'] != 'awaiting_capacity':
                        run.update(state='awaiting_capacity', error='No eligible CSM/team capacity; request queued')
                        self.store.save(run)
                        self.store.event(run, 'capacity_wait', run['error'])
                return self.store.get(run_id)
        allowed = {'call': {'validated', 'retry_voice'}, 'outcome': {'awaiting_voice'},
                   'project': {'confirmed', 'awaiting_capacity'}, 'channel': {'project_created'},
                   'add_member': {'channel_created', 'team_adding'},
                   'customer_invite': {'team_added'},
                   'topic': {'team_added','customer_invited'}, 'welcome': {'topic_set'}}
        with self.store.transaction():
            run = self.store.get(run_id)
            if run['state'] not in allowed[action]:
                raise ValueError('Action no longer matches persisted state')
            if action in {'project', 'channel', 'add_member', 'customer_invite', 'topic', 'welcome'} and not run.get('plan'):
                raise ValueError('Explicit voice plan required')
            if action in {'channel', 'add_member', 'customer_invite', 'topic', 'welcome'} and not run.get('project_id'):
                raise ValueError('Project required')
            if action in {'add_member', 'customer_invite', 'topic', 'welcome'} and not run.get('channel_id'):
                raise ValueError('Channel required')
            if action in {'topic','welcome'} and run.get('customer_invite_required') and (
                    run.get('customer_invitation',{}).get('status') not in {'member_added','invitation_sent','simulated'}):
                raise ValueError('Customer invitation must be resolved before announcing setup readiness')
            if action == 'call':
                run['call_attempts'] += 1
            if action == 'add_member':
                if 'team_user_ids' not in run:  # Existing channels from earlier versions.
                    run['team_user_ids'] = self.services.team(run['plan'])
                remaining = [user for user in run['team_user_ids'] if user not in run.get('added_team_user_ids', [])]
                if not remaining:
                    run['state'] = 'team_added'
                    self.store.save(run)
                    return run
                run['pending_member_id'] = remaining[0]
            if action != 'outcome':
                run['state'] = action + '_pending'
                run['pending_action'] = action
            self.store.event(run, action + '_intent', 'Persisted action before provider write; validated current-state preconditions',
                             inputs={'run_id': run_id, 'action': action, 'call_id': run.get('call_id'),
                                     'project_id': run.get('project_id'), 'channel_id': run.get('channel_id'),
                                     'member_id': run.get('pending_member_id'),
                                     'customer_email': run['deal']['contact_email'] if action=='customer_invite' else None,
                                     'plan': run.get('plan'), 'attempt': run['call_attempts']})
            self.store.save(run)
        try:
            if action == 'call':
                run['call_id'] = self.services.call(run['deal'])
                run['call_started_at'] = time.time()
                run['state'] = 'awaiting_voice'
            elif action == 'outcome':
                answer = self.services.outcome(run['call_id'])
                if answer is None:
                    if time.time() - run.get('call_started_at', 0) < 600:
                        with self.store.transaction():
                            self.store.event(run, 'outcome_result', 'Provider call still active; no redial')
                        return run
                    run['state'] = 'escalated'
                    run['error'] = 'Call unresolved after 10 minutes; inspect provider before redial'
                    with self.store.transaction():
                        self.store.save(run)
                        self.store.event(run, 'voice_timeout', run['error'])
                    return run
                plan = explicit_plan(answer)
                run['voice_evidence'] = {'call_id': run['call_id'], 'confirmed_plan': plan.value if plan else None,
                                         'answer_sha256': hashlib.sha256(str(answer).encode()).hexdigest()}
                if plan:
                    config = plan_config(plan.value)
                    run.update(plan=plan.value, duration=config['duration_days'],
                               csm_mode=config['csm_mode'], phases=config['phases'],
                               start_date=datetime.now(ZoneInfo('Asia/Kolkata')).date().isoformat(), state='confirmed')
                    run.pop('confirmation_request', None)
                else:
                    run['state'] = 'retry_voice' if run['call_attempts'] < self.max_calls else 'escalated'
                    run['next_attempt_at'] = time.time() + self.retry_delay
                    run['confirmation_request'] = (f'Please explicitly confirm Enterprise or Growth for '
                                                   f'{run["deal"]["customer_name"]}. Descriptions such as '
                                                   '"the expensive one" do not confirm a plan.')
            elif action == 'project':
                run['project_id'] = self.services.project(run)
                run['state'] = 'project_created'
            elif action == 'channel':
                # Persist the approved draft with the created resource so retries do
                # not ask a model to generate a different message after channel creation.
                name, text = self.communication_agent.content(run)
                if getattr(self.services, 'real_slack', False):
                    run['team_user_ids'] = self.services.team(run['plan'])
                    run['slack_mode'] = 'real_slack_demo'
                elif run.get('csm_id'):
                    from .team_directory import assigned_slack_team
                    run['team_user_ids'] = assigned_slack_team(self.store, run, getattr(self.services, 'simulated', False))
                else:
                    run['team_user_ids'] = self.services.team(run['plan'])
                run['added_team_user_ids'] = []
                run['channel_id'] = self.services.channel(name)
                run['welcome_text'] = text
                run['state'] = 'channel_created'
            elif action == 'add_member':
                user = run['pending_member_id']
                self.services.invite_member(run['channel_id'], user)
                run.setdefault('added_team_user_ids', []).append(user)
                run.pop('pending_member_id', None)
                run['state'] = 'team_added' if set(run['team_user_ids']) <= set(run['added_team_user_ids']) else 'team_adding'
            elif action == 'topic':
                self.services.topic(run['channel_id'], f'{run["deal"]["customer_name"]} | {run["plan"]} onboarding | Project {run["project_id"]}')
                run['state'] = 'topic_set'
            elif action == 'customer_invite':
                receipt=self.services.invite_customer(run['channel_id'],run['deal']['contact_email'])
                if receipt.get('status') not in {'member_added','invitation_sent','simulated','manual_required'}:
                    raise UncertainWrite('Customer invitation outcome missing')
                if receipt.get('email')!=run['deal']['contact_email']:
                    raise UncertainWrite('Customer invitation recipient mismatch; inspect Slack')
                receipt_field='user_id' if receipt['status']=='member_added' else 'invite_id'
                if receipt['status']!='manual_required' and not receipt.get(receipt_field):
                    raise UncertainWrite('Customer invitation reference missing; inspect Slack')
                if receipt['status']=='simulated' and (not getattr(self.services,'simulated',False) or getattr(self.services,'real_slack',False) or run.get('slack_mode')=='real_slack_demo'):
                    raise IntegrationError('Live customer invitations cannot be reported as simulated success')
                run['customer_invitation']={**receipt,'channel_id':run['channel_id']}
                run['state']='customer_invite_manual' if receipt['status']=='manual_required' else 'customer_invited'
            elif action == 'welcome':
                text = run.get('welcome_text')
                if text is None:  # Compatibility with earlier ledger entries.
                    _, text = self.communication_agent.content(run)
                self.services.welcome(run['channel_id'], text, run['id'])
                run['state'] = 'complete'
            run['error'] = ('Customer Slack invitation requires administrator action: '+run['customer_invitation'].get('reason','')
                            if run['state']=='customer_invite_manual' else None)
        except UncertainWrite:
            run.update(state='reconcile', error=f'{action}: uncertain write; inspect provider and reconcile')
        except IntegrationError as exc:
            run.update(state='escalated', error=str(exc))
        if run['state'] not in {'reconcile'}:
            run.pop('pending_action', None)
        with self.store.transaction():
            if action == 'outcome' and run.get('confirmation_request'):
                self.store.event(run, 'plan_clarification', run['confirmation_request'])
            self.store.save(run)
            self.store.event(run, action + '_result', run['error'] or f'Outcome: {run["state"]}',
                             outputs={key: run.get(key) for key in ['state', 'call_id', 'plan', 'project_id',
                                                                  'channel_id', 'voice_evidence', 'added_team_user_ids','customer_invitation']})
        if action=='welcome' and run['state']=='complete' and run.get('csm_id') and (
                getattr(self.services,'real_slack',False) or not getattr(self.services,'simulated',False)):
            from .delivery import configure
            import os
            try:
                pm,owner,csm=run['team_user_ids']
                configure(self.store,run_id,'local_demo' if run.get('simulation') else 'live',
                          csm,pm,owner,os.getenv('ROCKETLANE_TASK_URL_TEMPLATE') or None)
            except (ValueError,IntegrationError):
                with self.store.transaction():
                    self.store.event(run,'delivery_monitor_setup_error','Channel ready; delivery monitor configuration requires operator attention')
        return run

    def retry_customer_invite(self,run_id):
        with self.store.transaction():
            run=self.store.get(run_id)
            if run['state']!='customer_invite_manual':
                raise ValueError('Only a definitive manual invitation handoff can retry; uncertain writes require reconciliation')
            run.update(state='team_added',error=None)
            run.pop('customer_invitation',None)
            self.store.save(run)
            self.store.event(run,'customer_invite_retry_requested','Retry after configuration change; preserve existing channel and team')
        return run

    def record_customer_invite(self,run_id,email,status,resource_id,evidence):
        """Operator receipt for the specific customer/channel; no invitation is sent here."""
        import re
        if status not in {'invitation_sent','member_added'} or not evidence.strip() or not resource_id.strip():
            raise ValueError('Invitation status, provider reference and evidence required')
        if status=='member_added' and (not re.fullmatch(r'[UW][A-Z0-9]+',resource_id) or resource_id.startswith('UDEMO')):
            raise ValueError('Actual customer Slack member ID required')
        with self.store.transaction():
            run=self.store.get(run_id)
            if run['state']!='customer_invite_manual' or email.casefold()!=run['deal']['contact_email'].casefold():
                raise ValueError('Receipt must match the waiting run and customer email')
            run['customer_invitation']={'status':status,'email':run['deal']['contact_email'],
                                       'channel_id':run['channel_id'],'source':'human_receipt',
                                       'user_id' if status=='member_added' else 'invite_id':resource_id}
            run.update(state='customer_invited',error=None)
            self.store.save(run)
            self.store.event(run,'customer_invite_operator_receipt',evidence)
        return run

    def _validate_reconciliation(self, run_id, target, evidence, resource_id=None):
        allowed = {'awaiting_voice': 'call_id', 'project_created': 'project_id',
                   'channel_created': 'channel_id', 'member_added': 'pending_member_id',
                   'customer_invited':'customer_invite_id',
                   'topic_set': None, 'complete': None}
        if target not in allowed or not isinstance(evidence, str) or not evidence.strip():
            raise ValueError('Valid target and provider evidence required')
        run = self.store.get(run_id)
        if run['state'] != 'reconcile':
            raise ValueError('Only uncertain writes can be reconciled')
        expected = {'call': 'awaiting_voice', 'project': 'project_created',
                    'channel': 'channel_created', 'add_member': 'member_added',
                    'customer_invite':'customer_invited',
                    'topic': 'topic_set', 'welcome': 'complete'}
        if expected.get(run.get('pending_action')) != target:
            raise ValueError('Reconciliation target must match the interrupted action')
        field = allowed[target]
        if field and (not isinstance(resource_id, str) or not resource_id.strip()):
            raise ValueError('Provider resource ID required')
        if target == 'member_added' and resource_id != run.get('pending_member_id'):
            raise ValueError('Member ID must match the interrupted invitation')
        if target in {'project_created', 'channel_created', 'member_added','customer_invited', 'topic_set', 'complete'} and not run.get('plan'):
            raise ValueError('Voice confirmation required')
        if target in {'channel_created', 'member_added','customer_invited', 'topic_set', 'complete'} and not run.get('project_id'):
            raise ValueError('Project required')
        if target in {'member_added','customer_invited', 'topic_set', 'complete'} and not run.get('channel_id'):
            raise ValueError('Channel required')
        return run, field

    def _apply_reconciliation(self, run_id, target, evidence, resource_id=None):
        with self.store.transaction():
            current = self.store.get(run_id)
            receipt = {'target': target, 'evidence': evidence, 'resource_id': resource_id}
            # The operator update can commit just before a process dies while
            # checkpointing its result. Replaying that exact receipt is safe.
            if current.get('reconciliation_receipt') == receipt and current['state'] != 'reconcile':
                return current
            run, field = self._validate_reconciliation(run_id, target, evidence, resource_id)
            if field:
                run[field] = resource_id
            if target == 'awaiting_voice':
                run['call_started_at'] = time.time()
            if target=='customer_invited':
                run['customer_invitation']={'status':'invitation_sent','invite_id':resource_id,
                                           'email':run['deal']['contact_email'],'channel_id':run['channel_id'],'source':'human_reconciliation'}
            if target == 'member_added':
                run.setdefault('added_team_user_ids', []).append(resource_id)
                run.pop('pending_member_id', None)
                state = 'team_added' if set(run['team_user_ids']) <= set(run['added_team_user_ids']) else 'team_adding'
            else:
                state = target
            run.update(state=state, error=None)
            run['reconciliation_receipt'] = receipt
            run.pop('pending_action', None)
            self.store.save(run)
            self.store.event(run, 'operator_reconciliation', evidence)
        return run

    def verify_migration(self, run_id, verifier, evidence):
        if not verifier.strip() or not evidence.strip():
            raise ValueError('Verifier and evidence required')
        with self.store.transaction():
            run = self.store.get(run_id)
            if not run.get('project_id'):
                raise ValueError('Project required')
            run['migration_verified'] = True
            self.store.save(run)
            self.store.event(run, 'migration_verification', f'{verifier}: {evidence}')
        return run
