"""Key figures from the company's own published annual report (Sections 5.3, 5.5).

Primary-source revenue (SCALE.01, SCALE.02), operating margin direction
(PRESS.01) and profit growth against revenue growth (PRESS.02). The model only
extracts; a figure is kept only if the exact printed string is on the page it
cites. Each signal carries the report URL with its page and the financial
year-end as its date, so the freshness rules apply.
"""
from __future__ import annotations

import io
import re

import httpx

from app.data.evidence import Evidence, Method, SourceAuthority, SourceType

_TIMEOUT = httpx.Timeout(40.0, connect=8.0)
_MAX_BYTES = 30 * 1024 * 1024
_MAX_PAGES = 250
_KEYWORDS = re.compile(
    r"key figures|financial highlights|kerncijfers|kennzahlen|chiffres cl[eé]s|"
    r"revenue|net sales|turnover|omzet|umsatz|operating (profit|result|income)|ebita|ebit\b|"
    r"bedrijfsresultaat|operatives ergebnis|revenue from operations|total income|profit before tax|ebitda", re.I)
_UNIT = {"units": 1, "unit": 1, "thousand": 1e3, "thousands": 1e3, "million": 1e6,
         "millions": 1e6, "billion": 1e9, "billions": 1e9,
         # Indian reports: 1 lakh = 100,000; 1 crore = 10 million
         "lakh": 1e5, "lakhs": 1e5, "crore": 1e7, "crores": 1e7}
_FX_TO_EUR = {"EUR": 1.0, "USD": 0.92, "GBP": 1.17, "CHF": 1.05, "SEK": 0.088,
              "NOK": 0.086, "DKK": 0.134, "INR": 0.0105}  # rough, as the Wikidata adapter


def _year_of(url: str) -> int:
    years = [int(y) for y in re.findall(r"20[1-3]\d", url)]
    return max(years) if years else 0


def fetch_report_pages(urls: list[str]) -> tuple[str, list[tuple[int, str]]] | None:
    """Most recent report among the links -> (url, [(page_no, text)]) of the
    pages most likely to hold the key figures. None if none could be read."""
    from pypdf import PdfReader

    for url in sorted(urls, key=_year_of, reverse=True)[:2]:
        try:
            with httpx.stream("GET", url, timeout=_TIMEOUT, follow_redirects=True,
                              headers={"User-Agent": "AiropaBot/1.0 (+https://airopa.co)"}) as r:
                if r.status_code >= 400 or "pdf" not in r.headers.get("content-type", "pdf"):
                    continue
                buf = bytearray()
                for chunk in r.iter_bytes():
                    buf.extend(chunk)
                    if len(buf) > _MAX_BYTES:
                        break
            reader = PdfReader(io.BytesIO(bytes(buf)))
            scored = []
            for i, page in enumerate(reader.pages[:_MAX_PAGES], start=1):
                try:
                    text = page.extract_text() or ""
                except Exception:
                    continue
                hits = len(_KEYWORDS.findall(text))
                if hits:
                    scored.append((hits + (5 if re.search(r"key figures|kerncijfers|kennzahlen|highlights", text, re.I) else 0), i, text))
            if scored:
                top = sorted(scored, reverse=True)[:5]
                return url, sorted(((i, t) for _, i, t in top))
        except Exception:
            continue
    return None


def _num(printed: str | None) -> float | None:
    """'3,215.4' / '3.215,4' / '(12.0)' -> float."""
    if not printed:
        return None
    s = printed.strip().replace("−", "-").replace(" ", "")
    neg = s.startswith("(") and s.endswith(")") or s.startswith("-")
    s = s.strip("()-")
    if re.fullmatch(r"\d{1,3}(\.\d{3})+(,\d+)?", s):          # 3.215,4 (EU style)
        s = s.replace(".", "").replace(",", ".")
    else:
        s = s.replace(",", "")
    try:
        v = float(s)
    except ValueError:
        return None
    return -v if neg else v


def _on_page(printed: str | None, page_no, pages: dict[int, str]) -> bool:
    if not printed or page_no not in pages:
        return False
    flat = re.sub(r"\s+", "", pages[page_no])
    return re.sub(r"\s+", "", printed) in flat


_UNIT_WORDS = {"thousand": r"thousands?|'000|000s|in 000", "million": r"millions?|mn|m",
               "billion": r"billions?|bn", "lakh": r"lakhs?|lacs?", "crore": r"crores?|cr"}


