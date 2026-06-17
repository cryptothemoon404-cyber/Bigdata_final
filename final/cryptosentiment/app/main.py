"""
CryptoSentiment API — Main FastAPI application
Endpoints:
  GET /                     - Dashboard HTML
  GET /api/v1/sentiment     - Aggregated sentiment for a symbol
  GET /api/v1/sentiment/history - Time-series sentiment history
  GET /api/v1/prices        - Live prices from CoinGecko
  GET /api/v1/feed          - Latest headlines with scores
  POST /api/v1/ingest       - Trigger manual data ingestion (admin)
"""
import os
import logging
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from .database import init_db, get_connection
from .ingestion import (
    ingest_rss,
    fetch_coingecko_prices,
    aggregate_sentiment,
    seed_demo_data,
    KEYWORDS,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="CryptoSentiment API",
    description="Real-time cryptocurrency sentiment intelligence from news and social media.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPPORTED_SYMBOLS = list(KEYWORDS.keys())


@app.on_event("startup")
async def startup():
    init_db()
    conn = get_connection()
    count = conn.execute("SELECT COUNT(*) FROM sentiment_records").fetchone()[0]
    conn.close()
    if count == 0:
        logger.info("No data found — seeding demo data...")
        seed_demo_data()
    logger.info("CryptoSentiment API ready")


# ── API Endpoints ────────────────────────────────────────────────────────────

@app.get("/api/v1/sentiment", tags=["Sentiment"])
def get_sentiment(
    symbol: str = Query(..., description="Coin symbol, e.g. BTC"),
    hours: int = Query(24, ge=1, le=168, description="Lookback window in hours"),
):
    """Return aggregated sentiment for a symbol over the last N hours."""
    symbol = symbol.upper()
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported symbol. Use one of: {SUPPORTED_SYMBOLS}",
        )
    result = aggregate_sentiment(symbol, hours)
    return result


