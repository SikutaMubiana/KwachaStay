"""Copy the Supabase project URL and server key into .env without opening a browser.

Requires SUPABASE_ACCESS_TOKEN (and optionally SUPABASE_PROJECT_REF). Uses the
official Supabase Management API, prints only whether values were stored, and
never prints key material.

Usage:
  python scripts/sync_supabase_env.py --check
  python scripts/sync_supabase_env.py
"""
import argparse
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

try:
    from postgres_schema import ROOT
except ImportError:  # imported as a package from the project root
    from scripts.postgres_schema import ROOT

ENV_FILE = ROOT / '.env'


def load_env():
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ENV_FILE)


def project_ref():
    ref = os.getenv('SUPABASE_PROJECT_REF', '').strip()
    if ref:
        return ref
    host = urllib.parse.urlsplit(os.getenv('SUPABASE_URL', '').strip()).hostname or ''
    if host.endswith('.supabase.co'):
        return host.split('.')[0]
    raise SystemExit('Set SUPABASE_PROJECT_REF or SUPABASE_URL before syncing.')


def api_get(token, path):
    request = urllib.request.Request(
        f'https://api.supabase.com{path}',
        headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
        method='GET',
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            return json.loads(response.read() or b'[]')
    except urllib.error.HTTPError as error:
        detail = error.read().decode('utf-8', 'replace').strip()[:300]
        raise SystemExit(f'Supabase Management API error (HTTP {error.code}): {detail}') from error
    except urllib.error.URLError as error:
        raise SystemExit('The Supabase Management API could not be reached.') from error


def server_key(keys):
    for key in keys:
        name = str(key.get('name', '')).lower()
        if name == 'service_role' or name.startswith('service_role'):
            return key.get('api_key')
    for key in keys:
        if str(key.get('type', '')).lower() == 'secret':
            return key.get('api_key')
    return None


def read_env_lines():
    return ENV_FILE.read_text(encoding='utf-8').splitlines() if ENV_FILE.is_file() else []


def set_value(lines, key, value):
    pattern = re.compile(rf'^{re.escape(key)}=.*$')
    for index, line in enumerate(lines):
        if pattern.match(line):
            lines[index] = f'{key}={value}'
            return
    lines.append(f'{key}={value}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Only report current configuration')
    args = parser.parse_args()

    load_env()
    token = os.getenv('SUPABASE_ACCESS_TOKEN', '').strip()
    ref = project_ref()
    existing_url = os.getenv('SUPABASE_URL', '').strip()
    existing_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '').strip()

    if args.check:
        print(f'SUPABASE_PROJECT_REF: {ref}')
        print(f'SUPABASE_URL: {"SET" if existing_url else "EMPTY"}')
        print(f'SUPABASE_SERVICE_ROLE_KEY: {"SET" if existing_key else "EMPTY"}')
        return

    if not token:
        raise SystemExit('SUPABASE_ACCESS_TOKEN is required. Run setup_deployment.py --service supabase first.')

    keys = api_get(token, f'/v1/projects/{ref}/api-keys?reveal=true')
    if isinstance(keys, dict):
        keys = keys.get('data', [])
    key = server_key(keys)
    if not key:
        raise SystemExit('Supabase did not return a service-role or secret key for this project.')

    lines = read_env_lines()
    if not existing_url:
        set_value(lines, 'SUPABASE_URL', f'https://{ref}.supabase.co')
    set_value(lines, 'SUPABASE_SERVICE_ROLE_KEY', key)
    ENV_FILE.write_text('\n'.join(lines) + '\n', encoding='utf-8')
    print(f'SUPABASE_URL: SET (https://{ref}.supabase.co)')
    print(f'SUPABASE_SERVICE_ROLE_KEY: SET (len {len(key)})')


if __name__ == '__main__':
    main()
