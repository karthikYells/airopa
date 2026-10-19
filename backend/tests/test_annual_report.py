"""Annual report figures: the model reads, the code checks. A figure survives
only if the exact printed string is on the page it cites."""
from __future__ import annotations

from app.data.records import CompanyRecord
from app.signals.annual_report import _num, _on_page, apply_financials, verify_financials

PAGES = [(12, "Key figures\nin EUR million 2025 2024\nRevenue 3,090.8 3,147.2\n"
              "Operating profit (EBITA) 259.6 291.3")]
URL = "https://example.com/annual-report-2025.pdf"


def test_number_parsing():
    assert _num("3,090.8") == 3090.8
    assert _num("3.090,8") == 3090.8
    assert _num("(12.0)") == -12.0
    assert _num("n/a") is None and _num(None) is None


def test_on_page_ignores_whitespace_but_not_digits():
    by_page = dict(PAGES)
    assert _on_page("3,090.8", 12, by_page)
    assert not _on_page("3,090.9", 12, by_page)
    assert not _on_page("3,090.8", 13, by_page)  # wrong page


def test_fabricated_figures_are_dropped():
    data = {"currency": "EUR", "unit": "million", "years": [
        {"year": 2025, "revenue": "3,090.8", "revenue_page": 12,
         "operating_profit": "259.6", "operating_profit_page": 12},
        {"year": 2024, "revenue": "3,147.2", "revenue_page": 12,
         "operating_profit": "301.0", "operating_profit_page": 12},   # not printed
        {"year": 2023, "revenue": "3,300.0", "revenue_page": 12},     # not printed
    ]}
    fin = verify_financials(data, PAGES)
    assert [y["year"] for y in fin["years"]] == [2025, 2024]
    assert fin["years"][0]["revenue"] == 3090.8e6
    assert fin["years"][1]["op_profit"] is None


def test_unknown_unit_or_currency_rejected():
    base = {"years": [{"year": 2025, "revenue": "3,090.8", "revenue_page": 12}]}
    assert verify_financials({**base, "currency": "EUR", "unit": "furlong"}, PAGES) is None
    assert verify_financials({**base, "currency": "XYZ", "unit": "million"}, PAGES) is None


def test_figures_become_filing_signals():
    data = {"currency": "EUR", "unit": "million", "years": [
        {"year": 2025, "revenue": "3,090.8", "revenue_page": 12,
         "operating_profit": "259.6", "operating_profit_page": 12},
        {"year": 2024, "revenue": "3,147.2", "revenue_page": 12,
         "operating_profit": "291.3", "operating_profit_page": 12}]}
    rec = CompanyRecord(input_url="example.com")
    assert apply_financials(rec, verify_financials(data, PAGES), URL) == 4
    rev = rec.get("SCALE.01")
    assert rev.value == 3090800000 and rev.source_url == URL + "#page=12"
    assert rev.as_of_date == "2025-12-31" and rev.source_type.value == "filing"
    assert rec.get("PRESS.01").value is True   # 9.3% -> 8.4%
    assert rec.get("PRESS.02").value is True   # profit fell faster than revenue


def test_unit_must_be_printed_and_indian_units_scale():
    base = {"currency": "EUR", "years": [{"year": 2025, "revenue": "3,090.8", "revenue_page": 12}]}
    assert verify_financials({**base, "unit": "lakh"}, PAGES) is None          # page says million
    inr = [(4, "Revenue from operations (Rs. in crore) FY2024-25: 5,210.6")]
    fin = verify_financials({"currency": "INR", "unit": "crore",
                             "years": [{"year": 2025, "revenue": "5,210.6", "revenue_page": 4}]}, inr)
    assert round(fin["years"][0]["revenue"] / 1e6) == round(5210.6e7 * 0.0105 / 1e6)  # ~EUR 547m
