"""Real public-web collection — the company's OWN website and careers page.

This is the one live data source in v1. It fetches a small number of the
company's own pages and extracts only what is actually present: product/
category text, technology-stack mentions, job titles from the careers page,
India mentions, and whether a public technology executive is named. Everything
it returns carries the page URL as its source, so the evidence envelope is
honest. Nothing here is inferred or invented.

Deliberately NOT a job-board aggregator: aggregators match keywords against the
whole job body, so a construction firm shows hundreds of 'software development'
hits for one role (Section 5.7). We read the company's own careers pages and
count actual titles.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from urllib.parse import urljoin, urlparse

import httpx
from selectolax.parser import HTMLParser

_UA = "AiropaBot/1.0 (+https://airopa.co; public assessment)"
_TIMEOUT = httpx.Timeout(8.0, connect=5.0)

_CAREERS_HINTS = ["career", "careers", "jobs", "vacanc", "join-us", "join us",
                  "work-with-us", "working-at", "stellen", "karriere", "vacatures",
                  "emploi", "recrutement"]

# Other pages worth a look for firmographics and India presence.
_INFO_HINTS = ["about", "about-us", "company", "who-we-are", "unternehmen",
               "ueber-uns", "over-ons", "locations", "location", "contact",
               "standorte", "global", "worldwide", "offices", "investor",
               "investors", "annual-report", "group", "where-we-are"]

_TECH_STACK = {
    "SAP S/4HANA": ["s/4hana", "s4hana", "s/4 hana"],
    "SAP ECC": ["sap ecc", "sap r/3", "ecc 6"],
    "SAP": ["sap"],
    "Oracle": ["oracle"],
    "Salesforce": ["salesforce"],
    "Workday": ["workday"],
    "ServiceNow": ["servicenow"],
    "Microsoft Dynamics": ["dynamics 365", "microsoft dynamics"],
    "Snowflake": ["snowflake"],
    "Databricks": ["databricks"],
    "dbt": ["dbt"],
    "AWS": ["aws", "amazon web services"],
    "Azure": ["microsoft azure", "azure"],
    "Google Cloud": ["google cloud", "gcp"],
    "Mainframe/COBOL": ["mainframe", "cobol", "as/400", "as400"],
}

_INDIA_HINTS = ["india", "bengaluru", "bangalore", "pune", "hyderabad", "chennai",
                "mumbai", "gurgaon", "gurugram", "noida", "kolkata", "ahmedabad"]

_TECH_EXEC = ["chief information officer", "chief technology officer",
              "chief digital officer", "cio", "cto", "cdo", "head of it",
              "head of digital", "vp engineering", "vp of engineering"]

# Job-title line heuristic: short lines that look like a role.
_TITLE_LINE = re.compile(r"^[A-Z][A-Za-z0-9&/()+.\- ]{3,60}$")


@dataclass
class ScrapeResult:
    input_url: str
    resolved_host: str | None = None
    reachable: bool = False
    pages_fetched: list[str] = field(default_factory=list)
    careers_urls: list[str] = field(default_factory=list)
    homepage_text: str = ""
    job_titles: list[str] = field(default_factory=list)
    tech_stack: list[str] = field(default_factory=list)
    india_mentions: list[str] = field(default_factory=list)
    india_careers_titles: list[str] = field(default_factory=list)
    tech_exec_named: bool = False
    product_text: str = ""
    site_title: str = ""
    india_pages: list[str] = field(default_factory=list)   # pages mentioning India
    india_office_detected: bool = False
    india_checks: int = 0                                  # India-targeted checks run
    page_title_name: str | None = None                     # company name guess


def _normalise_url(raw: str) -> str:
    raw = raw.strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    return raw


def _text(html: str) -> str:
    try:
        tree = HTMLParser(html)
        for tag in tree.css("script, style, noscript"):
            tag.decompose()
        return tree.body.text(separator="\n") if tree.body else tree.text()
    except Exception:
        return ""


def _find_links(html: str, base: str, hints: list[str], limit: int) -> list[str]:
    out: list[str] = []
    try:
        tree = HTMLParser(html)
        host = urlparse(base).netloc
        for a in tree.css("a"):
            href = a.attributes.get("href") or ""
            label = (a.text() or "").lower()
            if any(h in href.lower() or h in label for h in hints):
                full = urljoin(base, href)
                if urlparse(full).netloc not in ("", host):
                    continue  # stay on the company's own domain
                if full not in out:
                    out.append(full)
    except Exception:
        pass
    return out[:limit]


def _find_careers_links(html: str, base: str) -> list[str]:
    return _find_links(html, base, _CAREERS_HINTS, 4)


def _page_title(html: str) -> str:
    try:
        t = HTMLParser(html).css_first("title")
        return (t.text() if t else "").strip()
    except Exception:
        return ""


def _india_office(text: str) -> bool:
    """A real India presence cue: an Indian city or an India legal-entity marker,
    not merely the word 'india' appearing once."""
    low = text.lower()
    if "pvt ltd" in low or "private limited" in low or "pvt. ltd" in low:
        if "india" in low:
            return True
    city_hits = sum(1 for h in _INDIA_HINTS[1:] if h in low)  # skip bare 'india'
    if city_hits >= 1:
        return True
    # "India" near office/location/subsidiary words
    import re as _re
    return bool(_re.search(
        r"\bindia\b[^.]{0,40}\b(office|location|subsidiary|operations|plant|centre|center|team)\b"
        r"|\b(office|location|subsidiary|operations|plant|centre|center|team)\b[^.]{0,40}\bindia\b",
        low))


def _extract_titles(text: str) -> list[str]:
    titles: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if _TITLE_LINE.match(line) and 1 <= len(line.split()) <= 7:
            # Filter obvious non-titles (nav, legal).
            low = line.lower()
            if any(w in low for w in ["cookie", "privacy", "imprint", "copyright",
                                      "contact", "newsletter", "sitemap"]):
                continue
            titles.append(line)
    # De-dup, keep order.
    seen, out = set(), []
    for t in titles:
        if t.lower() not in seen:
            seen.add(t.lower()); out.append(t)
    return out[:120]


def scrape(input_url: str) -> ScrapeResult:
    url = _normalise_url(input_url)
    host = urlparse(url).netloc
    res = ScrapeResult(input_url=input_url, resolved_host=host)

    headers = {"User-Agent": _UA, "Accept-Language": "en,de,nl,fr"}
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True, headers=headers) as c:
            home = c.get(url)
            if home.status_code >= 400:
                return res
            res.reachable = True
            res.pages_fetched.append(str(home.url))
            home_html = home.text
            res.homepage_text = _text(home_html)[:20000]
            res.product_text = res.homepage_text[:4000]
            res.site_title = _page_title(home_html)
            if res.site_title:
                res.page_title_name = res.site_title.split("|")[0].split("-")[0].strip()[:80]

            # India check on the homepage counts.
            res.india_checks += 1
            if _india_office(res.homepage_text):
                res.india_office_detected = True
                res.india_pages.append(str(home.url))

            res.careers_urls = _find_careers_links(home_html, str(home.url))
            info_urls = _find_links(home_html, str(home.url), _INFO_HINTS, 6)

            for cu in res.careers_urls:
                try:
                    cp = c.get(cu)
                    if cp.status_code < 400:
                        res.pages_fetched.append(str(cp.url))
                        res.india_checks += 1
                        ctext = _text(cp.text)
                        page_titles = _extract_titles(ctext)
                        res.job_titles.extend(page_titles)
                        low = ctext.lower()
                        if any(h in low for h in _INDIA_HINTS):
                            res.india_careers_titles.extend(page_titles)
                            res.india_pages.append(str(cp.url))
                        if _india_office(ctext):
                            res.india_office_detected = True
                except Exception:
                    continue

            for iu in info_urls:
                try:
                    ip = c.get(iu)
                    if ip.status_code < 400:
                        res.pages_fetched.append(str(ip.url))
                        res.india_checks += 1
                        itext = _text(ip.text)
                        if _india_office(itext):
                            res.india_office_detected = True
                            res.india_pages.append(str(ip.url))
                        elif any(h in itext.lower() for h in _INDIA_HINTS):
                            res.india_pages.append(str(ip.url))
                        res.homepage_text += "\n" + itext[:6000]  # enrich product text
                except Exception:
                    continue
    except Exception:
        return res

    blob = (res.homepage_text + " " + " ".join(res.job_titles)).lower()
    res.tech_stack = [name for name, keys in _TECH_STACK.items()
                      if any(k in blob for k in keys)]
    res.india_mentions = [h for h in _INDIA_HINTS if h in blob]
    res.tech_exec_named = any(e in res.homepage_text.lower() for e in _TECH_EXEC)
    # De-dup job titles across pages.
    seen, uniq = set(), []
    for t in res.job_titles:
        if t.lower() not in seen:
            seen.add(t.lower()); uniq.append(t)
    res.job_titles = uniq
    return res
