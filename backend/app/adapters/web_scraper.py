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

# 'Join us' is deliberately absent: retail and membership sites use it for
# sign-up pages (nike.com), whose menus were then read as job titles.
_CAREERS_HINTS = ["career", "careers", "jobs", "vacanc", "work-with-us",
                  "working-at", "stellen", "karriere", "vacatures", "emploi",
                  "recrutement"]

# A careers-page line counts as a job title only if it names a role. Without
# this, navigation and product menus ('Find a Store', 'Running Shoes') were
# counted as jobs.
_ROLE_WORDS = re.compile(
    r"\b(engineer|developer|programmer|architect|analyst|scientist|consultant|"
    r"manager|director|head|lead|leader|specialist|expert|officer|administrator|"
    r"technician|designer|coordinator|associate|assistant|executive|representative|"
    r"advisor|adviser|accountant|controller|planner|buyer|operator|mechanic|"
    r"electrician|intern|internship|trainee|apprentice|graduate|tester|devops|sre|"
    r"owner|scrum master|recruiter|partner|agent|supervisor|foreman|"
    # German / Dutch / French
    r"ingenieur|entwickler|leiter|leiterin|mitarbeiter|mitarbeiterin|referent|"
    r"sachbearbeiter|techniker|berater|beraterin|projektleiter|werkstudent|"
    r"ausbildung|praktikum|medewerker|adviseur|ontwikkelaar|monteur|stagiair|"
    r"developpeur|responsable|chef de projet|technicien|stage)\b"
    r"|\(m/w/d\)|\(w/m/d\)|\(m/f/d\)|\(f/m/d\)|\(h/f\)|\(m/v\)",
    re.IGNORECASE)

_INDIA_WORD = re.compile(
    r"\b(india|bengaluru|bangalore|pune|hyderabad|chennai|mumbai|gurgaon|"
    r"gurugram|noida|kolkata|ahmedabad)\b", re.IGNORECASE)

# Other pages worth a look for firmographics and India presence.
# Their own newsroom / press releases (EN, NL, DE, FR).
_NEWS_HINTS = ["newsroom", "news", "press", "media", "nieuws", "pers", "presse",
               "aktuelles", "neuigkeiten", "actualites", "actualités"]

# Tried only when the menu shows no newsroom; stops at the first "429 Too Many Requests".
_NEWS_PATHS = ["/news", "/newsroom", "/press", "/en/news", "/nieuws", "/presse"]

# Annual / integrated reports, usually PDFs on the site or a CDN.
_REPORT_HINTS = ["annual report", "annual-report", "annualreport", "integrated report",
                 "annual review", "jaarverslag", "jaarrapport", "geschäftsbericht",
                 "geschaeftsbericht", "jahresbericht", "rapport annuel", "rapport-annuel"]


def _find_report_links(html: str, base: str) -> list[str]:
    """Links to annual reports: anchor text or URL names one. PDFs may live on a
    CDN, so other hosts are allowed here (and only here)."""
    out: list[str] = []
    try:
        for a in HTMLParser(html).css("a"):
            href = a.attributes.get("href") or ""
            label = (a.text() or "").lower()
            hl = href.lower()
            if any(h in hl or h in label for h in _REPORT_HINTS):
                full = urljoin(base, href)
                if full.startswith("http") and full not in out:
                    out.append(full)
    except Exception:
        pass
    # Prefer direct PDFs.
    return sorted(out, key=lambda u: 0 if u.lower().split("?")[0].endswith(".pdf") else 1)


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
_TITLE_LINE = re.compile(r"^[A-Z][A-Za-z0-9&/()+.,\- ]{3,70}$")


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
    news_pages: list[dict] = field(default_factory=list)   # [{url, text}] own newsroom
    annual_report_urls: list[str] = field(default_factory=list)  # PDF links, own site
    error: str | None = None                               # why a crawl stopped early


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


def _site(host: str) -> str:
    """Registrable domain, roughly: 'jobs.nike.com' -> 'nike.com',
    'careers.example.co.uk' -> 'example.co.uk'."""
    parts = host.lower().split(":")[0].split(".")
    if len(parts) >= 3 and parts[-2] in ("co", "com", "org", "net", "ac", "gov") and len(parts[-1]) == 2:
        return ".".join(parts[-3:])
    return ".".join(parts[-2:])


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
                netloc = urlparse(full).netloc
                if netloc and netloc != host and _site(netloc) != _site(host):
                    continue  # stay on the company's own site (subdomains allowed)
                if full not in out:
                    out.append(full)
    except Exception:
        pass
    return out[:limit]


def _find_careers_links(html: str, base: str) -> list[str]:
    return _find_links(html, base, _CAREERS_HINTS, 4)


_GENERIC_TITLES = {"home", "homepage", "home page", "welcome", "start", "startseite",
                   "index", "main", "accueil", "inicio", "untitled"}


