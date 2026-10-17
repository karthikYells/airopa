# Putting the India Market Assessment on accessindia.nl

The page becomes a new engine at **accessindia.nl/engines/india-market-assessment/**, next
to the GCC Business Case engine, with the same look, the same email rules and
the same lead flow.

## How it fits together

```
visitor ── accessindia.nl/engines/india-market-assessment/   (static page, on Netlify with the rest of the site)
              │  POST /api/score, /api/report  (direct, CORS limited to accessindia.nl)
              ▼
          Google Cloud Run, europe-west1 (Belgium)  (this Python engine; free tier)
              ├─ Apollo, Wikidata, company websites, Claude
              └─ email: PDF from connect@airopa.co (copy to connect@airopa.co)
```

Why the engine is not a Netlify Function like `/api/send-report`: it reads other
companies' websites and uses secret API keys (neither can happen in a browser),
it is Python, and a run takes 10 to 60 seconds, longer than Netlify functions are
allowed to run. So it runs on Cloud Run and the page calls it directly.

**Cloud Run keeps no files between restarts** (it stops when idle, which is what
keeps it free). So:
- every lead is kept in **Netlify Forms** (form `india-market-assessment-report`, which
  notifies connect@airopa.co) and connect@airopa.co gets a copy of every report;
- the page carries a **signed copy** of the snapshot, so "email me the report"
  works even if the engine restarted in between;
- caches (24-hour snapshots, Apollo lookups, saved sectors) last only while an
  instance is running.

## 1. The engine on Google Cloud Run (free tier)

At this volume it stays inside Cloud Run's free tier (2 million requests,
180,000 vCPU-seconds and 360,000 GiB-seconds a month). `--max-instances 2` caps
what it can ever use. Google requires a card on the billing account; set a budget
alert of EUR 1 so you are told if anything is ever charged.

One-time setup (in a browser):
1. console.cloud.google.com, sign in with the Airopa Google account, create a
   project `accessindia-engine`, and link a billing account.
2. Billing > Budgets & alerts > create a budget of EUR 1 with email alerts.

Deploy (from the repository root, with the Google Cloud CLI installed and
`gcloud auth login` done):

```bash
gcloud config set project accessindia-engine
gcloud services enable run.googleapis.com cloudbuild.googleapis.com artifactregistry.googleapis.com
gcloud run deploy india-market-assessment --source backend --region europe-west1 \
  --allow-unauthenticated --memory 1Gi --cpu 1 --timeout 300 \
  --max-instances 2 --concurrency 10 \
  --set-env-vars "CORS_ORIGINS=https://accessindia.nl,ENABLE_INTERNAL=false,PUBLISH_REFERENCE_SCORES=false,MAIL_PROVIDER=graph,MAIL_NOTIFY=connect@airopa.co,PUBLIC_SITE_URL=https://accessindia.nl/engines/india-market-assessment/"
```

Use the settings file, not `--set-env-vars`: on Windows the `^;^` separator
needed for the commas is mangled and the settings silently fall back to the
defaults (internal view on, any website allowed). Check with
`gcloud run services describe india-market-assessment --region europe-west1`.

The command prints the engine's address, `https://india-market-assessment-….run.app`.
`backend/.gcloudignore` keeps `.env`, local data and tests out of the upload.

Then add the **secrets** in the Cloud Run console (india-market-assessment > Edit & deploy
new revision > Variables & secrets), never in git:

| Variable | Value |
|---|---|
| `ANTHROPIC_API_KEY` | workspace key (`sk-ant-api03-…`) |
| `APOLLO_API_KEY` | Airopa Apollo key |
| `MS_TENANT_ID`, `MS_CLIENT_ID`, `MS_CLIENT_SECRET` | the same values as in Netlify for `send-report` |
| `SNAPSHOT_SIGNING_KEY` | any long random string (keep it the same from now on) |

Optional later: map `engine.accessindia.nl` to the service (Cloud Run > Manage
custom domains, supported in europe-west1) and rebuild the page with that address.

## 2. The page in the accessindia.nl site

```bash
cd frontend
npm install
VITE_PUBLIC_ONLY=true VITE_BASE=/engines/india-market-assessment/ \
VITE_API_BASE=https://india-market-assessment-XXXX.run.app npm run build
```

Use the address Cloud Run printed in step 1 for `VITE_API_BASE`.

On Windows in Git Bash, put `MSYS_NO_PATHCONV=1` in front of that command, or
Git Bash rewrites `/engines/...` into a Windows path and the page loads blank.

Copy everything in `frontend/dist/` into the site repository at
`engines/india-market-assessment/`, add a card for it on `/engines/`, and deploy the site
as usual. Netlify detects the `india-market-assessment-report` form on deploy; turn on its
email notification to connect@airopa.co in Netlify > Forms.

The page uses the site's own `/fonts/fonts.css`, header, footer and privacy link.

## 3. Sending the PDF

Exactly as the GCC Business Case engine does: Microsoft Graph `sendMail` from
connect@airopa.co, using the **same Entra app** (Mail.Send, restricted to that
mailbox). Copy `MS_TENANT_ID`, `MS_CLIENT_ID` and `MS_CLIENT_SECRET` from Netlify >
Project configuration > Environment variables into the engine host's settings.
Nothing else is needed; the email uses the same design as the business case email.

Until those are set, requests are marked `queued` and the visitor is told the
report will arrive within one business day; the team follows up from the Netlify
Forms notification (on Cloud Run the saved PDF does not survive a restart). Personal email addresses are always queued
for a person, as on the business case engine. (SMTP and Resend are also supported
via `MAIL_PROVIDER=smtp` or `resend`.)

## 4. Before launch (spec Section 12 items 14 to 17)

- Blocklist of competitors and current clients (`app/api/abuse.py`).
- Who reviews the first 100 public snapshots (spec 9.6) and answers correction requests.
- Legal review of the page wording and the PDF footer.
- Capacity to deliver the two-week business case at the expected request volume.
- Privacy notice on accessindia.nl updated for this engine (company lookups, Apollo, report emails).
