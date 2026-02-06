# Bayesline

**News discovery platform where importance is inferred from informed attention — not editorial judgment.**

Bayesline ingests prediction-market signals (trading volume, price movements, liquidity) alongside news and primary sources, then surfaces topics ranked by a composite **ImpactScore**. Users never see markets, prices, or contracts — only plain-language topics with evidence-backed summaries.

## What It Does

1. **Finds topics early** — before mainstream coverage — by detecting where informed traders are spending effort.
2. **Downranks hype** — sensational headlines without consequential, tradable expectations get penalized.
3. **Explains what matters** — each topic includes what happened, what's likely next, key uncertainties, and primary-source citations.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                     Frontend (React)                     │
│  Feed sections: Breaking │ Undercovered │ Deadlines │ Slow Burn  │
└────────────────────────┬────────────────────────────────┘
                         │ REST API
┌────────────────────────▼────────────────────────────────┐
│                   FastAPI Backend                         │
│                                                          │
│  ┌──────────┐  ┌──────────┐  ┌────────────┐  ┌────────┐│
│  │Ingestion │  │  Topic   │  │  Scoring   │  │Summary ││
│  │ Markets  │  │Discovery │  │ImpactScore │  │Pipeline││
│  │  News    │  │ Entities │  │  Formula   │  │  LLM   ││
│  │  GDELT   │  │  Dedup   │  │            │  │        ││
│  └──────────┘  └──────────┘  └────────────┘  └────────┘│
│                                                          │
│  ┌──────────────────────────────────────────────────────┐│
│  │              DataStore (in-memory / DB)               ││
│  │  Markets │ Snapshots │ Articles │ Topics │ Entities   ││
│  └──────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────┘
```

## ImpactScore Formula

```
ImpactScore(t) = 0.45·MarketSignal + 0.20·CoverageGap + 0.20·Consequence
               + 0.10·TimeSensitivity - 0.15·ManipulationRisk - 0.10·HypeGap
```

- **MarketSignal**: Aggregate of volume, open interest, depth, price change, and jump scores across mapped markets, weighted by quality and robustness.
- **CoverageGap**: `max(0, MarketSignal - NewsCoverage)` — "traders care more than editors."
- **HypeGap**: `max(0, NewsCoverage - MarketSignal)` — editorial hype without consequence.
- **Consequence**: Population scale, financial magnitude, policy irreversibility, tail-risk flags.
- **TimeSensitivity**: Peaks near deadlines and resolution dates.
- **ManipulationRisk**: Thin liquidity, single-venue, short-lived spikes, excessive edits.

## Quick Start

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # Edit with your API keys
uvicorn app.main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

### Docker

```bash
docker compose up --build
```

### Run Tests

```bash
cd backend
pytest tests/ -v
```

## Data Sources

| Source | Type | API |
|--------|------|-----|
| Polymarket | Prediction market | Public CLOB API |
| Manifold Markets | Prediction market | Public REST API |
| Kalshi | Prediction market | REST API (key optional) |
| NewsAPI.org | News headlines | API key required |
| GDELT | Global news | Public API |

## Feed Sections

| Section | Logic |
|---------|-------|
| **Breaking Importance** | Highest ImpactScore with recent changes |
| **Undercovered** | Highest CoverageGap (significant but not in headlines) |
| **Deadlines** | Upcoming resolution dates and real-world deadlines |
| **Slow Burn** | High consequence, low recent volatility |

## Configuration

All settings via environment variables (prefix `BAYESLINE_`). See `.env.example` for the full list. Scoring weights are tunable without code changes.

## Project Structure

```
backend/
  app/
    models/       # Pydantic data models
    ingestion/    # Market + news connectors
    scoring/      # ImpactScore pipeline
    topics/       # Discovery, deduplication, entities
    summarization/ # LLM-powered evidence summaries
    services/     # Store, feed assembly, orchestrator
    api/          # FastAPI routes
  tests/          # Pytest suite
frontend/
  src/
    components/   # React UI components
    hooks/        # Data fetching hooks
    services/     # API client
    types/        # TypeScript types
    styles/       # CSS
```
