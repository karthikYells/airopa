# Airopa — GCC Prospect Scoring Engine

A standalone app that scores a European company's India Global Capability Centre
(GCC) opportunity from its website. Built to the engineering specification
`Airopa-GCC-Scoring-Engine-Spec-v3.0.docx`.

One engine, two surfaces:

- **Public** — `Score my Company`: a prospect enters their domain and gets a
  one-page animated snapshot (the India Market Opportunity and Technology Hub
  Readiness scores, a peer-penetration headline, their own evidence, and a
  business-case call to action). Never shows the internal GCC Fit score or any
  third-party names.
- **Internal** — the full assessment including **GCC Fit**, every sub-score with
  its evidenced basis, the India gate verdict, exclusion codes, recommended
  engagement model and source list.

```
airopa/
  backend/     Python + FastAPI scoring engine and API
  frontend/    React + Vite animated UI (FT-style)
```

---

## Run it locally (two terminals)

**1 — Backend** (Python 3.9+)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # optional: add your ANTHROPIC_API_KEY
uvicorn app.main:app --port 8077 --reload
```

Backend is now at `http://localhost:8077` (health check: `/api/health`).

**2 — Frontend** (Node 18+)

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5190`. The dev server proxies `/api` to the backend
automatically. Add `?internal` to the URL for the internal pipeline view.

Try the illustrative example companies on the landing page (chips under the
input), or any real domain.

---

## The AI model (optional)

The engine runs fully **without** an API key — the India gate, exclusions,
scoring and the whole snapshot are deterministic. A Claude key only enriches two
things the spec permits a model to do: classify ambiguous job titles, and
generate narrative prose. To enable it, put your key in `backend/.env`:

```
ANTHROPIC_API_KEY=sk-ant-...
```

Models are never used for arithmetic, scores, or looking up India facts — that
is a deliberate design rule from the spec.

---

## How it works for any domain

Enter any company website and the engine produces a real assessment from live,
free, public sources:

- **Entity + firmographics** — resolved via **Wikidata** (name, country, sector,
  founding year, parent/subsidiaries, and revenue/headcount where public) plus a
  crawl of the company's own About / Locations / Careers pages.
- **India presence** (the gate) — detected from the site crawl (India offices,
  Indian cities, `Pvt Ltd` markers) and Wikidata subsidiaries.
- **India Market & Technology Hub scores** — computed from a **curated,
  sector-keyed India reference dataset** (`app/reference/india_reference.py`).
  The company is classified into a sector (keywords, or Claude if a key is set),
  and the India figures are looked up — so two companies in the same sector
  always get the same India numbers (the Section 6.2 consistency rule). The raw
  figures drive the scores and stay in the internal brief; the public page shows
  only scores, bands and ranges (Section 9.1).

What's honest about it:

- Where a specific fact isn't public (e.g. a private firm's revenue), that one
  signal stays `UNKNOWN` — never invented (Design Principle #1).
- If a site is unreachable or too thin, the page returns `INSUFFICIENT_DATA` and
  asks for the missing facts (a real spec feature, Section 9.4) — it never
  fabricates to fill the gap.

The curated India reference figures are v1 values to be refined against a
licensed dataset; each row carries its own `as_of` date. The example chips on
the landing page use a seeded verified-entity store to demonstrate the richest
possible output (own-evidence panels, named-cohort peer headline).

---

## Tests

```bash
cd backend && source .venv/bin/activate && python -m pytest -q
```

Covers the six Section 11.1 gate fixtures (Hettich, BHS, Merck, Hoermann,
Drees und Sommer, Statkraft), the public-safety guarantees (no GCC Fit or names
leak publicly), response modes, and reproducibility.

---

## Deploying (plugging into airopa.co)

Recommended shape: a standalone subdomain, e.g. `tool.airopa.co`.

1. **Backend** → host on a platform with a persistent disk (Render, Railway,
   Fly.io). Set `ANTHROPIC_API_KEY`, `INTERNAL_API_TOKEN`, and (for scale) a
   Postgres `DATABASE_URL`. Start command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`.
2. **Frontend** → `npm run build` produces `frontend/dist`, a static site. Host
   it (Vercel/Netlify/same box) and set `VITE_API_BASE` to the backend URL, or
   serve both behind one domain so `/api` is same-origin.
3. Link to the tool from the main airopa.co site, or embed it in an iframe.

The local SQLite database (`backend/data/airopa.db`) is dev scratch data and is
git-ignored — the hosted app creates its own. Nothing is tied to your laptop.

See `ARCHITECTURE.md` for the full module map and design decisions.
