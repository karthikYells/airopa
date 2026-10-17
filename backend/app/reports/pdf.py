"""The emailed snapshot report (Section 9.5).

Built ONLY from the stored public payload, the exact page the visitor saw, so
the PDF can never carry more than the public surface may show (Section 9.3):
no GCC Fit, no peer, vendor or person names. Styled to accessindia.nl.
"""
from __future__ import annotations

import io
import re
from datetime import date

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

BAND = colors.HexColor("#18191E")
ACCENT = colors.HexColor("#E8791C")
ACCENT_SOFT = colors.HexColor("#FBEBDC")
FG = colors.HexColor("#1A1B20")
MUTED = colors.HexColor("#5C5E66")
LINE = colors.HexColor("#E2E1DD")
GREEN = colors.HexColor("#1E9E6A")

_S = {
    "eyebrow": ParagraphStyle("eyebrow", fontName="Helvetica-Bold", fontSize=8, leading=10,
                              textColor=ACCENT, spaceAfter=2),
    "h1": ParagraphStyle("h1", fontName="Helvetica-Bold", fontSize=22, leading=26, textColor=FG),
    "h2": ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=12.5, leading=16,
                         textColor=FG, spaceBefore=10, spaceAfter=4),
    "body": ParagraphStyle("body", fontName="Helvetica", fontSize=9.5, leading=13.5, textColor=FG),
    "muted": ParagraphStyle("muted", fontName="Helvetica", fontSize=8.5, leading=12, textColor=MUTED),
    "big": ParagraphStyle("big", fontName="Helvetica-Bold", fontSize=30, leading=32, textColor=ACCENT),
    "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=9.5, leading=13.5,
                             textColor=FG, leftIndent=10, bulletIndent=0, alignment=TA_LEFT),
}


def _esc(s: str) -> str:
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _rich(s: str) -> str:
    """**bold** markers from the payload -> reportlab <b>."""
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", _esc(s))


def _header(canvas, doc):
    w, h = A4
    canvas.saveState()
    canvas.setFillColor(BAND)
    canvas.rect(0, h - 22 * mm, w, 22 * mm, fill=1, stroke=0)
    canvas.setFillColor(colors.HexColor("#F3F2EF"))
    canvas.setFont("Helvetica-Bold", 12)
    canvas.drawString(18 * mm, h - 13 * mm, "Access India")
    canvas.setFillColor(ACCENT)
    canvas.drawString(18 * mm + canvas.stringWidth("Access India ", "Helvetica-Bold", 12),
                      h - 13 * mm, "Netherlands")
    canvas.setFillColor(colors.HexColor("#A3A5AD"))
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(w - 18 * mm, h - 11 * mm, "India Market Assessment")
    canvas.drawRightString(w - 18 * mm, h - 15.5 * mm, "with founding partner Airopa Global")
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(MUTED)
    canvas.drawString(18 * mm, 10 * mm, "accessindia.nl  ·  accessindia@airopa.co")
    canvas.drawRightString(w - 18 * mm, 10 * mm, f"Page {doc.page}")
    canvas.restoreState()


