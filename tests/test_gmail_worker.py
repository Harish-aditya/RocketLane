from urllib.error import HTTPError
import pytest
from app import services
from app.services import GmailService, IntegrationError


def test_unauthorized_gmail_request_refreshes_once(monkeypatch):
    monkeypatch.setenv('GMAIL_ACCESS_TOKEN', 'expired')
    gmail = GmailService()
    attempts = []
    def get(method, url, headers):
        attempts.append(headers['Authorization'])
        if len(attempts) == 1:
            raise IntegrationError('unauthorized') from HTTPError(url, 401, 'Unauthorized', None, None)
        return {'messages': []}
    def refresh():
        gmail.headers = {'Authorization': 'Bearer refreshed'}
    monkeypatch.setattr(services, 'request', get)
    monkeypatch.setattr(gmail, '_refresh', refresh)
    assert list(gmail.messages()) == []
    assert attempts == ['Bearer expired', 'Bearer refreshed']


def test_gmail_non_auth_failure_does_not_refresh(monkeypatch):
    monkeypatch.setenv('GMAIL_ACCESS_TOKEN', 'test')
    gmail = GmailService()
    def failed(*args):
        raise IntegrationError('unavailable')
    monkeypatch.setattr(services, 'request', failed)
    monkeypatch.setattr(gmail, '_refresh', lambda: pytest.fail('No refresh for non-auth failure'))
    with pytest.raises(IntegrationError):
        list(gmail.messages())
