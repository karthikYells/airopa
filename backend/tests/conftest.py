from __future__ import annotations

import pytest

from app.config import get_settings
from app.data import kv


@pytest.fixture(autouse=True)
def _isolated_store(tmp_path, monkeypatch):
    """Tests never read or write the real store (saved sectors, Apollo cache, roles)."""
    monkeypatch.setattr(kv, "_DIR", tmp_path / "kv")


@pytest.fixture(autouse=True)
def _no_paid_apollo(monkeypatch):
    """Tests never call Apollo: company lookups and peer searches cost credits,
    and with an empty test store nothing would ever come from the cache."""
    monkeypatch.setattr(get_settings(), "apollo_api_key", "")


@pytest.fixture(autouse=True)
def _no_network_lookups(monkeypatch):
    """Visit logging looks up the visitor's network in the background; tests never call out."""
    from app.api import visits
    monkeypatch.setattr(visits, "lookup_network", lambda ip: {"network_owner": "Test Network BV", "country": "NL"})
