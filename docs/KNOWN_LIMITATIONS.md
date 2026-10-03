# Known limitations — read before go-live

**Not tested in this environment**
- **Supabase itself.** All testing used a local PostgreSQL 16. The pooler settings (`DB_DISABLE_STATEMENT_CACHE`,
  ports 6543/5432) follow Supabase's documented behaviour but have not been run against a real Supabase project.
  Run `alembic upgrade head` and the smoke test below against a staging project first.
- **Docker.** The `Dockerfile`/`docker-compose.yml` were not built or run (no Docker available).
- **Browsers/devices.** Browser testing was Chromium via Playwright only (desktop, 820px tablet and 375px phone
  viewports). Not tested on Safari, Firefox, or real touch devices.
- **TLS / reverse proxy.** `deploy/nginx.conf.example` is a starting point and was not run.

**Design limits**
- Login throttling is in-process: correct for one API instance, not shared across several. Run one worker or move it to Redis.
- Tokens are kept in `localStorage` (standard for SPAs, but readable by any script injected via XSS). A strict CSP at the proxy is recommended.
- Tamil translation covers navigation, login and register labels; remaining text falls back to English. Have a native speaker review before launch.
- A completed meeting is immutable by design (also enforced by DB triggers). Corrections require a database restore or a deliberate migration.
- Frontend has no unit tests; the single JS bundle is ~630 kB (≈184 kB gzipped).
- `meeting_date` advances by 15 days from the previous meeting; there is no UI to pick a different date.
- Audit-log append-only protection applies only if you create a restricted DB role and set `APP_DB_ROLE`.

**Smoke test after deploying:** sign in → add region/group/member → start meeting → save → complete → confirm the
register is read-only → Dashboard/Loans show the figures.
