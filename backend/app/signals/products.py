"""What an Indian company sells, as HS codes and service types (PROD cluster).

Europe Market Assessment, increment 2. Claude proposes products (with HS
codes) and services (with Eurostat service types) from the company's own
pages; the code keeps an item only if its evidence phrase appears on a page
we fetched. The result decides goods or services, the v1 sector, and which
product codes the trade lookups use. HS codes are the model's mapping and are
shown for confirmation in the internal view, never as a fact on the public page.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.reference import europe_reference as ref
from app.reference import hs_codes

_SERVICE_CODES = {"SI", "SJ", "SJ3"}
_MIN_CONFIDENCE = 0.5


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", (s or "").lower()).strip()


@dataclass
class Offering:
    kind: str                               # goods | services | both
    products: list[dict] = field(default_factory=list)   # verified, with HS and v1 group
    services: list[dict] = field(default_factory=list)   # verified, with service code
    sector: str | None = None               # v1 sector key, or None if outside v1
    dropped: int = 0                        # items whose evidence was not on the page
    segment: str | None = None              # what they sell, in a phrase (model, shown as such)
    buyers: list[str] = field(default_factory=list)   # NACE codes of the industries that buy from them


def verify_offering(raw: dict, pages: list[dict]) -> Offering | None:
    """Keep only items whose evidence phrase is on one of our pages; re-point
    each item to the page that holds it. None if nothing survives."""
    texts = [(p["url"], _norm(p["text"])) for p in pages]

    def found(evidence: str) -> str | None:
        ev = _norm(evidence)
        if len(ev) < 4:
            return None
        return next((u for u, t in texts if ev in t), None)

    products, services, dropped = [], [], 0
    for it in (raw.get("products") or [])[:6]:
        if not isinstance(it, dict):
            continue
        url = found(it.get("evidence", ""))
        hs = re.sub(r"\D", "", str(it.get("hs", "")))[:6]
        try:
            conf = float(it.get("confidence", 0))
        except (TypeError, ValueError):
            conf = 0.0
        # The heading must exist in the official list; the six digits are
        # settled later by a choice among that heading's official codes.
        if (not url or len(hs) < 4 or not (1 <= int(hs[:2]) <= 97)
                or not hs_codes.exists(hs[:4]) or conf < _MIN_CONFIDENCE):
            dropped += 1
            continue
        if not hs_codes.exists(hs):
            hs = hs[:4]
        g = ref.group_for_hs(hs)
        products.append({"name": str(it.get("name", ""))[:80], "evidence": it["evidence"][:160],
                         "url": url, "hs": hs, "hs_label": str(it.get("hs_label", ""))[:120],
                         "confidence": round(conf, 2), "group": g["id"] if g else None,
                         "sector": g["sector"] if g else None})
    for it in (raw.get("services") or [])[:4]:
        if not isinstance(it, dict):
            continue
        url = found(it.get("evidence", ""))
        code = str(it.get("code", "")).upper()
        if not url or code not in _SERVICE_CODES:
            dropped += 1
            continue
        services.append({"name": str(it.get("name", ""))[:80], "evidence": it["evidence"][:160],
                         "url": url, "code": code})
    if not products and not services:
        return None
    kind = "both" if products and services else "goods" if products else "services"
    from app.reference.nace import codes as nace_codes
    valid = nace_codes()
    # A buyer industry counts only if the page names those buyers (checked like products).
    buyers = []
    for b in raw.get("buyers") or []:
        if isinstance(b, dict) and b.get("code") in valid and found(str(b.get("evidence", ""))) \
                and b["code"] not in buyers:
            buyers.append(b["code"])
    buyers = buyers[:3]
    seg = raw.get("segment")
    return Offering(kind=kind, products=products, services=services,
                    sector=_sector(products, services), dropped=dropped,
                    segment=str(seg)[:80] if isinstance(seg, str) and seg.strip() else None,
                    buyers=buyers)


def _sector(products: list[dict], services: list[dict]) -> str | None:
    """The v1 sector: the one most of their v1 products fall in; services when
    they sell no v1 goods. None when what they sell is outside v1."""
    counts: dict[str, int] = {}
    for p in products:
        if p["sector"]:
            counts[p["sector"]] = counts.get(p["sector"], 0) + 1
    if counts:
        return max(counts, key=counts.get)
    return "it_services" if services else None


def refine_hs(off: Offering, llm) -> Offering:
    """Replace each product's model-made code with one chosen from the official
    six-digit codes under its heading. A choice outside the options is ignored
    and the product keeps its heading only (never an invented code)."""
    items = []
    for p in off.products:
        opts = hs_codes.children(p["hs"][:4])
        if opts:
            items.append({"name": p["name"], "evidence": p["evidence"], "options": opts})
    picks = llm.choose_hs(items) if items and llm is not None else {}
    for p in off.products:
        allowed = {c for c, _ in hs_codes.children(p["hs"][:4])}
        pick = picks.get(p["name"])
        p["hs"] = pick if pick in allowed else p["hs"][:4]
        p["hs_label"] = hs_codes.label(p["hs"]) or p["hs_label"]
        p["hs_level"] = len(p["hs"])
        g = ref.group_for_hs(p["hs"])
        p["group"], p["sector"] = (g["id"], g["sector"]) if g else (None, None)
    # One product per code: brand names of the same product (two insecticide
    # brands) are one market, not two.
    seen, uniq = set(), []
    for p in off.products:
        if p["hs"] not in seen:
            seen.add(p["hs"])
            uniq.append(p)
    off.products = uniq
    off.sector = _sector(off.products, off.services)
    return off


def map_offering(company: str, scrape, llm) -> Offering | None:
    """The company's offering from its homepage and product pages."""
    if llm is None or not getattr(llm, "enabled", False):
        return None
    home = scrape.pages_fetched[0] if scrape.pages_fetched else f"https://{scrape.resolved_host}"
    pages = [{"url": home, "text": scrape.homepage_text}] + list(scrape.product_pages)
    off = verify_offering(llm.map_offering(company, pages), pages)
    return refine_hs(off, llm) if off and off.products else off
