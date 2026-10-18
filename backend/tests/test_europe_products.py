"""Increment 2: what the company sells. The model proposes; anything whose
evidence is not on the company's own page is dropped."""
from __future__ import annotations

from app.signals.products import verify_offering

PAGES = [
    {"url": "https://example.in/", "text": "Example Forge makes precision forged crankshafts and "
     "connecting rods for passenger cars, and industrial ball valves for oil and gas."},
    {"url": "https://example.in/services", "text": "We also offer CAD design and testing services "
     "for automotive OEMs."},
]


def test_only_evidenced_products_survive_and_get_a_sector():
    raw = {"products": [
        {"name": "Crankshafts", "evidence": "precision forged crankshafts", "url": "x",
         "hs": "8483.10", "hs_label": "Transmission shafts and cranks", "confidence": 0.8},
        {"name": "Ball valves", "evidence": "industrial ball valves", "url": "x",
         "hs": "848180", "confidence": 0.7},
        {"name": "Turbochargers", "evidence": "turbochargers for trucks", "url": "x",   # not on page
         "hs": "841480", "confidence": 0.9},
        {"name": "Pistons", "evidence": "connecting rods", "url": "x", "hs": "8409", "confidence": 0.3},  # low conf
    ], "services": [
        {"name": "Engineering design", "evidence": "CAD design and testing services", "url": "x", "code": "sj3"},
        {"name": "Cloud", "evidence": "cloud migration", "url": "x", "code": "SI"},       # not on page
    ]}
    off = verify_offering(raw, PAGES)
    assert [p["hs"] for p in off.products] == ["848310", "848180"]
    assert off.products[0]["url"] == "https://example.in/" and off.products[0]["group"] == "eng_mach"
    assert [s["code"] for s in off.services] == ["SJ3"] and off.services[0]["url"].endswith("/services")
    assert off.kind == "both" and off.sector == "engineering_auto" and off.dropped == 3


def test_services_only_company():
    pages = [{"url": "https://soft.in/", "text": "We build SAP S/4HANA migrations and managed cloud services."}]
    off = verify_offering({"services": [{"name": "SAP", "evidence": "SAP S/4HANA migrations", "code": "SI"}]}, pages)
    assert off.kind == "services" and off.sector == "it_services"


def test_goods_outside_v1_have_no_sector():
    pages = [{"url": "https://tea.in/", "text": "Premium Darjeeling tea exported worldwide."}]
    off = verify_offering({"products": [{"name": "Tea", "evidence": "Darjeeling tea", "hs": "090240",
                                         "confidence": 0.9}]}, pages)
    assert off.kind == "goods" and off.sector is None and off.products[0]["group"] is None


def test_nothing_verifiable_is_none():
    assert verify_offering({"products": [{"evidence": "rockets", "hs": "880000", "confidence": 1}]}, PAGES) is None
    assert verify_offering({}, PAGES) is None


def test_codes_must_exist_and_the_choice_is_constrained():
    from app.signals.products import refine_hs

    class FakeLLM:
        enabled = True
        def choose_hs(self, items):
            return {"DCB": "290391", "Mystery": "999999"}   # one real option, one invented

    pages = [{"url": "https://chem.in/", "text": "We are a leading maker of dichlorobenzene (DCB) and a mystery compound."}]
    raw = {"products": [
        {"name": "DCB", "evidence": "dichlorobenzene (DCB)", "hs": "290369", "confidence": 0.8},
        {"name": "Mystery", "evidence": "a mystery compound", "hs": "290300", "confidence": 0.8},
        {"name": "Fake", "evidence": "leading maker", "hs": "999900", "confidence": 0.9},     # heading does not exist
    ]}
    off = refine_hs(verify_offering(raw, pages), FakeLLM())
    assert [(p["name"], p["hs"]) for p in off.products] == [("DCB", "290391"), ("Mystery", "2903")]
    assert off.products[0]["hs_label"].startswith("Halogenated derivatives of aromatic hydrocarbons")
    assert off.products[1]["hs_level"] == 4 and off.dropped == 1


def test_narrow_markets_step_up_to_the_heading(monkeypatch):
    from app.adapters import eurostat
    views = {"290391": {"extra_eu": 9e6}, "2903": {"extra_eu": 2.4e9}}
    monkeypatch.setattr(eurostat, "market_view", lambda hs, reporters=("EU",): views.get(hs))
    v = eurostat.demand_view("290391")
    assert v["basis"] == "heading" and v["extra_eu"] == 2.4e9 and v["product_view"]["extra_eu"] == 9e6
    views["290391"] = {"extra_eu": 3e8}
    assert eurostat.demand_view("290391")["basis"] == "product"


def test_slow_site_is_cut_off_with_what_was_read(monkeypatch):
    import time as _t
    from app.adapters import web_scraper as ws

    def slow(input_url, products=False, budget_s=75.0, res=None):
        res.reachable = True
        res.homepage_text = "We make valves."
        res.pages_fetched.append("https://slow.in/")
        _t.sleep(5)               # a page that never finishes
        res.product_pages.append({"url": "late", "text": "too late"})
        return res
    monkeypatch.setattr(ws, "scrape", slow)
    t = _t.monotonic(); r = ws.scrape_with_deadline("slow.in", products=True, deadline_s=0.5)
    assert _t.monotonic() - t < 2 and r.reachable and r.homepage_text == "We make valves."
    assert r.product_pages == [] and "stopped after" in r.error
