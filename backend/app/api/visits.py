"""Visit log for both engines: who checked which company, from where.

Recorded per check and per report request: time, engine, the company checked,
whether it came from cache, the page that sent the visitor, browser, and the
visitor's network: shortened IP, a one-way code to spot repeat visitors, and
the network's owner and country from the internet registries (RDAP) plus its
reverse-DNS name. On a corporate network the owner is usually the company; at
home or on mobile it is the internet provider. No names or email addresses are
stored (for a report request only the email's domain).

The full IP is stored only when `visit_full_ip` is on, which must not happen
before the privacy notice says so. Visits are kept `visit_retention_days`.
The lookup runs after the response, so a visitor never waits for it.
"""
from __future__ import annotations

import hashlib
import ipaddress
import secrets
import socket
import threading
import time
from datetime import datetime, timezone

import httpx
from fastapi import Request

from app.api.ratelimit import client_ip
from app.config import get_settings
from app.data import kv

COLLECTION = "visits"


def _prefix(ip: str) -> str:
    """192.0.2.0/24 or 2001:db8:1234::/48: the network, not the device."""
    try:
        addr = ipaddress.ip_address(ip)
        net = ipaddress.ip_network(f"{ip}/{24 if addr.version == 4 else 48}", strict=False)
        return str(net)
    except ValueError:
        return ""


def _code(ip: str) -> str:
    salt = get_settings().snapshot_signing_key or "airopa-visits"
    return hashlib.sha256(f"{salt}:{ip}".encode()).hexdigest()[:16]


def lookup_network(ip: str) -> dict:
    """Owner and country of the IP's network (RDAP, free) and its reverse-DNS name."""
    out: dict = {}
    try:
        if ipaddress.ip_address(ip).is_private:
            return {"network_owner": "private network"}
    except ValueError:
        return out
    try:
        r = httpx.get(f"https://rdap.org/ip/{ip}", timeout=8, follow_redirects=True)
        d = r.json() if r.status_code == 200 else {}
        out["network_name"] = d.get("name")
        out["country"] = d.get("country")
        for e in d.get("entities") or []:
            fn = next((x[3] for x in (e.get("vcardArray") or [None, []])[1] if x and x[0] == "fn"), None)
            if fn and set(e.get("roles") or []) & {"registrant", "administrative"}:
                out["network_owner"] = fn
                break
    except Exception:
        pass
    try:
        socket.setdefaulttimeout(4)
        out["hostname"] = socket.gethostbyaddr(ip)[0]
    except Exception:
        pass
    return out


def _enrich(doc_id: str, doc: dict, ip: str) -> None:
    doc.update(lookup_network(ip))
    kv.put(COLLECTION, doc_id, doc)


def record(request: Request, *, engine: str, event: str, company: str | None,
           run_id: str | None = None, mode: str | None = None, cached: bool = False,
           email_domain: str | None = None) -> None:
    """Log one visit. Never raises; the registry lookup runs in the background."""
    try:
        s = get_settings()
        ip = client_ip(request)
        now = datetime.now(timezone.utc)
        doc_id = f"{now.strftime('%Y%m%dT%H%M%S')}-{secrets.token_hex(3)}"
        doc = {
            "at": now.isoformat(timespec="seconds"), "ts": time.time(),
            "engine": engine, "event": event, "company_checked": company,
            "run_id": run_id, "mode": mode, "cached": cached, "email_domain": email_domain,
            "ip_prefix": _prefix(ip), "visitor": _code(ip),
            "ip": ip if s.visit_full_ip else None,
            "referer": (request.headers.get("referer") or "")[:300] or None,
            "origin": request.headers.get("origin"),
            "user_agent": (request.headers.get("user-agent") or "")[:200] or None,
            "language": (request.headers.get("accept-language") or "")[:40] or None,
        }
        kv.put(COLLECTION, doc_id, doc)
        threading.Thread(target=_enrich, args=(doc_id, dict(doc), ip), daemon=True).start()
    except Exception:
        pass


def recent(limit: int = 500) -> list[dict]:
    ids = sorted(kv.keys(COLLECTION, limit=5000), reverse=True)[:limit]
    return [{**d, "_id": i} for i, d in ((i, kv.get(COLLECTION, i)) for i in ids) if d]


def fill_missing(rows: list[dict], most: int = 40) -> None:
    """Look up network and country for visits that have none yet. Cloud Run
    throttles the CPU once a response is sent, so the background lookup in
    `record` often never finishes; the dashboard completes it on opening.
    Lookups are cached per address, so each address is asked once."""
    todo = [r for r in rows if "country" not in r and (r.get("ip") or r.get("ip_prefix"))][:most]
    if not todo:
        return

    def addr(r: dict) -> str:
        return r.get("ip") or str(ipaddress.ip_network(r["ip_prefix"], strict=False).network_address)

    def one(ip: str) -> dict:
        hit = kv.get("ip_networks", ip)
        if hit is None:
            hit = lookup_network(ip)
            hit.setdefault("country", None)          # mark as looked up, even when nothing came back
            kv.put("ip_networks", ip, hit)
        return hit

    from concurrent.futures import ThreadPoolExecutor
    ips = sorted({addr(r) for r in todo})
    with ThreadPoolExecutor(max_workers=8) as pool:
        found = dict(zip(ips, pool.map(one, ips)))
    for r in todo:
        r.update(found[addr(r)])
        kv.put(COLLECTION, r["_id"], {k: v for k, v in r.items() if k != "_id"})


def prune() -> int:
    """Delete visits older than the retention period. Returns how many."""
    cutoff = time.time() - get_settings().visit_retention_days * 86400
    gone = 0
    for i in kv.keys(COLLECTION, limit=20000):
        d = kv.get(COLLECTION, i)
        if d and d.get("ts", 0) < cutoff:
            kv.delete(COLLECTION, i)
            gone += 1
    return gone
