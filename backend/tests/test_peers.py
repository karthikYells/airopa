"""Peer set: same industry only, own company excluded, unknown never counted as no."""
from __future__ import annotations

from app.adapters.apollo import ApolloResult
from app.signals import peers


def test_parse_keeps_same_industry_and_drops_self():
    data = {"organizations": [
        {"name": "Self BV", "primary_domain": "self.nl", "industry": "machinery"},
        {"name": "Peer A", "primary_domain": "www.peer-a.de", "industry": "machinery"},
        {"name": "CAD Soft", "primary_domain": "cadsoft.fr", "industry": "computer software"},
        {"name": "Peer B", "primary_domain": "peer-b.se"},          # no industry: kept
    ]}
    got = peers.parse_peers(data, "self.nl", "Self BV", "Machinery")
    assert [p["domain"] for p in got] == ["peer-a.de", "peer-b.se"]


def test_no_industry_no_search():
    assert peers.peer_filters(ApolloResult(domain="x.nl", revenue_eur=10**9)) is None
    f = peers.peer_filters(ApolloResult(domain="x.nl", industry="machinery", revenue_eur=920_000_000))
    assert f["q_organization_keyword_tags"] == ["machinery"]
    f = peers.peer_filters(ApolloResult(domain="x.nl", industry="machinery", naics_codes=["332911"],
                                        revenue_eur=920_000_000), "precision_components")
    assert f["organization_naics_codes"] == ["3327", "3329", "3336"] and "q_organization_keyword_tags" not in f
    assert f["revenue_range"] == {"min": 333333333, "max": 3000000000}


def test_unknown_peers_are_left_out_of_the_count(monkeypatch):
    ap = ApolloResult(domain="self.nl", industry="machinery", revenue_eur=10**9)
    found = {"peers": [{"name": f"P{i}", "domain": f"p{i}.de"} for i in range(7)], "credits_used": 1}
    status = ["yes", "yes", "no", "unknown", "yes", "no", "unknown"]
    monkeypatch.setattr(peers, "discover", lambda ap, s, k=None: found)
    monkeypatch.setattr(peers, "check_peer", lambda p, s, llm=None: {
        **p, "status": status[int(p["name"][1:])], "india_profiles": 100})
    c = peers.build_cohort(ap, "Industrial machinery", None)
    assert (c["with_centre"], c["known"], c["publishable"]) == (3, 5, True)
    assert c["aggregate_india_profiles"] == 300


def test_candidates_outside_the_sector_are_dropped(monkeypatch):
    ap = ApolloResult(domain="self.nl", industry="machinery", revenue_eur=10**9)
    found = {"peers": [{"name": n, "domain": f"{n}.com"} for n in ("press", "fashion", "pump")],
             "credits_used": 1}
    monkeypatch.setattr(peers, "discover", lambda ap, s, k=None: found)
    monkeypatch.setattr(peers, "peer_sector", lambda p, llm=None:
                        "consumer_goods" if p["name"] == "fashion"
                        else None if p["name"] == "pump" else "precision_components")
    monkeypatch.setattr(peers, "check_peer", lambda p, s, llm=None: {**p, "status": "yes", "india_profiles": 1})
    c = peers.build_cohort(ap, "Industrial machinery", None, sector_key="industrial_machinery")
    assert [p["name"] for p in c["peers"]] == ["press", "pump"]


def test_visit_queues_and_task_builds(monkeypatch):
    from app.data import kv
    ap = ApolloResult(domain="self.nl", industry="machinery", revenue_eur=10**9)
    kv.put("apollo", "self.nl", ap.__dict__)
    assert peers.cached_cohort(ap, "Industrial machinery", "industrial_machinery") is None
    assert kv.get("cohort_queue", "self.nl")["sector_key"] == "industrial_machinery"
    monkeypatch.setattr(peers, "build_cohort", lambda ap, sector, s, llm=None, sector_key=None: {
        "peers": [], "known": 6, "with_centre": 4, "publishable": True})
    assert peers.build_queued(None) == [{"domain": "self.nl", "known": 6, "with_centre": 4}]
    assert kv.get("cohort_queue", "self.nl") is None
    assert peers.cached_cohort(ap, "Industrial machinery", "industrial_machinery")["with_centre"] == 4
