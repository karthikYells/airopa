"""Newsroom events: the model extracts, the code decides. Anything not on the
page, undated, in the future or older than 36 months is dropped."""
from __future__ import annotations

from datetime import date

from app.data.records import CompanyRecord
from app.signals.newsroom import apply_events, verify_events

PAGE = {"url": "https://example.de/news",
        "text": "News\n12 March 2026\nExample launches efficiency programme to save EUR 40m by 2027\n"
                "3 Jan 2025\nExample acquires Widget GmbH\n"
                "5 May 2021\nExample opens plant in Poland"}
TODAY = date(2026, 10, 17)


def test_only_headlines_on_the_page_survive():
    events = [
        {"headline": "Example launches efficiency programme to save EUR 40m by 2027",
         "date": "2026-03-12", "url": PAGE["url"], "type": "cost_programme"},
        {"headline": "Example announces 500 layoffs across Europe",          # invented
         "date": "2026-06-01", "url": PAGE["url"], "type": "restructuring"},
        {"headline": "Example acquires Widget GmbH", "date": "2025-01-03",
         "url": "https://wrong.example/page", "type": "acquisition"},          # wrong URL, real text
        {"headline": "Example opens plant in Poland", "date": "2021-05-05",
         "url": PAGE["url"], "type": "facility_change"},                       # too old
        {"headline": "Example launches efficiency programme to save EUR 40m by 2027",
         "date": "2027-01-01", "url": PAGE["url"], "type": "cost_programme"},  # future
    ]
    kept = verify_events(events, [PAGE], today=TODAY)
    assert [(k["type"], k["date"]) for k in kept] == [("cost_programme", "2026-03-12"),
                                                      ("acquisition", "2025-01-03")]
    assert kept[1]["url"] == PAGE["url"]  # re-pointed to the page that holds the text


def test_events_become_dated_press_signals():
    rec = CompanyRecord(input_url="example.de")
    kept = verify_events([{"headline": "Example acquires Widget GmbH", "date": "2025-01-03",
                           "url": PAGE["url"], "type": "acquisition"}], [PAGE], today=TODAY)
    assert apply_events(rec, kept) == 1
    ev = rec.get("PRESS.09")
    assert ev.value is True and ev.as_of_date == "2025-01-03" and ev.source_url == PAGE["url"]
