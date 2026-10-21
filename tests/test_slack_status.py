from pathlib import Path
import pytest
from app.services import DemoServices, UncertainWrite
from app.slack_status import publish
from app.store import Store
from app.workflow import Workflow


class Slack:
    def __init__(self, fail=False):
        self.posts = []
        self.fail = fail

    def slack(self, method, payload):
        self.posts.append(payload)
        if self.fail:
            raise UncertainWrite('timeout')
        return {'ok': True, 'ts': '123.456'}


def setup_run():
    store = Store(':memory:')
    flow = Workflow(store, DemoServices())
    run = flow.run(flow.ingest('slack', Path('examples/minimal_deal.txt').read_text())['id'])
    return store, flow, run


def test_simulated_channel_cannot_receive_real_post():
    store, flow, run = setup_run()
    try:
        with pytest.raises(ValueError, match='real Slack channel'):
            publish(store, run['id'], Slack())
    finally:
        flow.close()


def test_changed_snapshot_only_and_honest_progress():
    store, flow, run = setup_run()
    try:
        run['channel_id'] = 'C12345678'
        with store.transaction():
            store.save(run)
        slack = Slack()
        assert publish(store, run['id'], slack)['status'] == 'sent'
        assert publish(store, run['id'], slack)['status'] == 'unchanged'
        assert len(slack.posts) == 1
        assert '0/15 completed' in slack.posts[0]['text']
        assert 'has not been synchronized' in slack.posts[0]['text']
        assert 'Elena CSM' in slack.posts[0]['text']
        with store.transaction():
            store.db.execute("UPDATE onboarding_tasks SET status='completed' WHERE task_id=(SELECT task_id FROM onboarding_tasks LIMIT 1)")
        assert publish(store, run['id'], slack)['status'] == 'sent'
        assert '1/15 completed' in slack.posts[-1]['text']
    finally:
        flow.close()


def test_uncertain_delivery_blocks_duplicate():
    store, flow, run = setup_run()
    try:
        run['channel_id'] = 'C12345678'
        with store.transaction():
            store.save(run)
        slack = Slack(fail=True)
        with pytest.raises(UncertainWrite):
            publish(store, run['id'], slack)
        with pytest.raises(UncertainWrite):
            publish(store, run['id'], slack)
        assert len(slack.posts) == 1
    finally:
        flow.close()
