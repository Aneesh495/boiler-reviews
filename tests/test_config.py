from __future__ import annotations

import pytest

from boiler_reviews.config import Settings


def test_production_requires_explicit_secret():
    with pytest.MonkeyPatch.context() as monkeypatch:
        monkeypatch.setenv("APP_ENV", "production")
        monkeypatch.delenv("SECRET_KEY", raising=False)
        with pytest.raises(RuntimeError):
            Settings.from_env()
