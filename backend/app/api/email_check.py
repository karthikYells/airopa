"""Work-email check, kept identical to the GCC Business Case engine on
accessindia.nl (engine.js checkEmail) so both engines treat addresses alike."""
from __future__ import annotations

import re

PERSONAL_DOMAINS = {
    # Global webmail
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com", "msn.com",
    "yahoo.com", "ymail.com", "rocketmail.com", "icloud.com", "me.com", "mac.com", "aol.com",
    "proton.me", "protonmail.com", "pm.me", "tutanota.com", "tuta.io", "zohomail.com",
    "yandex.com", "mail.com", "gmx.com", "gmx.net", "fastmail.com", "hey.com",
    # Netherlands
    "ziggo.nl", "kpnmail.nl", "kpnplanet.nl", "planet.nl", "home.nl", "hetnet.nl", "xs4all.nl",
    "telfort.nl", "upcmail.nl", "chello.nl", "casema.nl", "quicknet.nl", "online.nl", "tele2.nl",
    "freeler.nl", "zeelandnet.nl", "solcon.nl", "caiway.nl", "hotmail.nl", "live.nl",
    "outlook.nl", "yahoo.nl",
    # Belgium, Germany, France, UK, Ireland
    "skynet.be", "telenet.be", "proximus.be", "hotmail.be", "outlook.be", "gmx.de", "web.de",
    "t-online.de", "freenet.de", "hotmail.de", "yahoo.de", "orange.fr", "free.fr",
    "laposte.net", "sfr.fr", "wanadoo.fr", "hotmail.fr", "yahoo.fr", "btinternet.com",
    "sky.com", "virginmedia.com", "hotmail.co.uk", "yahoo.co.uk", "eircom.net",
    # India
    "rediffmail.com", "yahoo.co.in", "yahoo.in", "hotmail.co.in", "outlook.in",
}

_EMAIL_RE = re.compile(r"^[^\s@<>()\"',;:]+@[a-z0-9-]+(\.[a-z0-9-]+)*\.[a-z]{2,}$", re.I)


def check_email(email: str) -> dict:
    e = (email or "").strip().lower()
    if len(e) > 254 or not _EMAIL_RE.match(e):
        return {"ok": False, "reason": "invalid"}
    return {"ok": True, "email": e, "personal": e.split("@")[1] in PERSONAL_DOMAINS}
