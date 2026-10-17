from __future__ import annotations

import pytest

from app.data import kv


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    """Tests never read or write the real store (saved sectors, Apollo cache, roles)."""
    monkeypatch.setattr(kv, "_DIR", tmp_path / "kv")
