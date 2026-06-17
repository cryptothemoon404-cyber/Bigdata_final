"""
Basic tests for CryptoSentiment API
Run with: pytest tests/
"""
import pytest
from fastapi.testclient import TestClient
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ["DB_PATH"] = "/tmp/test_sentiment.db"

from app.main import app
from app.database import init_db

init_db()

client = TestClient(app)


def test_dashboard_loads():
    r = client.get("/")
    assert r.status_code == 200
    assert "CryptoSentiment" in r.text


def test_symbols_endpoint():
    r = client.get("/api/v1/symbols")
    assert r.status_code == 200
    assert "BTC" in r.json()["symbols"]


def test_sentiment_invalid_symbol():
    r = client.get("/api/v1/sentiment?symbol=FAKECOIN")
    assert r.status_code == 400


def test_sentiment_valid_symbol():
    r = client.get("/api/v1/sentiment?symbol=BTC&hours=24")
    assert r.status_code == 200
    data = r.json()
    assert "symbol" in data
    assert data["symbol"] == "BTC"


def test_feed_endpoint():
    r = client.get("/api/v1/feed?limit=5")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_history_endpoint():
    r = client.get("/api/v1/sentiment/history?symbol=BTC&hours=24&bucket_hours=6")
    assert r.status_code == 200
    data = r.json()
    assert "history" in data


def test_ingest_requires_secret():
    r = client.post("/api/v1/ingest?secret=wrong")
    assert r.status_code == 403
