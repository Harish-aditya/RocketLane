"""Continuous Slack delivery monitoring and guarded Rocketlane synchronization."""
import argparse
import json
import os
import re
import sqlite3
import time
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import TypedDict
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
from .services import request, required, IntegrationError, UncertainWrite, LiveServices
from .worker import single_worker
from .checkpoints import LoggedSqliteSaver

STATES = {'not_started','in_progress','blocked','completed'}


def initialize(db):
    columns = {r[1] for r in db.execute('PRAGMA table_info(onboarding_tasks)')}
    for name, kind in [('native_task_id','TEXT'),('due_date','TEXT'),('progress','INTEGER'),
                       ('last_progress_at','TEXT'),('synced_at','TEXT'),('blocker_note','TEXT')]:
        if name not in columns:
            db.execute(f'ALTER TABLE onboarding_tasks ADD COLUMN {name} {kind}')
    db.executescript('''
        CREATE TABLE IF NOT EXISTS delivery_monitors(
            run_id TEXT PRIMARY KEY,channel_id TEXT UNIQUE NOT NULL,project_id TEXT NOT NULL,
            mode TEXT NOT NULL CHECK(mode IN ('live','local_demo')),csm_user TEXT NOT NULL,
            pm_user TEXT NOT NULL,owner_user TEXT NOT NULL,task_url_template TEXT,
            oldest_ts TEXT NOT NULL,enabled INTEGER NOT NULL DEFAULT 1,last_checked TEXT,error TEXT);
        CREATE TABLE IF NOT EXISTS delivery_updates(
            channel_id TEXT NOT NULL,message_ts TEXT NOT NULL,run_id TEXT NOT NULL,
            user_id TEXT,task_id TEXT,status TEXT NOT NULL,detail TEXT NOT NULL,
            payload TEXT,created_at TEXT NOT NULL,PRIMARY KEY(channel_id,message_ts));
        CREATE TABLE IF NOT EXISTS delivery_alerts(
            run_id TEXT NOT NULL,task_id TEXT NOT NULL,due_date TEXT NOT NULL,
            threshold INTEGER NOT NULL,recipient TEXT NOT NULL,status TEXT NOT NULL,
            message_ts TEXT,created_at TEXT NOT NULL,
            PRIMARY KEY(run_id,task_id,due_date,threshold));
    ''')


def now():
    return datetime.now(timezone.utc).isoformat()


def parse_update(text):
    match = re.fullmatch(r'TASK\s+(\S+)\s+STATUS\s+(not_started|in_progress|blocked|completed)\s+PROGRESS\s+(\d{1,3})(?:\s+NOTE\s+(.{1,500}))?',text.strip(),re.I)
    if not match:
        raise ValueError('Use TASK <task_id> STATUS <not_started|in_progress|blocked|completed> PROGRESS <0-100>')
    task_id, status, progress = match[1], match[2].lower(), int(match[3])
    if progress > 100 or (status=='completed') != (progress==100) or (status=='not_started' and progress!=0):
        raise ValueError('Status and progress disagree')
    return {'task_id':task_id,'status':status,'progress':progress,'note':match[4] or None}


