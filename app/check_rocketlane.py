"""Read a Rocketlane project using ROCKETLANE_API_KEY and ROCKETLANE_PROJECT_ID."""
import argparse
import json
import os
import sys
from pathlib import Path
from urllib.error import HTTPError

from dotenv import load_dotenv

from .rocketlane_agent import RocketlaneAgent
from .services import IntegrationError


def check_connection(env_file=None):
    load_dotenv(env_file or Path(__file__).resolve().parents[1] / '.env', override=False)
    if not os.getenv('ROCKETLANE_API_KEY', '').strip():
        raise ValueError('Set ROCKETLANE_API_KEY in .env')
    project_id = os.getenv('ROCKETLANE_PROJECT_ID', '').strip()
    if not project_id or not project_id.isascii() or not project_id.isdigit() or int(project_id) <= 0:
        raise ValueError('Set ROCKETLANE_PROJECT_ID to a real positive numeric project ID in .env')
    project = RocketlaneAgent().project(project_id)
    if not isinstance(project, dict) or str(project.get('projectId')) != project_id:
        raise ValueError('Unexpected project response; the returned project ID does not match')
    return {'connected': True, 'read_only': True, 'project_id': project_id, 'project': project}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--env-file', type=Path, help='Optional .env path; defaults to the repository .env')
    args = parser.parse_args(argv)
    try:
        result = check_connection(args.env_file)
    except ValueError as exc:
        print(json.dumps({'connected': False, 'error': str(exc)}), file=sys.stderr)
        return 1
    except IntegrationError as exc:
        cause = exc.__cause__
        code = cause.code if isinstance(cause, HTTPError) else None
        reasons = {401: 'API key rejected. Check ROCKETLANE_API_KEY.',
                   403: 'Access denied. Check API key permissions and tenant access.',
                   404: 'Project not found or unavailable to this API key.',
                   429: 'Rate limit reached. Retry later.'}
        # Never print provider error bodies, request headers or credentials.
        print(json.dumps({'connected': False, 'http_status': code,
                          'error': reasons.get(code, 'Connection failed. Check configuration, network and Rocketlane availability.')}),
              file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
