"""Company-registry adapters (Tier 0, Section 2.1).

Resolving a domain to a legal entity and registry identifier (KVK, Handelsregister/
Bundesanzeiger, BCE/KBO, Companies House, and MCA for India) is the highest-risk
component in the system — every downstream signal is wrong if the entity is wrong.

v1 ships a STUB: it performs a light host-based guess so the pipeline runs end to
end, but it does NOT invent a registry identifier. A record it cannot resolve to a
real identifier is marked RESOLUTION_FAILED and routed to manual review (never
scored), exactly as Section 2.1 mandates. Swap `resolve()` for a real registry
integration without touching the pipeline.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from urllib.parse import urlparse


@dataclass
class ResolvedEntity:
    resolved: bool
    legal_name: str | None = None
    registry_id: str | None = None
    jurisdiction: str | None = None
    ultimate_parent: str | None = None
    subsidiaries: list[dict] = field(default_factory=list)
    alternate_domains: list[str] = field(default_factory=list)
    country: str | None = None
    note: str = ""


# Domain TLD -> (jurisdiction, country label) for a best-effort country guess.
_TLD_COUNTRY = {
    "nl": ("Netherlands", "NL"), "de": ("Germany", "DE"),
    "be": ("Belgium", "BE"), "co.uk": ("United Kingdom", "UK"),
    "uk": ("United Kingdom", "UK"), "fr": ("France", "FR"),
    "se": ("Sweden", "Nordics"), "no": ("Norway", "Nordics"),
    "dk": ("Denmark", "Nordics"), "fi": ("Finland", "Nordics"),
}


def _country_from_host(host: str) -> tuple[str | None, str | None]:
    parts = host.lower().split(".")
    if len(parts) >= 2 and ".".join(parts[-2:]) in _TLD_COUNTRY:
        j, c = _TLD_COUNTRY[".".join(parts[-2:])]
        return j, c
    if parts and parts[-1] in _TLD_COUNTRY:
        j, c = _TLD_COUNTRY[parts[-1]]
        return j, c
    return None, None


def resolve(input_url: str, scraped_host: str | None = None) -> ResolvedEntity:
    """STUB resolver. Returns resolved=False with no registry_id, so the record
    is treated as RESOLUTION_FAILED. A real integration fills registry_id from
    the national registry and sets resolved=True.
    """
    host = scraped_host or urlparse(
        input_url if "://" in input_url else "https://" + input_url
    ).netloc
    jurisdiction, country = _country_from_host(host or "")
    name_guess = host.split(".")[0].replace("-", " ").title() if host else None
    return ResolvedEntity(
        resolved=False,
        legal_name=name_guess,
        registry_id=None,
        jurisdiction=jurisdiction,
        country=country,
        note="STUB registry adapter: no registry identifier available. Record "
             "is RESOLUTION_FAILED pending a real registry integration "
             "(KVK / Handelsregister / KBO / Companies House / MCA).",
    )