class DeliveryAPI:
    def slack_get(self, method, params):
        result = request('GET','https://slack.com/api/'+method+'?'+urlencode(params),
                         {'Authorization':'Bearer '+required('SLACK_BOT_TOKEN')})
        if not result.get('ok'):
            raise IntegrationError('Slack '+method+': '+result.get('error','unknown_error'))
        return result

    def history(self, channel, oldest):
        params = {'channel':channel,'oldest':oldest,'limit':100}
        messages, cursors = [], set()
        for _ in range(100):
            result = self.slack_get('conversations.history',params)
            messages.extend(result.get('messages',[]))
            cursor = result.get('response_metadata',{}).get('next_cursor')
            if not cursor:
                if result.get('has_more'):
                    raise IntegrationError('Slack history incomplete; cursor missing')
                return sorted(messages,key=lambda m:Decimal(m['ts']))
            if cursor in cursors:
                raise IntegrationError('Slack history pagination loop')
            cursors.add(cursor);params['cursor']=cursor
        raise IntegrationError('Slack history page limit reached')

    def post(self,channel,text):
        result = LiveServices().slack('chat.postMessage',{'channel':channel,'text':text,
                                                         'unfurl_links':False,'unfurl_media':False})
        if not result.get('ts'):
            raise UncertainWrite('Slack message receipt missing')
        return result['ts']

    def rocket(self,method,path,payload=None):
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
        mappings=json.loads(required('ROCKETLANE_TASK_STATUS_VALUES'))
        if status not in mappings or isinstance(mappings[status],bool):
            raise IntegrationError('Verified tenant task status values required')
        if not str(task_id).isdigit():
            raise IntegrationError('Native task ID must be numeric')
        self.rocket('PUT','tasks/'+str(task_id),{'status':{'value':mappings[status]},
                                               'progress':progress,'atRisk':status=='blocked'})


def normalize_task(item, project):
    if str((item.get('project') or {}).get('projectId')) != str(project):
        raise IntegrationError('Task belongs to a different Rocketlane project')
    tid=str(item.get('taskId',''))
    if not tid.isdigit() or not item.get('taskName'):
        raise IntegrationError('Rocketlane task identity missing')
    label=str((item.get('status') or {}).get('label','')).lower().replace('-',' ').replace('_',' ')
    aliases={'not started':'not_started','to do':'not_started','open':'not_started',
             'in progress':'in_progress','blocked':'blocked','completed':'completed','complete':'completed','done':'completed'}
    status=aliases.get(label)
    mappings=json.loads(os.getenv('ROCKETLANE_TASK_STATUS_VALUES','{}'))
    raw=(item.get('status') or {}).get('value')
    if status is None:
        status=next((k for k,v in mappings.items() if k in STATES and str(v)==str(raw)),None)
    progress=item.get('progress')
    if progress is not None and (isinstance(progress,bool) or not isinstance(progress,(int,float)) or not 0<=progress<=100):
        raise IntegrationError('Invalid task progress')
    if status is None:
        raise IntegrationError('Unmapped Rocketlane task status; configure status values')
    if progress is not None and ((progress==100)!=(status=='completed')):
        raise IntegrationError('Rocketlane status and progress disagree')
    due=item.get('dueDate')
    if due:
        date.fromisoformat(due)
    assignees=(item.get('assignees') or {}).get('members',[])
    owners=', '.join(str(m.get('firstName') or m.get('emailId') or m.get('userId')) for m in assignees) or None
    return {'native_task_id':tid,'task_name':item['taskName'],
            'phase_name':(item.get('phase') or {}).get('phaseName') or 'Unspecified',
            'status':status,'progress':progress,'due_date':due,'owner_name':owners}


