"""Email that carries the Europe Market Assessment PDF: branded like the India
engine's, with the short version and both scores in the body."""
from __future__ import annotations

from html import escape


def build_email(payload: dict, name: str, link: str) -> tuple[str, str, str]:
    c = payload.get("company") or {}
    company = c.get("name") or c.get("input") or "your company"
    s = payload.get("summary") or {}
    m, r = payload.get("market") or {}, payload.get("readiness") or {}
    subject = f"Your Europe Market Assessment: {company}"
    lines = [f"Dear {name},", "",
             f"Attached is the Europe Market Assessment for {company}."]
    if s:
        lines += ["", s.get("headline", ""), s.get("body", "")]
    if m and r:
        lines += ["", f"Europe Market Opportunity: {m.get('score')} / 100 ({m.get('band')})",
                  f"Europe Readiness: {r.get('score')} / 100 ({r.get('band')})"]
    lines += ["", "The PDF has the reasoning behind every score, where to start in Europe, and what the "
              "full business case adds. Reply to this email to talk to Airopa Global about selling in Europe.",
              "", f"Open your assessment: {link}", "", "Access India Netherlands, with founding partner Airopa Global"]
    text = "\n".join(lines)
    font = "font-family:Segoe UI,Helvetica,Arial,sans-serif;"
    scores = "" if not (m and r) else (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin:18px 0;"><tr>'
        f'<td width="50%" style="{font}padding:14px;border:1px solid #E2E1DD;"><div style="font-size:12px;color:#5C5E66;">'
        f'Europe Market Opportunity</div><div style="font-size:28px;font-weight:700;color:#E8791C;">{m.get("score")}'
        f'<span style="font-size:13px;color:#5C5E66;"> / 100 · {escape(str(m.get("band")))}</span></div></td>'
        f'<td width="50%" style="{font}padding:14px;border:1px solid #E2E1DD;"><div style="font-size:12px;color:#5C5E66;">'
        f'Europe Readiness</div><div style="font-size:28px;font-weight:700;color:#1E9E6A;">{r.get("score")}'
        f'<span style="font-size:13px;color:#5C5E66;"> / 100 · {escape(str(r.get("band")))}</span></div></td></tr></table>')
    short = "" if not s else (
        f'<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#18191E;margin-top:16px;">'
        f'<tr><td style="{font}padding:18px 20px;color:#F3F2EF;">'
        f'<div style="font-size:11px;letter-spacing:.12em;text-transform:uppercase;color:#E8791C;">The short version</div>'
        f'<div style="font-size:19px;font-weight:700;margin-top:6px;">{escape(s.get("headline", ""))}</div>'
        f'<div style="font-size:14px;color:#C9CAD0;margin-top:8px;line-height:1.5;">{escape(s.get("body", ""))}</div>'
        f'</td></tr></table>')
    html = f"""<!doctype html><html><body style="margin:0;background:#F6F6F4;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F6F6F4;"><tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#FFFFFF;">
<tr><td style="background:#18191E;padding:22px 28px;{font}">
<div style="font-size:18px;font-weight:700;color:#F3F2EF;">Access India <span style="color:#E8791C;">Netherlands</span></div>
<div style="font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:#E8791C;margin-top:14px;">Engines · Europe Market Assessment</div>
<div style="font-size:24px;font-weight:700;color:#F3F2EF;margin-top:6px;">{escape(company)}</div></td></tr>
<tr><td style="padding:24px 28px;{font}color:#1A1B20;font-size:15px;line-height:1.55;">
<p style="margin:0 0 12px;">Dear {escape(name)},</p>
<p style="margin:0 0 12px;">Attached is the Europe Market Assessment for {escape(company)}: whether Europe is a market for what you sell, how ready you are to win it, and where to start.</p>
{short}{scores}
<p style="margin:0 0 12px;">The PDF has the reasoning behind every score, where to start in Europe, and what the full business case adds. Simply reply to this email to talk to Airopa Global about selling in Europe.</p>
<p style="margin:18px 0 0;"><a href="{escape(link)}" style="display:inline-block;background:#E8791C;color:#16120D;text-decoration:none;font-weight:600;padding:12px 22px;border-radius:999px;">Open your assessment</a></p>
</td></tr>
<tr><td style="background:#18191E;padding:16px 28px;{font}font-size:12px;color:#A3A5AD;">Sent on behalf of Access India Netherlands by our founding partner Airopa Global, Eindhoven.</td></tr>
</table></td></tr></table></body></html>"""
    return subject, text, html
