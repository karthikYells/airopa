"""Sends the snapshot PDF (Section 9.5). Provider is configuration:
  none    -> nothing is sent; the caller queues the request for a person
  smtp    -> any SMTP server with STARTTLS (e.g. Microsoft 365 for connect@airopa.co)
  resend  -> Resend HTTP API
Returns (sent, detail). Never raises: a failed send is recorded on the lead.
"""
from __future__ import annotations

import base64
import smtplib
from email.message import EmailMessage

import httpx

from app.config import Settings


def configured(settings: Settings) -> bool:
    p = settings.mail_provider.lower()
    if p == "smtp":
        return bool(settings.smtp_host and settings.smtp_user and settings.smtp_password)
    if p == "resend":
        return bool(settings.resend_api_key)
    return False


def send(settings: Settings, to: str, subject: str, text: str, html: str,
         pdf: bytes, filename: str, bcc: str | None = None) -> tuple[bool, str]:
    if not configured(settings):
        return False, "mail provider not configured"
    try:
        if settings.mail_provider.lower() == "smtp":
            msg = EmailMessage()
            msg["From"], msg["To"], msg["Subject"] = settings.mail_from, to, subject
            msg.set_content(text)
            msg.add_alternative(html, subtype="html")
            msg.add_attachment(pdf, maintype="application", subtype="pdf", filename=filename)
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=30) as s:
                s.starttls()
                s.login(settings.smtp_user, settings.smtp_password)
                s.send_message(msg, to_addrs=[to] + ([bcc] if bcc else []))
            return True, "sent via smtp"
        r = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={"from": settings.mail_from, "to": [to], "bcc": [bcc] if bcc else [],
                  "subject": subject, "text": text, "html": html,
                  "attachments": [{"filename": filename,
                                   "content": base64.b64encode(pdf).decode()}]},
            timeout=30)
        if r.status_code >= 400:
            return False, f"resend error {r.status_code}: {r.text[:200]}"
        return True, "sent via resend"
    except Exception as e:  # recorded on the lead, never shown to the visitor
        return False, f"{type(e).__name__}: {str(e)[:200]}"
