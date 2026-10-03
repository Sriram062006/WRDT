# What was found and changed

Every item below was reproduced or exercised by a test (backend: 93 pytest tests against PostgreSQL 16;
frontend: production build + a 24-step Chromium run) unless marked otherwise.

## Security
- **Cross-organization access (critical).** Every by-ID route fetched by bare UUID, so any Owner could read/modify
  other organizations' regions, groups, members, meetings and users. All routes now resolve through
  `app/services/access.py` (foreign org → 404, unassigned Supervisor → 403). 21 regression tests.
- Owner could create users inside another organization via a body field; user list returned a global count;
  import batches could be committed cross-tenant. Fixed.
- Logout did nothing server-side (refresh tokens lived 14 days). Refresh tokens now rotate and are single-use; logout revokes.
- No login rate limiting; account existence leaked via response/timing. Added throttling and constant-work unknown-user path.
- No security headers; no production-config safety. Added headers; the app refuses to boot in production with placeholder
  secrets, debug on, or wildcard CORS.
- The shipped `.env` contained real Supabase credentials and JWT secrets. **Those credentials were exposed in the
  ZIP you received and should be rotated.** This package contains no `.env`.

## Database / migrations
- `alembic upgrade head` failed at migration 0004 (hard-coded role that doesn't exist). Fixed; migrations run up and down cleanly.
- The permanent-lock trigger errored on DELETE instead of enforcing the lock. Fixed (migration 0005); tested with direct SQL.
- No way to create the first user. Added `scripts/bootstrap.py`; `seed_roles.py` is now idempotent.

## WRDT business logic
- New members were charged an installment they never paid on their first row.
- Outstanding loans were summed across every historical meeting (one ₹5,000 loan showed as ₹15,000 after 3 meetings).
- Region report showed zero outstanding once its meetings were completed; monthly cash omitted interest and fines.
- Excel import rejected the very headers the UI template used; now accepts common spellings and ₹/comma formatting.

## Bugs found by the tests (would have been live 500s)
- Every single-row ledger/expense/loan-override save returned 500 (async lazy-load of `updated_at`).
- Validation errors on money fields returned 500 instead of 422 (Decimal not JSON-serializable).

## Frontend (rewritten)
The original was a single mock-data file with no API calls (hard-coded dashboard figures, fake login that accepted
anything, five "Coming Next" placeholder screens, unusable below ~1100px). Rebuilt as a real client: auth with silent
token refresh, Regions/Groups/Members/Member ledger, Meetings and the Meeting Register (explicit atomic save,
unsaved-changes guard, completion lock), Loans, Expenses, Reports, Activity (real audit trail), Settings
(change password, create users, assign groups), Excel Import with preview, English/Tamil, responsive layout.
The vulnerable `xlsx` dependency was removed (parsing is server-side); `npm audit` reports 0 vulnerabilities.
Two bugs were caught by the browser run and fixed: literal `\u20b9` placeholders in JSX attributes, and a race that
sent an empty role when "Add User" was opened before roles finished loading.
