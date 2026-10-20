"""Private visit dashboard: GET /api/internal/visits?key=<dashboard_key>.

Off (404) unless `dashboard_key` is set, and 404 for a wrong key, so the
page cannot be found by guessing. Shows the last visits to both engines.
"""
from __future__ import annotations

import hmac
from collections import Counter
from datetime import datetime, timedelta, timezone
from html import escape

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse

from app.api import visits
from app.config import get_settings

router = APIRouter()


def _authorised(key: str) -> None:
    want = get_settings().dashboard_key
    if not want or not hmac.compare_digest(key or "", want):
        raise HTTPException(status_code=404, detail="not found")


def _who(v: dict) -> str:
    parts = [v.get("network_owner"), v.get("network_name"), v.get("hostname")]
    return " · ".join(dict.fromkeys(x for x in parts if x))


@router.get("/internal/visits", response_class=HTMLResponse)
def dashboard(key: str = "") -> HTMLResponse:
    _authorised(key)
    rows = visits.recent(500)
    visits.fill_missing(rows)
    now = datetime.now(timezone.utc)
    week = [r for r in rows if datetime.fromisoformat(r["at"]) >= now - timedelta(days=7)]
    checks = [r for r in rows if r.get("event") == "check"]
    reports = [r for r in rows if r.get("event") == "report"]
    top_companies = Counter(r.get("company_checked") for r in checks if r.get("company_checked")).most_common(10)
    top_networks = Counter(r.get("network_name") or r.get("network_owner") for r in rows
                           if r.get("network_name") or r.get("network_owner")).most_common(10)
    countries = Counter(r.get("country") for r in rows if r.get("country")).most_common(10)

    def li(items):
        return "".join(f"<li><b>{escape(str(k))}</b> <span>{n}</span></li>" for k, n in items) or "<li>None yet</li>"

    table = "".join(
        f"<tr><td>{escape(r['at'][:16].replace('T', ' '))}</td><td>{escape(r.get('engine') or '')}</td>"
        f"<td>{escape(r.get('event') or '')}{' (cached)' if r.get('cached') else ''}</td>"
        f"<td>{escape(r.get('company_checked') or '')}</td><td>{escape(r.get('email_domain') or '')}</td>"
        f"<td>{escape(_who(r))}</td><td>{escape(r.get('country') or '')}</td>"
        f"<td class='mono'>{escape(r.get('ip') or r.get('ip_prefix') or '')}</td>"
        f"<td class='mono'>{escape(r.get('visitor') or '')}</td>"
        f"<td>{escape((r.get('referer') or '')[:60])}</td><td>{escape((r.get('user_agent') or '')[:40])}</td></tr>"
        for r in rows)
    html = f"""<!doctype html><html><head><meta charset="utf-8"><meta name="robots" content="noindex">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Engine visits</title>
<style>
body{{font:14px/1.45 "Segoe UI",system-ui,sans-serif;margin:0;background:#F7F6F3;color:#18191E}}
header{{background:#18191E;color:#F3F2EF;padding:20px max(16px,4vw)}} h1{{margin:0;font-size:22px}}
main{{padding:20px max(16px,4vw);display:grid;gap:20px}} .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:14px}}
.card{{background:#fff;border:1px solid #E3E1DB;border-radius:10px;padding:14px}} .card h2{{margin:0 0 8px;font-size:14px;color:#5C5E66}}
.big{{font-size:30px;font-weight:700}} ul{{margin:0;padding-left:18px}} li span{{color:#5C5E66}}
.wrap{{overflow-x:auto;background:#fff;border:1px solid #E3E1DB;border-radius:10px}}
table{{border-collapse:collapse;width:100%;font-size:13px}} th,td{{text-align:left;padding:7px 10px;border-bottom:1px solid #E3E1DB;white-space:nowrap}}
th{{background:#F7F6F3;font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:#5C5E66}} .mono{{font-family:Consolas,monospace}}
</style></head><body><header><h1>Engine visits</h1><div>India Market Assessment and Europe Market Assessment · last {len(rows)} events</div></header>
<main><div class="cards">
<div class="card"><h2>Checks, last 7 days</h2><div class="big">{sum(1 for r in week if r.get('event') == 'check')}</div></div>
<div class="card"><h2>Report requests, last 7 days</h2><div class="big">{sum(1 for r in week if r.get('event') == 'report')}</div></div>
<div class="card"><h2>Distinct visitors (all shown)</h2><div class="big">{len({r.get('visitor') for r in rows})}</div></div>
<div class="card"><h2>Report requests (all shown)</h2><div class="big">{len(reports)}</div></div>
</div><div class="cards">
<div class="card"><h2>Companies checked</h2><ul>{li(top_companies)}</ul></div>
<div class="card"><h2>Visitor networks</h2><ul>{li(top_networks)}</ul></div>
<div class="card"><h2>Countries</h2><ul>{li(countries)}</ul></div>
</div>
<div class="wrap"><table><tr><th>Time (UTC)</th><th>Engine</th><th>Event</th><th>Company checked</th><th>Email domain</th>
<th>Visitor network</th><th>Country</th><th>IP</th><th>Visitor code</th><th>Came from</th><th>Browser</th></tr>{table}</table></div>
<p style="color:#5C5E66;font-size:12px">Network owner: the company on corporate networks, the internet provider at home or on mobile.
IP shown in full only once the privacy notice covers it; until then the network (last part removed). Kept {get_settings().visit_retention_days} days.</p>
</main></body></html>"""
    return HTMLResponse(html)
