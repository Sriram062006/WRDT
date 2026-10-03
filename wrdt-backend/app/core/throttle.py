"""
In-process login throttle.

Without any rate limit, `POST /auth/login` is an unbounded password
oracle: an attacker can try thousands of passwords per minute against a
known Owner email. This module keeps a small sliding window of recent
failures keyed by both the submitted email and the client IP, and blocks
further attempts for a cool-off period once either crosses its limit.

Scope and limits, stated plainly: the counter lives in this process's
memory. Behind several replicas each instance enforces its own share, and
a restart clears the state. That is a meaningful improvement over nothing
and is right-sized for the single-container deployment this project
ships with; if the deployment is scaled out, swap `_Bucket` for a Redis
counter -- the call sites in `auth.py` do not change.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

MAX_FAILURES_PER_EMAIL = 8
MAX_FAILURES_PER_IP = 25
WINDOW_SECONDS = 15 * 60
BLOCK_SECONDS = 15 * 60


@dataclass
class _Bucket:
    failures: list[float] = field(default_factory=list)
    blocked_until: float = 0.0


class LoginThrottle:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._buckets: dict[str, _Bucket] = {}

    def _prune(self, bucket: _Bucket, now: float) -> None:
        cutoff = now - WINDOW_SECONDS
        bucket.failures = [t for t in bucket.failures if t > cutoff]

    def retry_after(self, keys: list[tuple[str, int]]) -> int:
        """Returns seconds to wait if any key is currently blocked, else 0."""
        now = time.time()
        with self._lock:
            worst = 0
            for key, _limit in keys:
                bucket = self._buckets.get(key)
                if bucket and bucket.blocked_until > now:
                    worst = max(worst, int(bucket.blocked_until - now) + 1)
            return worst

    def record_failure(self, keys: list[tuple[str, int]]) -> None:
        now = time.time()
        with self._lock:
            for key, limit in keys:
                bucket = self._buckets.setdefault(key, _Bucket())
                self._prune(bucket, now)
                bucket.failures.append(now)
                if len(bucket.failures) >= limit:
                    bucket.blocked_until = now + BLOCK_SECONDS
            self._evict(now)

    def record_success(self, keys: list[tuple[str, int]]) -> None:
        with self._lock:
            for key, _limit in keys:
                self._buckets.pop(key, None)

    def _evict(self, now: float) -> None:
        """Keep the dict from growing without bound under a spray attack
        against many distinct emails."""
        if len(self._buckets) < 10_000:
            return
        stale = [
            k
            for k, b in self._buckets.items()
            if b.blocked_until < now and (not b.failures or b.failures[-1] < now - WINDOW_SECONDS)
        ]
        for k in stale:
            self._buckets.pop(k, None)

    def reset(self) -> None:
        with self._lock:
            self._buckets.clear()


login_throttle = LoginThrottle()


def login_keys(email: str, client_ip: str | None) -> list[tuple[str, int]]:
    keys = [(f"email:{email.strip().lower()}", MAX_FAILURES_PER_EMAIL)]
    if client_ip:
        keys.append((f"ip:{client_ip}", MAX_FAILURES_PER_IP))
    return keys
