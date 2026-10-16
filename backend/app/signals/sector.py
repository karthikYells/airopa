"""Sector classification — maps a company to an India-reference sector key.

Claude decides when configured (name + registry industry + site text); otherwise
deterministic keyword scoring over the company's own homepage/product text and
its Wikidata industry label. The result keys the India reference lookup
(Section 6.2); the keyword path is fully deterministic.
"""
from __future__ import annotations

_KEYWORDS: dict[str, list[str]] = {
    "automotive_components": ["automotive", "vehicle", "car ", "powertrain",
        "drivetrain", "chassis", "tier 1 supplier", "oem supplier", "mobility"],
    "industrial_machinery": ["machinery", "machine tool", "machine building",
        "capital equipment", "industrial equipment", "plant engineering", "mechanical engineering"],
    "precision_components": ["precision", "components", "fasteners", "fittings",
        "bearings", "seals", "machined parts", "tooling", "stamping", "forging"],
    "electronics_hardware": ["electronics", "semiconductor", "pcb", "sensors",
        "embedded", "hardware", "circuit", "chip", "microcontroller"],
    "medical_devices": ["medical device", "medical technology", "medtech",
        "diagnostics", "surgical", "implant", "healthcare technology", "in vitro"],
    "pharma_chemicals": ["pharmaceutical", "pharma", "chemical", "specialty chemical",
        "biotech", "life sciences", "api ", "coatings", "polymers", "formulation"],
    "software_saas": ["software", "saas", "platform", "cloud application",
        "app ", "developer", "api platform", "digital product"],
    "industrial_automation": ["automation", "robotics", "plc", "scada",
        "control systems", "motion control", "industrial software", "mes "],
    "building_construction": ["construction", "building", "architecture",
        "engineering consultancy", "real estate", "infrastructure", "bim",
        "facade", "hvac", "building services"],
    "logistics_distribution": ["logistics", "distribution", "supply chain",
        "freight", "warehousing", "wholesale", "fulfilment", "transport"],
    "consumer_goods": ["consumer goods", "fmcg", "household", "personal care",
        "appliances", "furniture", "retail brand", "cosmetics"],
    "energy_utilities": ["energy", "utility", "utilities", "power generation",
        "renewable", "solar", "wind", "grid", "oil and gas", "hydro"],
    "financial_services": ["bank", "insurance", "financial services", "asset management",
        "fintech", "payments", "lending", "wealth management"],
    "professional_services": ["consulting", "advisory", "professional services",
        "audit", "legal services", "engineering services", "outsourcing"],
    "food_beverage": ["food", "beverage", "dairy", "brewery", "nutrition",
        "ingredients", "bakery", "confectionery"],
    "aerospace_defence": ["aerospace", "defence", "defense", "aviation",
        "avionics", "space ", "satellite", "military"],
    "textiles": ["textile", "apparel", "garment", "fabric", "clothing",
        "fashion", "yarn", "footwear"],
}


def classify_sector(text: str, wikidata_industry: str | None = None,
                    llm=None, name: str | None = None) -> tuple[str | None, float, str]:
    """Returns (sector_key | None, confidence, method).

    With a model configured it decides first: keyword counts are fooled by
    customer words ('food' on a food-machinery maker's site, 'app' on an online
    grocer's). Keyword scoring is the deterministic fallback.
    """
    if llm is not None and llm.enabled and (text or "").strip():
        key = llm.classify_sector(text[:3000], list(_KEYWORDS.keys()),
                                  name=name, industry=wikidata_industry)
        if key in _KEYWORDS:
            return key, 0.75, "model"

    blob = (text or "").lower()
    if wikidata_industry:
        blob += " " + wikidata_industry.lower() * 3  # weight the structured hint

    scores: dict[str, int] = {}
    for key, words in _KEYWORDS.items():
        hits = sum(blob.count(w) for w in words)
        if hits:
            scores[key] = hits

    if scores:
        best = max(scores, key=scores.get)
        total = sum(scores.values())
        conf = min(0.9, 0.4 + scores[best] / max(total, 1) * 0.5)
        if scores[best] >= 2:
            return best, round(conf, 2), "keyword"

    if scores:  # weak keyword hit, better than nothing
        best = max(scores, key=scores.get)
        return best, 0.4, "keyword_weak"
    return None, 0.0, "unresolved"
