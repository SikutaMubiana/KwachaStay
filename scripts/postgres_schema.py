"""Generate the PostgreSQL schema for Supabase from the canonical schema.sql.

schema.sql stays the single source of truth for local SQLite development. This
module translates the SQLite DDL into equivalent PostgreSQL DDL:

- ``INTEGER PRIMARY KEY AUTOINCREMENT`` becomes ``BIGSERIAL PRIMARY KEY``.
- ``BOOLEAN`` becomes ``INTEGER`` because the application stores and compares
  flags as 0/1, so PostgreSQL keeps identical route behavior.
- ``REAL`` becomes ``DOUBLE PRECISION`` to avoid float4 rounding on money.
- SQLite helper functions used by queries (``julianday``, ``distance_km``) are
  added as PostgreSQL functions.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQLITE_SCHEMA = ROOT / 'schema.sql'

AUTOINCREMENT = re.compile(
    r'\bid\s+INTEGER\s+PRIMARY\s+KEY\s+AUTOINCREMENT\b', re.IGNORECASE
)
BOOLEAN_TYPE = re.compile(r'\bBOOLEAN\b', re.IGNORECASE)
REAL_TYPE = re.compile(r'\bREAL\b', re.IGNORECASE)

POSTGRES_FUNCTIONS = """
CREATE OR REPLACE FUNCTION julianday(ts text, modifier text DEFAULT NULL)
RETURNS double precision
LANGUAGE sql STABLE
AS $$
    SELECT EXTRACT(EPOCH FROM (
        (CASE WHEN ts = 'now' THEN now()::text ELSE ts END)::timestamp
        + COALESCE(modifier, '0 days')::interval
    )) / 86400.0 + 2440587.5
$$;

CREATE OR REPLACE FUNCTION distance_km(
    latitude_a double precision,
    longitude_a double precision,
    latitude_b double precision,
    longitude_b double precision
)
RETURNS double precision
LANGUAGE sql IMMUTABLE
AS $$
    SELECT CASE
        WHEN latitude_a IS NULL OR longitude_a IS NULL
             OR latitude_b IS NULL OR longitude_b IS NULL THEN NULL
        ELSE 6371 * 2 * ASIN(SQRT(LEAST(1,
            POWER(SIN(RADIANS(latitude_b - latitude_a) / 2), 2)
            + COS(RADIANS(latitude_a)) * COS(RADIANS(latitude_b))
            * POWER(SIN(RADIANS(longitude_b - longitude_a) / 2), 2)
        )))
    END
$$;
"""


def build_schema_sql():
    """Return PostgreSQL DDL generated from schema.sql."""
    source = SQLITE_SCHEMA.read_text(encoding='utf-8')
    source = AUTOINCREMENT.sub('id BIGSERIAL PRIMARY KEY', source)
    source = BOOLEAN_TYPE.sub('INTEGER', source)
    source = REAL_TYPE.sub('DOUBLE PRECISION', source)
    header = (
        '-- Generated from schema.sql for PostgreSQL (Supabase).\n'
        '-- Regenerate with: python scripts/migrate_sqlite_to_postgres.py --print-schema\n\n'
    )
    return header + source + POSTGRES_FUNCTIONS


if __name__ == '__main__':
    print(build_schema_sql())