def _unit_printed(unit: str, text: str) -> bool:
    key = unit.rstrip("s")
    pattern = _UNIT_WORDS.get(key, re.escape(key))
    return re.search(pattern, text, re.I) is not None


def verify_financials(data: dict, pages: list[tuple[int, str]]) -> dict | None:
    """Keep only figures printed on the cited page. Returns
    {currency, scale, years: [{year, revenue, op_profit, rev_page, op_page}]} or None."""
    by_page = dict(pages)
    scale = _UNIT.get(str(data.get("unit", "")).lower())
    cur = str(data.get("currency", "")).upper()
    if not scale or cur not in _FX_TO_EUR:
        return None
    # The unit must be printed on a page we read: a wrong unit (lakh for
    # million) would put every figure out by a factor of ten or more.
    unit = str(data.get("unit", "")).lower()
    if scale != 1 and not any(_unit_printed(unit, t) for t in by_page.values()):
        return None
    years = []
    for y in data.get("years") or []:
        try:
            year = int(y.get("year"))
        except (TypeError, ValueError):
            continue
        rev_ok = _on_page(y.get("revenue"), y.get("revenue_page"), by_page)
        op_ok = _on_page(y.get("operating_profit"), y.get("operating_profit_page"), by_page)
        rev = _num(y.get("revenue")) if rev_ok else None
        op = _num(y.get("operating_profit")) if op_ok else None
        if rev is None:
            continue
        years.append({"year": year, "revenue": rev * scale * _FX_TO_EUR[cur],
                      "op_profit": None if op is None else op * scale * _FX_TO_EUR[cur],
                      "rev_page": y.get("revenue_page"), "op_page": y.get("operating_profit_page")})
    years.sort(key=lambda x: x["year"], reverse=True)
    return {"currency": cur, "years": years} if years else None


def apply_financials(rec, fin: dict, url: str) -> int:
    """SCALE.01/02 and PRESS.01/02 from verified figures. Returns signals added."""
    ys = fin["years"]
    latest = ys[0]
    src = dict(source_type=SourceType.FILING, source_authority=SourceAuthority.PRIMARY,
               method=Method.MODEL, confidence=0.75)
    added = 0
    prev = ys[1] if len(ys) >= 2 else None
    def margin(y):
        return y["op_profit"] / y["revenue"] if y["op_profit"] is not None and y["revenue"] else None
    rec.financials = {
        "year": latest["year"], "revenue": latest["revenue"],
        "revenue_growth": (latest["revenue"] / prev["revenue"] - 1) if prev and prev["revenue"] else None,
        "op_margin": margin(latest), "op_margin_prev": margin(prev) if prev else None,
        "prev_year": prev["year"] if prev else None, "source_url": url,
    }
    rec.add(Evidence("SCALE.01", int(latest["revenue"]), unit="EUR",
                     source_url=f"{url}#page={latest['rev_page']}",
                     as_of_date=f"{latest['year']}-12-31",
                     notes=f"Annual report FY{latest['year']} (converted from {fin['currency']})"
                     if fin["currency"] != "EUR" else f"Annual report FY{latest['year']}", **src))
    added += 1
    if len(ys) >= 2:
        rec.add(Evidence("SCALE.02", {str(y["year"]): int(y["revenue"]) for y in ys}, unit="EUR",
                         source_url=f"{url}#page={latest['rev_page']}",
                         as_of_date=f"{latest['year']}-12-31", **src))
        added += 1
        prev = ys[1]
        if latest["op_profit"] is not None and prev["op_profit"] is not None and prev["revenue"]:
            m_now = latest["op_profit"] / latest["revenue"]
            m_prev = prev["op_profit"] / prev["revenue"]
            rec.add(Evidence("PRESS.01", m_now < m_prev, unit="margin compressing",
                             source_url=f"{url}#page={latest['op_page']}",
                             as_of_date=f"{latest['year']}-12-31",
                             notes=f"Operating margin {m_prev:.1%} (FY{prev['year']}) -> "
                                   f"{m_now:.1%} (FY{latest['year']})", **src))
            rev_g = latest["revenue"] / prev["revenue"] - 1
            op_g = (latest["op_profit"] / prev["op_profit"] - 1) if prev["op_profit"] > 0 else None
            if op_g is not None:
                rec.add(Evidence("PRESS.02", op_g < rev_g, unit="profit lagging revenue",
                                 source_url=f"{url}#page={latest['op_page']}",
                                 as_of_date=f"{latest['year']}-12-31",
                                 notes=f"Revenue {rev_g:+.1%}, operating profit {op_g:+.1%}", **src))
                added += 1
            added += 1
    return added
