"""One-time password and Gemini setup. Compatible with host Python 3.9+."""
import getpass
import json
import os
from pathlib import Path
import secrets
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from portal.auth import password_record


def save(path, value):
    # Exclusive creation prevents accidentally replacing an existing setup.
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(value, stream, indent=2)
    # Compose bind-backed secrets must be readable by the non-root container.
    # The containing host directory is private (0700 on POSIX).
    path.chmod(0o644)


def main():
    runtime = ROOT / 'runtime'
    credentials = runtime / 'credentials.json'
    if not credentials.exists():
        print('First run: py -3.9 scripts/setup.py')
        return 1
    runtime.chmod(0o700)
    portal = runtime / 'portal-config.json'
    runner = runtime / 'runner-config.json'
    if portal.exists() and runner.exists():
        print('Existing web setup preserved. Your passwords and Gemini settings are already saved.')
        return 0
    if portal.exists() or runner.exists():
        print('Partial web configuration found. Keep these files private and request setup recovery help.')
        return 1
    print('Create local login passwords. These are not your Google or GitHub passwords.')
    accounts = {}
    used = set()
    for role in ('analyst', 'responder', 'reviewer'):
        while True:
            password = getpass.getpass('Choose password for ' + role + ' (12+ characters): ')
            if len(password) < 12 or len(password) > 256 or password in used:
                print('Use 12–256 characters and a different password for each account.')
                continue
            if password != getpass.getpass('Confirm password: '):
                print('Passwords did not match. Try again.')
                continue
            accounts[role] = password_record(password)
            used.add(password)
            break
    key = getpass.getpass('Paste your Gemini API key (hidden): ').strip()
    if not key:
        print('A Gemini key is required. No web configuration was saved.')
        return 1
    model = input('Gemini model [gemini-3.5-flash-lite]: ').strip() or 'gemini-3.5-flash-lite'
    shared = secrets.token_urlsafe(32)
    save(runner, {'api_key': key, 'model': model, 'runner_secret': shared})
    save(portal, {'accounts': accounts, 'tokens': json.loads(credentials.read_text()),
                  'runner_secret': shared, 'origin': 'http://127.0.0.1:8001'})
    print('Web setup saved locally. No passwords or keys were printed.')
    print('Start: docker compose --profile ui up --build -d portal')
    print('Open http://127.0.0.1:8001 and sign in with your chosen password.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
