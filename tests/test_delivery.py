import copy
import time
from datetime import date,timedelta
from pathlib import Path
import pytest
from app.delivery import DeliveryMonitor,DeliveryAPI,configure,parse_update,normalize_task
from app.services import DemoServices,IntegrationError,UncertainWrite
from app.store import Store
from app.workflow import Workflow


class API:
    def __init__(self):
        self.messages=[];self.posts=[];self.items=[];self.writes=[];self.failure=None
    def history(self,channel,oldest):
        if self.failure=='history':
            raise IntegrationError('Slack history unavailable')
        return [m for m in self.messages if float(m['ts'])>float(oldest)]
    def tasks(self,project):
        if self.failure=='sync':
            raise IntegrationError('Rocketlane unavailable')
        return copy.deepcopy(self.items)
    def task(self,tid):
        return copy.deepcopy(next(t for t in self.items if str(t['taskId'])==str(tid)))
    def update(self,tid,status,progress):
        self.writes.append(tid)
        t=next(t for t in self.items if str(t['taskId'])==str(tid))
        t.update(status={'label':status},progress=progress)
        if self.failure=='write':
            raise UncertainWrite('PUT timed out')
    def post(self,channel,text):
        self.posts.append(text)
        if self.failure=='post':
            raise UncertainWrite('POST timed out')
        return str(len(self.posts))+'.001'


@pytest.fixture
def setup(tmp_path):
    store=Store(tmp_path/'delivery.db');flow=Workflow(store,DemoServices())
    run=flow.run(flow.ingest('delivery',Path('examples/minimal_deal.txt').read_text())['id'])
    run['channel_id']='C111'
    with store.transaction():
        store.save(run)
    configure(store,run['id'],'local_demo','U111','U222','U333')
    with store.transaction():
        store.db.execute('UPDATE onboarding_tasks SET due_date=? WHERE run_id=?',
                          ((date.today()+timedelta(days=365)).isoformat(),run['id']))
    api=API();monitor=DeliveryMonitor(store,api)
    yield store,run,api,monitor
    monitor.close();flow.close();store.db.close()


def message(task_id,status='in_progress',progress=40,user='U111',offset=1):
    return {'ts':str(time.time()+offset),'user':user,'text':f'TASK {task_id} STATUS {status} PROGRESS {progress}'}


def first_task(store,run):
    return dict(store.db.execute('SELECT * FROM onboarding_tasks WHERE run_id=? ORDER BY task_id LIMIT 1',(run['id'],)).fetchone())


def native(tid=101,status='not_started',progress=0):
    return {'taskId':tid,'taskName':'Configure settings','project':{'projectId':999},
            'phase':{'phaseName':'Configuration'},'status':{'label':status},'progress':progress,
            'dueDate':(date.today()+timedelta(days=3)).isoformat(),'assignees':{'members':[{'firstName':'Elsa'}]}}


def set_live(store,run,api):
    api.items=[native()]
    with store.transaction():
        store.db.execute("UPDATE delivery_monitors SET mode='live',project_id='999' WHERE run_id=?",(run['id'],))


@pytest.mark.parametrize('text', ['TASK 1 STATUS completed PROGRESS 40','TASK 1 STATUS in_progress PROGRESS 100',
                                'TASK 1 STATUS not_started PROGRESS 1','TASK 1 STATUS blocked PROGRESS 101',
                                'migration probably done','TASK 1 STATUS done PROGRESS 100'])
def test_parser_requires_explicit_consistent_update(text):
    with pytest.raises(ValueError):
        parse_update(text)


def test_local_update_ownership_dedup_and_checkpoints(setup):
    store,run,api,monitor=setup
    task=first_task(store,run)
    api.messages=[message(task['task_id'])]
    assert monitor.cycle()[0]['error'] is None
    assert first_task(store,run)['progress']==40
    assert first_task(store,run)['status']=='in_progress'
    monitor.cycle()
    assert store.db.execute('SELECT COUNT(*) FROM delivery_updates').fetchone()[0]==1
    assert store.db.execute("SELECT COUNT(*) FROM checkpoint_events WHERE state LIKE 'delivery_%'").fetchone()[0]>0
    assert api.writes==[]


