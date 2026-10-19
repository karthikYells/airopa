"""Increment 3: Europe presence check. Apollo is faked; site signals are real parsing."""
from __future__ import annotations

from types import SimpleNamespace

from app.config import get_settings
from app.signals import europe_presence as ep

S = get_settings()


def _scrape(text="", domains=(), langs=()):
    return SimpleNamespace(homepage_text=text, product_pages=[], external_domains=list(domains),
                           languages=list(langs))


def _apollo(total, europe, by_country=None, titles=()):
    return lambda domain, settings, extra_domains=(): {"total": total, "europe": europe,
                                                       "titles": list(titles), "by_country": by_country or {}}


def test_site_signals_find_entities_countries_and_group_sites():
    sig = ep.site_signals(_scrape("Our subsidiary Sundram Fasteners GmbH serves customers in Germany and Italy.",
                                  domains=["sundram.de", "bosch.com", "dealer.fr"], langs=["en", "de"]))
    assert any("GmbH" in e for e in sig["entities"]) and sig["countries"] == ["DE", "IT"]
    assert sig["eu_domains"] == ["sundram.de", "dealer.fr"] and sig["languages"] == ["de"]
    assert ep._own_group_domains("sundram.com", sig["eu_domains"]) == ["sundram.de"]


def test_verdicts(monkeypatch):
    monkeypatch.setattr(ep, "apollo_europe", _apollo(5000, 520, {"NL": 231, "UK": 40}, ["Sales Manager", "Engineer"]))
    p = ep.assess("big.in", _scrape(), S)
    assert p.verdict == "ESTABLISHED" and "most in Netherlands" in p.reason and p.commercial == 1 and p.delivery == 1

    monkeypatch.setattr(ep, "apollo_europe", _apollo(900, 12))
    assert ep.assess("mid.in", _scrape(), S).verdict == "EXPORTING"
    assert ep.assess("mid.in", _scrape("Mid Europe GmbH"), S).verdict == "ESTABLISHED"

    monkeypatch.setattr(ep, "apollo_europe", _apollo(800, 0))
    assert ep.assess("home.in", _scrape(), S).verdict == "GREENFIELD"

    monkeypatch.setattr(ep, "apollo_europe", _apollo(20, 0))
    assert ep.assess("tiny.in", _scrape(), S).verdict == "UNKNOWN"
