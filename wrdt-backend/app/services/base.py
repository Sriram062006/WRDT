"""
Base service class.

Services orchestrate one or more repositories inside a single unit of work
(one DB transaction per request, per FastAPI's get_db dependency) and are
where business rules live: uniqueness checks, the permanent meeting lock,
carry-forward computation, RBAC-aware scoping, etc.

No concrete services are implemented in Phase 1/2 (no CRUD/business logic
in scope yet) — this base class exists purely to fix the pattern that
Phase 4 onward will follow.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession


class BaseService:
    def __init__(self, db: AsyncSession):
        self.db = db
