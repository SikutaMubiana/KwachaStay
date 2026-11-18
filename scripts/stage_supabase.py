"""Stage the KwachaStay Supabase project (schema + public storage bucket).

The script is idempotent: it creates tables only if they do not exist, reuses an
existing bucket, and never drops or truncates application data. Run it after
setting the staging values in .env (never commit those values):

  DATABASE_URL=postgresql://...        # Supabase Postgres connection string
  SUPABASE_URL=https://<ref>.supabase.co
  SUPABASE_SERVICE_ROLE_KEY=...        # server only
  SUPABASE_STORAGE_BUCKET=property-images

Usage:
  python scripts/stage_supabase.py              # schema + bucket + upload probe
  python scripts/stage_supabase.py --check      # read-only verification
  python scripts/stage_supabase.py --skip-probe # skip the upload round trip

When SUPABASE_ACCESS_TOKEN is set and DATABASE_URL is empty, SQL runs through
the Supabase Management API, which is the same path as the dashboard SQL editor.
"""
import argparse
import io
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import uuid

try:
    from postgres_schema import ROOT, build_schema_sql
except ImportError:  # imported as a package from the project root
    from scripts.postgres_schema import ROOT, build_schema_sql

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DEFAULT_BUCKET = 'property-images'
BUCKET_DDL = """
-- Supabase Storage bucket for listing images (public read).
INSERT INTO storage.buckets (id, name, public)
VALUES ('{bucket}', '{bucket}', true)
ON CONFLICT (id) DO UPDATE SET public = EXCLUDED.public;
"""


def load_env():
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv(ROOT / '.env')


def require(name):
    value = os.getenv(name, '').strip()
    if not value:
        raise SystemExit(
            f'{name} is not set. Add it to .env (server only) before staging Supabase.'
        )
    return value


def project_ref():
    ref = os.getenv('SUPABASE_PROJECT_REF', '').strip()
    if ref:
        return ref
    host = urllib.parse.urlsplit(os.getenv('SUPABASE_URL', '').strip()).hostname or ''
    if host.endswith('.supabase.co'):
        return host.split('.')[0]
    raise SystemExit('Set SUPABASE_PROJECT_REF or SUPABASE_URL to identify the Supabase project.')


def management_query(access_token, ref, query):
    """Run SQL through the Supabase Management API with a personal access token."""
    request = urllib.request.Request(
        f'https://api.supabase.com/v1/projects/{ref}/database/query',
        data=json.dumps({'query': query}).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json',
        },
        method='POST',
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            body = response.read()
            return json.loads(body) if body.strip() else None
    except urllib.error.HTTPError as error:
        detail = error.read().decode('utf-8', 'replace').strip()[:400]
        raise SystemExit(
            f'Supabase Management API rejected the query (HTTP {error.code}): {detail}'
        ) from error
    except urllib.error.URLError as error:
        raise SystemExit('The Supabase Management API could not be reached.') from error


def _result_rows(result):
    if isinstance(result, dict):
        result = result.get('result', [])
    return result or []


def stage_via_management_api(access_token, ref, bucket, include_schema=True, include_bucket=True):
    statements = []
    if include_schema:
        statements.append(build_schema_sql())
    if include_bucket:
        statements.append(BUCKET_DDL.format(bucket=bucket.replace("'", "''")).strip())
    if not statements:
        return
    management_query(access_token, ref, '\n\n'.join(statements))
    print(f'Management API applied the staging SQL to project "{ref}".')


def verify_via_management_api(access_token, ref, bucket, check_schema=True, check_bucket=True):
    if check_schema:
        rows = _result_rows(management_query(
            access_token, ref,
            "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename",
        ))
        tables = [row.get('tablename') for row in rows if isinstance(row, dict)]
        required = {'users', 'properties', 'bookings', 'property_images', 'email_messages'}
        missing = required - set(tables)
        if missing:
            raise SystemExit(f'Missing required tables: {", ".join(sorted(missing))}')
        print(f'Schema check passed: {len(tables)} public tables, required tables present.')

    if check_bucket:
        rows = _result_rows(management_query(
            access_token, ref,
            f"SELECT id, public FROM storage.buckets WHERE id = '{bucket.replace(chr(39), chr(39) * 2)}'",
        ))
        if not rows:
            raise SystemExit(f'Storage bucket "{bucket}" does not exist yet.')
        bucket_row = rows[0] if isinstance(rows[0], dict) else {}
        if not bucket_row.get('public'):
            raise SystemExit(f'Storage bucket "{bucket}" exists but is not public.')
        print(f'Storage check passed: bucket "{bucket}" exists and is public.')



