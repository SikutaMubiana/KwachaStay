"""Database adapter for KwachaStay.

SQLite stays the zero-configuration local database. When ``DATABASE_URL`` is
set (Render + Supabase), the app uses PostgreSQL through a thin compatibility
layer that keeps the existing ``db.execute(sql, params)`` route code working:

- ``?`` placeholders become ``%s``.
- SQLite helpers used by the queries are rewritten to PostgreSQL equivalents.
- Rows support both ``row['column']`` and ``row[0]`` access like ``sqlite3.Row``.
- Inserts expose ``cursor.lastrowid`` by appending ``RETURNING id``.
"""
import os
import re
import sqlite3

try:
    import psycopg
except ImportError:  # local environments that only use SQLite
    psycopg = None


TABLES_WITH_ID = {
    'users', 'properties', 'property_images', 'reviews', 'review_photos',
    'bookings', 'payment_attempts', 'wishlists', 'messages', 'availability',
    'payout_methods', 'saved_searches', 'property_reports', 'support_requests',
    'notifications', 'trip_plans', 'calendar_imports', 'calendar_import_events',
    'seasonal_pricing', 'payout_ledger', 'email_messages', 'email_webhook_events',
}

INSERT_TARGET = re.compile(r'\bINSERT\s+INTO\s+"?([A-Za-z_]\w*)"?', re.IGNORECASE)

if psycopg is not None:
    DB_ERRORS = (sqlite3.Error, psycopg.Error)
    DB_INTEGRITY_ERRORS = (sqlite3.IntegrityError, psycopg.IntegrityError)
else:  # pragma: no cover - psycopg is a declared dependency
    DB_ERRORS = (sqlite3.Error,)
    DB_INTEGRITY_ERRORS = (sqlite3.IntegrityError,)


def postgres_url():
    return os.getenv('DATABASE_URL', '').strip()


class PgRow:
    """Row object with the mapping and positional access used by the app."""

    __slots__ = ('_names', '_values', '_index')

    def __init__(self, names, values):
        self._names = tuple(names)
        self._values = tuple(values)
        self._index = {name: position for position, name in enumerate(self._names)}

    def __getitem__(self, key):
        if isinstance(key, str):
            return self._values[self._index[key]]
        return self._values[key]

    def __iter__(self):
        return iter(self._values)

    def __len__(self):
        return len(self._values)

    def keys(self):
        return list(self._names)

    def values(self):
        return list(self._values)

    def items(self):
        return list(zip(self._names, self._values))

    def __repr__(self):
        return f'PgRow({dict(self.items())!r})'


def _row_factory(cursor):
    if not cursor.description:
        return lambda values: values
    names = [column.name for column in cursor.description]
    return lambda values: PgRow(names, values)


def translate_sql(sql):
    """Rewrite SQLite SQL into the PostgreSQL dialect used by Supabase."""
    original = sql
    sql = sql.replace('?', '%s')
    sql = re.sub(
        r'\bBEGIN\s+(?:IMMEDIATE|EXCLUSIVE|DEFERRED)\b', 'SELECT 1', sql, flags=re.IGNORECASE
    )
    ignored_insert = re.search(r'\bINSERT\s+OR\s+IGNORE\b', sql, re.IGNORECASE) is not None
    sql = re.sub(r'\bINSERT\s+OR\s+IGNORE\b', 'INSERT', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bINSERT\s+OR\s+REPLACE\b', 'INSERT', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bIFNULL\s*\(', 'COALESCE(', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bGROUP_CONCAT\s*\(', 'STRING_AGG(', sql, flags=re.IGNORECASE)
    sql = re.sub(r"\bdate\s*\(\s*'now'\s*\)", 'CURRENT_DATE', sql, flags=re.IGNORECASE)
    sql = re.sub(
        r"\bdatetime\s*\(\s*'now'\s*\)", 'CURRENT_TIMESTAMP', sql, flags=re.IGNORECASE
    )
    sql = re.sub(r'\blast_insert_rowid\s*\(\s*\)', 'lastval()', sql, flags=re.IGNORECASE)
    sql = re.sub(r'\bLIKE\b', 'ILIKE', sql, flags=re.IGNORECASE)
    sql = re.sub(
        r'julianday\(\s*([A-Za-z_][\w.]*)\s*\)', r'julianday((\1)::text)', sql,
        flags=re.IGNORECASE,
    )
    if ignored_insert and 'ON CONFLICT' not in sql.upper():
        sql = sql.rstrip().rstrip(';') + ' ON CONFLICT DO NOTHING'
    if original.rstrip().endswith(';'):
        sql = sql.rstrip().rstrip(';')
    return sql


def prepare_statement(sql, return_id=True):
    translated = translate_sql(sql)
    if not return_id or 'RETURNING' in translated.upper():
        return translated, False
    if not translated.lstrip().upper().startswith('INSERT'):
        return translated, False
    match = INSERT_TARGET.search(translated)
    if not match or match.group(1).lower() not in TABLES_WITH_ID:
        return translated, False
    return translated.rstrip().rstrip(';') + ' RETURNING id', True


class PgCursor:
    def __init__(self, connection, sql, params=None, return_id=True):
        translated, expects_id = prepare_statement(sql, return_id=return_id)
        self._raw = connection._connection.cursor()
        self.lastrowid = None
        self._raw.execute(translated, params)
        if expects_id and self._raw.description:
            row = self._raw.fetchone()
            self.lastrowid = row[0] if row is not None else None

    def __getattr__(self, name):
        return getattr(self._raw, name)

    def __iter__(self):
        return iter(self._raw)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self._raw.close()
        return False

    def close(self):
        self._raw.close()


class PgConnection:
    def __init__(self, database_url):
        if psycopg is None:
            raise RuntimeError('psycopg is required when DATABASE_URL is set.')
        self._connection = psycopg.connect(
            database_url,
            row_factory=_row_factory,
            connect_timeout=15,
            prepare_threshold=None,
            application_name='kwachastay',
        )

    def execute(self, sql, params=None):
        return PgCursor(self, sql, params)

    def executemany(self, sql, param_sequence):
        translated, _ = prepare_statement(sql, return_id=False)
        with self._connection.cursor() as cursor:
            cursor.executemany(translated, param_sequence)
        return self

    def executescript(self, script):
        for statement in filter(None, (part.strip() for part in script.split(';'))):
            self.execute(statement)

    def create_function(self, *_args, **_kwargs):
        return None

    def commit(self):
        self._connection.commit()

    def rollback(self):
        self._connection.rollback()

    def close(self):
        self._connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()
        return False


def connect(database_url):
    return PgConnection(database_url)
