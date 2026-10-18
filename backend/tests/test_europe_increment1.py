"""Europe Market Assessment, increment 1: corridor config, Eurostat parsing and
caching, reference lookups. No network: Eurostat calls are faked."""
from __future__ import annotations

import pytest

from app.adapters import eurostat
from app.corridor import Corridor, config
from app.reference import europe_reference as ref

# A real-shaped JSON-stat answer: 1 reporter x 2 partners x 2 years, one cell unpublished.
JSONSTAT = {
    "id": ["freq", "reporter", "partner", "product", "time"],
    "size": [1, 1, 2, 1, 2],
    "dimension": {
        "freq": {"category": {"index": {"A": 0}}},
        "reporter": {"category": {"index": {"EU": 0}}},
        "partner": {"category": {"index": {"IN": 0, "EXT_EU": 1}}},
        "product": {"category": {"index": {"8481": 0}}},
        "time": {"category": {"index": {"2023": 0, "2025": 1}}},
    },
    "value": {"0": 400.0, "1": 451.0, "3": 9000.0},   # EXT_EU 2023 not published
}


def test_parse_jsonstat_maps_cells_and_skips_unpublished():
    cells = {(c["partner"], c["time"]): c["value"] for c in eurostat.parse_jsonstat(JSONSTAT)}
    assert cells == {("IN", "2023"): 400.0, ("IN", "2025"): 451.0, ("EXT_EU", "2025"): 9000.0}


def test_fetch_is_cached_in_the_store(monkeypatch):
    calls = []

    class R:
        def raise_for_status(self): pass
        def json(self): return JSONSTAT

    monkeypatch.setattr(eurostat.httpx, "get", lambda *a, **k: calls.append(1) or R())
    for _ in range(3):
        assert len(eurostat.goods_imports(["8481"], ["EU"], ["IN", "EXT_EU"], ["2023", "2025"])) == 3
    assert len(calls) == 1


def test_fetch_failure_returns_nothing_rather_than_guessing(monkeypatch):
    def boom(*a, **k):
        raise eurostat.httpx.ConnectError("down")
    monkeypatch.setattr(eurostat.httpx, "get", boom)
    assert eurostat.goods_imports(["8481"], ["EU"], ["IN"], ["2025"]) == []


def test_market_view_shares_and_growth(monkeypatch):
    cells = [
        {"reporter": "EU", "partner": "EXT_EU", "time": "2023", "value": 8000.0},
        {"reporter": "EU", "partner": "EXT_EU", "time": "2025", "value": 9680.0},
        {"reporter": "EU", "partner": "IN", "time": "2023", "value": 400.0},
        {"reporter": "EU", "partner": "IN", "time": "2025", "value": 484.0},
        {"reporter": "EU", "partner": "CN", "time": "2025", "value": 2904.0},
    ]
    monkeypatch.setattr(eurostat, "goods_imports", lambda *a, **k: cells)
    v = eurostat.market_view("8481")
    assert round(v["extra_eu_growth"], 3) == 0.1 and round(v["india_growth"], 3) == 0.1
    assert v["india_share"] == 0.05 and v["china_share"] == 0.3
    monkeypatch.setattr(eurostat, "goods_imports", lambda *a, **k: [])
    assert eurostat.market_view("8481") is None


def test_reference_lookups():
    assert ref.version() == "europe-reference-v1"
    assert ref.group_for_hs("870830")["id"] == "eng_auto"      # heading beats chapter 87
    assert ref.group_for_hs("848180")["id"] == "eng_mach"
    assert ref.group_for_hs("2933.39")["id"] == "chem_org"
    assert ref.sector_for_hs("6109") == "textiles_apparel_leather"
    assert ref.group_for_hs("0901") is None                     # coffee: outside v1
    assert ref.target_countries() == ["DE", "IT", "FR", "NL", "ES", "BE", "PL", "SE", "CZ", "UK"]


def test_public_rules_leave_out_unverified():
    svc = {r["id"] for r in ref.rules_for("it_services")}
    assert "r_gdpr" in svc and "r_uk" in svc
    assert "r_ai" not in svc and "r_euin" not in svc            # still flagged verify
    assert "r_ai" in {r["id"] for r in ref.rules_for("it_services", public_only=False)}


def test_corridors():
    eu = config(Corridor.IN_TO_EU)
    assert eu.engine_name == "Europe Market Assessment" and eu.target_markets[-1] == "UK"
    assert config("eu_to_in").target_region == "India"
    with pytest.raises(ValueError):
        config("nowhere")