def test_ambiguous_unauthorized_cross_project_and_bot_messages(setup):
    store,run,api,monitor=setup;task=first_task(store,run)
    api.messages=[message(task['task_id'],user='U999'),message('wrong-task',offset=2),
                  {'ts':str(time.time()+3),'user':'U111','text':'Migration task might be done'},
                  {**message(task['task_id'],offset=4),'bot_id':'B111'}]
    assert monitor.cycle()[0]['error'] is None
    rows=store.db.execute('SELECT status FROM delivery_updates').fetchall()
    assert len(rows)==3 and all(r['status']=='needs_review' for r in rows)
    assert first_task(store,run)['status']=='not_started'


def test_migration_signoff_needs_evidence_and_human_review(setup):
    store,run,api,monitor=setup
    task=store.db.execute("SELECT * FROM onboarding_tasks WHERE task_name LIKE 'Verify record%' AND run_id=?",(run['id'],)).fetchone()
    m=message(task['task_id'],'completed',100);api.messages=[m]
    monitor.cycle()
    assert store.db.execute('SELECT status FROM delivery_updates').fetchone()[0]=='needs_review'
    with pytest.raises(ValueError):
        monitor.review(run['id'],m['ts'],'apply','Reviewer','Checked',task['task_id'],'completed',100)
    run['migration_verified']=True
    with store.transaction():
        store.save(run)
    monitor.review(run['id'],m['ts'],'apply','Reviewer','Customer sign-off recorded',task['task_id'],'completed',100)
    assert store.db.execute('SELECT status FROM onboarding_tasks WHERE task_id=?',(task['task_id'],)).fetchone()[0]=='completed'


def test_thresholds_replay_reschedule_and_completed_exclusion(setup):
    store,run,api,monitor=setup;task=first_task(store,run);today=date.today()
    with store.transaction():
        store.db.execute('UPDATE onboarding_tasks SET due_date=? WHERE task_id=?',((today-timedelta(days=1)).isoformat(),task['task_id']))
    monitor.escalate(run['id'],today)
    assert len(api.posts)==1 and '<@U222>' in api.posts[0]
    monitor.escalate(run['id'],today+timedelta(days=3))
    assert len(api.posts)==2 and '<@U333>' in api.posts[1]
    monitor.escalate(run['id'],today+timedelta(days=3))
    assert len(api.posts)==2
    with store.transaction():
        store.db.execute("UPDATE onboarding_tasks SET status='completed',progress=100 WHERE task_id=?",(task['task_id'],))
    monitor.escalate(run['id'],today+timedelta(days=10))
    assert len(api.posts)==2


def test_unknown_alert_result_is_not_reposted(setup):
    store,run,api,monitor=setup;task=first_task(store,run)
    with store.transaction():
        store.db.execute('UPDATE onboarding_tasks SET due_date=? WHERE task_id=?',((date.today()-timedelta(days=1)).isoformat(),task['task_id']))
    api.failure='post'
    with pytest.raises(UncertainWrite):
        monitor.escalate(run['id'])
    monitor.escalate(run['id'])
    assert len(api.posts)==1
    assert store.db.execute('SELECT status FROM delivery_alerts').fetchone()[0]=='pending_review'


