"""Checkpointed LangGraph orchestration over guarded integration operations."""
import sqlite3
import time
from typing import Any, TypedDict

from .checkpoints import LoggedSqliteSaver
from langgraph.graph import StateGraph, START, END
from langgraph.types import Command, interrupt

from .operations import Operations


class GraphState(TypedDict, total=False):
    run_id: str
    run: dict[str, Any]
    route: str


class Workflow(Operations):
    def __init__(self, store, services, max_calls=3, retry_delay=0, intake_agent=None, communication_agent=None):
        super().__init__(store, services, max_calls, retry_delay, intake_agent, communication_agent)
        checkpoint_path = ':memory:' if store.path == ':memory:' else store.path + '.checkpoints.db'
        self.checkpoint_connection = sqlite3.connect(checkpoint_path, check_same_thread=False)
        self.checkpointer = LoggedSqliteSaver(self.checkpoint_connection, store)
        self.checkpointer.setup()

        intake = StateGraph(GraphState)
        intake.add_node('call_ae', self._action('call'))
        intake.add_node('read_voice_outcome', self._action('outcome'))
        intake.add_conditional_edges(START, lambda s: 'read_voice_outcome' if s['run']['state'] == 'awaiting_voice' else 'call_ae')
        intake.add_edge('call_ae', END)
        intake.add_edge('read_voice_outcome', END)

        communication = StateGraph(GraphState)
        communication.add_node('create_channel', self._action('channel'))
        communication.add_node('add_team_member', self._action('add_member'))
        communication.add_node('set_topic', self._action('topic'))
        communication.add_node('invite_customer', self._action('customer_invite'))
        communication.add_node('send_welcome', self._action('welcome'))
        communication.add_conditional_edges(START, lambda s: {
            'project_created': 'create_channel', 'channel_created': 'add_team_member',
            'team_adding': 'add_team_member',
            'team_added': 'invite_customer' if s['run'].get('customer_invite_required') else 'set_topic',
            'customer_invited':'set_topic',
            'topic_set': 'send_welcome'}[s['run']['state']])
        for node in ['create_channel', 'add_team_member','invite_customer', 'set_topic', 'send_welcome']:
            communication.add_edge(node, END)

        graph = StateGraph(GraphState)
        graph.add_node('load_and_guard', self._load)
        graph.add_node('intake_routing_agent', intake.compile())
        graph.add_node('provision_project', self._action('project'))
        graph.add_node('communication_agent', communication.compile())
        graph.add_node('human_reconciliation', self._human)
        graph.add_edge(START, 'load_and_guard')
        graph.add_conditional_edges('load_and_guard', lambda s: s['route'], {
            'intake': 'intake_routing_agent', 'project': 'provision_project',
            'communication': 'communication_agent', 'human': 'human_reconciliation', 'stop': END})
        for node in ['intake_routing_agent', 'provision_project', 'communication_agent']:
            graph.add_conditional_edges(node, lambda s: 'human' if s['run']['state'] == 'reconcile' else 'stop',
                                        {'human': 'human_reconciliation', 'stop': END})
        graph.add_edge('human_reconciliation', END)
        self.graph = graph.compile(checkpointer=self.checkpointer)

    @staticmethod
    def config(run_id):
        return {'configurable': {'thread_id': run_id}}

    def _load(self, state):
        with self.store.transaction():
            run = self.store.get(state['run_id'])
            if run['state'] == 'reconcile' and not run.get('pending_action'):
                # Migrate uncertain-write records produced by the former orchestrator.
                action = (run.get('error') or '').partition(':')[0]
                if action in {'call', 'project', 'channel', 'add_member','customer_invite', 'topic', 'welcome'}:
                    run['pending_action'] = action
                    self.store.save(run)
            if run['state'].endswith('_pending'):
                run['pending_action'] = run.get('pending_action') or run['state'].removesuffix('_pending')
                run.update(state='reconcile', error='Interrupted remote write; inspect provider before resuming')
                self.store.event(run, 'escalation', run['error'])
                self.store.save(run)
        route = {
            'validated': 'intake', 'retry_voice': 'intake', 'awaiting_voice': 'intake',
            'confirmed': 'project', 'awaiting_capacity': 'project', 'project_created': 'communication',
            'channel_created': 'communication', 'team_adding': 'communication',
            'team_added': 'communication','customer_invited':'communication','customer_invite_manual':'stop', 'topic_set': 'communication',
            'reconcile': 'human', 'rejected': 'stop', 'complete': 'stop', 'escalated': 'stop',
        }.get(run['state'])
        if route is None:
            raise ValueError('Unknown persisted workflow state')
        if time.time() < run.get('next_attempt_at', 0):
            route = 'stop'
        if run.get('slack_mode')=='real_slack_demo' and not getattr(self.services,'real_slack',False):
            route='stop'  # A pure simulation worker cannot complete real Slack actions.
        return {'run': run, 'route': route}

    def _action(self, action):
        def node(state):
            return {'run': self._perform(state['run_id'], action)}
        return node

    def _human(self, state):
        decision = interrupt({'run_id': state['run_id'], 'reason': state['run'].get('error'),
                              'pending_action': state['run'].get('pending_action'),
                              'required': 'Provider evidence and matching resource ID; use reconcile command'})
        if not isinstance(decision, dict):
            raise ValueError('Reconciliation payload must be an object')
        run = self._apply_reconciliation(state['run_id'], decision.get('target'),
                                          decision.get('evidence', ''), decision.get('resource_id'))
        return {'run': run}

    def step(self, run_id):
        run = self.store.get(run_id)
        snapshot = self.graph.get_state(self.config(run_id))
        if snapshot.tasks and any(task.interrupts for task in snapshot.tasks):
            if run['state'] != 'reconcile' and run.get('reconciliation_receipt'):
                self.graph.invoke(Command(resume=run['reconciliation_receipt']), self.config(run_id))
            else:
                return run
        self.graph.invoke({'run_id': run_id}, self.config(run_id))
        return self.store.get(run_id)

    def reconcile(self, run_id, target, evidence, resource_id=None):
        if self.store.get(run_id)['state'] != 'reconcile':
            raise ValueError('Only uncertain writes can be reconciled')
        self.step(run_id)
        # Validate before checkpointing a resume value. An invalid persisted resume
        # otherwise replays on retries and can poison the pending interrupt.
        self._validate_reconciliation(run_id, target, evidence, resource_id)
        self.graph.invoke(Command(resume={'target': target, 'evidence': evidence,
                                          'resource_id': resource_id}), self.config(run_id))
        return self.store.get(run_id)

    def run(self, run_id, max_steps=16):
        """Advance until complete, waiting on a call, retry delay, or operator input."""
        for _ in range(max_steps):
            before = self.store.get(run_id)
            after = self.step(run_id)
            if after == before or after['state'] in {
                'complete', 'rejected', 'escalated', 'reconcile', 'retry_voice','customer_invite_manual'
            }:
                return after
        return self.store.get(run_id)

    def close(self):
        self.checkpoint_connection.close()
