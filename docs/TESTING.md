# Testing

**Backend** — `pytest -q` (PostgreSQL required). Covers authentication/session revocation/throttling,
tenant isolation (cross-organization and Supervisor scoping), the register arithmetic and carry-forward,
the permanent meeting lock including direct-SQL attempts against the database triggers, reports,
Excel import, delete semantics, production-boot guard and security headers.

**Frontend** — `npm run lint` and `npm run build`. There are no frontend unit tests.
`wrdt-frontend/e2e/flow.mjs` is a Playwright script that drives the production build in Chromium
(login, CRUD, register entry/save/complete/lock, reports, import template, supervisor scoping, logout,
reload, three viewport widths). It is a manual/CI aid, not wired into `npm test`.
