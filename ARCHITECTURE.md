# Architecture

How the engine maps to the specification, and why each piece is built the way
it is.

## Pipeline (Section 2) — four tiers, executed in order

A record that fails a tier never reaches the next one. This is what makes the
engine affordable at volume.

```
Tier 0  Resolve   entity, parent, domains, registry id   -> or RESOLUTION_FAILED
Tier 1  Screen    India gate (§3) + exclusions X1–X20 (§4) + scale band
Tier 2  Triage    cheap signals -> provisional GCC Fit, coverage, X20
Tier 3  Assess    full signal set -> three scores, interactions, narrative
```

Orchestrated in `backend/app/pipeline/orchestrator.py`.

## The India gate (Section 3) — the primary disqualifier

`backend/app/gate/` — deterministic, no model. A company with an India entity
AND technology roles is `CONFIRMED` (disqualified as a first-GCC prospect). An
entity alone is a positive signal. The title classifier (`title_classifier.py`,
`title_dictionary.py`) is dictionary-first with a model fallback only for
unresolved titles; plant/process engineering is `NON_TECH`, local IT support is
carved out, ambiguous titles never auto-count and tip the gate to `CAUTION`
above 40% of the mix. Validated against the six Section 11.1 fixtures.

## Evidence envelope (Section 7) — nothing is a bare value

`backend/app/data/evidence.py`. Every signal is an object with a value, a fact
date, a collection timestamp, a source URL (or inference inputs), authority,
confidence and method. `UNKNOWN` is a first-class sentinel, distinct from `None`
and `0`; the scoring layer gives it no points, never a low value. A resolved
value without a source cannot be constructed.

## Signals & scoring (Sections 5, 8)

- `signals/collect.py` turns a seed entity or a live scrape into evidence.
- `scoring/` computes the three scores deterministically from resolved evidence
  (`gcc_fit`, `india_market`, `technology_hub`), per-score `coverage`, output
  `bands`, and the three `interactions` rules (delivery gate caps GCC Fit when
  Technology Hub < 50; narrative mode; ranking tie-break on Technology Hub).
- `scoring/registry.py` lists which signals feed each score, for coverage.

## The two surfaces (Sections 9, 10)

- `narrative/public_snapshot.py` builds the nine-block public payload with the
  reveal/withhold discipline and the six response modes.
- `narrative/internal_brief.py` builds the full internal assessment.
- `narrative/safety.py` is the publication guard: it determines the response
  mode and **asserts** the public payload carries no GCC Fit score and no
  peer/vendor/individual name. This is the highest-cost disclosure failure, so
  it is enforced in code and tested.

## External feeds — swappable adapters (Section 12)

`backend/app/adapters/`:

- `web_scraper.py` — **real**: the company's own site + careers page.
- `llm.py` — Anthropic Claude, temperature 0, graceful when no key.
- `registry/` — **stub**: returns no fabricated registry id; a real KVK / MCA /
  Handelsregister / Companies House integration drops in here.
- Reference / people-search data is seeded (`fixtures/demo_companies.py`) as a
  stand-in for Airopa's licensed datasets (Section 6.1 / 6.2).

Because these sit behind interfaces, licensing real feeds later requires no
pipeline changes.

## Storage (Sections 6, 7, 9.6)

`data/store.py` — SQLite by default, Postgres via `DATABASE_URL`. Every run is
retained so any page can be reconstructed and defended. The peer/GCC database
and India reference dataset (the defensible assets) get dedicated tables here as
they are licensed.

## Reproducibility (Section 11.4)

All arithmetic is deterministic; the title dictionary is deterministic; LLM
calls run at temperature 0. Each run stores the config version and thresholds
used. Two runs on the same input produce identical scores — covered by tests.

## Configuration (every TUNE threshold)

`config.py` loads all TUNE thresholds from the environment (see
`backend/.env.example`). None are hard-coded in logic, so they can be calibrated
against the back-test set without code changes.
