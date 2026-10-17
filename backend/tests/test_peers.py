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
    assert f["revenue_range"] == {"min": 333333333, "max": 3000000000}


def test_unknown_peers_are_left_out_of_the_count(monkeypatch):
    ap = ApolloResult(domain="self.nl", industry="machinery", revenue_eur=10**9)
    found = {"peers": [{"name": f"P{i}", "domain": f"p{i}.de"} for i in range(7)], "credits_used": 1}
    status = ["yes", "yes", "no", "unknown", "yes", "no", "unknown"]
    monkeypatch.setattr(peers, "discover", lambda ap, s: found)
    monkeypatch.setattr(peers, "check_peer", lambda p, s, llm=None: {
        **p, "status": status[int(p["name"][1:])], "india_profiles": 100})
    c = peers.build_cohort(ap, "Industrial machinery", None)
    assert (c["with_centre"], c["known"], c["publishable"]) == (3, 5, True)
    assert c["aggregate_india_profiles"] == 300
