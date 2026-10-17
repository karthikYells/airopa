"""Company banner and score reasoning on the public page."""
from __future__ import annotations

from app.data.records import CompanyRecord, DimensionScore
from app.narrative.public_snapshot import _company_facts, _why
from app.signals.annual_report import apply_financials, verify_financials

PAGES = [(12, "Key figures in EUR million 2025 2024\nRevenue 3,090.8 3,147.2\n"
              "Operating profit 259.6 291.3")]


def test_banner_carries_report_trend():
    data = {"currency": "EUR", "unit": "million", "years": [
        {"year": 2025, "revenue": "3,090.8", "revenue_page": 12,
         "operating_profit": "259.6", "operating_profit_page": 12},
        {"year": 2024, "revenue": "3,147.2", "revenue_page": 12,
         "operating_profit": "291.3", "operating_profit_page": 12}]}
    rec = CompanyRecord(input_url="example.com")
    rec.hq_city, rec.jurisdiction = "Utrecht", "Netherlands"
    apply_financials(rec, verify_financials(data, PAGES), "https://example.com/ar.pdf")
    c = _company_facts(rec)
    assert c["revenue"] == "EUR 3.1bn (FY2025)" and c["location"] == "Utrecht, Netherlands"
    texts = [s["text"] for s in c["signals"]]
    assert texts == ["Revenue down 1.8% in FY2025", "Operating margin 8.4%, down from 9.3%",
                     "Profit growing slower than revenue"]


def test_no_report_no_signals():
    c = _company_facts(CompanyRecord(input_url="example.com"))
    assert c["signals"] == [] and c["signals_source"] is None


class _S:
    points = 71


def test_why_names_drivers_and_drags():
    dims = [DimensionScore("Addressable demand", 22, 25, ""),
            DimensionScore("Policy and incentives", 14, 15, ""),
            DimensionScore("Route to market", 7, 15, ""),
            DimensionScore("Competitive position", 10, 15, "")]
    assert _why(_S, dims) == "71 out of 100, lifted by policy and demand, held back by route to market."
