from __future__ import annotations

import importlib

import pytest


def test_database_url_is_required(monkeypatch):
    import backend.config as config

    monkeypatch.delenv("DATABASE_URL", raising=False)

    with pytest.raises(RuntimeError, match="DATABASE_URL"):
        importlib.reload(config)

    monkeypatch.setenv("DATABASE_URL", "sqlite:///:memory:")
    importlib.reload(config)
