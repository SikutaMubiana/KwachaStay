"""Generate the PostgreSQL schema for Supabase from the canonical schema.sql.

schema.sql stays the single source of truth for local SQLite development. This
module translates the SQLite DDL into equivalent PostgreSQL DDL:

- ``INTEGER PRIMARY KEY AUTOINCREMENT`` becomes ``BIGSERIAL PRIMARY KEY``.
- ``BOOLEAN ... DEFAULT 0/1`` becomes ``BOOLEAN ... DEFAULT FALSE/TRUE``.

Everything else in schema.sql is already valid PostgreSQL.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQLITE_SCHEMA = ROOT / 'schema.sql'

AUTOINCREMENT = re.compile(
    r'\bid\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b', re.IGNORECASE
)
BOOLEAN_DEFAULT = re.compile(
    r'\bBOOLEAN\b([^,\n]*?)DEFAULT\s+([01])\b', re.IGNORECASE
)


def _boolean_default(match):
    value = 'TRUE' if match.group(2) == '1' else 'FALSE'
    return f'BOOLEAN{match.group(1)}DEFAULT {value}'


def build_schema_sql():
    """Return PostgreSQL DDL generated from schema.sql."""
    source = SQLITE_SCHEMA.read_text(encoding='utf-8')
    source = AUTOINCREMENT.sub('id BIGSERIAL PRIMARY KEY', source)
    source = BOOLEAN_DEFAULT.sub(_boolean_default, source)
    header = (
        '-- Generated from schema.sql for PostgreSQL (Supabase).\n'
        '-- Regenerate with: python scripts/migrate_sqlite_to_postgres.py --print-schema\n\n'
    )
    return header + source


if __name__ == '__main__':
    print(build_schema_sql())