@app.get("/api/v1/sentiment/history", tags=["Sentiment"])
def get_sentiment_history(
    symbol: str = Query(..., description="Coin symbol, e.g. BTC"),
    hours: int = Query(72, ge=1, le=168),
    bucket_hours: int = Query(6, ge=1, le=24),
):
    """Return hourly-bucketed sentiment history for charting."""
    import datetime as dt
    symbol = symbol.upper()
    if symbol not in SUPPORTED_SYMBOLS:
        raise HTTPException(status_code=400, detail="Unsupported symbol")

    conn = get_connection()
    now = datetime.now(timezone.utc)
    cutoff = (now - dt.timedelta(hours=hours)).isoformat()
    rows = conn.execute(
        """SELECT score, collected_at FROM sentiment_records
           WHERE symbol = ? AND collected_at >= ?
           ORDER BY collected_at ASC""",
        (symbol, cutoff),
    ).fetchall()
    conn.close()

    # Bucket by bucket_hours
    buckets: dict[str, list[float]] = {}
    for row in rows:
        ts = datetime.fromisoformat(row["collected_at"].replace("Z", "+00:00"))
        # Round down to nearest bucket
        bucket_idx = int(ts.timestamp() // (bucket_hours * 3600))
        bucket_ts = datetime.fromtimestamp(
            bucket_idx * bucket_hours * 3600, tz=timezone.utc
        ).isoformat()
        buckets.setdefault(bucket_ts, []).append(row["score"])

    history = [
        {
            "timestamp": ts,
            "avg_score": round(sum(scores) / len(scores), 4),
            "count": len(scores),
        }
        for ts, scores in sorted(buckets.items())
    ]
    return {"symbol": symbol, "history": history, "bucket_hours": bucket_hours}


@app.get("/api/v1/prices", tags=["Market Data"])
def get_prices():
    """Fetch live coin prices from CoinGecko."""
    prices = fetch_coingecko_prices()
    if not prices:
        raise HTTPException(status_code=503, detail="Price data unavailable")
    return prices


@app.get("/api/v1/feed", tags=["Feed"])
def get_feed(
    symbol: Optional[str] = Query(None, description="Filter by symbol"),
    limit: int = Query(20, ge=1, le=100),
):
    """Return latest scored headlines."""
    conn = get_connection()
    if symbol:
        symbol = symbol.upper()
        rows = conn.execute(
            """SELECT symbol, source, headline, score, label, url, collected_at
               FROM sentiment_records WHERE symbol = ?
               ORDER BY collected_at DESC LIMIT ?""",
            (symbol, limit),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT symbol, source, headline, score, label, url, collected_at
               FROM sentiment_records
               ORDER BY collected_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


@app.post("/api/v1/ingest", tags=["Admin"])
def trigger_ingest(secret: str = Query(...)):
    """Manually trigger RSS ingestion (requires admin secret)."""
    admin_secret = os.getenv("ADMIN_SECRET", "change-me-in-production")
    if secret != admin_secret:
        raise HTTPException(status_code=403, detail="Forbidden")
    n = ingest_rss()
    return {"inserted": n, "timestamp": datetime.now(timezone.utc).isoformat()}


@app.get("/api/v1/symbols", tags=["Info"])
def list_symbols():
    """List all supported symbols."""
    return {"symbols": SUPPORTED_SYMBOLS}


# ── Dashboard ────────────────────────────────────────────────────────────────

DASHBOARD_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>CryptoSentiment Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.0/chart.umd.min.js"></script>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
         background: #0d1117; color: #c9d1d9; min-height: 100vh; }
  header { background: #161b22; border-bottom: 1px solid #30363d;
           padding: 16px 24px; display: flex; align-items: center; gap: 12px; }
  header h1 { font-size: 1.25rem; font-weight: 700; color: #e6edf3; }
  header span { font-size: 0.75rem; background: #1f6feb; color: #fff;
                padding: 2px 8px; border-radius: 12px; }
  .container { max-width: 1200px; margin: 0 auto; padding: 24px 16px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin-bottom: 32px; }
  .card { background: #161b22; border: 1px solid #30363d; border-radius: 8px; padding: 16px; }
  .card h3 { font-size: 0.75rem; text-transform: uppercase; letter-spacing: .05em;
              color: #8b949e; margin-bottom: 8px; }
  .card .value { font-size: 1.75rem; font-weight: 700; color: #e6edf3; }
  .card .sub { font-size: 0.8rem; color: #8b949e; margin-top: 4px; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 4px;
           font-size: 0.75rem; font-weight: 600; }
  .badge.positive { background: #0d4429; color: #3fb950; }
  .badge.negative { background: #4d1112; color: #f85149; }
  .badge.neutral  { background: #21262d; color: #8b949e; }
  .chart-wrap { background: #161b22; border: 1px solid #30363d;
                border-radius: 8px; padding: 20px; margin-bottom: 24px; }
  .chart-wrap h2 { font-size: 1rem; font-weight: 600; margin-bottom: 16px; color: #e6edf3; }
  select, button { background: #21262d; color: #c9d1d9; border: 1px solid #30363d;
                   border-radius: 6px; padding: 6px 12px; cursor: pointer; font-size: 0.875rem; }
  button:hover { background: #388bfd22; border-color: #388bfd; }
  .controls { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; align-items: center; }
  .feed-table { width: 100%; border-collapse: collapse; font-size: 0.85rem; }
  .feed-table th { text-align: left; color: #8b949e; padding: 8px 12px;
                   border-bottom: 1px solid #30363d; font-weight: 500; }
  .feed-table td { padding: 8px 12px; border-bottom: 1px solid #21262d; }
  .feed-table tr:hover td { background: #1c2128; }
  .loading { text-align: center; color: #8b949e; padding: 40px; }
</style>
</head>
<body>
<header>
  <h1>⚡ CryptoSentiment</h1>
  <span>LIVE</span>
  <span style="margin-left:auto;font-size:0.75rem;color:#8b949e">Real-time NLP Sentiment Intelligence</span>
</header>

<div class="container">
  <!-- Summary Cards -->
  <div class="grid" id="summary-grid">
    <div class="card"><h3>Loading...</h3><div class="value">—</div></div>
  </div>

  <!-- Chart -->
  <div class="chart-wrap">
    <h2>Sentiment History</h2>
    <div class="controls">
      <select id="sym-select">
        <option value="BTC">BTC</option>
        <option value="ETH">ETH</option>
        <option value="SOL">SOL</option>
        <option value="BNB">BNB</option>
        <option value="XRP">XRP</option>
      </select>
      <select id="hours-select">
        <option value="24">Last 24h</option>
        <option value="48">Last 48h</option>
        <option value="72" selected>Last 72h</option>
      </select>
      <button onclick="loadChart()">Refresh</button>
    </div>
    <canvas id="sentimentChart" height="80"></canvas>
  </div>

  <!-- Feed -->
  <div class="chart-wrap">
    <h2>Latest Headlines</h2>
    <div class="controls">
      <select id="feed-sym">
        <option value="">All Symbols</option>
        <option value="BTC">BTC</option>
        <option value="ETH">ETH</option>
        <option value="SOL">SOL</option>
      </select>
      <button onclick="loadFeed()">Refresh</button>
    </div>
    <table class="feed-table">
      <thead><tr><th>Symbol</th><th>Headline</th><th>Score</th><th>Label</th><th>Source</th></tr></thead>
      <tbody id="feed-body"><tr><td colspan="5" class="loading">Loading...</td></tr></tbody>
    </table>
  </div>
</div>

<script>
const API = '';
let chart;

async function fetchJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(r.statusText);
  return r.json();
}

async function loadSummaryCards() {
  const symbols = ['BTC','ETH','SOL','BNB','XRP'];
  const el = document.getElementById('summary-grid');
  el.innerHTML = '';
  for (const sym of symbols) {
    try {
      const d = await fetchJSON(`${API}/api/v1/sentiment?symbol=${sym}&hours=24`);
      const score = d.avg_score ?? 0;
      const label = d.label || 'neutral';
      const color = label==='positive'?'#3fb950':label==='negative'?'#f85149':'#8b949e';
      el.innerHTML += `<div class="card">
        <h3>${sym}</h3>
        <div class="value" style="color:${color}">${score>=0?'+':''}${score.toFixed(3)}</div>
        <div class="sub"><span class="badge ${label}">${label}</span> · ${d.total||0} sources · 24h</div>
      </div>`;
    } catch(e) { console.warn(sym, e); }
  }
}

async function loadChart() {
  const sym = document.getElementById('sym-select').value;
  const hours = document.getElementById('hours-select').value;
  const data = await fetchJSON(`${API}/api/v1/sentiment/history?symbol=${sym}&hours=${hours}&bucket_hours=6`);
  const hist = data.history || [];
  const labels = hist.map(h => {
    const d = new Date(h.timestamp);
    return d.toLocaleString('en',{month:'short',day:'numeric',hour:'2-digit',minute:'2-digit'});
  });
  const scores = hist.map(h => h.avg_score);
  const colors = scores.map(s => s>=0.05?'rgba(63,185,80,0.8)':s<=-0.05?'rgba(248,81,73,0.8)':'rgba(139,148,158,0.8)');

  const ctx = document.getElementById('sentimentChart').getContext('2d');
  if (chart) chart.destroy();
  chart = new Chart(ctx, {
    type: 'bar',
    data: {
      labels,
      datasets: [{
        label: `${sym} Sentiment Score`,
        data: scores,
        backgroundColor: colors,
        borderRadius: 4,
      }]
    },
    options: {
      responsive: true,
      plugins: {
        legend: { labels: { color: '#c9d1d9' } },
        tooltip: {
          callbacks: {
            label: ctx => `Score: ${ctx.raw.toFixed(4)} (${ctx.raw>=0.05?'Positive':ctx.raw<=-0.05?'Negative':'Neutral'})`
          }
        }
      },
      scales: {
        x: { ticks: { color: '#8b949e' }, grid: { color: '#21262d' } },
        y: {
          ticks: { color: '#8b949e' },
          grid: { color: '#21262d' },
          min: -1, max: 1,
        }
      }
    }
  });
}

async function loadFeed() {
  const sym = document.getElementById('feed-sym').value;
  const url = sym ? `${API}/api/v1/feed?symbol=${sym}&limit=20` : `${API}/api/v1/feed?limit=20`;
  const rows = await fetchJSON(url);
  const tbody = document.getElementById('feed-body');
  tbody.innerHTML = rows.map(r => `
    <tr>
      <td><b>${r.symbol}</b></td>
      <td>${r.headline ? r.headline.substring(0,80)+(r.headline.length>80?'…':'') : '—'}</td>
      <td style="color:${r.score>=0.05?'#3fb950':r.score<=-0.05?'#f85149':'#8b949e'}">${r.score.toFixed(3)}</td>
      <td><span class="badge ${r.label}">${r.label}</span></td>
      <td>${r.source}</td>
    </tr>
  `).join('');
}

// Init
loadSummaryCards();
loadChart();
loadFeed();
setInterval(() => { loadSummaryCards(); loadFeed(); }, 60000);
</script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def dashboard():
    return HTMLResponse(content=DASHBOARD_HTML)
