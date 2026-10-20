"""Increments 4 and 5: scores, page payload, API route and the preview's mail rule.
The pipeline is faked from real-shaped parts; no network."""
from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import get_settings
from app.main import app
from app.narrative import europe_snapshot
from app.pipeline.europe import EuropeAssessment
from app.reference import europe_reference as ref
from app.scoring import europe as scoring
from app.signals.europe_presence import EuropePresence
from app.signals.products import Offering

TOWELS = {"name": "Towels", "hs": "630260", "group": "tex_madeups", "sector": "textiles_apparel_leather",
          "hs_label": "Toilet and kitchen linen", "evidence": "towels", "url": "https://w.in/"}
VIEW = {"hs": "630260", "extra_eu": 9.7e8, "extra_eu_growth": 0.03, "india": 1.5e8, "india_growth": 0.148,
        "india_share": 0.154, "china_share": 0.076, "basis": "product"}


def _assessment(certs=(), verdict="EXPORTING", text="") -> EuropeAssessment:
    a = EuropeAssessment(input_url="w.in", domain="w.in", name="Weave Ltd", reachable=True)
    a.offering = Offering(kind="goods", products=[TOWELS], sector="textiles_apparel_leather")
    a.demand = [{"product": TOWELS, "view": VIEW, "tariff": {"rate": 12.0, "year": "2023", "hs": "630260"}}]
    a.presence = EuropePresence(verdict=verdict, reason="Some European activity.", europe_people=4,
                                by_country={"DE": 3, "UK": 1}, commercial=2)
    a.certs, a.site_text = list(certs), text
    a.services = ref.services()
    a.org = {"employees": 1200, "city": "Surat"}
    a.market = scoring.market_opportunity(a)
    a.ready = scoring.readiness(a)
    a.time_range = scoring.time_to_first_order(a, a.ready)
    a.countries = scoring.rank_countries(
        [{"code": "DE", "name": "Germany", "extra": 2.5e8, "india": 3e7, "growth": 0.02},
         {"code": "PL", "name": "Poland", "extra": 5.5e7, "india": 1.8e7, "growth": 0.17},
         {"code": "FR", "name": "France", "extra": 1.5e8, "india": 3.3e7, "growth": 0.0}], a.presence, False)
    return a


def test_scores_and_reasons_follow_the_facts():
    a = _assessment()
    dims = {d.name: d for d in a.market.dimensions}
    assert dims["Tariffs and trade terms"].points == 6 and "12%" in dims["Tariffs and trade terms"].basis
    assert dims["Competitive position"].points == 14                      # India gaining, share >= 5%
    cert = next(d for d in a.ready.dimensions if d.name == "Certification and compliance")
    assert cert.points == 4 and "OEKO-TEX" in cert.basis
    assert a.time_range["range"] == "9 to 15 months"                      # exporting + certification gap
    better = _assessment(certs=["OEKO-TEX", "GOTS", "BSCI / Sedex / SA8000", "ISO 9001"], text="OEKO-TEX ZDHC")
    assert better.ready.points > a.ready.points and better.time_range["range"] == "6 to 9 months"
    assert [c["code"] for c in a.countries][0] == "DE"                    # size outweighs a small high-share market


def test_rules_follow_the_product():
    regs = scoring.regs_for(_assessment())
    assert "Textile chemicals (REACH)" in regs and "EUDR" not in regs and "GDPR" not in regs


def test_payload_has_the_page_blocks_and_no_unverified_claims():
    p = europe_snapshot.build(_assessment())
    assert p["engine"] == "europe" and p["mode"] == "STANDARD"
    assert p["summary"]["headline"].startswith("Europe is buying what you sell")
    assert {d["name"] for d in p["market"]["dimensions"]} >= {"Addressable demand", "Tariffs and trade terms"}
    assert p["lead_capture"]["title"] == "We become your European team" and len(p["withheld"]) == 8
    text = str(p)
    assert "December 2026" not in text            # the EU–India signing date is still "to verify"
    assert "europe's shift" not in text           # names keep their capitals in the why line


def test_route_caches_and_preview_mail_goes_only_to_the_allow_list(monkeypatch):
    from app.api import routes_europe
    calls = []
    monkeypatch.setattr(routes_europe.europe_pipeline, "run", lambda host, s, llm=None: calls.append(host) or _assessment())
    sent = []
    monkeypatch.setattr(routes_europe.mailer, "send", lambda *a, **k: sent.append(a[1]) or (True, "ok"))
    import uuid
    host = f"weave-{uuid.uuid4().hex[:8]}.in"      # fresh, so no earlier run is cached
    c = TestClient(app)
    p = c.post("/api/europe/score", json={"url": host}).json()
    p2 = c.post("/api/europe/score", json={"url": host}).json()
    assert p["mode"] == "STANDARD" and p2["run_id"] == p["run_id"] and calls == [host]
    body = {"run_id": p["run_id"], "snapshot_token": p["snapshot_token"], "name": "T", "company": "Weave"}
    assert c.post("/api/europe/report", json={**body, "email": "someone@" + host}).json()["status"] == "queued"
    assert c.post("/api/europe/report", json={**body, "email": "varada.nama@airopa.co"}).json()["status"] == "sent"
    assert sent == ["varada.nama@airopa.co"] and get_settings().europe_mail_allow == "airopa.co"