class StorageApi:
    def __init__(self, base_url, service_role_key):
        self.base_url = base_url.rstrip('/')
        self.service_role_key = service_role_key

    def request(self, method, path, payload=None):
        data = json.dumps(payload).encode('utf-8') if payload is not None else None
        headers = {
            'Authorization': f'Bearer {self.service_role_key}',
            'apikey': self.service_role_key,
        }
        if data is not None:
            headers['Content-Type'] = 'application/json'
        request = urllib.request.Request(
            f'{self.base_url}{path}', data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                body = response.read()
                return response.status, (json.loads(body) if body.strip() else None)
        except urllib.error.HTTPError as error:
            body = error.read().decode('utf-8', 'replace')
            try:
                body = json.loads(body)
            except ValueError:
                pass
            return error.code, body
        except urllib.error.URLError as error:
            raise RuntimeError('Supabase Storage could not be reached.') from error


def apply_schema(database_url):
    try:
        import psycopg
    except ImportError as error:
        raise SystemExit('Install requirements.txt before staging Supabase.') from error

    with psycopg.connect(database_url, connect_timeout=20) as connection:
        with connection.cursor() as cursor:
            cursor.execute(build_schema_sql())
        connection.commit()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
            )
            tables = [row[0] for row in cursor.fetchall()]
            cursor.execute('SELECT current_database(), current_user')
            database, user = cursor.fetchone()

    print(f'Applied PostgreSQL schema to database "{database}" as "{user}".')
    print(f'{len(tables)} public tables present: {", ".join(tables)}')
    return tables


def bucket_state(api, bucket):
    status, body = api.request('GET', f'/storage/v1/bucket/{urllib.parse.quote(bucket)}')
    if status == 200 and isinstance(body, dict):
        return body
    if status in (400, 404):
        return None
    raise SystemExit(f'Could not read storage bucket "{bucket}" (HTTP {status}): {body}')


def ensure_bucket(api, bucket):
    state = bucket_state(api, bucket)
    if state is None:
        status, body = api.request(
            'POST', '/storage/v1/bucket', {'id': bucket, 'name': bucket, 'public': True}
        )
        if status in (200, 201):
            print(f'Created public storage bucket "{bucket}".')
            return
        if status != 409:
            raise SystemExit(f'Could not create storage bucket "{bucket}" (HTTP {status}): {body}')
        state = bucket_state(api, bucket)
        if state is None:
            raise SystemExit(f'Storage bucket "{bucket}" exists but could not be read.')
        print(f'Storage bucket "{bucket}" already existed.')

    if not state.get('public'):
        status, body = api.request(
            'PUT', f'/storage/v1/bucket/{urllib.parse.quote(bucket)}', {'public': True}
        )
        if status not in (200, 201):
            raise SystemExit(
                f'Storage bucket "{bucket}" is private and could not be made public '
                f'(HTTP {status}): {body}'
            )
        print(f'Made existing storage bucket "{bucket}" public.')
    else:
        print(f'Storage bucket "{bucket}" is already public.')


def probe_storage(api, base_url, bucket):
    from supabase_storage import SupabaseUploadStorage

    storage = SupabaseUploadStorage(
        url=base_url,
        service_role_key=api.service_role_key,
        bucket=bucket,
    )
    object_name = f'staging-probe-{uuid.uuid4().hex}.txt'
    probe = io.BytesIO(b'KwachaStay storage staging probe')
    probe.mimetype = 'text/plain'
    public_url = storage.save(probe, object_name)
    try:
        with urllib.request.urlopen(public_url, timeout=20) as response:
            if response.status != 200:
                raise SystemExit(f'Upload probe is not publicly readable (HTTP {response.status}).')
    finally:
        storage.delete(public_url)
    print('Upload probe succeeded: the bucket accepts writes and serves public reads.')