def configure(store,run_id,mode,csm,pm,owner,task_url_template=None):
    run=store.get(run_id)
    channel=run.get('channel_id','')
    if run['state']!='complete' or not re.fullmatch(r'[CG][A-Z0-9]+',channel):
        raise ValueError('A fully set up real Slack channel is required')
    if mode not in {'live','local_demo'}:
        raise ValueError('Choose live or local_demo mode')
    if mode=='live' and (run.get('simulation') or not str(run.get('project_id','')).isdigit()):
        raise ValueError('Live monitoring requires a real onboarding project, not a simulated run')
    if any(not re.fullmatch(r'[UW][A-Z0-9]+',u) or u.startswith('UDEMO') for u in (csm,pm,owner)):
        raise ValueError('Real Slack member IDs required')
    if task_url_template and (not task_url_template.startswith('https://') or '{task_id}' not in task_url_template):
        raise ValueError('Provide an HTTPS task URL template containing {task_id}')
    with store.transaction():
        existing=store.db.execute('SELECT * FROM delivery_monitors WHERE run_id=?',(run_id,)).fetchone()
        if existing:
            if (existing['mode'],existing['channel_id'])!=(mode,channel):
                raise ValueError('Existing monitor mode/channel cannot be changed implicitly')
            store.db.execute('UPDATE delivery_monitors SET csm_user=?,pm_user=?,owner_user=?,task_url_template=?,enabled=1 WHERE run_id=?',
                             (csm,pm,owner,task_url_template,run_id))
        else:
            store.db.execute('''INSERT INTO delivery_monitors(run_id,channel_id,project_id,mode,csm_user,pm_user,owner_user,task_url_template,oldest_ts)
                VALUES(?,?,?,?,?,?,?,?,?)''',(run_id,channel,run['project_id'],mode,csm,pm,owner,task_url_template,str(time.time())))
        if mode=='local_demo':
            for pi,phase in enumerate(run.get('phases',[]),1):
                due=(date.fromisoformat(run['start_date'])+timedelta(days=phase['end_day']-1)).isoformat()
                store.db.execute('UPDATE onboarding_tasks SET due_date=COALESCE(due_date,?) WHERE run_id=? AND phase_name=?',
                                 (due,run_id,phase['name']))
        store.event(run,'delivery_monitor_configured','Monitoring enabled: '+mode)


class MonitorState(TypedDict):
    run_id:str
    run:dict


