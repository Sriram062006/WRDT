# WRDT — Women's Rural Development Technology

SHG savings / loan / meeting-register system.

- `wrdt-backend/` — FastAPI + SQLAlchemy (async) + Alembic, PostgreSQL (Supabase-compatible)
- `wrdt-frontend/` — React 19 + Vite
- `deploy/` — example nginx config
- `docs/` — deployment, testing, change log, known limitations

## Quick start (local development)

Prerequisites: Python 3.12, Node 20+, PostgreSQL 14+.

```bash
# 1. database
createdb wrdt

# 2. backend
cd wrdt-backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then edit DATABASE_URL(_SYNC) and generate two different secrets
alembic upgrade head            # creates all tables, triggers, indexes
python -m scripts.bootstrap     # creates the first Organization + Owner (prompts for password)
uvicorn app.main:app --reload   # http://127.0.0.1:8000  (docs at /docs when APP_DEBUG=true)

# 3. frontend (new terminal)
cd wrdt-frontend
npm install
npm run dev                     # http://localhost:5173, proxies /api to :8000
```

Sign in with the Owner you bootstrapped. From **Settings → Add User** create Supervisors,
then assign them groups; a Supervisor can only see and edit groups assigned to them.

## Production

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md). In short: set real environment variables
(`APP_ENV=production`, two distinct random secrets), run `alembic upgrade head`,
run `python -m scripts.bootstrap`, serve `wrdt-frontend/dist` and reverse-proxy `/api` to the API
on one origin. In production the API **refuses to start** with placeholder secrets,
`APP_DEBUG=true`, or `CORS_ORIGINS=*`.

## Tests

```bash
cd wrdt-backend && pip install -r requirements-dev.txt
createdb wrdt_test
pytest -q            # needs PostgreSQL; the schema is built by the real migrations
ruff check app scripts tests
cd ../wrdt-frontend && npm run lint && npm run build
```

Read [docs/CHANGES.md](docs/CHANGES.md) for what was fixed and [docs/KNOWN_LIMITATIONS.md](docs/KNOWN_LIMITATIONS.md) before go-live.
