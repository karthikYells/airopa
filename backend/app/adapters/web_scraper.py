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
import time
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

# What they sell: product and service pages (Europe Market Assessment only).
_PRODUCT_HINTS = ["products", "product", "solutions", "services", "portfolio", "offerings",
                  "capabilities", "what we do", "what-we-do", "industries", "range", "catalogue",
                  "catalog"]

# Quality, certification and trust pages (Europe Market Assessment only).
_CERT_HINTS = ["quality", "certification", "certificates", "accreditation", "compliance",
               "trust", "security", "sustainability", "esg"]
_CERT_PATHS = ["/certifications", "/certification", "/quality", "/quality-policy",
               "/about-us/certifications", "/about/certifications", "/trust-center", "/trust"]
# Investor pages of listed companies, where annual reports live.
_INVESTOR_HINTS = ["investor", "investors", "annual-report", "financial-results", "shareholders"]

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
    product_pages: list[dict] = field(default_factory=list)  # [{url, text}] what they sell
    external_domains: list[str] = field(default_factory=list)  # other sites linked from home
    languages: list[str] = field(default_factory=list)        # site language versions (hreflang)
    trust_text: str = ""                                       # quality / certification / trust pages
    annual_report_urls: list[str] = field(default_factory=list)  # PDF links, own site
    error: str | None = None                               # why a crawl stopped early


def _normalise_url(raw: str) -> str:
    raw = raw.strip()
    if not raw.startswith(("http://", "https://")):
        raw = "https://" + raw
    return raw


_MAX_HTML = 1_500_000   # characters; enough for any real page's text


def _text(html: str) -> str:
    """Visible text of a page. Scripts and styles are stripped in one pass:
    removing them tag by tag took minutes on pages with thousands of tags."""
    try:
        tree = HTMLParser(html[:_MAX_HTML])
        tree.strip_tags(["script", "style", "noscript"])
        return tree.body.text(separator="\n") if tree.body else tree.text()
    except Exception:
        return ""


def _external_domains(html: str, base: str) -> list[str]:
    """Other web domains the homepage links to (subsidiaries, group sites,
    distributors), minus social and generic platforms."""
    skip = ("facebook.", "linkedin.", "twitter.", "x.com", "instagram.", "youtube.", "google.",
            "apple.com", "wa.me", "whatsapp.", "t.me", "pinterest.", "bit.ly", "goo.gl",
            "w3.org", "schema.org", "gstatic.", "cloudflare", "jsdelivr", "wordpress.")
    out: list[str] = []
    try:
        own = _site(urlparse(base).netloc)
        for a in HTMLParser(html[:_MAX_HTML]).css("a"):
            host = urlparse(urljoin(base, a.attributes.get("href") or "")).netloc.lower()
            host = host[4:] if host.startswith("www.") else host
            if host and "." in host and _site(host) != own and not any(k in host for k in skip):
                if host not in out:
                    out.append(host)
    except Exception:
        pass
    return out[:40]


def _languages(html: str) -> list[str]:
    """Language versions the site declares (hreflang), e.g. ['en', 'de', 'fr']."""
    langs: list[str] = []
    try:
        for ln in HTMLParser(html[:_MAX_HTML]).css("link[hreflang], a[hreflang]"):
            code = (ln.attributes.get("hreflang") or "").lower().split("-")[0]
            if code and code != "x" and code not in langs:
                langs.append(code)
    except Exception:
        pass
    return langs


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


def scrape_with_deadline(input_url: str, products: bool = False, deadline_s: float = 90.0) -> ScrapeResult:
    """scrape() with a hard stop: after `deadline_s` the pages read so far are
    used and the rest is abandoned. A slow site that drips its pages can no
    longer hold a visitor for minutes."""
    import copy
    import threading

    res = ScrapeResult(input_url=input_url, resolved_host=urlparse(_normalise_url(input_url)).netloc)
    t = threading.Thread(target=scrape, args=(input_url, products, deadline_s * 0.8, res), daemon=True)
    t.start()
    t.join(deadline_s)
    if t.is_alive():
        snap = copy.copy(res)
        for f in ("pages_fetched", "careers_urls", "job_titles", "india_pages", "news_pages",
                  "product_pages", "annual_report_urls", "india_careers_titles"):
            setattr(snap, f, list(getattr(res, f)))
        snap.error = snap.error or f"stopped after {deadline_s:.0f}s; used the pages read so far"
        return snap
    return res