def _name_guess(html: str, title: str) -> str | None:
    """Company name from the site: og:site_name first, then the page title's
    first segment, never a generic word like 'Home'."""
    candidates = []
    try:
        meta = HTMLParser(html).css_first('meta[property="og:site_name"]')
        if meta and (meta.attributes.get("content") or "").strip():
            candidates.append(meta.attributes["content"].strip())
    except Exception:
        pass
    if title:
        parts = [p.strip() for p in re.split(r"\s[|\-–—:]\s", title) if p.strip()]
        candidates += parts
    for c in candidates:
        if c.lower() not in _GENERIC_TITLES and len(c) <= 80:
            return c
    return None


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


def _extract_titles(text: str) -> list[tuple[str, bool]]:
    """Job titles on a careers page, each with whether it is located in India.

    A line counts as a title only if it is short, title-shaped AND names a role.
    India is judged per title from the title line and the few lines after it
    (where listings put the location), not from 'India' anywhere on the page —
    a country selector would otherwise make every title an India title.
    """
    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if l]

    def is_title(line: str) -> bool:
        if not (_TITLE_LINE.match(line) and 1 <= len(line.split()) <= 9):
            return False
        low = line.lower()
        if any(w in low for w in ["cookie", "privacy", "imprint", "copyright",
                                  "contact", "newsletter", "sitemap",
                                  "chat with", "virtual assistant"]):
            return False
        return bool(_ROLE_WORDS.search(line))

    found: list[tuple[str, bool]] = []
    for i, line in enumerate(lines):
        if not is_title(line):
            continue
        # Location: the title itself plus up to four following lines (listings
        # often put a req id and a 'Job location' label first), stopping at the
        # next title and skipping list-like lines (country pickers).
        nearby = [line]
        for nxt in lines[i + 1:i + 5]:
            if is_title(nxt):
                break
            if nxt.count(",") < 3:
                nearby.append(nxt)
        found.append((line, bool(_INDIA_WORD.search(" ".join(nearby)))))
    # De-dup, keep order; a title is India if any occurrence is.
    out: dict[str, tuple[str, bool]] = {}
    for t, india in found:
        k = t.lower()
        out[k] = (out[k][0], out[k][1] or india) if k in out else (t, india)
    return list(out.values())[:120]


def scrape(input_url: str) -> ScrapeResult:
    url = _normalise_url(input_url)
    host = urlparse(url).netloc
    res = ScrapeResult(input_url=input_url, resolved_host=host)

    headers = {"User-Agent": _UA, "Accept-Language": "en,de,nl,fr"}
    try:
        with httpx.Client(timeout=_TIMEOUT, follow_redirects=True, headers=headers) as c:
            # One retry: a single slow first response (cold CDN cache) should not
            # mark a live site 'unreachable'.
            try:
                home = c.get(url)
            except httpx.TransportError:
                home = c.get(url)
            if home.status_code >= 500:
                home = c.get(url)
            if home.status_code >= 400:
                return res
            res.reachable = True
            res.pages_fetched.append(str(home.url))
            home_html = home.text
            res.homepage_text = _text(home_html)[:20000]
            res.product_text = res.homepage_text[:4000]
            res.site_title = _page_title(home_html)
            res.page_title_name = _name_guess(home_html, res.site_title)

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
                        res.job_titles.extend(t for t, _ in page_titles)
                        india_titles = [t for t, india in page_titles if india]
                        if india_titles:
                            res.india_careers_titles.extend(india_titles)
                            res.india_pages.append(str(cp.url))
                        if _india_office(ctext):
                            res.india_office_detected = True
                except Exception:
                    continue

            report_links = _find_report_links(home_html, str(home.url))
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
                        report_links += _find_report_links(ip.text, str(ip.url))
                except Exception:
                    continue
            res.annual_report_urls = list(dict.fromkeys(report_links))[:3]

            # Their own newsroom: dated press releases for the timing panel (PRESS).
            # Menus are often JavaScript, so fall back to the usual addresses.
            news_urls = [u for u in _find_links(home_html, str(home.url), _NEWS_HINTS, 6)
                         if "newsletter" not in u.lower() and "subscribe" not in u.lower()]
            root = f"{urlparse(str(home.url)).scheme}://{urlparse(str(home.url)).netloc}"
            news_urls += [root + p for p in _NEWS_PATHS]
            seen_final: set[str] = set()
            for nu in list(dict.fromkeys(news_urls)):
                if len(res.news_pages) >= 2:
                    break
                try:
                    np_ = c.get(nu)
                    if np_.status_code == 429:
                        break  # the site asks us to slow down: stop, don't keep probing
                    final = str(np_.url).rstrip("/")
                    if np_.status_code >= 400 or final in seen_final or final == str(home.url).rstrip("/"):
                        continue
                    seen_final.add(final)
                    ntext = _text(np_.text)
                    if len(ntext) < 400:
                        continue  # empty shell (JavaScript-only page)
                    res.pages_fetched.append(str(np_.url))
                    res.news_pages.append({"url": str(np_.url), "text": ntext[:15000]})
                except Exception:
                    continue
    except Exception as e:  # keep what was collected; record why it stopped
        res.error = f"{type(e).__name__}: {str(e)[:200]}"
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
