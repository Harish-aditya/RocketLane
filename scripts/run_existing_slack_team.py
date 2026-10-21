"""Exercise real Slack membership using three existing accounts; no voice/project calls."""
import json
from urllib.parse import urlencode
from dotenv import load_dotenv
from app.services import LiveServices, request, required
from app.store import Store

TEAM = [('CSM','U0CAQDLMDC3'),('Project Manager','U0CA22QMVMG'),('Project Owner','U0CA09DLC6S')]
CHANNEL = 'C0CAQQTDYR3'


def main():
    load_dotenv('.env')
    service = LiveServices()
    auth = service.slack('auth.test', {})
    if auth['team_id'] != 'T0C9LSJASF9':
        raise ValueError('Unexpected Slack workspace')
    users = {}
    cursor = ''
    while True:
        result = service.slack('users.list', {'limit':100, **({'cursor':cursor} if cursor else {})})
        users.update({u['id']:u for u in result['members']})
        cursor = result.get('response_metadata',{}).get('next_cursor','')
        if not cursor:
            break
    for role, uid in TEAM:
        u = users.get(uid)
        if not u or u.get('deleted') or u.get('is_bot') or u.get('is_invited_user'):
            raise ValueError('Joined human account required for '+role)
    store = Store('demo-local-worker.db')
    try:
        with store.transaction():
            store.db.execute('''CREATE TABLE IF NOT EXISTS slack_demo_members(
                channel_id TEXT,role TEXT,slack_user_id TEXT,display_name TEXT,invite_status TEXT,
                PRIMARY KEY(channel_id,role))''')
            store.db.execute('''CREATE TABLE IF NOT EXISTS slack_demo_welcome(
                channel_id TEXT PRIMARY KEY,status TEXT,message_ts TEXT)''')
        for role,uid in TEAM:
            u = users[uid]
            name = u.get('profile',{}).get('display_name') or u.get('real_name') or u['name']
            with store.transaction():
                store.db.execute('INSERT OR IGNORE INTO slack_demo_members VALUES(?,?,?,?,?)',
                                 (CHANNEL,role,uid,name,'pending'))
            # An invitation to an existing member is safe to reconcile via already_in_channel.
            service.invite_member(CHANNEL,uid)
            with store.transaction():
                store.db.execute("UPDATE slack_demo_members SET invite_status='added' WHERE channel_id=? AND role=?",(CHANNEL,role))
        with store.transaction():
            row = store.db.execute('SELECT * FROM slack_demo_welcome WHERE channel_id=?',(CHANNEL,)).fetchone()
            if row is None:
                store.db.execute("INSERT INTO slack_demo_welcome VALUES(?,'pending_review',NULL)",(CHANNEL,))
        if row is None:
            text = ('NovaCRM onboarding Slack demo is ready.\n'
                    'CSM: Elsa (also responsible for migration and configuration)\n'
                    'Project Manager: Star Boy\nProject Owner: Harish Aditya\n'
                    'These existing accounts represent the demo roles. The 13-profile mock roster remains in SQLite. '
                    'Voice calls, Rocketlane projects and delivery progress remain simulated. No customer onboarding is declared complete.')
            response = service.slack('chat.postMessage',{'channel':CHANNEL,'text':text,'mrkdwn':False})
            with store.transaction():
                store.db.execute("UPDATE slack_demo_welcome SET status='sent',message_ts=? WHERE channel_id=?",(response['ts'],CHANNEL))
        # Membership read must use query arguments, not a JSON body.
        headers = {'Authorization':'Bearer '+required('SLACK_BOT_TOKEN')}
        response = request('GET','https://slack.com/api/conversations.members?'+urlencode({'channel':CHANNEL,'limit':100}),headers)
        if not response.get('ok'):
            raise ValueError('Membership verification failed: '+response.get('error','unknown'))
        actual = set(response['members'])
        assert {uid for _,uid in TEAM} <= actual, 'A mapped team member is missing'
        print(json.dumps({'status':'verified','channel_id':CHANNEL,
                         'team':[dict(r) for r in store.db.execute('SELECT * FROM slack_demo_members WHERE channel_id=?',(CHANNEL,))],
                         'voice_and_projects':'simulated'}))
    finally:
        store.db.close()


if __name__ == '__main__':
    main()