def verify(database_url, bucket, api):
    if database_url:
        try:
            import psycopg
        except ImportError as error:
            raise SystemExit('Install requirements.txt before verifying Supabase.') from error
        with psycopg.connect(database_url, connect_timeout=20) as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT tablename FROM pg_tables WHERE schemaname = 'public' ORDER BY tablename"
                )
                tables = [row[0] for row in cursor.fetchall()]
        required = {'users', 'properties', 'bookings', 'property_images', 'email_messages'}
        missing = required - set(tables)
        if missing:
            raise SystemExit(f'Missing required tables: {", ".join(sorted(missing))}')
        print(f'Schema check passed: {len(tables)} public tables, required tables present.')

    if api:
        state = bucket_state(api, bucket)
        if state is None:
            raise SystemExit(f'Storage bucket "{bucket}" does not exist yet.')
        if not state.get('public'):
            raise SystemExit(f'Storage bucket "{bucket}" exists but is not public.')
        print(f'Storage check passed: bucket "{bucket}" exists and is public.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Only verify schema and bucket state')
    parser.add_argument('--print-sql', action='store_true',
                        help='Print schema and bucket SQL for the Supabase SQL editor and exit')
    parser.add_argument('--skip-schema', action='store_true', help='Do not touch PostgreSQL')
    parser.add_argument('--skip-bucket', action='store_true', help='Do not touch Storage')
    parser.add_argument('--skip-probe', action='store_true', help='Skip the storage upload round trip')
    args = parser.parse_args()

    load_env()
    database_url = os.getenv('DATABASE_URL', '').strip()
    base_url = os.getenv('SUPABASE_URL', '').strip()
    bucket = os.getenv('SUPABASE_STORAGE_BUCKET', DEFAULT_BUCKET).strip() or DEFAULT_BUCKET
    token = os.getenv('SUPABASE_ACCESS_TOKEN', '').strip()

    if args.print_sql:
        print(build_schema_sql())
        print(BUCKET_DDL.format(bucket=bucket.replace("'", "''")).strip())
        return

    if args.check:
        verified = False
        if database_url and not args.skip_schema:
            verify(database_url, bucket, None)
            verified = True
        elif token:
            verify_via_management_api(
                token, project_ref(), bucket,
                check_schema=not args.skip_schema,
                check_bucket=not args.skip_bucket,
            )
            verified = True
        if database_url and not args.skip_bucket and base_url:
            service_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY', '').strip()
            if service_key:
                state = bucket_state(StorageApi(base_url, service_key), bucket)
                if state is None:
                    raise SystemExit(f'Storage bucket "{bucket}" does not exist yet.')
                if not state.get('public'):
                    raise SystemExit(f'Storage bucket "{bucket}" exists but is not public.')
                print(f'Storage check passed: bucket "{bucket}" exists and is public.')
                verified = True
        if not verified:
            raise SystemExit('Set SUPABASE_ACCESS_TOKEN or DATABASE_URL before checking Supabase.')
        return

    if token:
        stage_via_management_api(
            token, project_ref(), bucket,
            include_schema=not args.skip_schema,
            include_bucket=not args.skip_bucket,
        )
        verify_via_management_api(
            token, project_ref(), bucket,
            check_schema=not args.skip_schema,
            check_bucket=not args.skip_bucket,
        )
        print('Supabase staging complete.')
        return

    if not args.skip_schema:
        apply_schema(require('DATABASE_URL'))
    if not args.skip_bucket:
        api = StorageApi(require('SUPABASE_URL'), require('SUPABASE_SERVICE_ROLE_KEY'))
        ensure_bucket(api, bucket)
        if not args.skip_probe:
            probe_storage(api, base_url, bucket)
    print('Supabase staging complete.')


if __name__ == '__main__':
    try:
        main()
    except RuntimeError as error:
        raise SystemExit(str(error))
