"""
Apply Supabase Postgres migrations from supabase/migrations/*.sql

Uses the DATABASE_URL direct connection string. Safe to re-run:
migration files should be idempotent (IF NOT EXISTS etc.).

Usage:
    uv run python scripts/apply_migrations.py
"""

import os
import sys
import glob

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from dotenv import load_dotenv  # noqa: E402

project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
load_dotenv(os.path.join(project_root, '.env'))

DATABASE_URL = (
    os.environ.get('DATABASE_URL')
    or os.environ.get('POSTGRES_URL')
)

MIGRATIONS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '../../supabase/migrations')
)


def main():
    if not DATABASE_URL:
        print("ERROR: DATABASE_URL not configured (.env)")
        sys.exit(1)

    import psycopg

    # Supabase requires SSL on direct connections
    conninfo = DATABASE_URL
    if 'sslmode=' not in conninfo:
        conninfo += '?sslmode=require' if '?' not in conninfo else '&sslmode=require'

    migration_files = sorted(glob.glob(os.path.join(MIGRATIONS_DIR, '*.sql')))
    if not migration_files:
        print(f"No migration files found in {MIGRATIONS_DIR}")
        sys.exit(1)

    with psycopg.connect(conninfo) as conn:
        with conn.cursor() as cur:
            cur.execute("create table if not exists _migrations (name text primary key, applied_at timestamptz default now())")
            conn.commit()

            for path in migration_files:
                name = os.path.basename(path)
                cur.execute("select 1 from _migrations where name = %s", (name,))
                if cur.fetchone():
                    print(f"SKIP  {name} (already applied)")
                    continue

                with open(path, 'r', encoding='utf-8') as f:
                    sql = f.read()

                print(f"APPLY {name} ...")
                cur.execute(sql)
                cur.execute("insert into _migrations (name) values (%s)", (name,))
                conn.commit()
                print(f"OK    {name}")

    print("\nAll migrations applied.")


if __name__ == '__main__':
    main()