class DeliveryMonitor:
    def __init__(self,store,api=None):
        self.store=store;self.api=api or DeliveryAPI()
        checkpoint_path=':memory:' if store.path==':memory:' else store.path+'.delivery.checkpoints.db'
        self.connection=sqlite3.connect(checkpoint_path,check_same_thread=False)
        self.checkpointer=LoggedSqliteSaver(self.connection,store)
        self.checkpointer.setup()
        graph=StateGraph(MonitorState)
        graph.add_node('sync_tasks',self._node(self.sync_tasks))
        graph.add_node('read_slack_updates',self._node(self.read_updates))
        graph.add_node('escalate_overdue',self._node(self.escalate))
        graph.add_edge(START,'sync_tasks');graph.add_edge('sync_tasks','read_slack_updates')
        graph.add_edge('read_slack_updates','escalate_overdue');graph.add_edge('escalate_overdue',END)
        # Business ledgers persist processing/delivery intents across invocations.
        self.graph=graph.compile(checkpointer=self.checkpointer)

    def close(self):
        self.connection.close()

    def config(self,rid):
        row=self.store.db.execute('SELECT * FROM delivery_monitors WHERE run_id=?',(rid,)).fetchone()
        if not row:
            raise ValueError('Monitor not configured')
        return dict(row)

    def _node(self,operation):
        def execute(state):
            operation(state['run_id'])
            with self.store.transaction():
                self.store.event({'id':state['run_id']},'delivery_checkpoint',operation.__name__+' completed')
            cfg=self.config(state['run_id'])
            return {'run':{'state':'delivery_'+operation.__name__,'project_id':cfg['project_id'],'channel_id':cfg['channel_id']}}
        return execute

    def cycle(self):
        results=[]
        for row in self.store.db.execute('SELECT run_id FROM delivery_monitors WHERE enabled=1').fetchall():
            rid=row['run_id'];error=None
            if self.store.get(rid).get('onboarding_status') in {'completed','cancelled'}:
                with self.store.transaction():
                    self.store.db.execute('UPDATE delivery_monitors SET enabled=0 WHERE run_id=?',(rid,))
                continue
            try:
                self.graph.invoke({'run_id':rid},{'configurable':{'thread_id':rid}})
            except Exception as exc:
                # Provider bodies, tokens and message contents never appear in errors.
                error=str(exc) if isinstance(exc,(IntegrationError,ValueError)) else 'Delivery monitoring failed; inspect configuration and provider availability'
            with self.store.transaction():
                self.store.db.execute('UPDATE delivery_monitors SET last_checked=?,error=? WHERE run_id=?',(now(),error,rid))
            results.append({'run_id':rid,'error':error})
        return results

    def sync_tasks(self,rid):
        cfg=self.config(rid)
        if cfg['mode']=='local_demo':
            return
        # Validate the complete snapshot before mutating local tasks; a failed page
        # never replaces a previously valid snapshot or triggers stale alerts.
        normalized=[normalize_task(t,cfg['project_id']) for t in self.api.tasks(cfg['project_id'])]
        if len({t['native_task_id'] for t in normalized})!=len(normalized):
            raise IntegrationError('Duplicate Rocketlane task IDs')
        with self.store.transaction():
            wanted={'rocketlane:'+t['native_task_id'] for t in normalized}
            for old in self.store.db.execute('SELECT task_id FROM onboarding_tasks WHERE run_id=?',(rid,)).fetchall():
                if old['task_id'] not in wanted:
                    self.store.db.execute('DELETE FROM onboarding_tasks WHERE task_id=?',(old['task_id'],))
            for t in normalized:
                self.store.db.execute('''INSERT INTO onboarding_tasks
                    (task_id,run_id,phase_name,task_name,status,owner_role,owner_name,source,updated_at,native_task_id,due_date,progress,synced_at)
                    VALUES(?,?,?,?,?,'CSM',?,'rocketlane',?,?,?,?,?)
                    ON CONFLICT(task_id) DO UPDATE SET phase_name=excluded.phase_name,task_name=excluded.task_name,
                    status=excluded.status,owner_name=excluded.owner_name,source=excluded.source,
                    updated_at=excluded.updated_at,due_date=excluded.due_date,progress=excluded.progress,
                    synced_at=excluded.synced_at''',
                    ('rocketlane:'+t['native_task_id'],rid,t['phase_name'],t['task_name'],t['status'],t['owner_name'],now(),
                     t['native_task_id'],t['due_date'],t['progress'],now()))

    def _record(self,cfg,message,status,detail,payload=None):
        with self.store.transaction():
            self.store.db.execute('''INSERT OR IGNORE INTO delivery_updates
                VALUES(?,?,?,?,?,?,?,?,?)''',(cfg['channel_id'],message['ts'],cfg['run_id'],message.get('user'),
                (payload or {}).get('task_id'),status,detail,json.dumps(payload) if payload else None,now()))

    def read_updates(self,rid):
        cfg=self.config(rid)
        messages=self.api.history(cfg['channel_id'],cfg['oldest_ts'])
        for message in messages:
            if message.get('bot_id') or message.get('subtype') or not message.get('user'):
                continue
            text=message.get('text','')
            if not re.search(r'\b(task|progress|blocked|complete|done)\b',text,re.I):
                continue
            existing=self.store.db.execute('SELECT status FROM delivery_updates WHERE channel_id=? AND message_ts=?',
                                           (cfg['channel_id'],message['ts'])).fetchone()
            if existing:
                continue
            try:
                if message['user'] not in {cfg['csm_user'],cfg['pm_user'],cfg['owner_user']}:
                    raise ValueError('Only assigned CSM, PM or Owner may update delivery tasks')
                payload=parse_update(text)
                task=self.store.db.execute('SELECT * FROM onboarding_tasks WHERE run_id=? AND (task_id=? OR native_task_id=?)',
                                           (rid,payload['task_id'],payload['task_id'])).fetchone()
                if not task:
                    raise ValueError('Task does not belong to this onboarding')
                payload['task_id']=task['task_id']
                if (task['status']=='completed' and payload['status']!='completed') or (task['progress'] is not None and payload['progress']<task['progress']):
                    raise ValueError('Reopening tasks or reducing progress requires human review')
                gate=bool(re.search(r'verif|readiness|sign.off',task['task_name'],re.I))
                if payload['status']=='completed' and gate and not self.store.get(rid).get('migration_verified'):
                    raise ValueError('Migration/customer verification evidence required before sign-off')
                self._record(cfg,message,'pending_review','Intent recorded before task update',payload)
                self.apply_update(cfg,message,payload,task)
            except ValueError as exc:
                self._record(cfg,message,'needs_review',str(exc))
        # Only advance after all pages and processing succeed. Review/uncertain
        # rows are durable; replay never blindly repeats a write.
        if messages:
            with self.store.transaction():
                self.store.db.execute('UPDATE delivery_monitors SET oldest_ts=? WHERE run_id=?',
                                     (max((m['ts'] for m in messages),key=Decimal),rid))

    def apply_update(self,cfg,message,payload,task):
        if cfg['mode']=='live':
            fresh=normalize_task(self.api.task(task['native_task_id']),cfg['project_id'])
            if fresh['status']!=task['status'] or fresh['progress']!=task['progress']:
                raise IntegrationError('Task changed remotely; update retained for human review')
            self.api.update(task['native_task_id'],payload['status'],payload['progress'])
            verified=normalize_task(self.api.task(task['native_task_id']),cfg['project_id'])
            if verified['status']!=payload['status'] or verified['progress']!=payload['progress']:
                raise UncertainWrite('Rocketlane update not verified; human reconciliation required')
        with self.store.transaction():
            self.store.db.execute('''UPDATE onboarding_tasks SET status=?,progress=?,updated_at=?,
                last_progress_at=CASE WHEN progress IS NULL OR progress<? OR status!=? THEN ? ELSE last_progress_at END,
                blocker_note=? WHERE task_id=? AND run_id=?''',
                (payload['status'],payload['progress'],now(),payload['progress'],payload['status'],now(),
                 payload.get('note') if payload['status']=='blocked' else None,payload['task_id'],cfg['run_id']))
            self.store.db.execute("UPDATE delivery_updates SET status='applied',detail='Task update recorded and verified' WHERE channel_id=? AND message_ts=?",
                                  (cfg['channel_id'],message['ts']))
            self.store.event({'id':cfg['run_id']},'delivery_task_updated',json.dumps({'task_id':payload['task_id'],
                             'status':payload['status'],'progress':payload['progress'],'slack_ts':message['ts'],'mode':cfg['mode']}))

    def review(self,rid,message_ts,decision,reviewer,evidence,task_id=None,status=None,progress=None):
        if not reviewer.strip() or not evidence.strip() or decision not in {'apply','reject'}:
            raise ValueError('Reviewer, evidence and apply/reject decision required')
        cfg=self.config(rid)
        item=self.store.db.execute('SELECT * FROM delivery_updates WHERE run_id=? AND message_ts=? AND status IN (\'needs_review\',\'pending_review\')',
                                   (rid,message_ts)).fetchone()
        if not item:
            raise ValueError('Unresolved update not found')
        if decision=='reject':
            with self.store.transaction():
                self.store.db.execute("UPDATE delivery_updates SET status='rejected',detail=? WHERE channel_id=? AND message_ts=?",
                                      (reviewer+': '+evidence,cfg['channel_id'],message_ts))
                self.store.event({'id':rid},'delivery_human_review',reviewer+': rejected update; '+evidence)
            return
        payload=parse_update(f'TASK {task_id} STATUS {status} PROGRESS {progress}') if task_id is not None else json.loads(item['payload'] or 'null')
        if not payload:
            raise ValueError('Specify task ID, status and progress for an ambiguous update')
        task=self.store.db.execute('SELECT * FROM onboarding_tasks WHERE run_id=? AND (task_id=? OR native_task_id=?)',
                                   (rid,payload['task_id'],payload['task_id'])).fetchone()
        if not task:
            raise ValueError('Task does not belong to this onboarding')
        if payload['status']=='completed' and re.search(r'verif|readiness|sign.off',task['task_name'],re.I) and not self.store.get(rid).get('migration_verified'):
            raise ValueError('Migration verification evidence is still required')
        payload['task_id']=task['task_id']
        if cfg['mode']=='live':
            remote=normalize_task(self.api.task(task['native_task_id']),cfg['project_id'])
            if remote['status']==payload['status'] and remote['progress']==payload['progress']:
                # Prior PUT succeeded: finalize locally without repeating the write.
                with self.store.transaction():
                    self.store.db.execute('UPDATE onboarding_tasks SET status=?,progress=? WHERE task_id=?',
                                          (payload['status'],payload['progress'],task['task_id']))
                    self.store.db.execute("UPDATE delivery_updates SET status='applied',detail=? WHERE channel_id=? AND message_ts=?",
                                          (reviewer+': verified prior update; '+evidence,cfg['channel_id'],message_ts))
                    self.store.event({'id':rid},'delivery_human_review',reviewer+': reconciled prior write; '+evidence)
                return
        with self.store.transaction():
            self.store.db.execute("UPDATE delivery_updates SET status='pending_review',task_id=?,payload=?,detail=? WHERE channel_id=? AND message_ts=?",
                                  (task['task_id'],json.dumps(payload),reviewer+': approved; '+evidence,cfg['channel_id'],message_ts))
            self.store.event({'id':rid},'delivery_human_review',reviewer+': approved update; '+evidence)
        self.apply_update(cfg,{'ts':message_ts},payload,task)

    def escalate(self,rid,today=None):
        cfg=self.config(rid)
        today=today or datetime.now(ZoneInfo('Asia/Kolkata')).date()
        # Completion/cancellation releases monitoring, never capacity implicitly.
        if self.store.get(rid).get('onboarding_status') in {'completed','cancelled'}:
            return
        for task in self.store.db.execute('SELECT * FROM onboarding_tasks WHERE run_id=?',(rid,)).fetchall():
            if not task['due_date'] or task['status']=='completed' or task['progress']==100:
                continue
            overdue=(today-date.fromisoformat(task['due_date'])).days
            pending=self.store.db.execute("SELECT 1 FROM delivery_updates WHERE run_id=? AND task_id=? AND status='pending_review'",
                                          (rid,task['task_id'])).fetchone()
            if pending:
                continue  # Unknown remote update must be reconciled before alerts.
            for threshold,role in ((1,'pm_user'),(4,'owner_user')):
                if overdue<threshold:
                    continue
                recipient=cfg[role]
                with self.store.transaction():
                    key=(rid,task['task_id'],task['due_date'],threshold)
                    previous=self.store.db.execute('SELECT status FROM delivery_alerts WHERE run_id=? AND task_id=? AND due_date=? AND threshold=?',key).fetchone()
                    if previous:
                        continue
                    self.store.db.execute('INSERT INTO delivery_alerts VALUES(?,?,?,?,?,?,NULL,?)',
                                          (*key,recipient,'pending_review',now()))
                def safe(value):
                    return str(value).replace('&','&amp;').replace('<','&lt;').replace('>','&gt;')
                link=(cfg['task_url_template'] or '').replace('{task_id}',str(task['native_task_id'] or task['task_id'])).replace('{project_id}',cfg['project_id'])
                text=(f"{'[LOCAL DEMO] ' if cfg['mode']=='local_demo' else ''}<@{recipient}> Overdue onboarding task (+{threshold} day escalation)\n"
                      f"Task: {safe(task['task_name'])}\nOwner: {safe(task['owner_name'] or 'Unassigned')}\n"
                      f"Due: {task['due_date']} | {overdue} calendar days overdue | Status: {task['status']} | Progress: {task['progress'] if task['progress'] is not None else 'unknown'}%\n"
                      f"Blocker: {safe(task['blocker_note'] or 'Not supplied; request an update from the CSM')}\n"
                      f"Task reference: {safe(task['task_id'])}"+(f'\nTask link: {safe(link)}' if link else '\nNo verified native task link configured.'))
                receipt=self.api.post(cfg['channel_id'],text)
                with self.store.transaction():
                    self.store.db.execute("UPDATE delivery_alerts SET status='sent',message_ts=? WHERE run_id=? AND task_id=? AND due_date=? AND threshold=?",
                                          (receipt,*key))
                    self.store.event({'id':rid},'delivery_escalation_sent',json.dumps({'task_id':task['task_id'],'threshold':threshold,'recipient':recipient}))


