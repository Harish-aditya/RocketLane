import json
from urllib.error import URLError
from app import services
from app.services import LiveServices, UncertainWrite
import pytest


def test_post_timeout_is_not_retried(monkeypatch):
    calls = []
    def fail(*args, **kwargs):
        calls.append(args)
        raise URLError('timeout')
    monkeypatch.setattr(services, 'urlopen', fail)
    with pytest.raises(UncertainWrite):
        services.request('POST', 'https://example.com', {}, {})
    assert len(calls) == 1


def test_get_transient_failure_recovers(monkeypatch):
    calls = []
    class Response:
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def read(self):
            return b'{"ok":true}'
    def get(*args, **kwargs):
        calls.append(args)
        if len(calls) < 3:
            raise URLError('timeout')
        return Response()
    monkeypatch.setattr(services, 'urlopen', get)
    monkeypatch.setattr(services.time, 'sleep', lambda _: None)
    assert services.request('GET', 'https://example.com', {})['ok']
    assert len(calls) == 3


def test_rocketlane_payload_uses_configured_source_and_owner(monkeypatch):
    for key, value in {'ENTERPRISE_TEMPLATE_SOURCES': '[{"templateId":123}]',
                       'ROCKETLANE_OWNER_EMAIL': 'owner@example.com',
                       'ENTERPRISE_CSM_EMAIL': 'csm@example.com', 'ROCKETLANE_API_KEY': 'test'}.items():
        monkeypatch.setenv(key, value)
    sent = []
    def post(*args):
        sent.append(args)
        return {'projectId': 42}
    monkeypatch.setattr(services, 'request', post)
    run = {'plan': 'Enterprise', 'id': 'run-1', 'start_date': '2026-10-19', 'deal': {'customer_name': 'Acme'}}
    assert LiveServices().project(run) == '42'
    payload = sent[0][3]
    assert payload['sources'] == [{'templateId': 123}]
    assert payload['externalReferenceId'] == 'run-1'
    assert payload['teamMembers']['members'][0]['emailId'] == 'csm@example.com'


