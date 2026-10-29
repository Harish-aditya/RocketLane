from urllib.error import HTTPError

from app import check_rocketlane
from app.services import IntegrationError


def test_connection_reads_dotenv_and_fetches_project(tmp_path, monkeypatch):
    monkeypatch.delenv('ROCKETLANE_API_KEY', raising=False)
    monkeypatch.delenv('ROCKETLANE_PROJECT_ID', raising=False)
    env = tmp_path / '.env'
    env.write_text('ROCKETLANE_API_KEY=test-secret\nROCKETLANE_PROJECT_ID=123\n')
    monkeypatch.setattr(check_rocketlane.RocketlaneAgent, 'project', lambda self, pid: {'projectId': int(pid), 'projectName': 'Acme'})
    result = check_rocketlane.check_connection(env)
    assert result['connected'] and result['project']['projectName'] == 'Acme'
    assert 'test-secret' not in str(result)
    # load_dotenv mutates process environment, so remove the fixture values.
    check_rocketlane.os.environ.pop('ROCKETLANE_API_KEY', None)
    check_rocketlane.os.environ.pop('ROCKETLANE_PROJECT_ID', None)


def test_missing_configuration_never_calls_provider(tmp_path, monkeypatch, capsys):
    env = tmp_path / '.env'
    env.write_text('ROCKETLANE_PROJECT_ID=demo-project-123\n')
    monkeypatch.setenv('ROCKETLANE_API_KEY', 'secret')
    monkeypatch.setenv('ROCKETLANE_PROJECT_ID', 'demo-project-123')
    monkeypatch.setattr(check_rocketlane.RocketlaneAgent, 'project', lambda *args: (_ for _ in ()).throw(AssertionError('No request allowed')))
    assert check_rocketlane.main(['--env-file', str(env)]) == 1
    assert 'positive numeric' in capsys.readouterr().err


def test_authentication_error_is_actionable_and_redacted(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv('ROCKETLANE_API_KEY', 'secret-do-not-print')
    monkeypatch.setenv('ROCKETLANE_PROJECT_ID', '123')
    def fail(*args):
        raise IntegrationError('Internal request details') from HTTPError('https://api.rocketlane.com', 401, 'secret-do-not-print', {}, None)
    monkeypatch.setattr(check_rocketlane.RocketlaneAgent, 'project', fail)
    assert check_rocketlane.main(['--env-file', str(tmp_path / 'unused')]) == 1
    error = capsys.readouterr().err
    assert 'API key rejected' in error
    assert 'secret-do-not-print' not in error