def scrape(input_url: str, products: bool = False, budget_s: float = 75.0,
           res: ScrapeResult | None = None) -> ScrapeResult:
    """`products=True` also reads up to three product or service pages (used by
    the Europe Market Assessment to map what the company sells). After
    `budget_s` seconds no further optional pages are fetched, so one slow site
    cannot hold a visitor for minutes."""
    started = time.monotonic()

    def late() -> bool:
        return time.monotonic() - started > budget_s
    url = _normalise_url(input_url)
    host = urlparse(url).netloc
    res = res if res is not None else ScrapeResult(input_url=input_url, resolved_host=host)

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
                # A 403 is usually bot protection the site owner chose; we respect it
                # and say so, rather than trying to get round it.
                res.error = (f"blocked: the site refuses automated readers (HTTP {home.status_code})"
                             if home.status_code in (401, 403, 429) else f"HTTP {home.status_code}")
                return res
            res.reachable = True
            res.pages_fetched.append(str(home.url))
            home_html = home.text
            res.homepage_text = _text(home_html)[:20000]
            res.product_text = res.homepage_text[:4000]
            res.site_title = _page_title(home_html)
            res.external_domains = _external_domains(home_html, str(home.url))
            res.languages = _languages(home_html)
            res.page_title_name = _name_guess(home_html, res.site_title)

            # India check on the homepage counts.
            res.india_checks += 1
            if _india_office(res.homepage_text):
                res.india_office_detected = True
                res.india_pages.append(str(home.url))

            res.careers_urls = _find_careers_links(home_html, str(home.url))
            info_urls = _find_links(home_html, str(home.url), _INFO_HINTS, 6)

            for cu in res.careers_urls:
                if late():
                    break
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
                if late():
                    break
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
            if products:
                # Investor pages hold the annual reports of listed Indian companies.
                for vu in _find_links(home_html, str(home.url), _INVESTOR_HINTS, 2):
                    if late():
                        break
                    try:
                        vp = c.get(vu)
                        if vp.status_code < 400:
                            res.pages_fetched.append(str(vp.url))
                            report_links += _find_report_links(vp.text, str(vp.url))
                    except Exception:
                        continue
                # Quality, certification and trust pages: what European buyers check.
                trust = []
                for tu in _find_links(home_html, str(home.url), _CERT_HINTS, 6)[:3]:
                    if late():
                        break
                    try:
                        tp = c.get(tu)
                        if tp.status_code < 400:
                            res.pages_fetched.append(str(tp.url))
                            trust.append(_text(tp.text)[:8000])
                    except Exception:
                        continue
                # Certification pages are often not linked from the homepage.
                root = f"{urlparse(str(home.url)).scheme}://{urlparse(str(home.url)).netloc}"
                for path in _CERT_PATHS:
                    if late() or len(trust) >= 4:
                        break
                    try:
                        tp = c.get(root + path)
                        if tp.status_code == 429:
                            break
                        if tp.status_code < 400 and str(tp.url).rstrip("/") != str(home.url).rstrip("/"):
                            ttext = _text(tp.text)
                            if len(ttext) > 300 and re.search(r"ISO|certif|accredit", ttext, re.I):
                                res.pages_fetched.append(str(tp.url))
                                trust.append(ttext[:8000])
                    except Exception:
                        continue
                res.trust_text = "\n".join(trust)
            res.annual_report_urls = list(dict.fromkeys(report_links))[:3]

            if products:
                seen_p = {str(home.url).rstrip("/")}
                for pu in _find_links(home_html, str(home.url), _PRODUCT_HINTS, 8):
                    if len(res.product_pages) >= 3 or late():
                        break
                    try:
                        pp = c.get(pu)
                        final = str(pp.url).rstrip("/")
                        if pp.status_code == 429:
                            break
                        if pp.status_code >= 400 or final in seen_p:
                            continue
                        seen_p.add(final)
                        ptext = _text(pp.text)
                        if len(ptext) < 300:
                            continue
                        res.pages_fetched.append(str(pp.url))
                        res.product_pages.append({"url": str(pp.url), "text": ptext[:12000]})
                    except Exception:
                        continue

            # Their own newsroom: dated press releases for the timing panel (PRESS).
            # Menus are often JavaScript, so fall back to the usual addresses.
            news_urls = [u for u in _find_links(home_html, str(home.url), _NEWS_HINTS, 6)
                         if "newsletter" not in u.lower() and "subscribe" not in u.lower()]
            root = f"{urlparse(str(home.url)).scheme}://{urlparse(str(home.url)).netloc}"
            news_urls += [root + p for p in _NEWS_PATHS]
            seen_final: set[str] = set()
            for nu in list(dict.fromkeys(news_urls)):
                if len(res.news_pages) >= 2 or late():
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
