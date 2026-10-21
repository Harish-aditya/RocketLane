from types import SimpleNamespace
from dotenv import dotenv_values

from scripts import gmail_authorize


def test_authorization_is_readonly_and_preserves_configuration(tmp_path, monkeypatch, capsys):
    env = tmp_path / '.env'
    env.write_text('GMAIL_CLIENT_ID=test-client\nGMAIL_CLIENT_SECRET=test-secret\nROCKETLANE_API_KEY=keep-me\n')
    calls = {}
    class Flow:
        def run_local_server(self, **kwargs):
            calls['browser'] = kwargs
            return SimpleNamespace(token='private-access', refresh_token='private-refresh', expiry=None)
    def create(config, scopes, **kwargs):
        calls['scopes'] = scopes
        calls['pkce'] = kwargs
        return Flow()
    monkeypatch.setattr(gmail_authorize.InstalledAppFlow, 'from_client_config', create)
    gmail_authorize.authorize(env)
    values = dotenv_values(env)
    assert values['GMAIL_ACCESS_TOKEN'] == 'private-access'
    assert values['GMAIL_REFRESH_TOKEN'] == 'private-refresh'
    assert values['ROCKETLANE_API_KEY'] == 'keep-me'
    assert calls['scopes'] == ['https://www.googleapis.com/auth/gmail.readonly']
    assert calls['pkce']['autogenerate_code_verifier'] is True
    assert calls['browser']['host'] == 'localhost'
    assert calls['browser']['access_type'] == 'offline'
    output = capsys.readouterr().out
    assert 'private-access' not in output and 'private-refresh' not in output and 'test-secret' not in output