def main():
    from .store import Store
    load_dotenv(Path(__file__).resolve().parents[1]/'.env')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db',default='demo-local-worker.db')
    sub=parser.add_subparsers(dest='command',required=True)
    config=sub.add_parser('configure');config.add_argument('run_id')
    config.add_argument('--mode',choices=['live','local_demo'],required=True)
    for role in ('csm','pm','owner'):
        config.add_argument('--'+role,required=True)
    config.add_argument('--task-url-template')
    worker=sub.add_parser('worker');worker.add_argument('--once',action='store_true')
    worker.add_argument('--interval',type=int,default=60)
    sub.add_parser('status')
    review=sub.add_parser('review');review.add_argument('run_id');review.add_argument('message_ts')
    review.add_argument('--decision',choices=['apply','reject'],required=True)
    review.add_argument('--reviewer',required=True);review.add_argument('--evidence',required=True)
    review.add_argument('--task-id');review.add_argument('--status',choices=sorted(STATES));review.add_argument('--progress',type=int)
    alert=sub.add_parser('resolve-alert');alert.add_argument('run_id');alert.add_argument('task_id');alert.add_argument('due_date')
    alert.add_argument('--threshold',type=int,choices=[1,4],required=True)
    alert.add_argument('--decision',choices=['sent','retry'],required=True)
    alert.add_argument('--reviewer',required=True);alert.add_argument('--evidence',required=True)
    args=parser.parse_args()
    if not Path(args.db).is_file():
        parser.error('Existing workflow database required')
    store=Store(args.db)
    try:
        if args.command=='configure':
            configure(store,args.run_id,args.mode,args.csm,args.pm,args.owner,args.task_url_template)
            print(json.dumps({'configured':args.run_id,'mode':args.mode}))
        elif args.command=='status':
            print(json.dumps([dict(r) for r in store.db.execute('SELECT * FROM delivery_monitors')],indent=2))
        elif args.command=='review':
            monitor=DeliveryMonitor(store)
            try:
                monitor.review(args.run_id,args.message_ts,args.decision,args.reviewer,args.evidence,args.task_id,args.status,args.progress)
                print(json.dumps({'reviewed':args.message_ts,'decision':args.decision}))
            finally:
                monitor.close()
        elif args.command=='resolve-alert':
            if not args.reviewer.strip() or not args.evidence.strip():
                raise ValueError('Reviewer and provider evidence required')
            key=(args.run_id,args.task_id,args.due_date,args.threshold)
            with store.transaction():
                row=store.db.execute("SELECT * FROM delivery_alerts WHERE run_id=? AND task_id=? AND due_date=? AND threshold=? AND status='pending_review'",key).fetchone()
                if not row:
                    raise ValueError('Uncertain alert not found')
                if args.decision=='sent':
                    store.db.execute("UPDATE delivery_alerts SET status='sent' WHERE run_id=? AND task_id=? AND due_date=? AND threshold=?",key)
                else:
                    store.db.execute('DELETE FROM delivery_alerts WHERE run_id=? AND task_id=? AND due_date=? AND threshold=?',key)
                store.event({'id':args.run_id},'delivery_alert_reconciliation',args.reviewer+': '+args.decision+'; '+args.evidence)
            print(json.dumps({'resolved_alert':args.task_id,'decision':args.decision}))
        else:
            if not 30<=args.interval<=3600:
                parser.error('Polling interval must be 30–3600 seconds')
            with single_worker(args.db+'.delivery'):
                monitor=DeliveryMonitor(store)
                try:
                    while True:
                        print(json.dumps({'timestamp':now(),'results':monitor.cycle()}),flush=True)
                        if args.once:
                            break
                        time.sleep(args.interval)
                finally:
                    monitor.close()
    finally:
        store.db.close()


if __name__=='__main__':
    main()
