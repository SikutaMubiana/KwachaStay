"""Collect the deployment credentials locally and write them to .env.

Run this in your own terminal so secrets never pass through chat:

  python scripts/setup_deployment.py          # prompt for anything missing
  python scripts/setup_deployment.py --check  # show which values are present

Existing non-empty values are kept. All four services work on their free tiers.
"""
import argparse
import getpass
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / '.env'

FIELDS = [
    ('SUPABASE_ACCESS_TOKEN', 'Supabase access token (Account -> Access Tokens)', True),
    ('DATABASE_URL', 'Supabase Postgres URI (Connect -> Session pooler)', True),
    ('GITHUB_TOKEN', 'GitHub fine-grained PAT (Contents + Administration: write)', True),
    ('GITHUB_USERNAME', 'GitHub username', False),
    ('RENDER_API_KEY', 'Render API key (Account Settings -> API Keys)', True),
    ('BREVO_API_KEY', 'Brevo API key (SMTP & API -> API Keys)', True),
    ('BREVO_SENDER_EMAIL', 'Verified Brevo sender email', False),
]


def read_env():
    if not ENV_FILE.is_file():
        return []
    return ENV_FILE.read_text(encoding='utf-8').splitlines()


def current_value(lines, key):
    pattern = re.compile(rf'^{re.escape(key)}=(.*)$')
    for line in lines:
        match = pattern.match(line)
        if match:
            return match.group(1).strip()
    return ''


def write_value(lines, key, value):
    pattern = re.compile(rf'^{re.escape(key)}=.*$')
    for index, line in enumerate(lines):
        if pattern.match(line):
            lines[index] = f'{key}={value}'
            return
    lines.append(f'{key}={value}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Only report which values are set')
    args = parser.parse_args()

    lines = read_env()
    missing = []
    for key, _label, _secret in FIELDS:
        value = current_value(lines, key)
        if args.check:
            print(f'{key}: {"SET" if value else "EMPTY"}')
        elif not value:
            missing.append(key)

    if args.check:
        return

    for key, label, secret in FIELDS:
        if current_value(lines, key):
            continue
        prompt = f'{label}: '
        value = getpass.getpass(prompt) if secret else input(prompt)
        value = value.strip()
        if not value:
            raise SystemExit(f'{key} is required. Re-run when you have it.')
        write_value(lines, key, value)

    if not ENV_FILE.is_file():
        raise SystemExit('.env was not found. Create it from .env.example first.')
    ENV_FILE.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print('Deployment credentials saved to .env (not committed). You can now ask Kilo to deploy.')


if __name__ == '__main__':
    main()
