"""
Background scheduler — runs RSS ingestion every 30 minutes.
Can be started as a standalone process alongside the API server.
"""
import time
import logging
from datetime import datetime, timezone

from .database import init_db
from .ingestion import ingest_rss

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

INTERVAL_SECONDS = 30 * 60  # 30 minutes


def run():
    init_db()
    logger.info(f"Scheduler started. Ingesting every {INTERVAL_SECONDS // 60} minutes.")
    while True:
        try:
            n = ingest_rss()
            logger.info(f"[{datetime.now(timezone.utc).isoformat()}] Ingested {n} records")
        except Exception as exc:
            logger.error(f"Ingestion error: {exc}")
        time.sleep(INTERVAL_SECONDS)


if __name__ == "__main__":
    run()
