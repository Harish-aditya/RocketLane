from pathlib import Path
from app.services import GmailSlackDemoServices
from app.store import Store
from app.workflow import Workflow


def test_real_slack_adapter_keeps_voice_and_projects_simulated():
    store = Store(':memory:')
    store.db.execute('CREATE TABLE slack_demo_members(channel_id,role,slack_user_id,invite_status)')
    for role,uid in [('CSM','U111'),('Project Manager','U222'),('Project Owner','U333')]:
        store.db.execute('INSERT INTO slack_demo_members VALUES(?,?,?,?)',('C0CAQQTDYR3',role,uid,'added'))
    store.db.commit()
    service = GmailSlackDemoServices(store)
    invitations, messages = [], []
    service.live.channel = lambda name: 'C12345678'
    service.live.invite_member = lambda channel,user: invitations.append(user)
    service.live.invite_customer = lambda channel,email: {'status':'member_added','email':email,'user_id':'U444'}
    service.live.topic = lambda channel,text: None
    service.live.welcome = lambda channel,text,run_id: messages.append(text)
    flow = Workflow(store, service)
    try:
        run = flow.run(flow.ingest('test',Path('examples/minimal_deal.txt').read_text())['id'])
        assert run['state'] == 'complete'
        assert run['project_id'].startswith('demo-project-')
        assert run['call_id'].startswith('demo-call-')
        assert run['channel_id'] == 'C12345678'
        assert run['slack_mode'] == 'real_slack_demo'
        assert store.db.execute('SELECT mode FROM delivery_monitors WHERE run_id=?',(run['id'],)).fetchone()[0]=='local_demo'
        assert invitations == ['U222','U333','U111']
        assert 'simulated' in messages[0] and 'INTEGRATION TEST' in messages[0]
    finally:
        flow.close()
