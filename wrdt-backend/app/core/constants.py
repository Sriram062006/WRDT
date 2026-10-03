"""
Business constants shared across services. Centralized here so a future
Settings module (Phase 9+/pending) has one obvious place to source
defaults from, without hunting through service files.
"""
from datetime import timedelta
from decimal import Decimal

# Matches the frontend's default weekly/fortnightly saving amount applied
# to a fresh ledger row when a meeting is started.
DEFAULT_CURRENT_SAVING = Decimal("300")

# Matches the frontend's addDays(15) meeting-interval convention.
MEETING_INTERVAL_DAYS = 15
MEETING_INTERVAL = timedelta(days=MEETING_INTERVAL_DAYS)

DEFAULT_REMARKS = "Paid"