def test_rescheduling_creates_new_schedule_and_restart_preserves_receipts(setup):
    store,run,api,monitor=setup;task=first_task(store,run);today=date.today()
    with store.transaction():
        store.db.execute('UPDATE onboarding_tasks SET due_date=? WHERE task_id=?',((today-timedelta(days=1)).isoformat(),task['task_id']))
    monitor.escalate(run['id'],today)
    restarted=DeliveryMonitor(store,api)
    try:
        restarted.escalate(run['id'],today)
        assert len(api.posts)==1
        with store.transaction():
            store.db.execute('UPDATE onboarding_tasks SET due_date=? WHERE task_id=?',((today-timedelta(days=2)).isoformat(),task['task_id']))
        restarted.escalate(run['id'],today)
        assert len(api.posts)==2
    finally:
        restarted.close()


def test_blocker_note_and_progress_regression_review(setup):
    store,run,api,monitor=setup;task=first_task(store,run)
    one=message(task['task_id'],'blocked',40)
    one['text']+=' NOTE Waiting for customer access'
    api.messages=[one]
    monitor.cycle()
    assert first_task(store,run)['blocker_note']=='Waiting for customer access'
    api.messages.append(message(task['task_id'],'in_progress',20,offset=2))
    monitor.cycle()
    assert first_task(store,run)['progress']==40
    assert store.db.execute("SELECT COUNT(*) FROM delivery_updates WHERE status='needs_review'").fetchone()[0]==1


def test_provider_outage_prevents_stale_escalations(setup):
    store,run,api,monitor=setup;task=first_task(store,run)
    with store.transaction():
        store.db.execute('UPDATE onboarding_tasks SET due_date=? WHERE task_id=?',((date.today()-timedelta(days=5)).isoformat(),task['task_id']))
    api.failure='history'
    assert monitor.cycle()[0]['error']
    assert api.posts==[]


def test_native_sync_update_and_uncertain_reconciliation(setup):
    store,run,api,monitor=setup;set_live(store,run,api)
    api.messages=[message('101')];api.failure='write'
    assert monitor.cycle()[0]['error']
    assert api.writes==['101']
    assert store.db.execute('SELECT status FROM delivery_updates').fetchone()[0]=='pending_review'
    api.failure=None
    monitor.cycle()
    assert api.writes==['101']
    monitor.review(run['id'],api.messages[0]['ts'],'apply','Owner','Verified remote task state')
    assert api.writes==['101']
    assert store.db.execute('SELECT status FROM delivery_updates').fetchone()[0]=='applied'
    assert first_task(store,run)['source']=='rocketlane'


def test_failed_sync_preserves_snapshot_and_wrong_project_rejected(setup):
    store,run,api,monitor=setup;set_live(store,run,api)
    monitor.sync_tasks(run['id']);assert first_task(store,run)['native_task_id']=='101'
    api.items=[native(),{**native(102),'project':{'projectId':888}}]
    assert monitor.cycle()[0]['error']
    assert store.db.execute('SELECT COUNT(*) FROM onboarding_tasks').fetchone()[0]==1
    assert first_task(store,run)['native_task_id']=='101'


def test_rocketlane_pagination_and_scope(monkeypatch):
    api=DeliveryAPI();requests=[]
    def rocket(method,path,payload=None):
        requests.append(path)
        return {'data':[native()], 'pagination':{'hasMore':len(requests)==1,'nextPageToken':'next' if len(requests)==1 else None}}
    monkeypatch.setattr(api,'rocket',rocket)
    assert len(api.tasks('999'))==2
    assert 'projectId.eq=999' in requests[0] and 'pageToken=next' in requests[1]
    monkeypatch.setattr(api,'rocket',lambda *args:{'data':[],'pagination':{'hasMore':True}})
    with pytest.raises(IntegrationError):
        api.tasks('999')


def test_live_mode_rejects_simulated_project(setup):
    store,run,api,monitor=setup
    with pytest.raises(ValueError,match='real onboarding'):
        configure(store,run['id'],'live','U111','U222','U333')


def test_native_status_unknown_and_conflicting_progress_rejected():
    with pytest.raises(IntegrationError):
        normalize_task(native(status='unknown'),999)
    with pytest.raises(IntegrationError):
        normalize_task(native(status='blocked',progress=100),999)