def test_unknown_offering_shows_no_scores():
    a = _assessment()
    a.offering = None
    p = europe_snapshot.build(a)
    assert p["mode"] == "NO_OFFERING" and "market" not in p and "readiness" not in p and "summary" not in p
    assert "Tell us your main products" in p["message"] and [e["title"] for e in p["own_evidence"]] == ["Your Europe presence today"]


def test_services_demand_is_the_buyer_industry_not_all_it(monkeypatch):
    from app.signals.products import Offering as Off
    a = _assessment()
    a.offering = Off(kind="services", services=[{"code": "SI", "name": "Traceability"}], sector="it_services",
                     segment="seed traceability software", buyers=["A01"])
    a.buyer_view = {"codes": ["A01"], "labels": ["Crop and animal production, hunting and related service activities"],
                    "gva": 2.42e11, "year": 2023, "growth": 0.097}
    m = scoring.market_opportunity(a)
    names = [d.name for d in m.dimensions]
    assert "Europe's shift away from China" not in names                  # not applicable to services
    demand = next(d for d in m.dimensions if d.name == "Addressable demand")
    assert "crop and animal production" in demand.basis and "seed traceability software" in demand.basis
    assert "125bn" not in demand.basis and demand.points <= 20             # capped: a stand-in for their niche
    a.market, a.ready = m, scoring.readiness(a)
    p = europe_snapshot.build(a)
    timing = next(e for e in p["own_evidence"] if e["title"].startswith("Your timing"))
    assert any("deforestation" in b for b in timing["bullets"])


def test_industry_view_uses_latest_common_year(monkeypatch):
    from app.adapters import eurostat
    data = {"id": ["nace_r2", "time"], "size": [1, 3],
            "dimension": {"nace_r2": {"category": {"index": {"A01": 0}, "label": {"A01": "Crop and animal production"}}},
                          "time": {"category": {"index": {"2021": 0, "2022": 1, "2023": 2}}}},
            "value": {"0": 201304.9, "1": 235380.1, "2": 242292.3}}
    monkeypatch.setattr(eurostat, "_cached", lambda url, params: data)
    v = eurostat.industry_view(["A01", "C20"])                            # C20 confidential: no values
    assert v["codes"] == ["A01"] and v["year"] == 2023 and round(v["gva"] / 1e9) == 242
    assert round(v["growth"], 3) == round((242292.3 / 201304.9) ** 0.5 - 1, 3)


def test_competitors_need_proof_on_their_own_site(monkeypatch):
    from app.signals import competitors as comp
    from app.signals.products import Offering as Off

    class FakeLLM:
        enabled = True
        def propose_competitors(self, company, segment, lines):
            return {"competitors": [{"name": "RealRival", "domain": "realrival.com"},
                                    {"name": "Imposter", "domain": "imposter.com"},
                                    {"name": "Silent", "domain": "silent.com"}], "keywords": []}
        def check_competitors(self, segment, cands):
            return {"realrival.com": "AI recruiting platform for staffing agencies",
                    "imposter.com": "AI recruiting platform for staffing agencies",   # not on its page
                    "silent.com": None}
    pages = {"realrival.com": "RealRival is the AI recruiting platform for staffing agencies. " * 10,
             "imposter.com": "We sell garden furniture across Europe. " * 10,
             "silent.com": "Coming soon. " * 30}
    monkeypatch.setattr(comp, "_homepage", lambda d: pages.get(d, ""))
    monkeypatch.setattr(comp, "_count", lambda cl, d, locs: (40, []) if locs == comp._EUROPE else (300, []) if locs == ["India"] else (400, []))
    monkeypatch.setattr("app.signals.europe_peers._recent_europe", lambda cl, d: 12)
    s = get_settings()
    monkeypatch.setattr(s, "apollo_api_key", "test-key")
    off = Off(kind="services", services=[{"code": "SI", "name": "AI recruiting"}], segment="AI recruiting software")
    r = comp.find("fabric-test.ai", "Fabric", off, s, FakeLLM())
    assert r["confirmed"] == 1 and r["in_europe"] == 1 and r["indian_in_europe"] == 1
    assert r["named"] == [{"name": "RealRival", "domain": "realrival.com", "europe_people": 40, "indian": True}]


def test_competitor_names_reach_only_the_pdf(monkeypatch):
    import uuid
    from app.api import routes_europe
    from app.reports.pdf import build_pdf
    a = _assessment()
    a.competitors = {"in_europe": 3, "indian_in_europe": 1, "europe_people": 120, "recent_people": 30,
                     "named": [{"name": "RivalCo", "domain": "rivalco.eu", "europe_people": 80, "indian": False}]}
    monkeypatch.setattr(routes_europe.europe_pipeline, "run", lambda host, s, llm=None: a)
    c = TestClient(app)
    host = f"rival-{uuid.uuid4().hex[:6]}.in"
    p = c.post("/api/europe/score", json={"url": host}).json()
    assert "RivalCo" not in str(p) and "_private" not in p
    panel = next(e for e in p["own_evidence"] if e["title"] == "Your competitors are already in Europe")
    assert "3 companies" in panel["bullets"][0] and "120 people" in panel["bullets"][0]
    from app.data.store import get_run
    stored = get_run(p["run_id"])["payload"]
    assert stored["_private"]["competitors"][0]["name"] == "RivalCo"
    assert len(build_pdf(stored)) > 1000 and len(build_pdf(p)) > 1000
