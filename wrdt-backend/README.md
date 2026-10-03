# WRDT backend

FastAPI + async SQLAlchemy + Alembic on PostgreSQL. See the top-level `README.md` for setup.

- `app/api/v1/` routes · `app/services/` business logic (`ledger_engine.py` = all register arithmetic,
  `access.py` = tenant/role scoping) · `app/repositories/` queries · `app/models/` ORM
- `app/db/migrations/versions/0001…0006` — schema, case-insensitive uniqueness, one-open-meeting rule,
  **permanent meeting lock triggers**, audit-log hardening, revoked tokens
- `scripts/seed_roles.py` (idempotent) · `scripts/bootstrap.py` (first Owner)
- `tests/` — 90+ tests against real PostgreSQL; run `pytest -q`

Every by-ID route resolves its object through `app/services/access.py`. A foreign-organization ID returns 404;
an unassigned Supervisor gets 403. Do not fetch tenant data by bare UUID in new code.

Interactive API docs: `/docs` (only when `APP_DEBUG=true`).
