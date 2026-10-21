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
    a.certs, a.site_text = list(certs), text + " " + "Weave Ltd makes cotton towels for hotels and retailers. " * 12
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
    monkeypatch.setattr(routes_europe.europe_pipeline, "run", lambda host, s, llm=None, **k: calls.append(host) or _assessment())
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
    a.competitors = {"in_europe": 3, "indian_in_europe": 1, "europe_people": 120, "recent_people": 30, "confirmed": 8,
                     "named": [{"name": "RivalCo", "domain": "rivalco.eu", "europe_people": 80, "indian": False}]}
    monkeypatch.setattr(routes_europe.europe_pipeline, "run", lambda host, s, llm=None, **k: a)
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


def test_launch_sends_to_any_work_address_and_holds_personal(monkeypatch):
    import uuid
    from app.api import routes_europe
    monkeypatch.setattr(routes_europe.europe_pipeline, "run", lambda host, s, llm=None, **k: _assessment())
    sent = []
    monkeypatch.setattr(routes_europe.mailer, "send", lambda *a, **k: sent.append((a[1], a[2])) or (True, "ok"))
    monkeypatch.setattr(get_settings(), "europe_mail_allow", "*")
    c = TestClient(app)
    p = c.post("/api/europe/score", json={"url": f"open-{uuid.uuid4().hex[:6]}.in"}).json()
    body = {"run_id": p["run_id"], "snapshot_token": p["snapshot_token"], "name": "Asha", "company": "Weave"}
    assert c.post("/api/europe/report", json={**body, "email": "asha@weave-textiles.in"}).json()["status"] == "sent"
    r = c.post("/api/europe/report", json={**body, "email": "asha@gmail.com", "allow_personal": True}).json()
    assert r["status"] == "queued"
    assert sent == [("asha@weave-textiles.in", "Your Europe Market Assessment: Weave Ltd")]


def test_one_competitor_in_europe_is_not_headlined():
    """KLR case: 14 verified sellers, mostly tiny, 1 in Europe. No '1 of 14' card,
    no competitor-led headline; the panel says '1 company' in the singular."""
    a = _assessment(verdict="GREENFIELD")
    rows = [{"name": "Robit", "domain": "robit.fi", "europe_people": 43, "known": True}] + \
           [{"name": f"Small{i}", "domain": f"s{i}.cn", "europe_people": 0, "known": i < 3} for i in range(13)]
    a.competitors = {"in_europe": 1, "indian_in_europe": 0, "europe_people": 43, "recent_people": 12,
                     "confirmed": 14, "competitors": rows,
                     "named": [{"name": "Robit", "domain": "robit.fi", "europe_people": 43, "indian": False}]}
    p = europe_snapshot.build(a)
    assert p.get("peer_headline") is None
    assert not p["summary"]["headline"].startswith("Your competitors")
    panel = next(e for e in p["own_evidence"] if e["title"] == "A competitor is already in Europe")
    assert "1 company selling" in panel["bullets"][0] and "Which company it is" in panel["bullets"][-1]
    rows += [{"name": f"Big{i}", "domain": f"b{i}.de", "europe_people": 50, "known": True} for i in range(2)]
    a.competitors.update(in_europe=3, competitors=rows)
    p = europe_snapshot.build(a)
    assert p["peer_headline"]["with_centre"] == 3 and p["peer_headline"]["total"] == 6   # known-size base only
    assert p["summary"]["headline"].startswith("Your competitors are already selling in Europe")