def build_pdf(payload: dict, recipient_name: str | None = None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=18 * mm, rightMargin=18 * mm,
                            topMargin=30 * mm, bottomMargin=18 * mm,
                            title="India Market Assessment", author="Access India Netherlands")
    c = payload.get("company") or {}
    story: list = []

    story.append(Paragraph("INDIA MARKET ASSESSMENT", _S["eyebrow"]))
    story.append(Paragraph(_esc(c.get("name") or c.get("input") or ""), _S["h1"]))
    facts = [c.get("sector"), c.get("location") or c.get("country"), c.get("revenue"),
             c.get("headcount"), c.get("founded")]
    story.append(Paragraph(_esc("  ·  ".join(f for f in facts if f)), _S["muted"]))
    sigs = c.get("signals") or []
    if sigs:
        story.append(Paragraph(
            "  ·  ".join(f'<font color="{"#B42318" if g["tone"] == "red" else "#1E9E6A" if g["tone"] == "green" else "#18191E"}">'
                         f'<b>{_esc(g["text"])}</b></font>' for g in sigs)
            + f'  <font color="#5C5E66">({_esc(c.get("signals_source") or "")})</font>', _S["body"]))
    prepared = f"Prepared {date.today().strftime('%d %B %Y')}"
    if recipient_name:
        prepared += f" for {_esc(recipient_name)}"
    story.append(Paragraph(prepared + f"  ·  {_esc(c.get('input') or '')}", _S["muted"]))
    story.append(Spacer(1, 8))

    def reasoned(card: dict, title: str, color, dims: list[tuple[str, str, str]]):
        hexc = "#" + color.hexval()[2:]
        head = Table([[Paragraph(f'<font color="{hexc}">{card["score"]}</font>', _S["big"]),
                       Paragraph(f'<b>{_esc(card["label"])}: {_esc(card["band"])}</b>, out of 100.<br/>'
                                 f'<font color="#5C5E66">{_esc(card.get("question", ""))}</font>',
                                 _S["body"])]],
                     colWidths=[30 * mm, None])
        head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                                  ("LINEABOVE", (0, 0), (-1, 0), 2, color),
                                  ("TOPPADDING", (0, 0), (-1, -1), 8)]))
        rows = [[Paragraph(f'<b>{_esc(n)}</b>', _S["body"]), Paragraph(f'<b>{_esc(lv)}</b>', _S["body"]),
                 Paragraph(_esc(r), _S["body"])] for n, lv, r in dims]
        table = Table(rows, colWidths=[42 * mm, 24 * mm, None])
        table.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP"),
                                   ("LINEBELOW", (0, 0), (-1, -1), 0.4, LINE),
                                   ("TOPPADDING", (0, 0), (-1, -1), 4),
                                   ("BOTTOMPADDING", (0, 0), (-1, -1), 4)]))
        out = [Paragraph(title, _S["h2"]), head]
        if card.get("why"):
            out.append(Paragraph(f'<b>Why:</b> {_esc(card["why"])}', _S["body"]))
        return out + [Spacer(1, 4), table, Paragraph(_esc(card.get("basis", "")), _S["muted"]),
                      Spacer(1, 8)]

    if payload.get("india_status"):
        t = Table([[Paragraph(f'<b>Your India status.</b> {_esc(payload["india_status"])}',
                              _S["body"])]])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), ACCENT_SOFT),
                               ("LEFTPADDING", (0, 0), (-1, -1), 8),
                               ("TOPPADDING", (0, 0), (-1, -1), 6),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 6)]))
        story += [t, Spacer(1, 6)]

    market = payload.get("market")
    if market:
        story += reasoned(market, "India as a market for what you sell", ACCENT,
                          [(d["name"], d["level"], d["insight"]) for d in market["dimensions"]])

    th = payload.get("technology_hub")
    if th:
        story += reasoned(th, "India as a place to build technology", GREEN,
                          [(d["name"], d["level"], d["reason"]) for d in th["dimensions"]])

    peer = payload.get("peer_headline")
    if peer:
        t = Table([[Paragraph(f'{peer["with_centre"]} of {peer["total"]}', _S["big"]),
                    Paragraph("<b>of the companies we identify as your closest peers already "
                              "run a capability centre in India.</b> Your cohort: "
                              f'{_esc(peer.get("cohort_definition", ""))}.', _S["body"])]],
                  colWidths=[45 * mm, None])
        t.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                               ("LINEABOVE", (0, 0), (-1, 0), 2, ACCENT),
                               ("TOPPADDING", (0, 0), (-1, -1), 8)]))
        story += [t, Spacer(1, 6)]

    if payload.get("message"):
        story.append(Paragraph(_esc(payload["message"]), _S["body"]))

    scale = payload.get("indicative_scale")
    if scale:
        story.append(Paragraph("Indicative scale, if you moved", _S["h2"]))
        story.append(Paragraph(
            f'First phase team <b>{_esc(scale["first_phase_team"])}</b>  ·  saving '
            f'<b>{_esc(scale["indicative_saving"])}</b>  ·  first team live in '
            f'<b>{_esc(scale["time_to_first_team_live"])}</b>. {_esc(scale["note"])}', _S["body"]))

    evidence = payload.get("own_evidence") or []
    if evidence:
        story.append(Paragraph("What we found when we looked at your company specifically", _S["h2"]))
        for p in evidence:
            block = [Paragraph(f'<b>{_esc(p["title"])}</b>', _S["body"])]
            block += [Paragraph(_rich(b), _S["bullet"], bulletText="•") for b in p["bullets"]]
            if p.get("as_of"):
                block.append(Paragraph(f'Source dated {_esc(p["as_of"])}', _S["muted"]))
            block.append(Spacer(1, 5))
            story.append(KeepTogether(block))

    withheld = payload.get("withheld") or []
    if withheld:
        story.append(Paragraph("What this assessment deliberately does not show you", _S["h2"]))
        story.append(Paragraph("These need judgement and verification, not automation. They "
                               "are what the full business case contains.", _S["muted"]))
        story += [Paragraph(_esc(w), _S["bullet"], bulletText="+") for w in withheld]

    lc = payload.get("lead_capture") or {}
    if lc.get("offer"):
        t = Table([[[Paragraph(f'<font color="#F3F2EF"><b>{_esc(lc.get("title") or "Next step")}</b></font>',
                               _S["h2"]),
                     Paragraph(f'<font color="#F3F2EF">{_esc(lc["offer"])}</font>', _S["body"]),
                     Spacer(1, 4),
                     Paragraph('<font color="#E8791C"><b>Reply to this email or write to '
                               'accessindia@airopa.co to request it.</b></font>', _S["body"])]]])
        t.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), BAND),
                               ("LEFTPADDING", (0, 0), (-1, -1), 12),
                               ("RIGHTPADDING", (0, 0), (-1, -1), 12),
                               ("TOPPADDING", (0, 0), (-1, -1), 8),
                               ("BOTTOMPADDING", (0, 0), (-1, -1), 12)]))
        story += [Spacer(1, 10), t]

    if payload.get("disclaimer"):
        story += [Spacer(1, 10), Paragraph(_esc(payload["disclaimer"]), _S["muted"])]

    doc.build(story, onFirstPage=_header, onLaterPages=_header)
    return buf.getvalue()
