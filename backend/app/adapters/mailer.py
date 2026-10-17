"""Sends the snapshot PDF (Section 9.5). Provider is configuration:
  graph   -> Microsoft Graph sendMail from connect@airopa.co, exactly as the
             accessindia.nl send-report function does (same Entra app:
             MS_TENANT_ID, MS_CLIENT_ID, MS_CLIENT_SECRET with Mail.Send)
  smtp    -> any SMTP server with STARTTLS
  resend  -> Resend HTTP API
  none    -> nothing is sent; the caller queues the request for a person
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
    if p == "graph":
        return bool(settings.ms_tenant_id and settings.ms_client_id and settings.ms_client_secret)
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
        if settings.mail_provider.lower() == "graph":
            return _send_graph(settings, to, subject, html, pdf, filename, bcc)
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


def _send_graph(settings: Settings, to: str, subject: str, html: str, pdf: bytes,
                filename: str, bcc: str | None) -> tuple[bool, str]:
    """Client-credentials token, then /users/{sender}/sendMail (202 = accepted)."""
    tok = httpx.post(
        f"https://login.microsoftonline.com/{settings.ms_tenant_id}/oauth2/v2.0/token",
        data={"client_id": settings.ms_client_id, "client_secret": settings.ms_client_secret,
              "scope": "https://graph.microsoft.com/.default", "grant_type": "client_credentials"},
        timeout=30)
    if tok.status_code != 200:
        return False, f"graph token {tok.status_code}"
    message = {
        "subject": subject,
        "body": {"contentType": "HTML", "content": html},
        "from": {"emailAddress": {"address": settings.report_sender,
                                  "name": settings.report_sender_name}},
        "toRecipients": [{"emailAddress": {"address": to}}],
        "attachments": [{"@odata.type": "#microsoft.graph.fileAttachment", "name": filename,
                         "contentType": "application/pdf",
                         "contentBytes": base64.b64encode(pdf).decode()}],
    }
    if bcc:
        message["bccRecipients"] = [{"emailAddress": {"address": bcc}}]
    r = httpx.post(
        f"https://graph.microsoft.com/v1.0/users/{settings.report_sender}/sendMail",
        headers={"Authorization": f"Bearer {tok.json()['access_token']}"},
        json={"message": message, "saveToSentItems": True}, timeout=30)
    if r.status_code != 202:
        return False, f"graph sendMail {r.status_code}: {r.text[:200]}"
    return True, "sent via microsoft graph"