def test_product_match_is_locked_and_a_visitor_can_correct_it(monkeypatch):
    """Same company, same products on every visit; typed products replace the lock."""
    import uuid
    from app.pipeline import europe as pipe
    from app.signals import products as prod
    calls = []

    class FakeLLM:
        enabled = True
        def map_offering(self, company, pages):
            calls.append(pages[0]["url"])
            text = pages[0]["text"]
            name = "Hand tools" if "visitor" == pages[0]["url"] else "Towels"
            ev = "hand tools" if name == "Hand tools" else "towels"
            hs = "8205" if name == "Hand tools" else "6302"
            return {"products": [{"name": name, "evidence": ev, "hs": hs, "confidence": 0.9}]} if ev in text.lower() else {}
        def choose_hs(self, items):
            return {}

    class Scrape:
        reachable, resolved_host, pages_fetched = True, "w.in", ["https://w.in/"]
        homepage_text, product_pages = "We weave towels for hotels. " * 5, []

    dom = f"lock-{uuid.uuid4().hex[:6]}.in"
    a = pipe.EuropeAssessment(input_url=dom, domain=dom, name="Weave")
    first = pipe._offering(a, Scrape(), FakeLLM(), None)
    again = pipe._offering(a, Scrape(), FakeLLM(), None)
    assert first.products[0]["name"] == again.products[0]["name"] == "Towels"
    assert calls == ["https://w.in/"] and a.offering_source == "site"          # second visit used the lock
    fixed = pipe._offering(a, Scrape(), FakeLLM(), ["Hand tools"])
    assert fixed.products[0]["hs"] == "8205" and a.offering_source == "visitor"
    assert prod.locked_offering(dom)[1] == "visitor"
    assert prod.offering_from_names("Weave", ["   "], FakeLLM()) is None


def test_stream_sends_stages_then_the_page(monkeypatch):
    import json, uuid
    from app.api import routes_europe

    def fake_run(host, s, llm=None, products=None, on_stage=None):
        a = _assessment()
        on_stage("company", a)
        on_stage("products", a)
        return a
    monkeypatch.setattr(routes_europe.europe_pipeline, "run", fake_run)
    r = TestClient(app).post("/api/europe/score/stream", json={"url": f"st-{uuid.uuid4().hex[:6]}.in"})
    items = [json.loads(l) for l in r.text.splitlines() if l.strip()]
    assert [i["stage"] for i in items] == ["company", "products", "done"]
    assert items[0]["company"]["name"] == "Weave Ltd"
    assert items[1]["products"][0]["name"] == "Towels" and "a year imported" in items[1]["products"][0]["demand"]
    done = items[2]["payload"]
    assert done["mode"] == "STANDARD" and done["run_id"] and "_private" not in done
    assert done["products_named"] == ["Towels"]


def test_unreadable_site_is_scored_from_typed_products():
    a = _assessment()
    a.reachable, a.org, a.presence = False, None, None
    a.offering_source = "visitor"
    p = europe_snapshot.build(a)
    assert p["mode"] == "STANDARD" and p["products_source"] == "visitor"
    assert any("From the products you told us" in b for e in p["own_evidence"] for b in e["bullets"])


def test_leads_are_kept_in_the_durable_store():
    from app.data.store import recent_leads, save_lead
    save_lead(engine="europe", run_id="r1", host="keep.in", name="Asha", email="asha@keep.in",
              email_type="work", company="Keep", role=None, call_partner="no", status="sent", detail="ok")
    got = [l for l in recent_leads() if l.get("host") == "keep.in"]
    assert got and got[0]["engine"] == "europe" and got[0]["email"] == "asha@keep.in"


def test_unread_site_is_not_resolved_not_weak():
    """KPIT case: the site needs JavaScript, so we saw almost nothing. Missing
    certifications or languages are then unknown, not a weakness."""
    a = _assessment()
    a.site_text, a.certs = "Loading...", []           # a JavaScript-only page
    r = scoring.readiness(a)
    dims = {d.name: d for d in r.dimensions}
    for name in ("Certification and compliance", "Regulatory exposure handled", "Localisation and commercial readiness"):
        assert dims[name].points == 0 and dims[name].basis.startswith("Not resolved")
    a.ready = r
    assert "certification" not in scoring.time_to_first_order(a, r)["basis"]
