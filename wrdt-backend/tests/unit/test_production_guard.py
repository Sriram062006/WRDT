"""The app must refuse to boot in production with an insecure config."""
from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.main import _assert_production_secrets


def cfg(**kw):
    base = dict(
        is_production=True,
        SECRET_KEY="a-long-random-value-aaaaaaaaaaaaaaaa",
        JWT_SECRET_KEY="a-different-random-bbbbbbbbbbbbbbbb",
        APP_DEBUG=False,
        cors_origins_list=["https://app.example.org"],
    )
    base.update(kw)
    return SimpleNamespace(**base)


def test_a_sound_production_config_boots():
    _assert_production_secrets(cfg())


def test_development_is_never_blocked():
    _assert_production_secrets(cfg(is_production=False, APP_DEBUG=True, SECRET_KEY="change-me"))


@pytest.mark.parametrize(
    "override",
    [
        {"SECRET_KEY": "change-me-to-a-long-random-string"},
        {"JWT_SECRET_KEY": "change-me-to-a-different-long-random-string"},
        {"JWT_SECRET_KEY": "a-long-random-value-aaaaaaaaaaaaaaaa"},  # identical to SECRET_KEY
        {"APP_DEBUG": True},
        {"cors_origins_list": ["*"]},
    ],
)
def test_insecure_production_configs_are_refused(override):
    with pytest.raises(RuntimeError, match="Refusing to start"):
        _assert_production_secrets(cfg(**override))
