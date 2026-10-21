"""Interactive desktop Gmail OAuth. Never prints tokens or client secrets."""
import argparse
import os
from pathlib import Path

from dotenv import dotenv_values, set_key
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def authorize(env_path, timeout=300):
    settings = {**dotenv_values(env_path), **os.environ}
    for key in ['GMAIL_CLIENT_ID', 'GMAIL_CLIENT_SECRET']:
        if not settings.get(key):
            raise ValueError(f'Missing {key} in environment or .env')
    config = {'installed': {
        'client_id': settings['GMAIL_CLIENT_ID'],
        'client_secret': settings['GMAIL_CLIENT_SECRET'],
        'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
        'token_uri': 'https://oauth2.googleapis.com/token',
        'redirect_uris': ['http://localhost'],
    }}
    flow = InstalledAppFlow.from_client_config(config, SCOPES, autogenerate_code_verifier=True)
    print('Opening Google authorization. Sign in to the Gmail account to monitor and approve read-only access.', flush=True)
    credentials = flow.run_local_server(
        host='localhost', port=0, open_browser=True, timeout_seconds=timeout,
        authorization_prompt_message='If a browser does not open, retry this command from your local terminal.',
        success_message='Gmail authorization completed. You can close this tab and return to Codex.',
        access_type='offline', prompt='consent',
    )
    if not credentials.token:
        raise ValueError('Google did not return an access token')
    set_key(str(env_path), 'GMAIL_ACCESS_TOKEN', credentials.token)
    if credentials.refresh_token:
        set_key(str(env_path), 'GMAIL_REFRESH_TOKEN', credentials.refresh_token)
    if credentials.expiry:
        set_key(str(env_path), 'GMAIL_TOKEN_EXPIRY', credentials.expiry.isoformat())
    print('Gmail access token saved to .env. Token values were not printed.', flush=True)
    print('Refresh token saved.' if credentials.refresh_token else 'No refresh token returned.', flush=True)
    print('Scope: Gmail read-only.', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, default=Path(__file__).resolve().parents[1] / '.env')
    parser.add_argument('--timeout', type=int, default=300)
    args = parser.parse_args()
    try:
        authorize(args.env_file, args.timeout)
    except Exception as exc:
        # Provider exceptions may contain authorization codes and token responses.
        print(f'Gmail authorization did not complete ({type(exc).__name__}). No token values printed.', flush=True)
        raise SystemExit(1) from None


if __name__ == '__main__':
    main()
