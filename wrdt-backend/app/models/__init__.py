"""
Import every model module here so `Base.metadata` is fully populated from a
single `import app.models` — this is what Alembic's env.py relies on for
autogenerate, and what db/base.py's bottom-of-file comment refers to.
"""
from app.models.organization import Organization  # noqa: F401
from app.models.role import Role  # noqa: F401
from app.models.user import User, UserGroupAssignment  # noqa: F401
from app.models.region import Region  # noqa: F401
from app.models.group import Group  # noqa: F401
from app.models.member import Member  # noqa: F401
from app.models.meeting import Meeting  # noqa: F401
from app.models.meeting_entry import MeetingEntry  # noqa: F401
from app.models.expense import Expense  # noqa: F401
from app.models.import_history import ImportHistory  # noqa: F401
from app.models.audit_log import AuditLog  # noqa: F401
from app.models.revoked_token import RevokedToken  # noqa: F401
