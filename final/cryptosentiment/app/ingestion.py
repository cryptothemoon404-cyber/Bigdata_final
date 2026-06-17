"""
Data Ingestion Module
Collects news headlines and computes sentiment scores.
Sources:
  - CoinGecko public API (price + market data)
  - RSS feeds (CoinDesk, CryptoSlate, Reuters Crypto)
  - Reddit r/CryptoCurrency via PRAW (optional, requires credentials)
"""
import time
import logging
from datetime import datetime, timezone
from typing import Optional

import feedparser
import requests
from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer

from .database import get_connection

logger = logging.getLogger(__name__)
analyzer = SentimentIntensityAnalyzer()

RSS_FEEDS = {
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
    "cryptoslate": "https://cryptoslate.com/feed/",
    "decrypt": "https://decrypt.co/feed",
}

COINGECKO_TOP_COINS = [
    "bitcoin", "ethereum", "solana", "bnb", "xrp",
    "cardano", "avalanche-2", "dogecoin", "polkadot", "chainlink"
]

SYMBOL_MAP = {
    "bitcoin": "BTC", "ethereum": "ETH", "solana": "SOL",
    "bnb": "BNB", "xrp": "XRP", "cardano": "ADA",
    "avalanche-2": "AVAX", "dogecoin": "DOGE",
    "polkadot": "DOT", "chainlink": "LINK",
}

KEYWORDS = {
    "BTC": ["bitcoin", "btc", "satoshi"],
    "ETH": ["ethereum", "eth", "ether"],
    "SOL": ["solana", "sol"],
    "BNB": ["binance", "bnb"],
    "XRP": ["xrp", "ripple"],
    "ADA": ["cardano", "ada"],
    "AVAX": ["avalanche", "avax"],
    "DOGE": ["dogecoin", "doge", "shiba"],
    "DOT": ["polkadot", "dot"],
    "LINK": ["chainlink", "link"],
}


def _score_to_label(score: float) -> str:
    if score >= 0.05:
        return "positive"
    elif score <= -0.05:
        return "negative"
    return "neutral"


def _match_symbols(text: str) -> list[str]:
    text_lower = text.lower()
    matched = []
    for sym, kws in KEYWORDS.items():
        if any(kw in text_lower for kw in kws):
            matched.append(sym)
    return matched or ["GENERAL"]


def ingest_rss(limit_per_feed: int = 20) -> int:
    """Fetch RSS feeds, score sentiment, store in DB."""
    conn = get_connection()
    inserted = 0
    now = datetime.now(timezone.utc).isoformat()

    for feed_name, url in RSS_FEEDS.items():
        try:
            feed = feedparser.parse(url)
            entries = feed.entries[:limit_per_feed]
            for entry in entries:
                title = entry.get("title", "")
                link = entry.get("link", "")
                if not title:
                    continue

                scores = analyzer.polarity_scores(title)
                compound = scores["compound"]
                label = _score_to_label(compound)
                symbols = _match_symbols(title)

                for sym in symbols:
                    conn.execute(
                        """INSERT INTO sentiment_records
                           (symbol, source, headline, score, label, url, collected_at)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (sym, feed_name, title, compound, label, link, now),
                    )
                    inserted += 1

            logger.info(f"[RSS] {feed_name}: {len(entries)} entries processed")
        except Exception as exc:
            logger.warning(f"[RSS] {feed_name} failed: {exc}")

    conn.commit()
    conn.close()
    return inserted


def fetch_coingecko_prices() -> dict:
    """Fetch live price + 24h change from CoinGecko (free, no key needed)."""
    ids = ",".join(COINGECKO_TOP_COINS)
    url = (
        f"https://api.coingecko.com/api/v3/coins/markets"
        f"?vs_currency=usd&ids={ids}&order=market_cap_desc&per_page=10&page=1"
    )
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        result = {}
        for coin in data:
            sym = SYMBOL_MAP.get(coin["id"], coin["symbol"].upper())
            result[sym] = {
                "price_usd": coin["current_price"],
                "change_24h": coin["price_change_percentage_24h"],
                "market_cap": coin["market_cap"],
                "volume_24h": coin["total_volume"],
            }
        return result
    except Exception as exc:
        logger.warning(f"[CoinGecko] API error: {exc}")
        return {}


def aggregate_sentiment(symbol: str, hours: int = 24) -> dict:
    """Compute aggregate sentiment metrics for a symbol over the last N hours."""
    conn = get_connection()
    cutoff = datetime.now(timezone.utc)
    import datetime as dt
    window_start = (cutoff - dt.timedelta(hours=hours)).isoformat()

    rows = conn.execute(
        """SELECT score, label FROM sentiment_records
           WHERE symbol = ? AND collected_at >= ?""",
        (symbol, window_start),
    ).fetchall()
    conn.close()

    if not rows:
        return {"symbol": symbol, "total": 0}

    scores = [r["score"] for r in rows]
    labels = [r["label"] for r in rows]
    total = len(scores)
    return {
        "symbol": symbol,
        "avg_score": round(sum(scores) / total, 4),
        "label": _score_to_label(sum(scores) / total),
        "positive": labels.count("positive"),
        "negative": labels.count("negative"),
        "neutral": labels.count("neutral"),
        "total": total,
        "window_hours": hours,
    }


def seed_demo_data():
    """Insert realistic demo data so the dashboard works without live feeds."""
    import random, datetime as dt
    conn = get_connection()
    now = datetime.now(timezone.utc)
    sources = ["coindesk", "cointelegraph", "cryptoslate", "decrypt"]
    headlines = {
        "BTC": [
            "Bitcoin surges past $70,000 as institutional demand grows",
            "BlackRock ETF sees record inflows, Bitcoin price follows",
            "Bitcoin network hashrate reaches all-time high",
            "Concerns rise as Bitcoin faces regulatory headwinds in EU",
            "Bitcoin drops 5% amid macro uncertainty and rate fears",
        ],
        "ETH": [
            "Ethereum staking rewards attract more validators",
            "ETH gas fees hit 6-month low after latest upgrade",
            "Ethereum DeFi TVL surpasses $80 billion milestone",
            "Vitalik warns of centralization risks in ETH staking pools",
            "Ethereum price lags Bitcoin in latest rally",
        ],
        "SOL": [
            "Solana DeFi activity breaks weekly record",
            "Major outage hits Solana network for third time this year",
            "Solana NFT volumes surge as new collections launch",
        ],
    }
    inserted = 0
    for hours_ago in range(72, 0, -1):
        ts = (now - dt.timedelta(hours=hours_ago)).isoformat()
        for sym, hlines in headlines.items():
            n = random.randint(2, 5)
            for _ in range(n):
                h = random.choice(hlines)
                score = analyzer.polarity_scores(h)["compound"]
                conn.execute(
                    """INSERT INTO sentiment_records
                       (symbol, source, headline, score, label, url, collected_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (sym, random.choice(sources), h,
                     score + random.uniform(-0.1, 0.1),
                     _score_to_label(score), "", ts),
                )
                inserted += 1
    conn.commit()
    conn.close()
    logger.info(f"[SEED] Inserted {inserted} demo records")
    return inserted
