# KwachaStay deployment guide

## Local preparation

1. Keep `kwachastay.db` as the source backup. Do not delete it.
2. Create a Supabase project, then copy its server-side PostgreSQL connection string into `DATABASE_URL` only in Render (and locally in `.env` while staging).
3. Create a **public** Supabase Storage bucket named `property-images`, or set `SUPABASE_STORAGE_BUCKET` to another public bucket name.

## Credentials

Run `python scripts/setup_deployment.py` in your terminal to enter missing tokens privately. `python scripts/setup_deployment.py --check` lists which values are still empty. Every service used here has a free tier.

## Supabase staging

`schema.sql` is the canonical model. `scripts/stage_supabase.py` converts it to PostgreSQL, creates the tables, creates the public storage bucket, and uploads/deletes a probe object. It is idempotent and never drops data.

```powershell
# Option A: run from this machine (set values in .env, never commit them)
python scripts/stage_supabase.py
python scripts/stage_supabase.py --check

# Option B: paste both scripts into the Supabase SQL editor
python scripts/stage_supabase.py --print-sql
```

The ready-to-paste bundle is also committed as [supabase_staging.sql](./supabase_staging.sql). Regenerate it after any `schema.sql` change.

Without the database password, an account-level Supabase personal access token in `SUPABASE_ACCESS_TOKEN` (plus `SUPABASE_PROJECT_REF`) lets the same script run the SQL through the Management API.


Then migrate data with a dry run first:

```powershell
python scripts/migrate_sqlite_to_postgres.py --database-url "$env:DATABASE_URL"
python scripts/migrate_sqlite_to_postgres.py --database-url "$env:DATABASE_URL" --apply
python scripts/verify_postgres.py --database-url "$env:DATABASE_URL"
```

## Render

Use [render.yaml](./render.yaml) as a Blueprint or create a Python Web Service manually.

- Build command: `pip install -r requirements.txt`
- Start command: `gunicorn --workers 2 --threads 4 --timeout 60 --bind 0.0.0.0:$PORT app:app`
- Health check: `/healthz`
- Set every secret in Render's Environment settings, never in Git.

## Brevo

Set `EMAIL_PROVIDER=brevo`, `BREVO_API_KEY`, `BREVO_SENDER_EMAIL`, and `BREVO_SENDER_NAME` in Render. Register the webhook URL as:

`https://your-domain/webhooks/brevo?token=<BREVO_WEBHOOK_TOKEN>`

Use a long random value for `BREVO_WEBHOOK_TOKEN`; it is required by the endpoint. Subscribe to delivery, bounce, blocked, invalid-address, deferred, and spam events.

## Runtime database

`app.py` uses SQLite only when `DATABASE_URL` is empty. When `DATABASE_URL` is set, `database.py` connects to PostgreSQL and translates the existing route SQL (placeholders, `julianday`, `date('now')`, `INSERT OR IGNORE`, `lastrowid`, case-insensitive `LIKE`, and the distance helper). Apply the Supabase staging schema before pointing the live service at that database.

## Important limitation

Do not point production traffic at a partially migrated database. Run `scripts/stage_supabase.py --check` and `scripts/verify_postgres.py` first, then deploy with `DATABASE_URL` set in Render.
