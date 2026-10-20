"""Anthropic Claude wrapper (Section 1.4 model allocation).

Models are used only for classification, extraction and narrative generation —
never for arithmetic, never to recall or generate reference facts. Current
models do not accept a temperature setting, so title classes are cached per
instance to keep a run self-consistent (Section 11.4 reproducibility). When no
API key is configured, `enabled` is False and callers fall back to
deterministic behaviour.
"""
from __future__ import annotations

import json

from app.config import Settings
from app.data.records import TitleClass


class LLM:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = None
        self._title_cache: dict[str, tuple[TitleClass, float]] = {}
        if settings.llm_enabled:
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            except Exception:
                self._client = None

    @property
    def enabled(self) -> bool:
        return self._client is not None

    # Current models think before answering and that counts against max_tokens;
    # without headroom a short answer (a 20-token sector key) comes back empty.
    _THINKING_HEADROOM = 2048

    def _complete(self, model: str, system: str, user: str, max_tokens: int) -> str:
        """`max_tokens` is the answer budget; thinking headroom is added on top."""
        msg = self._client.messages.create(
            model=model, max_tokens=max_tokens + self._THINKING_HEADROOM,
            system=system, messages=[{"role": "user", "content": user}],
        )
        return "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")

    # --- small/cheap model: classification only (Section 3.3 fallback) ---
    def classify_title(self, normalised: str, context: str | None = None) -> tuple[TitleClass, float]:
        if not self.enabled:
            return TitleClass.AMBIGUOUS, 0.3
        system = (
            "You classify a single job title into exactly one label for an India "
            "capability-centre screen. Labels: TECH (software/platform/data/security/"
            "product engineering), NON_TECH (commercial, finance, plant/process "
            "engineering, field service, country leadership), IT_SUPPORT (helpdesk/"
            "desktop/site IT), AMBIGUOUS (cannot tell without more context). "
            "Plant, manufacturing, process and field engineering are NON_TECH. "
            'Reply with JSON only: {"label": "...", "confidence": 0.0}.'
        )
        user = f"Title: {normalised}\nContext: {context or 'none'}"
        try:
            raw = self._complete(self._settings.llm_model_small, system, user, 100)
            data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            label = TitleClass(data["label"])
            return label, float(data.get("confidence", 0.6))
        except Exception:
            return TitleClass.AMBIGUOUS, 0.3

    def classify_titles_batch(self, titles: list[str], context: str | None = None
                              ) -> dict[str, tuple[TitleClass, float]]:
        """Classify many titles in one call per chunk (a people search returns
        ~100). Results are cached on the instance so a title is classed once per
        run. Titles the model fails on come back AMBIGUOUS."""
        out: dict[str, tuple[TitleClass, float]] = {}
        todo = [t for t in dict.fromkeys(titles) if t not in self._title_cache]
        if self.enabled:
            system = (
                "You classify job titles for an India capability-centre screen. "
                "Labels: TECH (software/platform/data/security/product engineering, "
                "enterprise applications such as SAP), NON_TECH (commercial, finance, "
                "HR, plant/process/mechanical/design engineering, field service, "
                "country leadership), IT_SUPPORT (helpdesk/desktop/site IT), "
                "AMBIGUOUS (cannot tell without more context). Plant, manufacturing, "
                "process, mechanical, CAD and field engineering are NON_TECH. "
                'Reply with JSON only: {"<title>": {"label": "...", "confidence": 0.0}, ...} '
                "using each title exactly as given."
            )
            for i in range(0, len(todo), 50):
                chunk = todo[i:i + 50]
                user = f"Context: {context or 'none'}\nTitles:\n" + "\n".join(chunk)
                try:
                    raw = self._complete(self._settings.llm_model_small, system, user, 4000)
                    data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
                except Exception:
                    data = {}
                for t in chunk:
                    try:
                        item = data[t]
                        self._title_cache[t] = (TitleClass(item["label"]),
                                                float(item.get("confidence", 0.6)))
                    except Exception:
                        self._title_cache[t] = (TitleClass.AMBIGUOUS, 0.3)
        for t in titles:
            out[t] = self._title_cache.get(t, (TitleClass.AMBIGUOUS, 0.3))
        return out

    # --- small model: dated events from the company's own newsroom (PRESS) ---
    def extract_news_events(self, company: str, pages: list[dict]) -> list[dict]:
        """Extraction only (Section 1.4): list the dated events that appear on the
        pages. The caller verifies every headline against the page text and drops
        anything it cannot find, so nothing the model adds survives."""
        if not self.enabled or not pages:
            return []
        system = (
            "You extract dated company events from a company's own news pages. Only "
            "use what is written on the pages. For each news item that has a visible "
            "date, return the headline copied EXACTLY as written, the date as "
            "YYYY-MM-DD (or YYYY-MM if no day), the page URL it is on, and one type: "
            "cost_programme (savings or efficiency programme, cost targets), "
            "restructuring (reorganisation, layoffs, hiring freeze), erp_migration "
            "(SAP S/4HANA or ERP programme), acquisition (they acquire or merge), "
            "leadership_change (new CEO, CFO, COO, CIO, CTO), facility_change (plant "
            "or site opened, closed or relocated), results (financial results), "
            "india_expansion (anything about India), other. Skip items without a date. "
            'Reply with JSON only: {"events": [{"headline": "...", "date": "...", '
            '"url": "...", "type": "..."}]}'
        )
        body = "\n\n".join(f"PAGE {p['url']}\n{p['text'][:12000]}" for p in pages[:2])
        try:
            raw = self._complete(self._settings.llm_model_small, system,
                                 f"Company: {company}\n\n{body}", 3000)
            data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            return [e for e in data.get("events", []) if isinstance(e, dict)][:40]
        except Exception:
            return []

    # --- small model: key figures from a published annual report (SCALE/PRESS) ---
    def extract_financials(self, company: str, pages: list[tuple[int, str]]) -> dict:
        """Extraction only: revenue and operating profit per year as PRINTED on
        the given pages. The caller checks each printed figure is on its page."""
        if not self.enabled or not pages:
            return {}
        system = (
            "You read pages of a company's annual report and extract its key figures. "
            "Only use numbers printed on the pages. Return the currency (ISO code), the "
            "unit the figures are in (units, thousand, lakh, crore, million or billion), and for up to "
            "4 financial years: the year (the year the financial year ends, e.g. FY2024-25 is 2025), revenue (net sales / turnover / revenue from operations / omzet / Umsatz) "
            "and operating profit (EBIT / EBITA / operating result), each copied EXACTLY as "
            "printed (e.g. \"3,215.4\") together with the page number it is printed on. "
            "Use group/consolidated figures, not segments. If a figure is not printed, use null. "
            'Reply with JSON only: {"currency": "EUR", "unit": "million", "years": [{"year": 2025, '
            '"revenue": "3,215.4", "revenue_page": 12, "operating_profit": "401.2", '
            '"operating_profit_page": 12}]}'
        )
        body = "\n\n".join(f"=== PAGE {n} ===\n{t[:6000]}" for n, t in pages)
        try:
            raw = self._complete(self._settings.llm_model_small, system,
                                 f"Company: {company}\n\n{body}", 1500)
            data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    # --- small model: what the company sells, as HS codes / service types ---
    def map_offering(self, company: str, pages: list[dict]) -> dict:
        """Extraction only: products and services named on the company's own
        pages, each with a phrase copied exactly from the page as evidence, a
        6-digit HS code for goods and a service type for services. The caller
        drops every item whose evidence is not on the page."""
        if not self.enabled or not pages:
            return {}
        system = (
            "You read a company's own web pages and list what it sells. Use only what the "
            "pages say. For each physical product line it makes or exports (up to 6), give: "
            "name; evidence, a short phrase copied EXACTLY from the page that names the "
            "product; url, the page it is on; hs, the most likely 6-digit Harmonized System "
            "code (HS 2022) for that product as exported; hs_label, the official short "
            "description of that code; confidence 0-1. For each service line it sells (up to "
            "4), give name, evidence, url and code: SI for software, IT, cloud, data or "
            "telecom services; SJ3 for engineering, design, testing or technical services; SJ "
            "for consulting, business process outsourcing and other business services. Do not "
            "list what its customers make, and do not list products it only buys. "
            "Also give: segment, a short phrase for what it sells (e.g. 'seed traceability "
            "software'); and buyers, up to 3 industries that buy from it, each as a code chosen ONLY "
            "from the INDUSTRY CODES list below (the most specific code for the BUYERS, not for the "
            "company itself) with evidence, a phrase copied EXACTLY from the page that names those "
            "buyers (e.g. 'for staffing agencies'). "
            'Reply with JSON only: {"products": [{"name": "", "evidence": "", "url": "", '
            '"hs": "", "hs_label": "", "confidence": 0.0}], "services": [{"name": "", '
            '"evidence": "", "url": "", "code": ""}], "segment": "", "buyers": [{"code": "", "evidence": ""}]}'
        )
        from app.reference.nace import codes as nace_codes
        system += "\n\nINDUSTRY CODES:\n" + "\n".join(f"{c} {t}" for c, t in nace_codes().items())
        body = "\n\n".join(f"PAGE {p['url']}\n{p['text'][:7000]}" for p in pages[:4])
        try:
            raw = self._complete(self._settings.llm_model_small, system,
                                 f"Company: {company}\n\n{body}", 2500)
            data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def propose_competitors(self, company: str, segment: str, lines: list[str]) -> dict:
        """Candidates only: companies known to sell the same offering, plus
        search keywords. Every candidate is checked against its own website by
        the caller; nothing here is used unverified."""
        if not self.enabled or not segment:
            return {}
        system = (
            "You are a market analyst. Given a company's offering, list up to 12 companies that sell "
            "the SAME kind of product or service to the same kind of buyer (direct competitors, any "
            "country; include European, American and Indian ones if they exist), each with its main "
            "website domain. Also give 3 short search keywords that describe the offering (as used to "
            "tag companies, e.g. 'recruiting software'). Do not include the company itself. "
            'Reply with JSON only: {"competitors": [{"name": "", "domain": ""}], "keywords": [""]}'
        )
        user = f"Company: {company}\nOffering: {segment}\nProduct and service lines: {'; '.join(lines[:8])}"
        try:
            raw = self._complete(self._settings.llm_model_small, system, user, 1200)
            data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def check_competitors(self, segment: str, candidates: list[dict]) -> dict:
        """For each candidate homepage text, does it sell the same kind of
        offering? Returns {domain: evidence phrase copied from that page, or
        null}. The caller keeps a candidate only if the phrase is on its page."""
        if not self.enabled or not candidates:
            return {}
        system = (
            "For each company below, decide from ITS OWN homepage text whether it sells the same kind "
            f"of offering as: '{segment}'. If yes, copy a short phrase (5 to 15 words) EXACTLY from that "
            "company's text that shows it; if no or unclear, use null. "
            'Reply with JSON only: {"<domain>": "<phrase or null>", ...}'
        )
        body = "\n\n".join(f"DOMAIN {c['domain']}\n{c.get('excerpt') or c['text'][:1500]}" for c in candidates)
        try:
            raw = self._complete(self._settings.llm_model_small, system, body, 1500)
            data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def choose_hs(self, items: list[dict]) -> dict:
        """Constrained choice: for each product, pick one six-digit code from the
        official options under its heading. Returns {product name: code}; the
        caller accepts a code only if it was one of that product's options."""
        if not self.enabled or not items:
            return {}
        system = (
            "For each product, choose the single best six-digit HS 2022 code from its list of "
            "official options, based on the product name and the evidence from the company's "
            "page. Choose only from the options given. If none fits, use null. "
            'Reply with JSON only: {"<product name>": "<code or null>", ...}'
        )
        body = "\n\n".join(
            f"PRODUCT: {it['name']}\nEVIDENCE: {it['evidence']}\nOPTIONS:\n"
            + "\n".join(f"{c} {t[:140]}" for c, t in it["options"][:60])
            for it in items)
        try:
            raw = self._complete(self._settings.llm_model_small, system, body, 800)
            data = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    # --- small model: sector classification for the reference lookup ---
    def classify_sector(self, text: str, sector_keys: list[str], name: str | None = None,
                        industry: str | None = None) -> str:
        if not self.enabled:
            return ""
        system = (
            "You map a company to exactly one sector key from a fixed list. Classify "
            "by what the company itself makes or does, not by who its customers are: "
            "a maker of packaging machines for bakeries is industrial_machinery, not "
            "food_beverage; an online supermarket with its own delivery is "
            "logistics_distribution or consumer_goods, not software_saas; a wholesale "
            "distributor of parts is logistics_distribution. Ignore cookie banners, "
            "navigation and language pickers. Reply with the single key only."
        )
        user = (f"Keys: {', '.join(sector_keys)}\n\nCompany: {name or 'unknown'}\n"
                f"Registry industry: {industry or 'unknown'}\n\nWebsite text:\n{text}")
        try:
            out = self._complete(self._settings.llm_model_small, system, user, 20)
            return out.strip().split()[0].strip(".,")
        except Exception:
            return ""

    # --- strong model: Tier-3 narrative from resolved facts only (Section 10.1) ---
    def generate_narrative(self, system: str, facts_json: str) -> str:
        if not self.enabled:
            return ""
        try:
            return self._complete(self._settings.llm_model_large, system,
                                  facts_json, 1200).strip()
        except Exception:
            return ""
