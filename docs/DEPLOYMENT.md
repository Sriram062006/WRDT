# Deployment

## 1. Database (Supabase or any PostgreSQL 14+)
Supabase: take the **pooled** string (port 6543) for `DATABASE_URL` (asyncpg) and the **direct** string
(port 5432) for `DATABASE_URL_SYNC` (migrations only). Keep `DB_DISABLE_STATEMENT_CACHE=true` for the
pooler; set `false` for a direct connection.

## 2. Configuration
Set real environment variables (do not ship a `.env`):

| Variable | Production value |
|---|---|
| `APP_ENV` | `production` |
| `APP_DEBUG` | `false` |
| `SECRET_KEY`, `JWT_SECRET_KEY` | two different values from `python -c "import secrets;print(secrets.token_urlsafe(48))"` |
| `CORS_ORIGINS` | exact frontend origin(s); unnecessary when served same-origin |
| `LOG_JSON` | `true` |

## 3. Migrate and bootstrap (once per environment)
```bash
alembic upgrade head
python -m scripts.bootstrap --org "Your Organization" --email owner@yourdomain.org --name "Full Name"
# password: prompted, or via env var WRDT_BOOTSTRAP_PASSWORD. Never pass it as an argument.
```
Re-run `python -m scripts.seed_roles` after upgrades; it is idempotent.

## 4. Run the API
`uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers` (or the provided `Dockerfile`).
Behind a proxy on another host/container also set `--forwarded-allow-ips` so the login throttle sees real client IPs.

## 5. Frontend
`cd wrdt-frontend && npm ci && npm run build`, publish `dist/`, and proxy `/api/` to the API on the same origin —
see `deploy/nginx.conf.example`. Terminate TLS at the proxy.

## 6. Health
`GET /api/v1/health` (liveness) and `/api/v1/health/ready` (checks the database).

## 7. Backups
Back up the database (Supabase PITR or `pg_dump`). Completed meetings are immutable by design, so a restore
is the only way to correct one.
