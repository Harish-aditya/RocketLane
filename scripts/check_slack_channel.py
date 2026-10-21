"""Create one private Slack test channel and retain its receipt for safe reruns."""
import json
from dotenv import load_dotenv
from app.services import LiveServices, IntegrationError, UncertainWrite
from app.store import Store


def main():
    load_dotenv('.env')
    store = Store('demo-local-worker.db')
    name = 'novacrm-onboarding-test'
    try:
        with store.transaction():
            store.db.execute('''CREATE TABLE IF NOT EXISTS slack_channel_checks (
                channel_name TEXT PRIMARY KEY, channel_id TEXT, status TEXT NOT NULL)''')
            previous = store.db.execute('SELECT * FROM slack_channel_checks WHERE channel_name=?', (name,)).fetchone()
            if previous:
                print(json.dumps(dict(previous)))
                return
            store.db.execute('INSERT INTO slack_channel_checks VALUES(?,NULL,?)', (name, 'pending_review'))
        try:
            channel_id = LiveServices().channel(name)
        except UncertainWrite:
            print(json.dumps({'status':'pending_review','reason':'Result uncertain; inspect Slack before retrying'}))
            return
        except IntegrationError as exc:
            with store.transaction():
                store.db.execute("UPDATE slack_channel_checks SET status='failed' WHERE channel_name=?", (name,))
            print(json.dumps({'status':'failed','reason':str(exc)}))
            return
        with store.transaction():
            store.db.execute("UPDATE slack_channel_checks SET channel_id=?,status='created' WHERE channel_name=?", (channel_id,name))
        print(json.dumps({'status':'created','channel_name':name,'channel_id':channel_id}))
    finally:
        store.db.close()


if __name__ == '__main__':
    main()
