# Putting the India Opportunity Snapshot on accessindia.nl

The page becomes a new engine at **accessindia.nl/engines/india-snapshot/**, next
to the GCC Business Case engine, with the same look, the same email rules and
the same lead flow.

## How it fits together

```
visitor ── accessindia.nl/engines/india-snapshot/   (static page, on Netlify with the rest of the site)
              │  POST /api/score, /api/report  (direct, CORS limited to accessindia.nl)
              ▼
          engine.accessindia.nl                    (this Python engine, on a small server)
              ├─ Apollo, Wikidata, company websites, Claude
              ├─ SQLite: every run and every lead
              └─ email: PDF from connect@airopa.co (copy to connect@airopa.co)
```

Why the engine is not a Netlify Function like `/api/send-report`: it is Python,
and a run takes 10 to 60 seconds, longer than Netlify allows a function or a proxy
to wait. So the page calls the engine on its own subdomain.

Every lead is kept twice, as on the business case engine: in **Netlify Forms**
(form `india-snapshot-report`, which notifies connect@airopa.co) and in the
engine's own database with the PDF that was sent.

## 1. The engine server

Any host that runs a Python web service with a persistent disk works. Render is
the simplest (about USD 7 a month for the smallest paid instance plus a 1 GB disk;
the free tier sleeps and loses the database, so it is not suitable).

- Root directory: `backend`
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Persistent disk mounted at `/opt/render/project/src/backend/data`
- Environment (secrets go in the host's settings, never in git):

| Variable | Production value |
|---|---|
| `ANTHROPIC_API_KEY` | workspace key (`sk-ant-api03-…`) |
| `APOLLO_API_KEY` | Airopa Apollo key |
| `CORS_ORIGINS` | `https://accessindia.nl,https://www.accessindia.nl` |
| `ENABLE_INTERNAL` | `false` (the internal view has no password; keep it local) |
| `PUBLISH_REFERENCE_SCORES` | `false` until the India data source is approved |
| `MAIL_PROVIDER` | `graph` (see step 3) |
| `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET` | the same values as in Netlify for `send-report` |
| `MAIL_NOTIFY` | `connect@airopa.co` (gets a copy of every report) |
| `PUBLIC_SITE_URL` | `https://accessindia.nl/engines/india-snapshot/` |

Then add the custom domain `engine.accessindia.nl` on the host and create the
DNS record it asks for (a CNAME) wherever accessindia.nl's DNS is managed
(Netlify DNS if the domain is on Netlify).

## 2. The page in the accessindia.nl site

```bash
cd frontend
npm install
VITE_PUBLIC_ONLY=true VITE_BASE=/engines/india-snapshot/ \
VITE_API_BASE=https://engine.accessindia.nl npm run build
```

On Windows in Git Bash, put `MSYS_NO_PATHCONV=1` in front of that command, or
Git Bash rewrites `/engines/...` into a Windows path and the page loads blank.

Copy everything in `frontend/dist/` into the site repository at
`engines/india-snapshot/`, add a card for it on `/engines/`, and deploy the site
as usual. Netlify detects the `india-snapshot-report` form on deploy; turn on its
email notification to connect@airopa.co in Netlify > Forms.

The page uses the site's own `/fonts/fonts.css`, header, footer and privacy link.

## 3. Sending the PDF

Exactly as the GCC Business Case engine does: Microsoft Graph `sendMail` from
connect@airopa.co, using the **same Entra app** (Mail.Send, restricted to that
mailbox). Copy `MS_TENANT_ID`, `MS_CLIENT_ID` and `MS_CLIENT_SECRET` from Netlify >
Project configuration > Environment variables into the engine host's settings.
Nothing else is needed; the email uses the same design as the business case email.

Until those are set, requests are saved as `queued` with their PDF in
`backend/data/reports/` for a person to send, and the visitor is told the report
will arrive within one business day. Personal email addresses are always queued
for a person, as on the business case engine. (SMTP and Resend are also supported
via `MAIL_PROVIDER=smtp` or `resend`.)

## 4. Before launch (spec Section 12 items 14 to 17)

- Blocklist of competitors and current clients (`app/api/abuse.py`).
- Who reviews the first 100 public snapshots (spec 9.6) and answers correction requests.
- Legal review of the page wording and the PDF footer.
- Capacity to deliver the two-week business case at the expected request volume.
- Privacy notice on accessindia.nl updated for this engine (company lookups, Apollo, report emails).
