# CryptoSentiment Intelligence API

> Real-time NLP sentiment scoring for cryptocurrencies — built for the NTU Big Data Systems Final Project (Spring 2026).

## What It Does

CryptoSentiment collects financial news headlines from multiple RSS feeds, runs VADER sentiment analysis on each headline, and exposes a REST API + live dashboard. Paying customers can query aggregated sentiment scores, historical trends, and scored headlines for 10 major cryptocurrencies.

## Quick Start (Local)

```bash
# 1. Clone and install
git clone https://github.com/<your-username>/cryptosentiment.git
cd cryptosentiment
pip install -r requirements.txt

# 2. Run the API
uvicorn app.main:app --reload

# 3. Open browser
open http://localhost:8000        # Dashboard
open http://localhost:8000/docs   # Swagger UI
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/sentiment?symbol=BTC&hours=24` | Aggregated sentiment |
| GET | `/api/v1/sentiment/history?symbol=ETH&hours=72` | Time-series history |
| GET | `/api/v1/feed?symbol=BTC&limit=20` | Latest scored headlines |
| GET | `/api/v1/prices` | Live coin prices (CoinGecko) |
| GET | `/api/v1/symbols` | Supported symbols |
| POST | `/api/v1/ingest?secret=<KEY>` | Trigger RSS ingestion |

### Example

```bash
curl http://localhost:8000/api/v1/sentiment?symbol=BTC&hours=24
# {
#   "symbol": "BTC",
#   "avg_score": 0.1423,
#   "label": "positive",
#   "positive": 18,
#   "negative": 4,
#   "neutral": 10,
#   "total": 32,
#   "window_hours": 24
# }
```

## Architecture

```
RSS Feeds ──┐
CoinGecko ──┼──► Ingestion (ingestion.py) ──► SQLite DB ──► FastAPI (main.py) ──► REST API
News APIs ──┘                                                                     └──► Dashboard
```

Full architecture diagram: see `docs/architecture.png` or the PDF report.

## Reproducing Demand Evidence

```bash
mkdir -p data
python scripts/collect_demand_evidence.py
# → outputs data/demand_evidence.json
```

## Running Tests

```bash
pytest tests/ -v
```

## Deployment (Render.com)

1. Fork this repo
2. Go to [render.com](https://render.com) → New Web Service
3. Connect the repo — Render auto-detects `render.yaml`
4. Click Deploy

## Data Sources

- **CoinDesk, CoinTelegraph, CryptoSlate, Decrypt** — RSS feeds (public)
- **CoinGecko** — Market data API (free tier, no key required)
- **VADER Sentiment** — Lexicon-based NLP (Hutto & Gilbert, 2014)

## Business Model

Freemium API subscription:
- **Free**: 100 queries/day
- **Pro** ($29/mo): 10K queries/day + historical data
- **Business** ($99/mo): 100K queries/day + webhook alerts + priority support

## License

MIT
