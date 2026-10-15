"""Abuse and misuse controls (Section 9.7).

Everything the public surface shows comes from public sources and names no
individuals, which is what makes accepting any input acceptable. Still:
validate that the input is a company domain, reject free email providers and
personal sites before spending anything, and keep a blocklist (competitors,
clients, sanctioned) that returns EXCLUDED.
"""
from __future__ import annotations

import re
from urllib.parse import urlparse

_FREE_EMAIL = {
    "gmail.com", "googlemail.com", "yahoo.com", "ymail.com", "outlook.com",
    "hotmail.com", "live.com", "icloud.com", "me.com", "proton.me",
    "protonmail.com", "aol.com", "gmx.com", "gmx.de", "web.de", "mail.com",
    "zoho.com", "yandex.com",
}

# Illustrative blocklist. In production this is maintained by Airopa and loaded
# from configuration (competitors, current clients, sanctioned entities).
_BLOCKLIST = {
    "adesso.de", "datagroup.de", "conet.de", "akquinet.de", "arvato-systems.de",
}

_DOMAIN_RE = re.compile(r"^(?=.{1,253}$)([a-z0-9-]{1,63}\.)+[a-z]{2,}$")


def normalise_host(raw: str) -> str:
    raw = (raw or "").strip().lower()
    if "@" in raw:  # someone pasted an email
        raw = raw.split("@", 1)[1]
    if "://" not in raw:
        raw = "https://" + raw
    host = urlparse(raw).netloc or urlparse(raw).path
    return host[4:] if host.startswith("www.") else host


def validate(raw: str) -> tuple[bool, str, str]:
    """Returns (ok, host, reason). ok=False means do not run the pipeline."""
    host = normalise_host(raw)
    if not host or not _DOMAIN_RE.match(host):
        return False, host, "not_a_company_domain"
    base = ".".join(host.split(".")[-2:])
    if host in _FREE_EMAIL or base in _FREE_EMAIL:
        return False, host, "free_email_provider"
    return True, host, "ok"


def is_blocklisted(host: str) -> bool:
    base = ".".join(host.split(".")[-2:])
    return host in _BLOCKLIST or base in _BLOCKLIST
