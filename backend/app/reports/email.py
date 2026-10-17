"""The report email, styled like the GCC Business Case email on accessindia.nl
(send-report.mjs), so both engines' emails read as one family. Built from the
stored public payload only, with visitor input escaped."""
from __future__ import annotations

from html import escape

C = {"fg": "#1A1B20", "muted": "#5C5E66", "line": "#E2E1DD", "accent": "#E8791C",
     "ink": "#B85A0B", "band": "#18191E", "soft": "#FBEBDC"}
FONT = "font-family:Segoe UI,Helvetica,Arial,sans-serif;"


def build_email(payload: dict, name: str, role: str, link: str) -> tuple[str, str, str]:
    """Returns (subject, text, html)."""
    c = payload.get("company") or {}
    company = c.get("name") or c.get("input") or "your company"
    status = payload.get("india_status") or ""
    evidence = payload.get("own_evidence") or []
    first = [b.replace("**", "") for p in evidence for b in p.get("bullets", [])][:3]

    subject = f"Your India Opportunity Snapshot: {company}"
    text = (f"Dear {name},\n\nAttached is the India Opportunity Snapshot for {company}, "
            f"built from public sources. {status}\n\nReopen it any time: {link}\n\n"
            "Want the full business case, built against your own estate and named peer "
            "group in two weeks at no obligation? Simply reply to this email.\n\n"
            "Access India Netherlands, with founding partner Airopa Global")

    bullets = "".join(f'<li style="margin:3px 0;">{escape(b)}</li>' for b in first)
    html = f"""<!doctype html><html><body style="margin:0;background:#F6F6F4;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#F6F6F4;"><tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="640" cellpadding="0" cellspacing="0" style="max-width:640px;width:100%;background:#FFFFFF;">
  <tr><td style="background:{C['band']};padding:22px 28px;{FONT}">
    <div style="font-size:18px;font-weight:700;color:#F3F2EF;">Access India <span style="color:{C['accent']};">Netherlands</span></div>
    <div style="font-size:12px;letter-spacing:.1em;text-transform:uppercase;color:{C['accent']};margin-top:14px;">Engines · India Opportunity Snapshot</div>
    <div style="font-size:24px;font-weight:700;color:#F3F2EF;margin-top:6px;">{escape(company)}</div>
  </td></tr>
  <tr><td style="padding:24px 28px;{FONT}color:{C['fg']};font-size:15px;line-height:1.55;">
    <p style="margin:0 0 12px;">Dear {escape(name)},</p>
    <p style="margin:0 0 12px;">Thank you for using the India Opportunity Snapshot. Here is what public sources show for {escape(company)}.</p>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:14px;border-left:4px solid {C['accent']};background:{C['soft']};"><tr><td style="padding:16px 18px;{FONT}">
      <div style="font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:{C['ink']};">Your India status</div>
      <div style="font-size:16px;font-weight:600;color:{C['fg']};margin-top:4px;">{escape(status)}</div>
      {f'<ul style="margin:10px 0 0;padding-left:18px;font-size:14px;color:{C["fg"]};">{bullets}</ul>' if bullets else ''}
    </td></tr></table>
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top:22px;border:1px solid {C['line']};"><tr><td style="padding:14px 16px;{FONT}font-size:14px;color:{C['fg']};">
      <strong>Your snapshot is attached as a PDF</strong>, ready to forward to your board, together with what the full business case would add.
    </td></tr></table>
    <table role="presentation" cellpadding="0" cellspacing="0" style="margin-top:26px;"><tr>
      <td style="background:{C['accent']};border-radius:999px;"><a href="{escape(link)}" style="{FONT}display:inline-block;padding:12px 22px;font-size:15px;font-weight:600;color:#16120D;text-decoration:none;">Open your snapshot</a></td>
    </tr></table>
    <p style="margin:26px 0 0;padding-top:18px;border-top:1px solid {C['line']};">Want the full business case? Our GCC partner, Airopa Global, builds it against your own estate, salary bands and named peer group in two weeks, at no obligation. Simply reply to this email.</p>
    <p style="margin:18px 0 0;font-size:12.5px;color:{C['muted']};">Compiled from public sources. Where something could not be verified it was left out rather than estimated. Nothing here is a statement about the conduct of any third party.</p>
  </td></tr>
  <tr><td style="background:{C['band']};padding:16px 28px;{FONT}font-size:12px;color:#A3A5AD;">
    You requested this report at accessindia.nl{f' ({escape(role)})' if role else ''}. Sent on behalf of Access India Netherlands by our founding partner Airopa Global, Eindhoven.
  </td></tr>
</table></td></tr></table></body></html>"""
    return subject, text, html
